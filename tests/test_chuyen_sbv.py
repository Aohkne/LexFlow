"""Ghim phép chuyển bộ test SBV-LawGraph → bộ câu hỏi eval.

Nhãn sinh ra là suy diễn từ file nguồn + corpus, không phải nhãn người — sai ở đây không làm
test nào đỏ, chỉ làm bảng kết quả sai một cách trông rất bình thường.
"""
from __future__ import annotations

import pytest

from eval.chuyen_sbv import NhanHong, tach_nhan, dieu_co_that


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


def _corpus() -> dict:
    """Bốn văn bản đủ để dựng mọi ca: còn hiệu lực, đã hết hiệu lực, điều bị chẻ khoản."""
    return {
        "documents": [
            {"doc_id": "TT40-2024", "so_hieu": "40/2024/TT-NHNN",
             "valid_from": "2024-07-17", "valid_to": None,
             "articles": [{"article": "Điều 18", "text": ""},
                          {"article": "Điều 23 Khoản 1-3", "text": ""},
                          {"article": "Điều 23 Khoản 4-6", "text": ""}]},
            {"doc_id": "TT17-2024", "so_hieu": "17/2024/TT-NHNN",
             "valid_from": "2024-07-01", "valid_to": None,
             "articles": [{"article": "Điều 17", "text": ""}]},
            {"doc_id": "ND52-2024", "so_hieu": "52/2024/NĐ-CP",
             "valid_from": "2024-07-01", "valid_to": None,
             "articles": [{"article": "Điều 3", "text": ""}]},
            {"doc_id": "TT23-2014", "so_hieu": "23/2014/TT-NHNN",
             "valid_from": "2014-10-15", "valid_to": "2024-07-01",
             "articles": [{"article": "Điều 5", "text": ""}]},
        ],
        "relationships": [],
    }


def test_dieu_co_that_gom_theo_so_dieu():
    assert dieu_co_that(_corpus())["TT40-2024"] == {"18", "23"}


def test_dieu_bi_che_khoan_van_tinh_la_co():
    """`pipeline._split_khoan` chẻ điều dài thành "Điều 23 Khoản 1-3" — nhãn vàng vẫn là "Điều 23".

    Nếu kiểm bằng so khớp nhãn nguyên văn thì mọi điều dài đều bị coi là không tồn tại.
    """
    assert "23" in dieu_co_that(_corpus())["TT40-2024"]


def test_van_ban_khong_co_dieu_nao_thi_tap_rong():
    corpus = {"documents": [{"doc_id": "X", "so_hieu": "1/2020/TT-NHNN", "articles": []}],
              "relationships": []}
    assert dieu_co_that(corpus) == {"X": set()}
