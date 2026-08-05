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

from app.ingestion.vbpl_luoc_do import so_hieu_tu_tieu_de
from app.ontology.citation import parse_citations, to_node_ids

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


def so_hieu_nen(tieu_de_dieu: str, mac_dinh: str) -> str:
    """Văn bản nền của MỘT điều lệnh. ND16 là lý do hàm này tồn tại: năm điều, năm nghị
    định nền khác nhau — lấy theo văn bản thì gán nhầm cả năm."""
    sh, _ = so_hieu_tu_tieu_de(tieu_de_dieu)
    return sh or mac_dinh


def dich_tu_menh_lenh(
    menh_lenh: str, so_hieu_nen: str, ctx_dieu: str | None
) -> tuple[list[str], list[str]]:
    """Câu lệnh → khoá node đích trong không gian văn bản NỀN.

    Dùng lại citation.py nguyên vẹn — nó đã thuộc 23 ca tiết của corpus. Không giải được
    thì BÁO chứ không đoán: một khoá sai trỏ vào node thật khác là kiểu hỏng im lặng nhất.
    """
    refs = parse_citations(menh_lenh)
    ra: list[str] = []
    for r in refs:
        for khoa in to_node_ids(r, ctx_so_hieu=so_hieu_nen, ctx_dieu=ctx_dieu):
            if khoa not in ra:
                ra.append(khoa)
    if ra:
        return ra, []
    return [], [f"không giải được đích từ mệnh lệnh: {menh_lenh[:80]!r}"]
