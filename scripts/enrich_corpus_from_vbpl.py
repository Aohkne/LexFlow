"""Bổ sung thuộc tính + cây điều khoản (crawl từ vbpl.vn) vào một văn bản đã có trong corpus.

Chỉ THÊM các trường mới, KHÔNG đụng vào `articles`, `title`, `valid_from`, `valid_to`:
những thứ đó đã được curate tay (cờ superseded, hiệu lực mức điều) và là đầu vào chunking
của RAG — ghi đè bằng bản crawl sẽ âm thầm đổi kết quả truy vấn.

Giữ nguyên doc_id đang dùng, vì các quan hệ trong corpus trỏ vào nó; crawl sinh doc_id
riêng theo Số hiệu nên phải chỉ định đích rõ ràng.

    uv run python scripts/enrich_corpus_from_vbpl.py \
        data/raw/vbpl/<file>.corpus.json --doc-id TT15-2024
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Trường được phép chép sang. `provisions` là cây; còn lại là thuộc tính phẳng.
_COPY_FIELDS = [
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
]


def enrich(corpus: dict, crawled: dict, doc_id: str) -> dict:
    """Trả bản tóm tắt những gì đã đổi; sửa `corpus` tại chỗ."""
    docs = corpus.get("documents", [])
    target = next((d for d in docs if d.get("doc_id") == doc_id), None)
    if target is None:
        have = ", ".join(sorted(d.get("doc_id", "?") for d in docs))
        raise SystemExit(f"Không có {doc_id!r} trong corpus. Đang có: {have}")

    changed: dict[str, str] = {}
    for field in _COPY_FIELDS:
        value = crawled.get(field)
        if value in (None, "", []):
            continue
        before = target.get(field)
        if before == value:
            continue
        target[field] = value
        changed[field] = (
            f"{len(value)} nút gốc" if field == "provisions" else f"{before!r} → {value!r}"
        )
    return changed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("crawled", type=Path, help="file .corpus.json do `vbpl dump --corpus` sinh")
    ap.add_argument("--doc-id", required=True, help="doc_id đích trong corpus")
    ap.add_argument("--corpus", type=Path, default=Path("data/corpus.real.json"))
    ap.add_argument("--dry-run", action="store_true", help="chỉ in ra, không ghi file")
    args = ap.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    crawled = json.loads(args.crawled.read_text(encoding="utf-8"))

    changed = enrich(corpus, crawled, args.doc_id)
    if not changed:
        print(f"[enrich] {args.doc_id}: không có gì để bổ sung.")
        return

    print(f"[enrich] {args.doc_id} — {len(changed)} trường:")
    for field, how in changed.items():
        print(f"    {field:<22} {how[:110]}")
    print("[enrich] articles / title / hiệu lực: giữ nguyên.")

    if args.dry_run:
        print("[enrich] --dry-run: không ghi file.")
        return
    args.corpus.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[enrich] Đã ghi {args.corpus}")


if __name__ == "__main__":
    main()
