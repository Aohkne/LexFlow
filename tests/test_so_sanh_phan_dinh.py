"""Định nghĩa chỉ số của phép so sánh model phán định — ghim để nó không trôi.

Lý do tầng đo này tồn tại: `run_benchmark.py` chỉ gọi `detect_conflicts` khi câu hỏi có
`expect_conflict` (7/36 câu), nên `conflict_recall` **không có đối trọng precision** — một bộ
phát hiện báo động mọi thứ vẫn đạt 7/7. Đo pilot 10/08 cho thấy đó không phải lo xa:
`gemini-2.5-flash-lite` báo mâu thuẫn ở **2/2** câu KHÔNG có mâu thuẫn.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_NGUON = Path("eval/so_sanh_phan_dinh.py")
pytestmark = pytest.mark.skipif(not _NGUON.exists(), reason="thiếu eval/so_sanh_phan_dinh.py")


def _nap():
    """`eval/` không phải package nên nạp thẳng theo đường dẫn."""
    spec = importlib.util.spec_from_file_location("so_sanh_phan_dinh", _NGUON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ca(expect: bool, so_lan_bao: int, n_lap: int = 3) -> dict:
    return {
        "query": "q", "group": "conflict" if expect else "lookup",
        "expect_conflict": expect, "n_lap": n_lap if expect else 1,
        "so_lan_bao": so_lan_bao,
    }


def test_recall_tinh_theo_bat_duoc_it_nhat_mot_luot():
    """Cùng cách `run_benchmark` tính, để hai con số so được với nhau."""
    t = _nap().tong_hop({"cases": [_ca(True, 1), _ca(True, 0), _ca(True, 3)]})
    assert (t["recall_bat_duoc"], t["recall_tong"]) == (2, 3)


def test_on_dinh_khat_khe_hon_recall():
    """Đúng 3/3 lượt khác hẳn đúng 1/3 — phán định LLM không tất định nên phải tách hai số."""
    t = _nap().tong_hop({"cases": [_ca(True, 1), _ca(True, 3), _ca(True, 3)]})
    assert t["recall_bat_duoc"] == 3, "cả ba đều bắt được ít nhất một lượt"
    assert t["on_dinh_tuyet_doi"] == 2, "chỉ hai ca đúng ở MỌI lượt"


def test_duong_tinh_gia_dem_tren_ca_khong_ky_vong():
    t = _nap().tong_hop({"cases": [_ca(True, 3), _ca(False, 1), _ca(False, 0), _ca(False, 1)]})
    assert (t["duong_tinh_gia"], t["am_tong"]) == (2, 3)
    assert t["recall_tong"] == 1, "ca âm không được lọt vào mẫu số của recall"


def test_gia_thieu_thi_bao_none_chu_khong_doan():
    mod = _nap()
    assert mod._tien("gemini-2.5-flash-lite", 1_000_000, 1_000_000) == pytest.approx(0.50)
    assert mod._tien("model-chua-co-trong-bang", 1_000_000, 0) is None
