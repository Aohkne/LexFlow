"""Compliance Gate: retrieval → CU ứng viên → meta-CU chặn → CU plan. Tất định."""
from app.compliance import gate
from app.compliance.gate import lap_cu_plan
from app.compliance.hypernym import DeXuat
from app.compliance.policy_graph import PolicyGraph
from app.ontology.schema import ActorCU, MetaCU
from tests.test_compliance_policy_graph import _actor, _field


def _meta(id, gates, dieu_kien_cong=None):
    return {
        "type": "meta_cu", "id": id, "references": [], "references_hep_hon": False,
        "warnings": [], "errors": [], "gates": gates, "dieu_kien_cong": dieu_kien_cong,
        "menh_de": _field("có hiệu lực thi hành"), "logic": "all", "conditions": [],
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
