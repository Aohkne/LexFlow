"""Đo: `merge_insert().execute()` có chạy trên LanceDB Cloud không.

Chạy trên một BẢNG NHÁP rồi drop — không đụng bảng đang phục vụ. Lý do phải đo: `hasattr` và
việc dựng được `LanceMergeInsertBuilder` chỉ chứng minh thuộc tính tồn tại, không chứng minh
backend từ xa cài đặt nó. Cả thiết kế ingest tăng dần đứng trên câu trả lời này.

Chạy: uv run python scripts/do_merge_insert_remote.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import vectordb  # noqa: E402
from app.core.config import settings  # noqa: E402

BANG_NHAP = "nhap_do_merge_insert"


def _hang(id_: str, text: str) -> dict:
    return {"id": id_, "doc_id": "NHAP", "text": text, "vector": [0.1, 0.2, 0.3]}


def main() -> int:
    print(f"cloud enabled: {settings.lancedb_cloud_enabled}")
    db = vectordb.connect()
    if BANG_NHAP in db.table_names():
        db.drop_table(BANG_NHAP)

    tbl = db.create_table(BANG_NHAP, data=[_hang("a", "cũ"), _hang("b", "giữ")])
    try:
        print(f"lớp bảng: {type(tbl).__name__} · {tbl.count_rows()} hàng")

        (
            tbl.merge_insert("id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute([_hang("a", "MỚI"), _hang("c", "thêm")])
        )

        sau = {r["id"]: r["text"] for r in tbl.search().select(["id", "text"]).limit(99).to_list()}
        print(f"sau merge_insert: {sau}")
        assert sau == {"a": "MỚI", "b": "giữ", "c": "thêm"}, f"merge_insert sai ngữ nghĩa: {sau}"

        tbl.delete("id IN ('b')")
        con = {r["id"] for r in tbl.search().select(["id"]).limit(99).to_list()}
        print(f"sau delete: {con}")
        assert con == {"a", "c"}, f"delete sai: {con}"
    finally:
        db.drop_table(BANG_NHAP)
        print(f"đã drop {BANG_NHAP}")

    print("\nXANH — merge_insert + delete chạy được trên bảng từ xa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
