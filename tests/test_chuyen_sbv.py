"""Ghim phép chuyển bộ test SBV-LawGraph → bộ câu hỏi eval.

Nhãn sinh ra là suy diễn từ file nguồn + corpus, không phải nhãn người — sai ở đây không làm
test nào đỏ, chỉ làm bảng kết quả sai một cách trông rất bình thường.
"""
from __future__ import annotations

import pytest

from eval.chuyen_sbv import NhanHong, tach_nhan


def test_tach_tu_phai_khong_phai_tu_trai():
    """Hậu tố là SỐ ĐIỀU. Tách từ trái thì "…_21" ra "2" và nhãn trỏ nhầm điều."""
    assert tach_nhan("08/2023/tt-nhnn_21") == ("08/2023/TT-NHNN", "21")


def test_chu_thuong_duoc_viet_hoa_de_khop_corpus():
    """Nhãn SBV viết thường hoàn toàn; corpus ghi số hiệu viết hoa."""
    assert tach_nhan("40/2024/tt-nhnn_18") == ("40/2024/TT-NHNN", "18")


def test_bo_dau_de_khop_nghi_dinh():
    """Corpus ghi "NĐ-CP", bộ SBV ghi "nd-cp"."""
    assert tach_nhan("52/2024/nd-cp_3")[0] == "52/2024/ND-CP"


def test_so_dieu_co_chu_cai():
    assert tach_nhan("40/2024/tt-nhnn_12a") == ("40/2024/TT-NHNN", "12a")


def test_thieu_gach_duoi_thi_nem():
    with pytest.raises(NhanHong):
        tach_nhan("12/2022/tt-nhnn")


def test_hau_to_khong_phai_so_thi_nem():
    """Nhãn hỏng là lỗi ĐỊNH DẠNG, khác câu ngoài phạm vi — không được nuốt im lặng."""
    with pytest.raises(NhanHong):
        tach_nhan("12/2022/tt-nhnn_dieu-ba")
