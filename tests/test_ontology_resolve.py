"""Test neo bằng chọn-đơn-vị + dựng ComplianceUnit — offline, không gọi Gemini.

Mô phỏng JSON Gemini trả về (chỉ có số hiệu đơn vị, không có offset) rồi kiểm tra
code tự tính span, và bắt được các kiểu bịa.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.ontology.extractor import build_cu, resolve
from app.ontology.parser import parse_dieu
from app.ontology.segmenter import segment

_FIXTURE = Path("data/fixtures/ND52-2024-dieu22.txt")
_SO_HIEU = "52/2024/NĐ-CP"

_DIEU_KHONG_CHU_NGU = """Điều 30. Trách nhiệm của tổ chức cung ứng dịch vụ
1. Bảo đảm an toàn hệ thống thông tin cấp độ 3."""


@pytest.fixture(scope="module")
def dieu():
    return parse_dieu(_FIXTURE.read_text(encoding="utf-8"), _SO_HIEU)


@pytest.fixture(scope="module")
def k2(dieu):
    return dieu.khoan[1]


@pytest.fixture(scope="module")
def units(dieu, k2):
    return segment(dieu, k2)


def test_don_vi_ra_span_hop_le(dieu, units):
    g = resolve({"units": [5]}, units, dieu.text)
    assert g.status == "unit"
    u5 = next(u for u in units if u.uid == 5)
    assert g.char_span == (u5.start, u5.end)
    assert dieu.text[g.char_span[0] : g.char_span[1]] == u5.text


def test_quote_thu_hep_span_trong_don_vi(dieu, units):
    g = resolve({"units": [5], "quote": "50 tỷ đồng"}, units, dieu.text)
    assert g.status == "exact"
    assert dieu.text[g.char_span[0] : g.char_span[1]] == "50 tỷ đồng"


def test_quote_ngoai_don_vi_lui_ve_span_don_vi(dieu, units):
    """Quote sai KHÔNG làm mất provenance — chỉ mất độ mịn."""
    g = resolve({"units": [5], "quote": "500 tỷ đồng mỗi tháng"}, units, dieu.text)
    assert g.status == "unit"
    u5 = next(u for u in units if u.uid == 5)
    assert g.char_span == (u5.start, u5.end)  # vẫn neo được


def test_quote_dung_chu_nhung_o_don_vi_khac_thi_khong_nhan(dieu, units):
    """Chuỗi có thật trong Điều nhưng ngoài đơn vị đã chọn → không được nhận."""
    g = resolve({"units": [5], "quote": "Có Bản thuyết minh giải pháp kỹ thuật"}, units, dieu.text)
    assert g.status == "unit"


def test_uid_khong_ton_tai_la_invalid(dieu, units):
    g = resolve({"units": [999]}, units, dieu.text)
    assert g.status == "invalid"
    assert g.char_span is None


def test_bao_loi_nhieu_don_vi(dieu, units):
    g = resolve({"units": [5, 6, 7]}, units, dieu.text)
    a = next(u for u in units if u.uid == 5)
    b = next(u for u in units if u.uid == 7)
    assert g.char_span == (a.start, b.end)


def _llm_tot() -> dict:
    return {
        "subject": {"units": [2], "quote": "Tổ chức không phải là ngân hàng, chi nhánh ngân hàng nước ngoài",
                    "label": "tổ chức không phải là ngân hàng", "source": "explicit"},
        "action": {"units": [2], "quote": "được Ngân hàng Nhà nước cấp Giấy phép",
                   "label": "được cấp Giấy phép khi đáp ứng đủ điều kiện"},
        "logic": "all",
        "conditions": [
            {"source_diem": "b", "units": [5], "object_label": "vốn điều lệ thực góp",
             "constraint_label": "tối thiểu 50 tỷ đồng với ví điện tử"},
        ],
    }


def test_build_cu_duong_sach(dieu, k2, units):
    cu = build_cu(_llm_tot(), k2, dieu, units)
    assert cu.id == "52/2024/NĐ-CP#than/dieu_22#khoan_2"
    assert cu.ok and cu.errors == []
    assert cu.subject.grounding.status == "exact"
    # Chữ của luật, KHÔNG phải chữ LLM viết.
    assert cu.subject.text == "Tổ chức không phải là ngân hàng, chi nhánh ngân hàng nước ngoài"
    assert cu.subject.label == "tổ chức không phải là ngân hàng"
    assert cu.conditions[0].text.startswith("b) Có vốn điều lệ")
    assert "bỏ sót điểm" in " ".join(cu.warnings)  # mới khai 1/8 điểm


def test_text_luon_la_lat_cat_cua_luat(dieu, k2, units):
    """Đóng lỗ hổng giai đoạn 1: text không còn là chữ tự do của LLM."""
    data = _llm_tot()
    data["action"]["label"] = "diễn giải tuỳ ý của mô hình"
    cu = build_cu(data, k2, dieu, units)
    g = cu.action.grounding
    assert cu.action.text == dieu.text[g.char_span[0] : g.char_span[1]]
    assert cu.action.text != cu.action.label


def test_hallucination_phai_la_loi_cung(dieu, k2, units):
    """Test hồi quy: chuỗi Gemini trả THẬT ở giai đoạn 1 phải bị chặn cứng.

    Giai đoạn 1 chỉ ghi một dòng warning và vẫn để chuỗi sai đi tiếp vào `action`.
    """
    data = _llm_tot()
    data["action"]["label"] = (
        "phải đáp ứng đầy đủ và phải đảm bảo duy trì đủ các điều kiện sau đây "
        "trong quá trình cung ứng dịch vụ trung gian thanh toán"
    )
    data["action"].pop("quote")  # neo cả câu bao trùm
    cu = build_cu(data, k2, dieu, units)
    assert not cu.ok
    assert any("ĐIỀU KIỆN" in e and "NGHĨA VỤ" in e for e in cu.errors)
    assert any(e.startswith("action:") for e in cu.errors)


def test_bia_so_trong_dieu_kien_la_loi_cung(dieu, k2, units):
    data = _llm_tot()
    data["conditions"][0]["constraint_label"] = "tối thiểu 500 tỷ đồng"
    cu = build_cu(data, k2, dieu, units)
    assert not cu.ok
    assert any("bịa số" in e for e in cu.errors)


def test_uid_sai_lam_mat_provenance(dieu, k2, units):
    data = _llm_tot()
    data["subject"]["units"] = [999]
    cu = build_cu(data, k2, dieu, units)
    assert not cu.ok
    assert any("mất provenance" in e for e in cu.errors)


def test_source_diem_lay_tu_units_chu_khong_lay_loi_khai(dieu, k2, units):
    """Lời khai sai không kéo được `source_diem` đi theo — parser thắng.

    Đơn vị [5] thuộc điểm `b` và parser biết điều đó (`Unit.source_diem`), nên hỏi lại
    LLM là hỏi câu đã có đáp án. Ca `"z"` ở đây là bản thu nhỏ của lỗi thật đo được
    trên corpus: 13/49 bản ghi khai điểm cho những Khoản không chẻ điểm nào.
    """
    data = _llm_tot()
    data["conditions"][0]["source_diem"] = "z"
    cu = build_cu(data, k2, dieu, units)
    assert cu.conditions[0].source_diem == "b"
    assert not any("z" == c.source_diem for c in cu.conditions)


def test_khai_diem_nhung_neo_ngoai_moi_diem_thi_bao_lech(dieu, k2, units):
    """Khoản CÓ chẻ điểm mà mọi đơn vị nằm ngoài ⇒ mâu thuẫn thật, phải nói ra.

    Khác hẳn ca Khoản không chẻ điểm: ở đó parser chắc chắn nên im lặng là đúng, còn ở
    đây có hai câu trả lời khả dĩ và máy không được tự chọn.
    """
    data = _llm_tot()
    chapeau = next(u.uid for u in units if u.uid > 0 and u.source_diem is None)
    data["conditions"][0] = {"source_diem": "b", "units": [chapeau],
                             "object_label": "", "constraint_label": ""}
    cu = build_cu(data, k2, dieu, units)
    assert cu.conditions[0].source_diem is None
    assert any("diem_khai_lech" in w for w in cu.warnings)


def test_span_vat_qua_nhieu_diem_thi_khong_quy_ve_mot_diem(dieu, k2, units):
    """Neo trùm hai điểm ⇒ KHÔNG có điểm nào đúng; đoán bừa sẽ giấu mất neo quá rộng."""
    a = next(u for u in units if u.source_diem == "a")
    b = next(u for u in units if u.source_diem == "b")
    data = _llm_tot()
    data["conditions"][0] = {"source_diem": "a", "units": [a.uid, b.uid],
                             "object_label": "", "constraint_label": ""}
    cu = build_cu(data, k2, dieu, units)
    assert cu.conditions[0].source_diem is None
    w = " ".join(cu.warnings)
    assert "diem_vat_nhieu_diem" in w and "a, b" in w


def test_subject_neo_tieu_de_thi_ha_ve_inherited():
    dieu = parse_dieu(_DIEU_KHONG_CHU_NGU, _SO_HIEU)
    k = dieu.khoan[0]
    units = segment(dieu, k)
    data = {
        "subject": {"units": [0], "label": "tổ chức cung ứng dịch vụ", "source": "explicit"},
        "action": {"units": [1], "label": "bảo đảm an toàn hệ thống thông tin"},
        "logic": "unknown",
        "conditions": [],
    }
    cu = build_cu(data, k, dieu, units)
    assert cu.subject_source == "inherited"
    assert cu.subject.text.startswith("Điều 30.")
    assert any("hạ về" in w for w in cu.warnings)


def test_logic_khong_hop_le_ve_unknown(dieu, k2, units):
    cu = build_cu({"logic": "bịa"}, k2, dieu, units)
    assert cu.logic == "unknown"
