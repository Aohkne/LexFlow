"""Kiểm phần chấm THUẦN (không mạng) của eval/judge.py: tiêu chí trích dẫn + tổng hợp."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.judge import cham_python, tong_hop


def test_cham_python_trich_dan():
    # dẫn đủ văn bản vàng → khớp
    assert cham_python(["TT40-2024"], ("TT40-2024",)) == {
        "co_trich_dan": True, "trich_dan_khop": True,
    }
    # dẫn thừa nhưng bao đủ vàng → vẫn khớp
    assert cham_python(["TT40-2024", "TT17-2024"], ("TT40-2024",))["trich_dan_khop"] is True
    # thiếu một văn bản vàng → không khớp
    assert cham_python(["TT40-2024"], ("TT40-2024", "TT17-2024"))["trich_dan_khop"] is False
    # không trích dẫn gì
    assert cham_python([], ("TT40-2024",)) == {"co_trich_dan": False, "trich_dan_khop": False}
    # không có nhãn vàng → không đánh giá được, không tính là khớp
    assert cham_python(["TT40-2024"], ())["trich_dan_khop"] is False


def test_tong_hop():
    kq = [
        {"tuong_duong": "dung", "diem": 1.0, "co_trich_dan": True, "trich_dan_khop": True},
        {"tuong_duong": "thieu", "diem": 0.5, "co_trich_dan": True, "trich_dan_khop": False},
        {"tuong_duong": "sai", "diem": 0.0, "co_trich_dan": False, "trich_dan_khop": False},
    ]
    t = tong_hop(kq)
    assert t["n"] == 3
    assert t["diem_ngu_nghia_tb"] == round(1.5 / 3, 3)
    assert t["ty_le_dung"] == round(1 / 3, 3)
    assert t["ty_le_co_trich_dan"] == round(2 / 3, 3)
    assert t["ty_le_trich_dan_khop"] == round(1 / 3, 3)


def test_tong_hop_rong():
    assert tong_hop([]) == {"n": 0}
