"""Test tách chunk mức Khoản cho điều dài."""
from __future__ import annotations

from app.ingestion.pipeline import _MAX_CHUNK, _split_khoan


def test_dieu_ngan_giu_nguyen():
    out = _split_khoan("Điều 1", "Nội dung ngắn.")
    assert out == [("Điều 1", "Nội dung ngắn.")]


def test_dieu_dai_tach_theo_khoan():
    khoan = [f"{i}. Nội dung khoản {i}. " + "x" * 700 for i in range(1, 7)]
    text = "Tiêu đề điều\n" + "\n".join(khoan)
    out = _split_khoan("Điều 26", text)
    assert len(out) > 1
    assert all(len(t) <= _MAX_CHUNK + 800 for _, t in out)
    # nhãn có dải khoản, phần mở đầu dính khoản đầu
    assert out[0][0].startswith("Điều 26 Khoản 1")
    assert "Tiêu đề điều" in out[0][1]
    # không mất nội dung
    joined = "\n".join(t for _, t in out)
    for i in range(1, 7):
        assert f"Nội dung khoản {i}" in joined


def test_dieu_dai_khong_co_khoan_cat_cua_so():
    text = "một đoạn rất dài không có cấu trúc khoản " * 200
    out = _split_khoan("Điều 3", text)
    assert len(out) >= 2
    assert out[0][0] == "Điều 3 (phần 1)"
