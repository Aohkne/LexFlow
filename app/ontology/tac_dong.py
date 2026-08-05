"""Mệnh lệnh tác động trong văn bản sửa đổi → cạnh con↔con của lớp phủ.

Vì sao đọc ĐỘNG TỪ MỞ ĐẦU chứ không tìm từ khoá trong cả câu: câu lệnh luật luôn mở đầu
bằng động từ ("Sửa đổi…", "Bãi bỏ…", "Bổ sung…"), còn giữa câu có thể nhắc thao tác khác
("…đã được sửa đổi bởi…" là mô tả, không phải lệnh). IGNORECASE bắt buộc: mệnh đề đứng
đầu khoản viết hoa — grep thường đã một lần bỏ sót câu bãi bỏ của TT22 (05/08).

Thứ tự khớp có chủ đích: `thay_cum_tu`/`thay_phu_luc` trước `sua_doi` — "Thay thế cụm từ"
cũng bắt đầu bằng "Thay thế"; `bo_sung` sau `sua_doi` — "Sửa đổi, bổ sung" là một thao tác
ghi đè lời văn, chỉ khi đứng một mình "Bổ sung" mới là thêm mới.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

_BANG_THAO_TAC: list[tuple[str, str]] = [
    (r"thay\s*thế\s+cụm\s+từ", "thay_cum_tu"),
    (r"thay\s*thế\s+(?:một\s+số\s+)?phụ\s+lục", "thay_phu_luc"),
    (r"bãi\s+bỏ", "bai_bo"),
    (r"sửa\s+đổi", "sua_doi"),
    (r"bổ\s+sung", "bo_sung"),
]


class CanhTacDong(BaseModel):
    """Một mệnh lệnh tác động: đơn vị NGUỒN (văn bản sửa) chạm đơn vị ĐÍCH (văn bản nền)."""

    nguon: str
    dich: str
    thao_tac: Literal["sua_doi", "bo_sung", "bai_bo", "thay_phu_luc", "thay_cum_tu"]
    #: span trong `noi_dung` của văn bản SỬA — xuất xứ lời văn mới; bãi bỏ thì None.
    loi_van_moi: tuple[int, int] | None = None
    valid_from: str | None = None
    menh_lenh: str
    canh_bao: list[str] = Field(default_factory=list)


def thao_tac_tu_cau(cau: str) -> str | None:
    dau = cau.strip()
    for mau, ma in _BANG_THAO_TAC:
        if re.match(mau, dau, re.IGNORECASE):
            return ma
    return None
