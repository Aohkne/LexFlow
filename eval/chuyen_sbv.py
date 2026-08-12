"""Chuyển bộ test của bài báo SBV-LawGraph thành bộ câu hỏi eval của LexFlow.

Nguồn: `data/evaluate/svb_graph/sbv_testset_tvpl.json` — 100 câu, nhãn dạng
`"12/2022/tt-nhnn_3"` = số hiệu + số điều, tức **nhãn cấp điều trên 100% câu**.

Sinh HAI file, không gán nhãn tay dòng nào:

| File | Nội dung | Ai dùng |
|---|---|---|
| `eval/bo_sbv.jsonl` | câu mà corpus phủ đủ văn bản | `run_benchmark.py`, `quet_trong_so.py` |
| `eval/bo_sbv_khong_can_cu.jsonl` | câu dẫn văn bản corpus KHÔNG có | T17 (ngưỡng τ), chưa chạy |

**File thứ hai KHÔNG chạy được bằng `run_benchmark`** — nó không có nhãn vàng nên mọi mức IR bỏ
qua nó (`run_benchmark._tong_hop_ir`). Chạy rồi tưởng hệ điểm 0 là đọc sai. Nó là dữ liệu cho
T17: câu hỏi mà câu trả lời đúng là "không đủ căn cứ".

Chạy:
    uv run python eval/chuyen_sbv.py
    uv run python -u eval/run_benchmark.py --bo eval/bo_sbv.jsonl
"""
from __future__ import annotations

import re

from eval.chuyen_tvpl import chuan_so_hieu

_SO_DIEU = re.compile(r"^\d+[a-zđ]?$")


class NhanHong(ValueError):
    """Nhãn không đúng dạng `{số hiệu}_{số điều}`.

    Ném chứ không bỏ qua: nhãn hỏng là lỗi định dạng của file nguồn, khác hẳn "câu này dẫn văn
    bản ngoài corpus". Trộn hai thứ vào một nhánh bỏ-qua là cách mất dữ liệu êm nhất.
    """


def tach_nhan(nhan: str) -> tuple[str, str]:
    """`"12/2022/tt-nhnn_3"` → `("12/2022/TT-NHNN", "3")`.

    Tách từ **phải** (`rpartition`): hậu tố là số điều, số hiệu ở trước và bản thân nó chứa dấu
    gạch. Tách từ trái thì `"08/2023/tt-nhnn_21"` ra `"2"`.

    Số hiệu đi qua `chuan_so_hieu` ở dạng **thô, chữ thường**. Ở đó regex cắt đuôi slug
    (`^\\d+/\\d{4}/[A-ZĐ]+…`) sẽ KHÔNG khớp chuỗi thường, nên hàm rơi vào nhánh dự phòng
    `.upper().replace("Đ","D")` — và đó đúng là điều ta cần, vì định dạng SBV **không có đuôi
    slug** để cắt. Đừng "sửa" bằng cách viết hoa trước khi gọi: đuôi slug viết hoa lên thì regex
    nuốt luôn nó, đúng lỗi đã gặp 11/08. Cũng đừng thêm `re.IGNORECASE` vào regex đó vì cùng lý do.
    """
    so_hieu, sep, so_dieu = nhan.rpartition("_")
    if not sep or not _SO_DIEU.match(so_dieu):
        raise NhanHong(f"nhãn {nhan!r} không đúng dạng {{số hiệu}}_{{số điều}}")
    return chuan_so_hieu(so_hieu), so_dieu
