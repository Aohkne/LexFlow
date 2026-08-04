"""Soát `relationships` trong corpus với TẬP ĐÓNG 13 quan hệ của KG v0.5 §6.

Chạy:
    uv run python -m app.ingestion.kiem_quan_he
    uv run python -m app.ingestion.kiem_quan_he --file data/corpus.real.json

Vì sao cần một công cụ riêng thay vì để `Relationship` tự ném lỗi: validator dừng ở **cạnh
sai đầu tiên**, còn người đang sửa dữ liệu cần thấy **toàn bộ** danh sách một lần. Nó cũng
đề xuất mã thay thế cho những tên cũ đã biết, nhưng chỉ khi phép ánh xạ là **cơ học**.

`HUONG_DAN` cố ý KHÔNG có trong bảng gợi ý. v0.5 §6.3 tách nó làm hai quan hệ mà Điều 53
khoản 2 đối xử khác nhau — `QUY_DINH_CHI_TIET_HUONG_DAN` (ban hành theo uỷ quyền, R5 *cùng
ngày hiệu lực* áp dụng) và `HUONG_DAN_AP_DUNG` (hướng dẫn thuần tuý, R5 **không** áp dụng).
Chọn hộ là phán định pháp lý, và gộp hai loại lại chính là cái đã sinh ra bốn cạnh sai.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app.core.schemas import REL_TYPES

_MAC_DINH = Path("data/corpus.real.json")

#: Chỉ những phép đổi tên CƠ HỌC — cùng một quan hệ, v0.5 gọi tên khác. Không suy diễn.
DOI_TEN_CO_HOC = {
    "SUA_DOI": "SUA_DOI_BO_SUNG",
    "TAM_NGUNG": "TAM_NGUNG_HIEU_LUC",
}


def soat(rels: list[dict]) -> tuple[Counter, list[dict]]:
    """→ (đếm theo mã, danh sách cạnh sai kèm gợi ý nếu có)."""
    dem: Counter = Counter(r.get("rel_type") for r in rels)
    sai = [
        {**r, "goi_y": DOI_TEN_CO_HOC.get(r.get("rel_type", ""))}
        for r in rels
        if r.get("rel_type") not in REL_TYPES
    ]
    return dem, sai


def main() -> int:
    ap = argparse.ArgumentParser(description="Soát rel_type với 13 quan hệ KG v0.5")
    ap.add_argument("--file", default=str(_MAC_DINH))
    args = ap.parse_args()

    raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
    rels = raw.get("relationships", [])
    dem, sai = soat(rels)

    print(f"{len(rels)} cạnh · {len(dem)} mã khác nhau · {len(sai)} cạnh SAI\n")
    for ma, n in dem.most_common():
        dau = "  ok " if ma in REL_TYPES else "  ✗  "
        print(f"{dau}{str(ma):32} {n}")

    if sai:
        print("\n--- cạnh cần sửa ---")
        for r in sai:
            gy = f"  ⇒ đổi thành {r['goi_y']}" if r.get("goi_y") else "  ⇒ CẦN NGƯỜI QUYẾT"
            print(f"  {r.get('source_doc'):16} → {r.get('target_doc'):16} "
                  f"{str(r.get('rel_type')):20}{gy}")
        print(f"\n13 mã hợp lệ: {', '.join(sorted(REL_TYPES))}")

    thieu = sorted(set(REL_TYPES) - set(dem))
    if thieu:
        print(f"\n--- {len(thieu)}/13 mã chưa có instance nào ---\n  {', '.join(thieu)}")
        if "BAI_BO" in thieu:
            print("\n  Lưu ý: 0 cạnh BAI_BO ⇒ truy vấn 'khoảng trống lập pháp' (§6.2) sẽ")
            print("  CHẠY nhưng trả RỖNG. Rỗng vì thiếu dữ liệu, không phải vì không có")
            print("  khoảng trống nào — đừng đọc kết quả đó thành một kết luận pháp lý.")
    return 1 if sai else 0


if __name__ == "__main__":
    sys.exit(main())
