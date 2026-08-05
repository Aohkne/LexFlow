"""Bộ đọc mệnh lệnh tác động: điều của văn bản sửa → cạnh con↔con. Offline."""
from __future__ import annotations

import pytest

from app.ontology.tac_dong import CanhTacDong, dich_tu_menh_lenh, so_hieu_nen, thao_tac_tu_cau


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
