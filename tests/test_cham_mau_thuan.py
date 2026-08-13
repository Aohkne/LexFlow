"""Chấm mâu thuẫn ở tầng cặp — ghim đúng những chỗ định nghĩa dễ trượt.

Bộ nhãn cũ (`expect_conflict` trong `eval/questions.jsonl`) gắn cho CÂU HỎI, còn bộ phát hiện
chạy trên TẬP CHUNK. Tầng chấm này gắn nhãn vào **cặp điều khoản** nên không mục khi retrieval
đổi, và nói được precision — thứ `conflict_recall` chưa bao giờ nói được.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_NGUON = Path("eval/cham_mau_thuan.py")
_VANG = Path("eval/mau_thuan_vang.jsonl")
pytestmark = pytest.mark.skipif(not _NGUON.exists(), reason="thiếu eval/cham_mau_thuan.py")


def _nap():
    spec = importlib.util.spec_from_file_location("cham_mau_thuan", _NGUON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_VANG_GIA = [
    {"noi_bo": "SHB-QD-THE-2023::Mục 6.1", "luat": "TT18-2024::Điều 13", "mo_ta": "vô danh"},
    {"noi_bo": "SHB-QD-VI-2023::Mục 3.1", "luat": "TT40-2024::Điều 26", "mo_ta": "ví"},
]


def test_ky_vong_chi_tinh_cap_du_hai_phia():
    """Thiếu một phía thì bộ phát hiện không đủ dữ kiện — không được tính là bỏ sót."""
    mod = _nap()
    du = ["SHB-QD-THE-2023::Mục 6.1", "TT18-2024::Điều 13"]
    thieu = ["SHB-QD-THE-2023::Mục 6.1", "TT40-2024::Điều 26"]
    assert [c["mo_ta"] for c in mod.cap_ky_vong(_VANG_GIA, du)] == ["vô danh"]
    assert mod.cap_ky_vong(_VANG_GIA, thieu) == []


def test_dia_chi_chi_tiet_hon_van_khop():
    """Bộ phát hiện trích `Điều 13 Khoản 4`, nhãn vàng ghi `Điều 13` — phải khớp."""
    mod = _nap()
    kq = mod.cham(
        _VANG_GIA,
        ["SHB-QD-THE-2023::Mục 6.1", "TT18-2024::Điều 13"],
        [("SHB-QD-THE-2023::Mục 6.1", "TT18-2024::Điều 13 Khoản 4")],
    )
    assert (kq["ky_vong"], kq["bat_duoc"], kq["duong_tinh_gia"]) == (1, 1, 0)


def test_khong_nuot_dieu_khac_cung_tien_to():
    mod = _nap()
    assert mod.khop_dia_chi("TT18-2024::Điều 130", "TT18-2024::Điều 13") is False
    assert mod.khop_dia_chi("TT18-2024::Điều 13 Khoản 4", "TT18-2024::Điều 13") is True


def test_thu_tu_hai_phia_khong_quan_trong():
    mod = _nap()
    kq = mod.cham(
        _VANG_GIA,
        ["SHB-QD-THE-2023::Mục 6.1", "TT18-2024::Điều 13"],
        [("TT18-2024::Điều 13", "SHB-QD-THE-2023::Mục 6.1")],  # đảo chiều
    )
    assert kq["bat_duoc"] == 1


def test_bao_dung_cap_vang_thieu_phia_khong_bi_tinh_la_gia():
    """Cặp vàng mà chunk chỉ có một phía: bộ phát hiện vẫn báo đúng cặp ấy thì không phải lỗi.

    Đây là chỗ dễ chấm oan nhất — nếu lấy `cap_ky_vong` làm mẫu số của dương tính giả thì mọi
    cảnh báo đúng-nhưng-thiếu-dữ-kiện đều bị đếm ngược.
    """
    mod = _nap()
    kq = mod.cham(
        _VANG_GIA,
        ["SHB-QD-VI-2023::Mục 3.1"],  # thiếu phía luật
        [("SHB-QD-VI-2023::Mục 3.1", "TT40-2024::Điều 26")],
    )
    assert kq["ky_vong"] == 0
    assert kq["duong_tinh_gia"] == 0


def test_gop_tinh_precision_va_recall():
    mod = _nap()
    g = mod.gop([
        {"ky_vong": 2, "bat_duoc": 2, "bao": 3, "duong_tinh_gia": 1},
        {"ky_vong": 2, "bat_duoc": 1, "bao": 1, "duong_tinh_gia": 0},
    ])
    assert (g["recall"], g["precision"]) == (0.75, 0.75)


@pytest.mark.skipif(not _VANG.exists(), reason="thiếu eval/mau_thuan_vang.jsonl")
def test_bo_vang_that_tro_dung_dieu_khoan_co_that():
    """Mọi địa chỉ trong bộ vàng phải tồn tại trong corpus — nhãn trỏ vào hư không thì vô dụng."""
    corpus = json.loads(Path("data/corpus.real.json").read_text(encoding="utf-8"))
    co = {
        f"{d['doc_id']}::{a['article']}" for d in corpus["documents"] for a in d["articles"]
    }
    thieu = [
        dc for c in _nap().doc_vang() for dc in (c["noi_bo"], c["luat"]) if dc not in co
    ]
    assert not thieu, f"nhãn vàng trỏ vào điều khoản không có trong corpus: {thieu}"
