"""Đồng bộ anchors từ data/corpus.real.json vào corpus.json canonical trên Storage.

Chạy khi canonical đã tồn tại trên Storage (do admin từng duyệt văn bản) nhưng
thiếu các trường mới (anchors mức Điều). Khớp quan hệ theo bộ ba
(source_doc, target_doc, rel_type) và chỉ bổ sung anchors còn thiếu.

Cách dùng (cần tài khoản admin):
    uv run python scripts/sync_corpus_storage.py --email you@x.com --password '...'
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from app.core.config import settings

_LOCAL = Path("data/corpus.real.json")
_OBJECT = "legal-docs/corpus.json"


def _login(email: str, password: str) -> str:
    r = httpx.post(
        settings.supabase_url.rstrip("/") + "/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_anon_key},
        json={"email": email, "password": password},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()

    token = _login(args.email, args.password)
    headers = {"apikey": settings.supabase_anon_key, "Authorization": f"Bearer {token}"}
    base = settings.supabase_url.rstrip("/") + "/storage/v1/object/"

    r = httpx.get(base + _OBJECT, headers=headers, timeout=60)
    if r.status_code in (400, 404):
        print("Canonical chưa tồn tại trên Storage — backend đang dùng file đóng gói, không cần sync.")
        return
    r.raise_for_status()
    canonical = r.json()

    local = json.loads(_LOCAL.read_text(encoding="utf-8"))
    local_rels = {
        (x["source_doc"], x["target_doc"], x["rel_type"]): x
        for x in local.get("relationships", [])
    }

    changed = 0
    for rel in canonical.get("relationships", []):
        key = (rel["source_doc"], rel["target_doc"], rel["rel_type"])
        src = local_rels.get(key)
        if src and src.get("anchors") and not rel.get("anchors"):
            rel["anchors"] = src["anchors"]
            changed += 1

    if changed == 0:
        print("Canonical đã có đủ anchors — không có gì để sync.")
        return

    up = httpx.post(
        base + _OBJECT,
        content=json.dumps(canonical, ensure_ascii=False, indent=1).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json", "x-upsert": "true"},
        timeout=60,
    )
    up.raise_for_status()
    print(f"Đã bổ sung anchors cho {changed} quan hệ trong canonical trên Storage.")


if __name__ == "__main__":
    main()
