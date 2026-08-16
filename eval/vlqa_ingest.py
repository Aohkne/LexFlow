"""Ingest VLQA vào bảng LanceDB RIÊNG `chunks_vlqa` — không đụng bảng "chunks" sản phẩm. T117.

Tái dùng `build_chunks` + `_embed_rows` của pipeline (cùng cách chẻ khoản + embedding) nhưng ghi
bảng khác, `mode="overwrite"` để chạy lại sạch. Neo4j KHÔNG dùng (VLQA không có quan hệ).

  uv run python -u eval/vlqa_ingest.py --slice 60   # Stage A: 60 doc đầu (~cents)
  uv run python -u eval/vlqa_ingest.py              # Stage B: toàn bộ 2.157 doc (~$4) — cần duyệt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # chạy như script thấy `app`

from app.core import vectordb  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.ingestion.pipeline import _FTS_OPTS, _embed_rows, build_chunks  # noqa: E402
from eval.vlqa_adapter import BANG_VLQA, aid_toi_da, nap_corpus  # noqa: E402


def ingest(gioi_han: int | None = None) -> None:
    docs = nap_corpus(gioi_han=gioi_han)
    rows = build_chunks(docs)
    print(f"{len(docs)} doc → {len(rows)} chunk (aid tối đa {aid_toi_da(docs)}). Embed…", flush=True)
    _embed_rows(rows)
    db = vectordb.connect()
    tbl = db.create_table(BANG_VLQA, data=rows, mode="overwrite")
    # FTS: Cloud không nhận `replace` (index tạo cùng bảng); local thì có. Giống pipeline sản phẩm.
    if settings.lancedb_cloud_enabled:
        tbl.create_fts_index("text", **_FTS_OPTS)
    else:
        tbl.create_fts_index("text", replace=True, **_FTS_OPTS)
    print(f"→ bảng {BANG_VLQA}: {tbl.count_rows()} chunk, FTS xong", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", type=int, default=None, help="chỉ ingest N doc đầu (Stage A)")
    args = ap.parse_args()
    ingest(args.slice)


if __name__ == "__main__":
    main()
