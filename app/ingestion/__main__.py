"""uv run python -m app.ingestion [corpus.json] [--doc ID]... [--xoa-doc-du]"""
from __future__ import annotations

import argparse
import sys

from app.ingestion.pipeline import DocDuTrongBang, main


def phan_tich(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m app.ingestion")
    p.add_argument("corpus", nargs="?", default="data/corpus.sample.json")
    p.add_argument(
        "--doc", action="append", default=[],
        help="ép nạp lại văn bản này dù vân tay khớp (lặp lại được)",
    )
    p.add_argument(
        "--xoa-doc-du", action="store_true",
        help="xoá khỏi bảng những văn bản không còn trong corpus",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    a = phan_tich(sys.argv[1:])
    try:
        main(a.corpus, ep=frozenset(a.doc), xoa_doc_du=a.xoa_doc_du)
    except DocDuTrongBang as exc:
        # Ca hay gặp nhất của lỗi này là gõ nhầm đường dẫn corpus, nên nói thẳng ra.
        print(f"[ingest] DỪNG: {exc}", file=sys.stderr)
        print(f"[ingest] corpus đang dùng: {a.corpus}", file=sys.stderr)
        raise SystemExit(1) from exc
