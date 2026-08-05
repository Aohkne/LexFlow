"""Bộ đọc mệnh lệnh tác động: điều của văn bản sửa → cạnh con↔con. Offline."""
from __future__ import annotations

import pytest

from app.ontology.tac_dong import (
    CanhTacDong,
    canh_tu_dieu,
    dich_tu_menh_lenh,
    so_hieu_nen,
    thao_tac_tu_cau,
)


@pytest.mark.parametrize(
    ("cau", "cho"),
    [
        ("Sửa đổi, bổ sung điểm b (ii) khoản 4 Điều 11", "sua_doi"),
        ("sửa đổi khoản 2 như sau:", "sua_doi"),
        ("Bãi bỏ điểm c khoản 7.", "bai_bo"),           # viết hoa đầu khoản — ca TT22
        ("bãi bỏ Điều 16, Điều 17, Điều 18", "bai_bo"),
        ("Bổ sung khoản 3 Điều 32", "bo_sung"),
        ("Thay thế Phụ lục kèm theo Thông tư 40/2024/TT-NHNN", "thay_phu_luc"),
        ('Thay thế cụm từ "Cơ quan Thanh tra, giám sát ngân hàng"', "thay_cum_tu"),
        ("Tổ chức thực hiện", None),                     # không phải mệnh lệnh tác động
        ("Trách nhiệm thi hành", None),
    ],
)
def test_thao_tac_tu_cau(cau, cho):
    assert thao_tac_tu_cau(cau) == cho


def test_sua_doi_bo_sung_gop_ve_sua_doi():
    """'Sửa đổi, bổ sung X' là MỘT thao tác ghi đè lời văn — không tách đôi."""
    assert thao_tac_tu_cau("Sửa đổi, bổ sung một số điểm, khoản của Điều 18") == "sua_doi"


def test_canh_mang_du_truong_va_mac_dinh():
    c = CanhTacDong(nguon="41/2025/TT-NHNN#than/dieu_8",
                    dich="40/2024/TT-NHNN#than/dieu_24#khoan_4",
                    thao_tac="bai_bo", menh_lenh="Bãi bỏ khoản 4 Điều 24")
    assert c.loi_van_moi is None and c.valid_from is None and c.canh_bao == []


def test_so_hieu_nen_tu_tieu_de_dieu_kieu_ND16():
    """ND16 mỗi điều sửa một nghị định KHÁC — số hiệu nền đọc từ tiêu đề điều."""
    td = ("Sửa đổi, bổ sung, bãi bỏ một số điều của Nghị định số 101/2012/NĐ-CP "
          "ngày 07 tháng 5 năm 2012 của Chính phủ về thanh toán không dùng tiền mặt")
    assert so_hieu_nen(td, mac_dinh="?") == "101/2012/NĐ-CP"


def test_so_hieu_nen_roi_ve_mac_dinh_khi_tieu_de_khong_neu():
    """TT41 tiêu đề điều chỉ ghi 'Sửa đổi, bổ sung một số khoản của Điều 9' — nền là TT40."""
    assert so_hieu_nen("Sửa đổi, bổ sung một số khoản của Điều 9",
                       mac_dinh="40/2024/TT-NHNN") == "40/2024/TT-NHNN"


def test_dich_diem_du_ngu_canh_dieu():
    """'Bãi bỏ điểm c khoản 7.' không nêu Điều — Điều lấy từ tiêu đề điều lệnh (ctx)."""
    khoa, cb = dich_tu_menh_lenh("Bãi bỏ điểm c khoản 7.", "40/2024/TT-NHNN", ctx_dieu="8")
    assert khoa == ["40/2024/TT-NHNN#than/dieu_8#khoan_7#diem_c"] and cb == []


def test_dich_nhieu_dieu_mot_cau():
    khoa, _ = dich_tu_menh_lenh("Bãi bỏ Điều 16, Điều 17, Điều 18 Thông tư số 41/2025/TT-NHNN",
                                "41/2025/TT-NHNN", ctx_dieu=None)
    assert khoa == ["41/2025/TT-NHNN#than/dieu_16", "41/2025/TT-NHNN#than/dieu_17",
                    "41/2025/TT-NHNN#than/dieu_18"]


def test_khong_giai_duoc_thi_bao_ra_khong_doan():
    khoa, cb = dich_tu_menh_lenh("Sửa đổi một số nội dung khác.", "40/2024/TT-NHNN", None)
    assert khoa == [] and len(cb) == 1


_DIEU_LENH = (
    "Sửa đổi, bổ sung một số điểm của Điều 8\n"
    "1. Sửa đổi điểm a khoản 1 như sau:\n"
    "“a) Quy định mới cho điểm a.”\n"
    "2. Bãi bỏ điểm c khoản 7.\n"
)


def _khoi_trich_cua(text: str, char_start: int) -> list[tuple[int, int]]:
    a = char_start + text.index("“")
    b = char_start + text.index("”") + 1
    return [(a, b)]


def test_canh_tu_dieu_che_khoan():
    cs = 1000  # vị trí giả định trong noi_dung
    canh = canh_tu_dieu("Điều 1", _DIEU_LENH, cs, "41/2025/TT-NHNN", "40/2024/TT-NHNN",
                        _khoi_trich_cua(_DIEU_LENH, cs), valid_from="2025-11-05")
    assert [c.thao_tac for c in canh] == ["sua_doi", "bai_bo"]
    assert canh[0].dich == "40/2024/TT-NHNN#than/dieu_8#khoan_1#diem_a"
    assert canh[1].dich == "40/2024/TT-NHNN#than/dieu_8#khoan_7#diem_c"  # ctx Điều 8 từ tiêu đề
    assert canh[0].nguon == "41/2025/TT-NHNN#than/dieu_1#khoan_1"
    assert canh[0].loi_van_moi is not None and canh[1].loi_van_moi is None
    assert all(c.valid_from == "2025-11-05" for c in canh)


def test_canh_tu_dieu_khong_che_khoan():
    canh = canh_tu_dieu("Điều 8", "Bãi bỏ khoản 4 Điều 24", 5000,
                        "41/2025/TT-NHNN", "40/2024/TT-NHNN", [], valid_from="2025-11-05")
    assert len(canh) == 1
    assert canh[0].nguon == "41/2025/TT-NHNN#than/dieu_8"
    assert canh[0].dich == "40/2024/TT-NHNN#than/dieu_24#khoan_4"


def test_sua_doi_thieu_khoi_trich_thi_canh_bao_khong_vut():
    canh = canh_tu_dieu("Điều 2", "Sửa đổi khoản 3 Điều 9 như sau:", 0,
                        "41/2025/TT-NHNN", "40/2024/TT-NHNN", [], None)
    assert len(canh) == 1 and canh[0].loi_van_moi is None
    assert any("lời văn mới" in c for c in canh[0].canh_bao)
