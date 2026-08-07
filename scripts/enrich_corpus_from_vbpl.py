"""Bổ sung thuộc tính + cây điều khoản (crawl từ vbpl.vn) vào một văn bản đã có trong corpus.

Chỉ THÊM các trường mới, KHÔNG đụng vào `articles`, `title`, `valid_from`, `valid_to`:
những thứ đó đã được curate tay (cờ superseded, hiệu lực mức điều) và là đầu vào chunking
của RAG — ghi đè bằng bản crawl sẽ âm thầm đổi kết quả truy vấn.

Giữ nguyên doc_id đang dùng, vì các quan hệ trong corpus trỏ vào nó; crawl sinh doc_id
riêng theo Số hiệu nên phải chỉ định đích rõ ràng.

    uv run python scripts/enrich_corpus_from_vbpl.py \
        data/raw/vbpl/<file>.corpus.json --doc-id TT15-2024

Cào xong nhiều văn bản thì ghép cả loạt — khớp theo `doc_id` bản crawl sinh ra, văn bản
nào corpus không có thì bỏ qua và báo tên:

    uv run python scripts/enrich_corpus_from_vbpl.py --tu-thu-muc data/raw/vbpl/corpus
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Trường được phép chép sang. `provisions` là cây, `source_files` là danh sách file gốc;
# còn lại là thuộc tính phẳng.
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
    "source_files",
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
        if field == "provisions":
            changed[field] = f"{len(value)} nút gốc"
        elif field == "source_files":
            changed[field] = f"{len(value)} file gốc"
        else:
            changed[field] = f"{before!r} → {value!r}"
    return changed


def _in_thay_doi(doc_id: str, changed: dict[str, str]) -> None:
    print(f"[enrich] {doc_id} — {len(changed)} trường:")
    for field, how in changed.items():
        print(f"    {field:<22} {how[:110]}")


def enrich_thu_muc(corpus: dict, thu_muc: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Ghép cả thư mục bản crawl, khớp theo `doc_id`.

    Trả `(thay_đổi theo doc_id, danh sách doc_id crawl có mà corpus không có)`. Văn bản lạ
    là chuyện thường (đã cào VBHN nhưng chưa duyệt vào corpus) nên chỉ báo, không dừng.
    """
    co_trong_corpus = {d.get("doc_id") for d in corpus.get("documents", [])}
    thay_doi: dict[str, dict[str, str]] = {}
    ngoai_corpus: list[str] = []
    for path in sorted(thu_muc.glob("*.json")):
        crawled = json.loads(path.read_text(encoding="utf-8"))
        doc_id = crawled.get("doc_id")
        if doc_id not in co_trong_corpus:
            ngoai_corpus.append(doc_id or path.name)
            continue
        changed = enrich(corpus, crawled, doc_id)
        if changed:
            thay_doi[doc_id] = changed
    return thay_doi, ngoai_corpus


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "crawled", type=Path, nargs="?", help="file .corpus.json do `vbpl dump --corpus` sinh"
    )
    ap.add_argument("--doc-id", help="doc_id đích trong corpus (bắt buộc khi ghép 1 file)")
    ap.add_argument(
        "--tu-thu-muc", type=Path, help="ghép cả thư mục bản crawl, khớp theo doc_id"
    )
    ap.add_argument("--corpus", type=Path, default=Path("data/corpus.real.json"))
    ap.add_argument("--dry-run", action="store_true", help="chỉ in ra, không ghi file")
    args = ap.parse_args()

    if bool(args.tu_thu_muc) == bool(args.crawled):
        raise SystemExit("Chọn một trong hai: <file> --doc-id … HOẶC --tu-thu-muc <thư mục>")
    if args.crawled and not args.doc_id:
        raise SystemExit("Ghép 1 file thì phải chỉ định --doc-id đích.")

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))

    if args.tu_thu_muc:
        thay_doi, ngoai_corpus = enrich_thu_muc(corpus, args.tu_thu_muc)
        for doc_id, changed in thay_doi.items():
            _in_thay_doi(doc_id, changed)
        if ngoai_corpus:
            print(f"[enrich] Bỏ qua {len(ngoai_corpus)} bản crawl không có trong corpus: "
                  f"{', '.join(ngoai_corpus)}")
        if not thay_doi:
            print("[enrich] Không có gì để bổ sung.")
            return
    else:
        crawled = json.loads(args.crawled.read_text(encoding="utf-8"))
        changed = enrich(corpus, crawled, args.doc_id)
        if not changed:
            print(f"[enrich] {args.doc_id}: không có gì để bổ sung.")
            return
        _in_thay_doi(args.doc_id, changed)

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
