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


# --- phien_ban_hien_hanh --------------------------------------------------------


class PhienBanHienHanh(BaseModel):
    """Phiên bản hiện hành của một đơn vị luật (`khoa`) tại một mốc thời gian."""

    khoa: str
    trang_thai: Literal["nguyen_ven", "da_sua", "bi_bai_bo"]
    #: Cạnh đã lọc + áp, sắp theo `valid_from` tăng dần.
    cac_lan: list[CanhTacDong]


def _tien_to(khoa_ngan: str, khoa_dai: str) -> bool:
    """`khoa_ngan` có phải là chính `khoa_dai` hoặc một tiền tố của nó theo ranh `#`.

    So theo ranh `#` để `dieu_1` không nuốt nhầm `dieu_11`: `"...dieu_1"` không phải tiền
    tố hợp lệ của `"...dieu_11"`, nhưng LÀ tiền tố hợp lệ của `"...dieu_1#khoan_2"`.
    """
    if khoa_dai == khoa_ngan:
        return True
    return khoa_dai.startswith(khoa_ngan + "#")


def phien_ban_hien_hanh(khoa: str, canh: list[CanhTacDong], hom_nay: str) -> PhienBanHienHanh:
    """Suy ra phiên bản hiện hành của đơn vị luật `khoa` tại mốc thời gian `hom_nay`.

    Ba luật:
    1. Chỉ áp cạnh có `valid_from` không rỗng và `valid_from <= hom_nay` (chỉ-hiện-tại;
       muốn as-of thì đổi tham số `hom_nay`). Chuỗi ISO "YYYY-MM-DD" so được bằng `<=` chuỗi.
    2. **Luật cạnh-chết**: một cạnh ứng cử bị loại nếu tồn tại một cạnh KHÁC, thao_tac
       `bai_bo`, đã áp được (valid_from <= hom_nay), có `dich` là tiền tố (theo ranh `#`)
       của `nguon` cạnh ứng cử — tức điều/khoản đã PHÁT lệnh đó đã bị bãi bỏ, nên lệnh nó
       phát ra không còn hiệu lực. Ca thật: TT22 bãi Đ16/17/18 TT41 ⇒ mọi cạnh có `nguon`
       bắt đầu bằng các khoá đó (kể cả khoản con) đều chết theo.
    3. Cạnh khớp `khoa` khi `dich == khoa` hoặc `dich` là tiền tố (ranh `#`) của `khoa` —
       bãi bỏ cả điều thì khoản con cũng bị bãi bỏ theo.

    `trang_thai` là `bi_bai_bo` khi cạnh ÁP ĐƯỢC cuối cùng (theo `valid_from`, đã lọc luật
    cạnh-chết) là `bai_bo`; `da_sua` khi có ít nhất một cạnh áp được nhưng lần cuối không
    phải bãi bỏ; `nguyen_ven` khi không có cạnh nào áp được.
    """
    ap_duoc = [c for c in canh if c.valid_from is not None and c.valid_from <= hom_nay]

    bai_bo_song = {
        c.dich for c in ap_duoc if c.thao_tac == "bai_bo"
    }

    def con_song(c: CanhTacDong) -> bool:
        return not any(_tien_to(dich_bai, c.nguon) for dich_bai in bai_bo_song)

    khop = [
        c for c in ap_duoc
        if _tien_to(c.dich, khoa) and con_song(c)
    ]
    khop.sort(key=lambda c: c.valid_from)

    if not khop:
        trang_thai: Literal["nguyen_ven", "da_sua", "bi_bai_bo"] = "nguyen_ven"
    elif khop[-1].thao_tac == "bai_bo":
        trang_thai = "bi_bai_bo"
    else:
        trang_thai = "da_sua"

    return PhienBanHienHanh(khoa=khoa, trang_thai=trang_thai, cac_lan=khop)
