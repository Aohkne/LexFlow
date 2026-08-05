"""Overlay lớp phủ: các đơn vị luật (điều, khoản, điểm) như các nút được tác động.

Mỗi cạnh `CanhTacDong` có hai mút: nguồn (văn bản sửa) và đích (văn bản nền).
Hàm `dung_overlay` tách những mút đó thành nút overlay riêng, với vai trò:
- `nguon_lenh` nếu nó chỉ xuất hiện là nguồn lệnh
- `dich_bi_tac_dong` nếu nó xuất hiện là đích bị tác động (vai này thắng nếu cùng một khoá
  vừa làm nguồn vừa bị làm đích)
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.ingestion.vbpl_corpus import doc_id_theo_corpus
from app.ontology.tac_dong import CanhTacDong


class DonViOverlay(BaseModel):
    """Một nút trong lớp phủ overlay: đơn vị luật được tác động hoặc tác động."""

    khoa: str
    doc_id: str | None
    vai: Literal["nguon_lenh", "dich_bi_tac_dong"]


def dung_overlay(canh: list[CanhTacDong]) -> list[DonViOverlay]:
    """Xây dựng nút overlay từ danh sách cạnh tác động.

    Mỗi mút của cạnh (nguồn và đích) thành một nút. Dedup theo khoá (khoa).
    Nếu một khoá vừa là nguồn vừa là đích, vai trò "dich_bi_tac_dong" thắng
    (ưu tiên: cái bị tác động quan trọng hơn cái tác động).

    Args:
        canh: Danh sách cạnh tác động.

    Returns:
        Danh sách nút overlay, mỗi nút có khoa, doc_id, và vai trò.
    """
    # Tập hợp các khoa và vai trò của chúng
    vai_theo_khoa: dict[str, Literal["nguon_lenh", "dich_bi_tac_dong"]] = {}

    for c in canh:
        # Xử lý nguồn (luôn là "nguon_lenh")
        if c.nguon not in vai_theo_khoa:
            vai_theo_khoa[c.nguon] = "nguon_lenh"

        # Xử lý đích (luôn là "dich_bi_tac_dong", và nó thắng nếu trùng)
        vai_theo_khoa[c.dich] = "dich_bi_tac_dong"

    # Xây dựng danh sách nút
    nodes = []
    for khoa, vai in vai_theo_khoa.items():
        # Lấy số hiệu (phần trước dấu "#" đầu tiên)
        so_hieu = khoa.split("#", 1)[0]
        doc_id = doc_id_theo_corpus(so_hieu)

        nodes.append(
            DonViOverlay(
                khoa=khoa,
                doc_id=doc_id,
                vai=vai,
            )
        )

    return nodes
