"""Ghim cách RRF cân hai nhánh.

Trọng số nhánh thưa là một hằng số đã được đo mà chọn (`docs/EVAL-IR.md` §7). Sai ở đây không làm
test nào khác đỏ — nó chỉ làm thứ hạng xấu đi một cách im lặng, đúng kiểu lỗi mà tầng đo mất một
ngày mới phát hiện ra.
"""
from __future__ import annotations

from app.knowledge.retrieval import _RRF_K, TRONG_SO_THUA, _rrf


def _hang(ids: list[str]) -> list[dict]:
    return [{"id": i} for i in ids]


def test_trong_so_1_thi_hai_nhanh_ngang_nhau():
    """RRF gốc: hạng 1 của nhánh này bằng đúng hạng 1 của nhánh kia."""
    ra = _rrf(_hang(["v"]), _hang(["f"]), 10, trong_so_thua=1.0)
    assert sorted(r["id"] for r in ra) == ["f", "v"]


def test_ha_trong_so_thi_nhanh_thua_thua_the():
    """Cùng ở hạng 1, nhánh thưa nhẹ hơn ⇒ xếp sau."""
    ra = _rrf(_hang(["v"]), _hang(["f"]), 10, trong_so_thua=0.1)
    assert [r["id"] for r in ra] == ["v", "f"]


def test_trung_id_thi_cong_diem_hai_nhanh():
    """Hit có ở cả hai nhánh phải được cộng, không phải ghi đè."""
    chung = _rrf(_hang(["x", "v"]), _hang(["x"]), 10, trong_so_thua=0.5)
    assert [r["id"] for r in chung] == ["x", "v"]


def test_trong_so_0_bo_han_nhanh_thua():
    """Không phải cộng 0 điểm: hit chỉ có ở nhánh thưa phải BIẾN MẤT, không nằm ở đuôi."""
    ra = _rrf(_hang(["v"]), _hang(["f"]), 10, trong_so_thua=0.0)
    assert [r["id"] for r in ra] == ["v"]


def test_diem_dung_cong_thuc():
    """1/(k+rank) nhân trọng số — ghim để đổi công thức là thấy ngay."""
    ra = _rrf(_hang(["a", "b"]), _hang(["b"]), 10, trong_so_thua=0.5)
    diem_b = 1.0 / (_RRF_K + 1) + 0.5 / _RRF_K
    diem_a = 1.0 / _RRF_K
    assert [r["id"] for r in ra] == (["b", "a"] if diem_b > diem_a else ["a", "b"])


def test_mac_dinh_la_hang_so_da_do():
    """`_rrf` không truyền trọng số thì phải dùng đúng hằng số sản phẩm, không phải 1.0 ẩn."""
    assert TRONG_SO_THUA == 0.1
    assert [r["id"] for r in _rrf(_hang(["v"]), _hang(["f"]), 10)] == ["v", "f"]
