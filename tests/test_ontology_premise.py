"""Test tầng premise (KhaiNiem) + viện dẫn gắn vào CU — offline, không gọi Gemini."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import _resolve_references, build_cu, build_khai_niem
from app.ontology.parser import parse_dieu
from app.ontology.segmenter import segment

_DIR = Path("data/fixtures")
_INDEX = _DIR / "_index.json"


@pytest.fixture(scope="module")
def index():
    return json.loads(_INDEX.read_text(encoding="utf-8"))


def _dieu(index, name):
    p = _DIR / name
    if not p.exists():
        pytest.skip(f"chưa sinh fixture {name}")
    return parse_dieu(p.read_text(encoding="utf-8"), index[name])


# --- premise → KhaiNiem, KHÔNG phải ComplianceUnit -------------------------


def test_dieu_giai_thich_tu_ngu_ra_khai_niem(index):
    """Ép Điều 3 thành CU sẽ sinh "nghĩa vụ" không tồn tại — đây là chỗ chặn."""
    dieu = _dieu(index, "ND52-2024-dieu3.txt")
    assert "Giải thích từ ngữ" in dieu.tieu_de
    k1 = dieu.khoan[0]
    units = segment(dieu, k1)
    # mô phỏng LLM chọn đơn vị đầu cho cả thuật ngữ lẫn định nghĩa
    uid = next(u.uid for u in units if u.uid > 0)
    kn = build_khai_niem(
        {"thuat_ngu": {"units": [uid]}, "dinh_nghia": {"units": [uid]}}, k1, dieu, units
    )
    assert kn.id == k1.id
    assert kn.thuat_ngu and kn.dinh_nghia
    # kỷ luật span giữ nguyên: là lát cắt của luật, không phải chữ LLM
    a, b = kn.char_span_thuat_ngu
    assert dieu.text[a:b] == kn.thuat_ngu
    assert kn.warnings == []


def test_premise_pham_vi_khac_premise_dinh_nghia(index):
    """Lỗi tìm ra khi chạy thật: Điều 1 "Phạm vi điều chỉnh" bị đem đi trích thuật
    ngữ và ra bản ghi rỗng kèm cảnh báo "mất provenance" sai sự thật.

    `premise` gộp hai loại rất khác nhau — chỉ `dinh_nghia` mới sinh KhaiNiem.
    """
    from app.ontology.roles import classify_dieu

    d1 = _dieu(index, "ND52-2024-dieu1.txt")
    d3 = _dieu(index, "ND52-2024-dieu3.txt")
    v1, v3 = classify_dieu(d1), classify_dieu(d3)
    assert v1.role == v3.role == "premise"
    assert v1.premise_kind == "pham_vi"
    assert v3.premise_kind == "dinh_nghia"


def test_units_rong_la_khong_co_thuat_ngu_khong_phai_mat_provenance(index):
    """LLM trả units rỗng = "ở đây không định nghĩa gì", khác hẳn uid sai."""
    dieu = _dieu(index, "ND52-2024-dieu1.txt")
    from app.ontology.parser import khoan_de_trich

    k = khoan_de_trich(dieu)[0]
    units = segment(dieu, k)
    assert build_khai_niem({"thuat_ngu": {"units": []}, "dinh_nghia": {"units": []}},
                           k, dieu, units) is None


def test_khai_niem_uid_sai_thi_bao_mat_provenance(index):
    dieu = _dieu(index, "ND52-2024-dieu3.txt")
    k1 = dieu.khoan[0]
    units = segment(dieu, k1)
    kn = build_khai_niem(
        {"thuat_ngu": {"units": [999]}, "dinh_nghia": {"units": [999]}}, k1, dieu, units
    )
    assert kn.char_span_thuat_ngu is None
    assert any("mất provenance" in w for w in kn.warnings)


def test_quote_thu_hep_duoc_thuat_ngu(index):
    """Thuật ngữ thường ngắn hơn cả đơn vị — quote thu hẹp vào đúng cụm."""
    dieu = _dieu(index, "ND52-2024-dieu3.txt")
    k1 = dieu.khoan[0]
    units = segment(dieu, k1)
    uid = next(u.uid for u in units if u.uid > 0)
    body = next(u for u in units if u.uid == uid).text
    # lấy một cụm có thật nằm trong đơn vị
    cum = body.split(" là ")[0].split(". ", 1)[-1][:40].strip()
    kn = build_khai_niem(
        {"thuat_ngu": {"units": [uid], "quote": cum}, "dinh_nghia": {"units": [uid]}},
        k1, dieu, units,
    )
    assert kn.thuat_ngu == cum


# --- references: nối citation.py vào CU ------------------------------------


def _llm_toi_thieu(units) -> dict:
    uid = next(u.uid for u in units if u.uid > 0)
    return {"subject": {"units": [uid]}, "action": {"units": [uid]}, "logic": "all",
            "conditions": []}


def test_references_duoc_dien_tu_diem_g(index):
    """Điểm g ND52 Đ22 K2: "…quy định tại điểm a, điểm b, điểm c, điểm d và điểm đ
    khoản 2 Điều này" — trước đây nằm chết trong text, giờ thành khoá node."""
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    k2 = dieu.khoan[1]
    refs, hep_hon = _resolve_references(k2, dieu)
    base = "52/2024/NĐ-CP#than/dieu_22#khoan_2"
    for d in ("a", "b", "c", "d", "đ"):
        assert f"{base}#diem_{d}" in refs
    assert not hep_hon  # không có viện dẫn tới tiết trong khoản này


def test_khong_tro_ve_chinh_minh(index):
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    k2 = dieu.khoan[1]
    refs, _ = _resolve_references(k2, dieu)
    assert k2.id not in refs


def test_references_vao_compliance_unit(index):
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    k2 = dieu.khoan[1]
    units = segment(dieu, k2)
    cu = build_cu(_llm_toi_thieu(units), k2, dieu, units)
    assert cu.references
    assert cu.role == "actor_cu"  # mặc định
    assert cu.references_hep_hon is False


def test_role_duoc_truyen_vao_cu(index):
    dieu = _dieu(index, "ND52-2024-dieu2.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    cu = build_cu(_llm_toi_thieu(units), k, dieu, units, role="meta_cu")
    assert cu.role == "meta_cu"


# --- subject = null khi cổng không có bên bị ràng buộc ----------------------
#
# Tiền lệ: Listing 1 của GraphCompliance chấp nhận `"context": null` khi trường không
# áp dụng. Cổng thời gian/lãnh thổ cũng vậy — *"Nghị định này có hiệu lực thi hành từ
# ngày…"* có chủ ngữ NGỮ PHÁP nhưng không có bên nào để tuân thủ hay vi phạm.


def _llm_khong_subject(units) -> dict:
    uid = next(u.uid for u in units if u.uid > 0)
    return {"subject": {"units": []}, "action": {"units": [uid]}, "logic": "unknown",
            "conditions": []}


def _gate(kind: str):
    from app.ontology.schema import Gate

    return Gate(kind=kind, pham_vi="van_ban", suy_ra_duoc=True)


def test_cong_thoi_gian_duoc_bo_trong_subject(index):
    from app.ontology.extractor import subject_khong_ap_dung

    dieu, k = _dieu(index, "ND52-2024-dieu37.txt"), None
    k = dieu.khoan[0]
    units = segment(dieu, k)
    gates = [_gate("thoi_gian")]
    assert subject_khong_ap_dung("meta_cu", gates)
    cu = build_cu(_llm_khong_subject(units), k, dieu, units, role="meta_cu", gates=gates)
    assert cu.subject is None
    assert cu.subject_source is None
    assert cu.ok, cu.errors  # KHÔNG phải lỗi mất provenance
    assert cu.action.text  # vị ngữ thì vẫn bắt buộc — câu có hành vi "có hiệu lực"


def test_cong_chu_the_van_bat_buoc_subject(index):
    """Role qualification CÓ một vai cần định danh — không được nới cho nhóm này."""
    from app.ontology.extractor import subject_khong_ap_dung
    from app.ontology.schema import Gate

    gates = [Gate(kind="chu_the", pham_vi="muc")]
    assert not subject_khong_ap_dung("meta_cu", gates)
    dieu, k = _dieu(index, "TT40-2024-dieu26.txt"), None
    k = dieu.khoan[1]
    units = segment(dieu, k)
    cu = build_cu(_llm_khong_subject(units), k, dieu, units, role="meta_cu", gates=gates)
    assert cu.subject is not None
    assert any("mất provenance" in e for e in cu.errors)


def test_actor_cu_khong_bao_gio_duoc_bo_trong_subject(index):
    from app.ontology.extractor import subject_khong_ap_dung

    assert not subject_khong_ap_dung("actor_cu", [_gate("thoi_gian")])
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    k = dieu.khoan[1]
    units = segment(dieu, k)
    cu = build_cu(_llm_khong_subject(units), k, dieu, units)
    assert any("mất provenance" in e for e in cu.errors)


def test_meta_cu_chua_xac_dinh_cong_thi_khong_duoc_mien(index):
    """Không có cổng = chưa có căn cứ nào để miễn. Miễn ở đó là để lọt trích hỏng."""
    from app.ontology.extractor import subject_khong_ap_dung

    assert not subject_khong_ap_dung("meta_cu", [])
    assert not subject_khong_ap_dung("meta_cu", None)


def test_null_khac_voi_trich_hong(index):
    """Phân biệt hai loại vắng mặt: uid SAI vẫn phải là lỗi, kể cả khi được miễn."""
    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    data = _llm_khong_subject(units)
    data["subject"] = {"units": [999]}  # khai có, nhưng đơn vị không tồn tại
    cu = build_cu(data, k, dieu, units, role="meta_cu", gates=[_gate("thoi_gian")])
    assert cu.subject is not None
    assert any("mất provenance" in e for e in cu.errors)


def test_dien_subject_du_duoc_mien_thi_canh_bao(index):
    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    cu = build_cu(_llm_toi_thieu(units), k, dieu, units,
                  role="meta_cu", gates=[_gate("thoi_gian")])
    assert cu.subject is not None
    assert any("chủ ngữ ngữ pháp" in w for w in cu.warnings)


def test_prompt_bao_mo_hinh_bo_trong_subject(index):
    from app.ontology.extractor import build_prompt

    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    p_mien = build_prompt(k, dieu, units, role="meta_cu", gates=[_gate("thoi_gian")])
    p_thuong = build_prompt(k, dieu, units)
    assert '"units": []' in p_mien
    assert '"units": []' not in p_thuong


def test_bao_cao_neo_hien_khong_ap_dung(index):
    from app.ontology.extractor import grounding_report

    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    cu = build_cu(_llm_khong_subject(units), k, dieu, units,
                  role="meta_cu", gates=[_gate("thoi_gian")])
    rows = grounding_report(cu)
    assert rows[0] == {"field": "subject", "status": "khong_ap_dung",
                       "units": [], "char_span": None}


def test_trang_kiem_van_hien_dong_subject(index):
    """Ô trống không được BIẾN MẤT khỏi bảng — người đọc phải thấy nó trống có chủ ý."""
    from app.ontology.report import render

    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    cu = build_cu(_llm_khong_subject(units), k, dieu, units,
                  role="meta_cu", gates=[_gate("thoi_gian")])
    html = render(cu, dieu)
    assert "<td>subject</td>" in html
    assert "không áp dụng" in html


def test_co_tiet_bat_co_references_hep_hon(index):
    """TT17 Đ16 không có viện dẫn tới tiết; dùng chuỗi tự dựng để kiểm cờ."""
    from app.ontology.citation import parse_citations

    refs = parse_citations("quy định tại điểm b(i) khoản này")
    assert refs and refs[0].co_tiet
