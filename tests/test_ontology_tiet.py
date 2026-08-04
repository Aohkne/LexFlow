"""Test nhận diện tiết `(i)/(ii)` và phép kết hợp logic — offline.

Tiết CỐ Ý không được cấp địa chỉ node (đo được 4/586 viện dẫn, cả 4 ở văn bản đã
hết hiệu lực). Nhưng quan hệ logic giữa các tiết thì phải giữ: "(i) …; hoặc (ii) …"
là phép TUYỂN bên trong một Điểm, bỏ đi là mất nghĩa pháp lý.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import build_cu
from app.ontology.parser import ROMAN_ORDER, parse_dieu, tiet_logic
from app.ontology.segmenter import segment

_DIR = Path("data/fixtures")
_INDEX = _DIR / "_index.json"


@pytest.fixture(scope="module")
def index():
    return json.loads(_INDEX.read_text(encoding="utf-8"))


def _dieu(index, name):
    return parse_dieu((_DIR / name).read_text(encoding="utf-8"), index[name])


def test_bang_la_ma_tuong_minh():
    # Cùng kỷ luật với VI_LETTERS: tra bảng, không suy ra bằng thuật toán.
    assert ROMAN_ORDER["i"] == 1
    assert ROMAN_ORDER["iv"] == 4
    assert ROMAN_ORDER["ix"] == 9


def test_nhan_dien_tiet_va_round_trip(index):
    name = "TT17-2024-dieu16.txt"
    text = (_DIR / name).read_text(encoding="utf-8")
    dieu = _dieu(index, name)
    diem_a = dieu.khoan[0].diem[0]
    assert [t.marker for t in diem_a.tiet] == ["i", "ii"]
    for k in dieu.khoan:
        for d in k.diem:
            for t in d.tiet:
                assert text[t.start : t.end] == t.text
                assert d.start <= t.start and t.end <= d.end


def test_hoac_tuong_minh_ra_phep_tuyen(index):
    """TT17 Đ16 K1 điểm b: "(i) …tạo lập; hoặc (ii) …" — phải ra `any`."""
    diem_b = _dieu(index, "TT17-2024-dieu16.txt").khoan[0].diem[1]
    assert diem_b.tiet[0].connector == "hoac"
    assert tiet_logic(diem_b) == "any"


def test_chuoi_bon_tiet(index):
    """TT40 Đ25 K6 điểm c có 4 tiết nối bằng "hoặc"."""
    dieu = _dieu(index, "TT40-2024-dieu25.txt")
    diem = next(d for k in dieu.khoan for d in k.diem if len(d.tiet) == 4)
    assert [t.marker for t in diem.tiet] == ["i", "ii", "iii", "iv"]
    assert tiet_logic(diem) == "any"


def test_chi_co_dau_cham_phay_thi_khong_doan(index):
    """';' trần dùng cho cả liệt kê lẫn lựa chọn — đoán bừa là đổi nghĩa pháp lý."""
    diem_a = _dieu(index, "TT17-2024-dieu16.txt").khoan[0].diem[0]
    assert all(t.connector == "unknown" for t in diem_a.tiet)
    assert tiet_logic(diem_a) == "unknown"


def test_diem_khong_co_tiet_thi_rong(index):
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    assert all(d.tiet == [] for k in dieu.khoan for d in k.diem)


def test_build_cu_dien_sub_va_logic_tat_dinh(index):
    """`logic`/`sub` lấy từ parser, KHÔNG hỏi LLM — nên không tốn token và tái lập."""
    dieu = _dieu(index, "TT17-2024-dieu16.txt")
    k1 = dieu.khoan[0]
    units = segment(dieu, k1)
    u_b = [u.uid for u in units if u.source_diem == "b"]
    data = {
        "subject": {"units": [1], "label": ""},
        "action": {"units": [1], "label": ""},
        "logic": "all",
        "conditions": [{"source_diem": "b", "units": u_b, "object_label": "", "constraint_label": ""}],
    }
    cu = build_cu(data, k1, dieu, units)
    c = cu.conditions[0]
    assert c.logic == "any"  # "hoặc" giữa (i) và (ii)
    assert [s.marker for s in c.sub] == ["i", "ii"]
    for s in c.sub:
        assert dieu.text[s.char_span[0] : s.char_span[1]] == s.text


def test_canh_bao_khi_khong_ro_va_hay_hoac(index):
    """Dấu ';' trần ⇒ `logic` phải là `unknown` VÀ phải có cảnh báo bàn giao cho người.

    Nội dung cảnh báo đổi theo việc các tiết đã có `ap_dung_khi` hay chưa (xem
    `docs/ONTOLOGY-POC.md` §14c), nhưng hai điều KHÔNG đổi và test này canh đúng chúng:
    `logic` không bao giờ tự nhảy lên `all`, và không bao giờ im lặng. Ở TT17 Đ16 k1
    điểm a mọi tiết đều có guard nên rơi vào mã `guard_da_phu`; ca không có guard nào
    được canh riêng ở `test_ontology_guard.py`.
    """
    dieu = _dieu(index, "TT17-2024-dieu16.txt")
    k1 = dieu.khoan[0]
    units = segment(dieu, k1)
    u_a = [u.uid for u in units if u.source_diem == "a"]
    data = {
        "subject": {"units": [1], "label": ""},
        "action": {"units": [1], "label": ""},
        "logic": "all",
        "conditions": [{"source_diem": "a", "units": u_a, "object_label": "", "constraint_label": ""}],
    }
    cu = build_cu(data, k1, dieu, units)
    assert cu.conditions[0].logic == "unknown"
    # Mã cụ thể đã đổi ba lần (mo_ho → guard_da_phu → guard_phan_hoach) khi câu hỏi bàn
    # giao cho người được mài sắc dần. Test này cố ý canh bất biến chứ không canh mã:
    # nhánh `logic == "unknown"` KHÔNG BAO GIỜ im lặng, dù kết luận là gì.
    assert any(("tiet_semicolon_" in w or "tiet_guard_" in w) for w in cu.warnings), cu.warnings


def test_canh_bao_khi_span_khong_bao_het_tiet(index):
    dieu = _dieu(index, "TT17-2024-dieu16.txt")
    k1 = dieu.khoan[0]
    units = segment(dieu, k1)
    first_b = min(u.uid for u in units if u.source_diem == "b")
    data = {
        "subject": {"units": [1], "label": ""},
        "action": {"units": [1], "label": ""},
        "logic": "all",
        # chỉ chọn đơn vị đầu của điểm b → bỏ sót tiết phía sau
        "conditions": [{"source_diem": "b", "units": [first_b], "object_label": "", "constraint_label": ""}],
    }
    cu = build_cu(data, k1, dieu, units)
    assert any("không bao hết các tiết" in w for w in cu.warnings)


def test_tiet_khong_duoc_cap_dia_chi(index):
    """Quyết định đã chốt: TietSpan không có `id`, không xuất hiện trong khoá node."""
    dieu = _dieu(index, "TT17-2024-dieu16.txt")
    diem_b = dieu.khoan[0].diem[1]
    assert not hasattr(diem_b.tiet[0], "id")
    assert "tiet" not in diem_b.id
