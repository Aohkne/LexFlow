"""Đồng bộ các trường mới từ data/corpus.real.json vào corpus.json canonical trên Storage.

Chạy khi canonical đã tồn tại trên Storage (do admin từng duyệt văn bản) nhưng thiếu các
trường mà bản local đã có:

* **anchors mức Điều** trên quan hệ — khớp theo bộ ba (source_doc, target_doc, rel_type);
* **thuộc tính + cây điều khoản + file gốc** của văn bản — khớp theo `doc_id`.

Chỉ **bổ sung**, không xoá: văn bản nào chỉ có trên canonical (duyệt qua `/admin` mà chưa
đưa vào corpus commit) vẫn giữ nguyên; `articles` / `title` / hiệu lực không bị đụng vì đó
là bản curate tay và là đầu vào chunking.

Cách dùng (cần tài khoản admin):
    uv run python scripts/sync_corpus_storage.py --email you@x.com --password '...'
    uv run python scripts/sync_corpus_storage.py --email … --password … --dry-run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from app.core.config import settings

_LOCAL = Path("data/corpus.real.json")
_OBJECT = "legal-docs/corpus.json"

#: Trường bản local được phép bổ sung cho văn bản trên canonical. Cùng danh sách với
#: `scripts/enrich_corpus_from_vbpl.py` — thuộc tính vbpl.vn, cây điều khoản, file gốc.
_DOC_FIELDS = [
    "so_hieu",
    "co_quan_ban_hanh",
    "nguoi_ky",
    "chuc_danh",
    "nganh",
    "linh_vuc",
    "ngay_ban_hanh",
    "tinh_trang_hieu_luc",
    "source_url",
    "provisions",
    "source_files",
]


def sync_anchors(canonical: dict, local: dict) -> int:
    """Bổ sung anchors cho quan hệ trên canonical. Trả số quan hệ đã sửa."""
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
    return changed


def sync_thuoc_tinh(canonical: dict, local: dict) -> dict[str, list[str]]:
    """Bổ sung thuộc tính/cây/file gốc cho văn bản trên canonical.

    Trả `{doc_id: [trường đã bổ sung]}`. Trường nào canonical đã có giá trị khác thì
    **ghi đè bằng bản local** — bản local là thứ vừa được kiểm bằng test và đối chiếu với
    bản crawl, còn canonical có thể mang bản cũ hơn.
    """
    local_docs = {d["doc_id"]: d for d in local.get("documents", [])}
    changed: dict[str, list[str]] = {}
    for doc in canonical.get("documents", []):
        src = local_docs.get(doc.get("doc_id"))
        if src is None:
            continue
        fields = []
        for field in _DOC_FIELDS:
            value = src.get(field)
            if value in (None, "", []) or doc.get(field) == value:
                continue
            doc[field] = value
            fields.append(field)
        if fields:
            changed[doc["doc_id"]] = fields
    return changed


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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--dry-run", action="store_true", help="chỉ in ra, không ghi Storage")
    ap.add_argument(
        "--backup",
        type=Path,
        default=Path("data/backup/corpus.canonical.json"),
        help="nơi lưu bản canonical trước khi ghi đè",
    )
    args = ap.parse_args()

    token = _login(args.email, args.password)
    headers = {"apikey": settings.supabase_anon_key, "Authorization": f"Bearer {token}"}
    base = settings.supabase_url.rstrip("/") + "/storage/v1/object/"

    r = httpx.get(base + _OBJECT, headers=headers, timeout=60)
    if r.status_code in (400, 404):
        print("Canonical chưa tồn tại trên Storage — backend đang dùng file đóng gói, "
              "không cần sync.")
        return
    r.raise_for_status()
    canonical = r.json()

    args.backup.parent.mkdir(parents=True, exist_ok=True)
    args.backup.write_bytes(r.content)
    print(f"Đã lưu bản canonical hiện tại vào {args.backup} ({len(r.content)} byte)")

    local = json.loads(_LOCAL.read_text(encoding="utf-8"))
    chi_co_canonical = {d["doc_id"] for d in canonical.get("documents", [])} - {
        d["doc_id"] for d in local.get("documents", [])
    }
    if chi_co_canonical:
        print(f"Giữ nguyên {len(chi_co_canonical)} văn bản chỉ có trên canonical: "
              f"{', '.join(sorted(chi_co_canonical))}")

    n_anchors = sync_anchors(canonical, local)
    thuoc_tinh = sync_thuoc_tinh(canonical, local)
    for doc_id, fields in thuoc_tinh.items():
        print(f"  {doc_id:14} {', '.join(fields)}")

    if n_anchors == 0 and not thuoc_tinh:
        print("Canonical đã đủ — không có gì để sync.")
        return
    print(f"Tổng: {n_anchors} quan hệ thêm anchors, {len(thuoc_tinh)} văn bản thêm thuộc tính.")

    if args.dry_run:
        print("--dry-run: không ghi Storage.")
        return

    up = httpx.post(
        base + _OBJECT,
        content=json.dumps(canonical, ensure_ascii=False, indent=1).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json", "x-upsert": "true"},
        timeout=60,
    )
    up.raise_for_status()
    print("Đã ghi canonical mới lên Storage. Cache backend hết hạn sau 60 giây.")


if __name__ == "__main__":
    main()
