"""Test tầng premise (KhaiNiem) + viện dẫn gắn vào CU — offline, không gọi Gemini."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import _resolve_references, build_cu, build_khai_niem
from app.ontology.parser import parse_dieu
from app.ontology.schema import ActorCU, MetaCU
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
    assert cu.type == "actor_cu"  # mặc định
    assert cu.references_hep_hon is False


def test_vai_quyet_dinh_KIEU_DU_LIEU_chu_khong_chi_mot_nhan(index):
    """Đây là điều `MetaCU`/`ActorCU` nói mà một trường `role` không nói được."""
    dieu = _dieu(index, "ND52-2024-dieu2.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    cu = build_cu(_llm_toi_thieu(units), k, dieu, units, role="meta_cu",
                  gates=[_gate("thoi_gian")])
    assert isinstance(cu, MetaCU) and cu.type == "meta_cu"
    assert not hasattr(cu, "subject") and not hasattr(cu, "subject_source")

    actor = build_cu(_llm_toi_thieu(units), k, dieu, units)
    assert isinstance(actor, ActorCU) and actor.type == "actor_cu"
    assert not hasattr(actor, "gates") and not hasattr(actor, "dieu_kien_cong")


# --- meta-CU KHÔNG CÓ ô chủ thể ---------------------------------------------
#
# Bản trước cho `subject=None` với cổng thời gian/lãnh thổ, viện Listing 1 của
# GraphCompliance (`"context": null` hợp lệ khi không áp dụng). Đo lại trên cả 9
# meta-CU thật thì **9/9 không có bên bị ràng buộc** — kể cả cái duy nhất có điền
# (TT40 Đ26 k2), vì nó điền *"Quy định tại khoản 1 Điều này"*, một **tập quy phạm**.
# Nên ô đó không phải "trống hợp lệ", nó **không tồn tại**. Kiểu dữ liệu nói điều ấy
# rõ hơn mọi giá trị `null`.


def _llm_khong_subject(units) -> dict:
    uid = next(u.uid for u in units if u.uid > 0)
    return {"subject": {"units": []}, "action": {"units": [uid]}, "logic": "unknown",
            "conditions": []}


def _gate(kind: str):
    from app.ontology.schema import Gate

    return Gate(kind=kind, pham_vi="van_ban", suy_ra_duoc=True)


def test_meta_cu_khong_co_o_chu_the_de_ma_trong(index):
    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    cu = build_cu(_llm_khong_subject(units), k, dieu, units,
                  role="meta_cu", gates=[_gate("thoi_gian")])
    assert isinstance(cu, MetaCU)
    assert "subject" not in cu.model_dump()
    assert cu.ok, cu.errors  # KHÔNG phải lỗi mất provenance
    assert cu.menh_de.text  # mệnh đề thì vẫn bắt buộc — "có hiệu lực thi hành"


def test_subject_mo_hinh_lo_khai_duoc_GOP_vao_menh_de_chu_khong_bi_vut(index):
    """Case thật TT40 Đ26 k2: hai span **liền kề**, ghép lại mới ra trọn mệnh đề.

    `subject` = *"Quy định tại khoản 1 Điều này"* [346,375], `action` = *"không áp
    dụng đối với"* [376,397]. Vứt vế đầu là mất nửa câu — và đó chính là vế mang
    viện dẫn mà `gates.targets` được suy ra từ đó.
    """
    from app.ontology.schema import Gate

    dieu = _dieu(index, "TT40-2024-dieu26.txt")
    k = dieu.khoan[1]
    units = segment(dieu, k)
    uid = next(u.uid for u in units if u.uid > 0)
    data = {"subject": {"units": [uid]}, "action": {"units": [uid]},
            "logic": "any", "conditions": []}
    cu = build_cu(data, k, dieu, units, role="meta_cu",
                  gates=[Gate(kind="chu_the", pham_vi="khoan")])
    assert "Quy định tại khoản 1 Điều này" in cu.menh_de.text
    assert "không áp dụng" in cu.menh_de.text
    assert any("gộp đơn vị" in w for w in cu.warnings)


def test_cong_chu_the_neu_can_ten_vai_thi_CHUA_CO_CHO_LUU(index):
    """Giới hạn đã biết, ghi ra để không ai tưởng là đã xử lý.

    Lý lẽ cũ giữ `subject` cho cổng `chu_the` là *"role qualification có một vai cần
    định danh"* — nhưng đó là ví dụ giả định. Cổng `chu_the` DUY NHẤT trong corpus
    (TT40 Đ26 k2) không nêu vai nào cả, nó nêu **quy định**. Nên `MetaCU` không dựng
    ô riêng cho tên vai: đúng kỷ luật đã áp cho `lanh_tho` — 0 case thì không dựng
    trường. Gặp case thật thì thêm một trường là xong.
    """
    from app.ontology.schema import Gate

    dieu = _dieu(index, "TT40-2024-dieu26.txt")
    k = dieu.khoan[1]
    units = segment(dieu, k)
    cu = build_cu(_llm_khong_subject(units), k, dieu, units,
                  role="meta_cu", gates=[Gate(kind="chu_the", pham_vi="khoan")])
    assert isinstance(cu, MetaCU)
    assert not any(f.startswith("chu_the") for f in cu.model_dump())


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


def test_uid_sai_van_la_mat_provenance_ke_ca_o_meta(index):
    """Vắng mặt CẤU TRÚC khác vắng mặt do TRÍCH HỎNG — tách kiểu không xoá ranh giới đó."""
    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    data = _llm_khong_subject(units)
    data["action"] = {"units": [999]}  # khai có, nhưng đơn vị không tồn tại
    cu = build_cu(data, k, dieu, units, role="meta_cu", gates=[_gate("thoi_gian")])
    assert any("mất provenance" in e for e in cu.errors)
    assert not cu.ok


def test_actor_cu_mang_cong_la_LOI_LAP_TRINH_chu_khong_phai_canh_bao(index):
    """Trước đây `build_cu` âm thầm bỏ `gates` của actor-CU kèm một cảnh báo.

    Nay `ActorCU` **không có** ô đó, nên truyền vào là sai ở chỗ gọi — phải nổ ngay
    thay vì trôi xuống một bản ghi trông hợp lệ.
    """
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    k = dieu.khoan[1]
    units = segment(dieu, k)
    with pytest.raises(ValueError, match="không được mang cổng"):
        build_cu(_llm_toi_thieu(units), k, dieu, units, gates=[_gate("thoi_gian")])


def test_prompt_bao_mo_hinh_bo_trong_subject(index):
    from app.ontology.extractor import build_prompt

    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    p_mien = build_prompt(k, dieu, units, role="meta_cu", gates=[_gate("thoi_gian")])
    p_thuong = build_prompt(k, dieu, units)
    assert '"units": []' in p_mien
    assert '"units": []' not in p_thuong


def test_bao_cao_neo_khong_con_dong_subject_gia(index):
    """Bản trước phải in dòng `subject: khong_ap_dung` vì ô đó tồn tại trong kiểu.

    Nay nó không tồn tại, nên in một dòng trống chỉ tổ gợi lại đúng câu hỏi vừa dọn.
    """
    from app.ontology.extractor import grounding_report

    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    cu = build_cu(_llm_khong_subject(units), k, dieu, units,
                  role="meta_cu", gates=[_gate("thoi_gian")])
    rows = grounding_report(cu)
    assert rows[0]["field"] == "menh_de"
    assert not any(r["field"] == "subject" for r in rows)


def test_trang_kiem_meta_hien_menh_de_khong_hien_subject(index):
    from app.ontology.report import render

    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    from app.ontology.schema import DieuKienCong

    cu = build_cu(
        _llm_khong_subject(units), k, dieu, units, role="meta_cu",
        gates=[_gate("thoi_gian")],
        dieu_kien_cong=DieuKienCong(kind="thoi_gian", ngay="2024-07-01"),
    )
    html = render(cu, dieu)
    assert "<td>menh_de</td>" in html
    assert "<td>subject</td>" not in html
    # Nhưng `conditions` thì VẪN tồn tại trong `MetaCU`, nên ô rỗng của nó vẫn phải
    # thấy được — hai loại "trống" khác nhau, không được gộp.
    assert "không áp dụng" in html


def test_co_tiet_bat_co_references_hep_hon(index):
    """TT17 Đ16 không có viện dẫn tới tiết; dùng chuỗi tự dựng để kiểm cờ."""
    from app.ontology.citation import parse_citations

    refs = parse_citations("quy định tại điểm b(i) khoản này")
    assert refs and refs[0].co_tiet
