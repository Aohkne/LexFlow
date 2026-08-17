"""Compliance Gate: retrieval → CU ứng viên → meta-CU chặn → CU plan. Tất định."""
from app.compliance import gate
from app.compliance.gate import lap_cu_plan, lap_plan_toan_van
from app.compliance.hypernym import DeXuat
from app.compliance.policy_graph import PolicyGraph
from app.ontology.schema import ActorCU, MetaCU
from tests.test_compliance_policy_graph import _actor, _field


def _meta(id, gates, dieu_kien_cong=None, conditions=()):
    return {
        "type": "meta_cu", "id": id, "references": [], "references_hep_hon": False,
        "warnings": [], "errors": [], "gates": gates, "dieu_kien_cong": dieu_kien_cong,
        "menh_de": _field("có hiệu lực thi hành"), "logic": "any", "conditions": list(conditions),
    }


def _condition(text, object_label="", constraint_label=""):
    return {
        "source_diem": None, "text": text, "object_label": object_label,
        "constraint_label": constraint_label,
        "grounding": {"units": [1], "char_span": [0, len(text)], "status": "unit", "quote": ""},
        "logic": "unknown", "sub": [], "ap_dung_khi": None, "guard_phan_hoach": None, "issues": [],
    }


def _pg(cu_dicts):
    cu = [
        ActorCU.model_validate(d) if d["type"] == "actor_cu" else MetaCU.model_validate(d)
        for d in cu_dicts
    ]
    return PolicyGraph(cu, [], [])


_CHUNK_DIEU_5 = {"id": "DOC-A::Điều 5", "doc_id": "DOC-A", "article": "Điều 5",
                 "doc_title": "A", "text": "…", "valid_from": "", "valid_to": ""}


def _pg_voi_cong_thoi_gian():
    return _pg([
        _actor("A/1#than/dieu_5#khoan_1"),
        _meta("A/1#than/dieu_5#khoan_2", gates=[{
            "kind": "thoi_gian", "pham_vi": "dieu", "targets": ["A/1#than/dieu_5"],
            "suy_ra_duoc": True, "phu_dinh": False, "ngoai_tru": [], "ghi_chu": "",
        }], dieu_kien_cong={"kind": "thoi_gian", "ngay": "2027-01-01", "moc": "bat_dau"}),
    ])


def test_chan_theo_moc_ngay_chua_hieu_luc(monkeypatch):
    monkeypatch.setattr(gate, "search_in_docs", lambda *a, **k: [_CHUNK_DIEU_5])
    monkeypatch.setattr(gate, "chu_thich_ket_qua", lambda c, *a, **k: (c, {}))
    plan = lap_cu_plan("điều hợp đồng", [], _pg_voi_cong_thoi_gian(),
                        ["DOC-A"], as_of="2026-08-11", so_hieu_cua={"DOC-A": "A/1"})
    # mốc bắt đầu 2027 > as_of 2026 → CU Điều 5 bị chặn, ghi chú nêu lý do
    assert plan.items == []
    assert any("2027-01-01" in g for g in plan.ghi_chu)


def _pg_voi_cong_lanh_tho():
    return _pg([
        _actor("A/1#than/dieu_5#khoan_1"),
        _meta("A/1#than/dieu_5#khoan_2", gates=[{
            "kind": "lanh_tho", "pham_vi": "dieu", "targets": ["A/1#than/dieu_5"],
            "suy_ra_duoc": True, "phu_dinh": False, "ngoai_tru": [], "ghi_chu": "",
        }]),
    ])


def test_gate_khong_xac_quyet_thi_fail_open(monkeypatch):
    # meta-CU cổng lanh_tho (không đánh giá được) → CU vẫn vào plan + cờ
    monkeypatch.setattr(gate, "search_in_docs", lambda *a, **k: [_CHUNK_DIEU_5])
    monkeypatch.setattr(gate, "chu_thich_ket_qua", lambda c, *a, **k: (c, {}))
    plan = lap_cu_plan("điều hợp đồng", [], _pg_voi_cong_lanh_tho(),
                        ["DOC-A"], as_of="2026-08-11", so_hieu_cua={"DOC-A": "A/1"})
    assert len(plan.items) == 1
    assert plan.items[0].gate_chua_xac_quyet is True
    assert any("lanh_tho" in g for g in plan.ghi_chu)


def _pg_voi_cong_chu_the_phu_dinh():
    # Mẫu thật TT40 Đ26 k2 (pred.jsonl): targets của gate là KHOÁ NODE bị chặn
    # ("…#khoan_1"), KHÔNG phải tên chủ thể — tên chủ thể bị loại trừ nằm ở
    # conditions[], do mệnh đề "…không áp dụng đối với:" liệt kê ở các Điểm con.
    return _pg([
        _actor("A/1#than/dieu_5#khoan_1"),
        _meta("A/1#than/dieu_5#khoan_2", gates=[{
            "kind": "chu_the", "pham_vi": "khoan", "targets": ["A/1#than/dieu_5#khoan_1"],
            "suy_ra_duoc": True, "phu_dinh": True, "ngoai_tru": [], "ghi_chu": "",
        }], conditions=[_condition(
            "a) Đại lý thanh toán;",
            object_label="Đại lý thanh toán", constraint_label="Đại lý thanh toán",
        )]),
    ])


def test_chu_the_phu_dinh_loai_theo_dieu_kien(monkeypatch):
    # party khớp hypernym của chủ thể bị phủ định (trong conditions[], không phải
    # gate.targets) → actor-CU trong phạm vi gate bị loại.
    monkeypatch.setattr(gate, "search_in_docs", lambda *a, **k: [_CHUNK_DIEU_5])
    monkeypatch.setattr(gate, "chu_thich_ket_qua", lambda c, *a, **k: (c, {}))
    hypernyms = [DeXuat(entity="X", hypernym="Đại lý thanh toán", do_tin=0.9, manh=True)]
    plan = lap_cu_plan("điều hợp đồng", hypernyms, _pg_voi_cong_chu_the_phu_dinh(),
                        ["DOC-A"], as_of="2026-08-11", so_hieu_cua={"DOC-A": "A/1"})
    assert plan.items == []
    assert any("phủ định" in g for g in plan.ghi_chu)


def test_chu_the_khang_dinh_fail_open(monkeypatch):
    # Cổng chủ thể KHẲNG ĐỊNH (phu_dinh=False) chưa đánh giá tất định được →
    # giữ CU + cờ + ghi chú (trước đây rơi qua `return` trần, im lặng).
    monkeypatch.setattr(gate, "search_in_docs", lambda *a, **k: [_CHUNK_DIEU_5])
    monkeypatch.setattr(gate, "chu_thich_ket_qua", lambda c, *a, **k: (c, {}))
    pg = _pg([
        _actor("A/1#than/dieu_5#khoan_1"),
        _meta("A/1#than/dieu_5#khoan_2", gates=[{
            "kind": "chu_the", "pham_vi": "khoan", "targets": ["A/1#than/dieu_5#khoan_1"],
            "suy_ra_duoc": True, "phu_dinh": False, "ngoai_tru": [], "ghi_chu": "",
        }]),
    ])
    plan = lap_cu_plan("điều hợp đồng", [], pg,
                        ["DOC-A"], as_of="2026-08-11", so_hieu_cua={"DOC-A": "A/1"})
    assert len(plan.items) == 1
    assert plan.items[0].gate_chua_xac_quyet is True
    assert any("chu_the khẳng định" in g for g in plan.ghi_chu)


def test_chu_the_phu_dinh_khong_khop_thi_khong_loai(monkeypatch):
    # party KHÔNG phải loại chủ thể bị phủ định → không bị loại
    monkeypatch.setattr(gate, "search_in_docs", lambda *a, **k: [_CHUNK_DIEU_5])
    monkeypatch.setattr(gate, "chu_thich_ket_qua", lambda c, *a, **k: (c, {}))
    hypernyms = [DeXuat(entity="X", hypernym="tổ chức tín dụng", do_tin=0.9, manh=True)]
    plan = lap_cu_plan("điều hợp đồng", hypernyms, _pg_voi_cong_chu_the_phu_dinh(),
                        ["DOC-A"], as_of="2026-08-11", so_hieu_cua={"DOC-A": "A/1"})
    assert len(plan.items) == 1


def test_plan_toan_van_chon_ca_dieu_theo_subject():
    # Điều 8: khoản 1 có subject "Hợp đồng hoặc thỏa thuận" → CẢ điều vào plan
    # (kéo theo khoản 2 dù subject nó không nhắc). Điều 9 chỉ nhắc hợp đồng trong
    # ACTION → không chọn (nghĩa vụ của tổ chức, thuộc gate theo điều). Văn bản
    # ngoài --against bị loại.
    k1 = _actor("A/1#than/dieu_8#khoan_1")
    k1["subject"] = _field("Hợp đồng hoặc thỏa thuận")
    k2 = _actor("A/1#than/dieu_8#khoan_2")
    d9 = _actor("A/1#than/dieu_9#khoan_1")
    d9["action"] = _field("phải có hợp đồng hợp tác với ngân hàng")
    ngoai = _actor("B/2#than/dieu_8#khoan_1")
    ngoai["subject"] = _field("Hợp đồng hoặc thỏa thuận")

    plan = lap_plan_toan_van(_pg([k1, k2, d9, ngoai]), ["A/1"], as_of="2026-08-16")

    assert sorted(i.cu.id for i in plan.items) == [
        "A/1#than/dieu_8#khoan_1", "A/1#than/dieu_8#khoan_2",
    ]
    assert all("CU mức hợp đồng" in i.ly_do for i in plan.items)


def test_plan_toan_van_van_qua_meta_gate():
    # Meta-CU cổng thoi_gian (mốc 2027 chưa tới) chặn cả plan toàn văn — lượt
    # toàn hợp đồng không được nhảy cóc qua tầng meta.
    k1 = _actor("A/1#than/dieu_5#khoan_1")
    k1["subject"] = _field("Hợp đồng hoặc thỏa thuận")
    pg = _pg([k1, _meta("A/1#than/dieu_5#khoan_2", gates=[{
        "kind": "thoi_gian", "pham_vi": "dieu", "targets": ["A/1#than/dieu_5"],
        "suy_ra_duoc": True, "phu_dinh": False, "ngoai_tru": [], "ghi_chu": "",
    }], dieu_kien_cong={"kind": "thoi_gian", "ngay": "2027-01-01", "moc": "bat_dau"})])

    plan = lap_plan_toan_van(pg, ["A/1"], as_of="2026-08-16")

    assert plan.items == []
    assert any("2027-01-01" in g for g in plan.ghi_chu)


def _kn(id, thuat_ngu, dinh_nghia="…"):
    from app.ontology.schema import KhaiNiem
    return KhaiNiem(id=id, thuat_ngu=thuat_ngu, dinh_nghia=dinh_nghia,
                     char_span_thuat_ngu=None, char_span_dinh_nghia=None)


def test_khai_niem_lien_quan_khop_nguyen_van_va_hypernym():
    from app.compliance.gate import khai_niem_lien_quan
    pg = PolicyGraph([], [], [
        _kn("A/1#than/dieu_3#khoan_1", "Ví điện tử"),
        _kn("A/1#than/dieu_3#khoan_2", "Đại lý thanh toán"),
        _kn("A/1#than/dieu_3#khoan_3", "Séc"),   # không nhắc tới → loại
        # thuật ngữ "bẩn" — cả câu, không bao giờ khớp nguyên văn → tự rơi
        _kn("A/1#than/dieu_3#khoan_4", "1. Dịch vụ X bao gồm: a, b, c và mọi thứ khác."),
    ])
    hyp = [DeXuat(entity="bên B", hypernym="Đại lý thanh toán", do_tin=0.9, manh=True)]
    khop, ghi_chu = khai_niem_lien_quan("Khách nạp tiền vào VÍ ĐIỆN TỬ.", hyp, pg)
    assert sorted(k.thuat_ngu for k in khop) == ["Ví điện tử", "Đại lý thanh toán"]
    assert ghi_chu == []


def test_khai_niem_lien_quan_cat_co_ghi_chu():
    from app.compliance.gate import khai_niem_lien_quan
    pg = PolicyGraph([], [], [
        _kn(f"A/1#than/dieu_3#khoan_{i}", f"thuật ngữ {i}") for i in range(1, 6)
    ])
    text = " — ".join(f"thuật ngữ {i}" for i in range(1, 6))
    khop, ghi_chu = khai_niem_lien_quan(text, [], pg, gioi_han=3)
    assert len(khop) == 3
    assert any("khớp 5" in g for g in ghi_chu)


def test_khai_niem_khop_gan_bat_ca_thieu_tu():
    # Tái hiện #13 (phân xử 17/08): hợp đồng gốc viết "dịch vụ cổng thanh toán"
    # thiếu "điện tử" — đường nguyên văn trượt, định nghĩa k18 không bao giờ
    # vào plan, judge không có cơ hội nhìn thấy.
    from app.compliance.gate import khai_niem_lien_quan
    pg = PolicyGraph([], [], [
        _kn("52/2024/NĐ-CP#than/dieu_3#khoan_18", "Dịch vụ cổng thanh toán điện tử"),
        _kn("A/1#than/dieu_3#khoan_1", "Séc"),  # không liên quan → không được khớp oan
    ])
    text = "Bên B cung ứng dịch vụ cổng thanh toán cho Ngân hàng theo Hợp đồng này."
    khop, ghi_chu = khai_niem_lien_quan(text, [], pg)
    assert [k.id for k in khop] == ["52/2024/NĐ-CP#than/dieu_3#khoan_18"]
    assert any("khớp gần" in g and "khoan_18" in g for g in ghi_chu)


def test_khop_gan_khong_ap_cho_thuat_ngu_ngan():
    # Thuật ngữ 3 token mà cho bỏ bớt từ thì "Ví điện tử" khớp mọi chỗ có "ví" —
    # dưới 4 token chỉ được khớp nguyên văn.
    from app.compliance.gate import khai_niem_lien_quan
    pg = PolicyGraph([], [], [_kn("A/1#than/dieu_3#khoan_1", "Ví điện tử")])
    khop, ghi_chu = khai_niem_lien_quan("Khách hàng dùng ví để thanh toán.", [], pg)
    assert khop == [] and ghi_chu == []


def test_khop_nguyen_van_uu_tien_truoc_khop_gan_khi_cat():
    from app.compliance.gate import khai_niem_lien_quan
    pg = PolicyGraph([], [], [
        _kn("A/1#than/dieu_3#khoan_1", "Dịch vụ cổng thanh toán điện tử"),  # khớp gần
        _kn("A/1#than/dieu_3#khoan_2", "Ví điện tử"),  # khớp nguyên văn
    ])
    text = "Nạp tiền vào ví điện tử qua dịch vụ cổng thanh toán."
    khop, _ = khai_niem_lien_quan(text, [], pg, gioi_han=1)
    assert [k.thuat_ngu for k in khop] == ["Ví điện tử"]


def test_subject_khop_hypernym_duoc_them(monkeypatch):
    # retrieval không trả gì, nhưng subject CU chứa "đại lý thanh toán" =
    # hypernym của một entity hợp đồng → vẫn vào plan với ly_do "subject khớp…"
    monkeypatch.setattr(gate, "search_in_docs", lambda *a, **k: [])
    monkeypatch.setattr(gate, "chu_thich_ket_qua", lambda c, *a, **k: (c, {}))
    d = _actor("A/1#than/dieu_9#khoan_1")
    d["subject"] = _field("Đại lý thanh toán ABC")
    pg = _pg([d])
    hypernyms = [DeXuat(entity="ABC Corp", hypernym="đại lý thanh toán",
                         do_tin=0.9, manh=True)]
    plan = lap_cu_plan("điều hợp đồng", hypernyms, pg,
                        ["DOC-A"], as_of="2026-08-11", so_hieu_cua={"DOC-A": "A/1"})
    assert len(plan.items) == 1
    assert "subject khớp" in plan.items[0].ly_do
