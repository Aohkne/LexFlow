"""Judge CU plan: self-consistency 2+1 theo từng CU, vi_pham → thử override mien_tru."""
from app.compliance import judge as judge_mod
from app.compliance.gate import CUPlan, PlanItem
from app.compliance.judge import phan_dinh
from app.compliance.policy_graph import PolicyGraph
from app.ontology.schema import ActorCU, KhaiNiem
from tests.test_compliance_policy_graph import _actor

_CU_ID = "A/1#than/dieu_5#khoan_1"


def _plan_mot_cu() -> CUPlan:
    cu = ActorCU.model_validate(_actor(_CU_ID))
    return CUPlan(items=[PlanItem(cu=cu, ly_do="test")], ghi_chu=[])


def _pg_rong() -> PolicyGraph:
    return PolicyGraph([], [], [])


def _pg_co_mien_tru() -> PolicyGraph:
    cu = ActorCU.model_validate(_actor(_CU_ID, refs=["A/1#than/dieu_6"]))
    mien_tru = ActorCU.model_validate(_actor("A/1#than/dieu_6#khoan_1", modality="mien_tru"))
    return PolicyGraph([cu, mien_tru], [], [])


def test_quote_null_khong_lam_vo_phan_quyet():
    # LLM trả key CÓ MẶT nhưng null — .get(key, "") không đỡ được (vỡ thật lúc
    # chạy ThuHo 16/08, giữa chừng ~30 lượt LLM đã tốn).
    recs = [{"verdict": "tuan_thu", "can_cu": None, "quote_hop_dong": None,
             "quote_luat": None}] * 2
    pq = judge_mod._da_so(_CU_ID, recs)
    assert pq.verdict == "tuan_thu" and pq.quote_hop_dong == ""


def test_llm_bo_sot_cu_thanh_thieu_thong_tin():
    # LLM không nhắc gì tới CU trong cả các phiếu → abstention, không suy từ im lặng.
    # Nhánh này đã chạy thật ở Task 14 (ThuHo/PAYFAC) mà chưa có test.
    pq = judge_mod._da_so(_CU_ID, [None, None])
    assert pq.verdict == "thieu_thong_tin"
    assert "bỏ sót" in pq.can_cu


def _vote(verdict):
    return {"phan_quyet": [{"cu_id": "A/1#than/dieu_5#khoan_1", "verdict": verdict,
                            "can_cu": "x", "quote_hop_dong": "", "quote_luat": ""}]}


def test_dong_thuan_hai_phieu(monkeypatch):
    calls = []
    monkeypatch.setattr(judge_mod, "chat_json",
                        lambda *a, **k: calls.append(1) or _vote("tuan_thu"))
    ra = phan_dinh("text", _plan_mot_cu(), _pg_rong())
    assert ra[0].verdict == "tuan_thu" and len(calls) == 2  # không cần phiếu 3


def test_bat_dong_lay_da_so(monkeypatch):
    votes = iter([_vote("vi_pham"), _vote("tuan_thu"), _vote("tuan_thu")])
    monkeypatch.setattr(judge_mod, "chat_json", lambda *a, **k: next(votes))
    assert phan_dinh("text", _plan_mot_cu(), _pg_rong())[0].verdict == "tuan_thu"


def test_vi_pham_co_mien_tru_thi_lat(monkeypatch):
    votes = iter([_vote("vi_pham"), _vote("vi_pham"),
                  {"ap_dung": True, "ly_do": "được miễn theo Điều 6"}])
    monkeypatch.setattr(judge_mod, "chat_json", lambda *a, **k: next(votes))
    ra = phan_dinh("text", _plan_mot_cu(), _pg_co_mien_tru())
    assert ra[0].verdict == "tuan_thu" and "Điều 6" in ra[0].override


def test_verdict_la_khong_hop_le_ve_thieu_thong_tin(monkeypatch):
    monkeypatch.setattr(judge_mod, "chat_json", lambda *a, **k: _vote("xyz"))
    assert phan_dinh("text", _plan_mot_cu(), _pg_rong())[0].verdict == "thieu_thong_tin"


_KN_ID = "A/1#than/dieu_3#khoan_2"


def _kn():
    return KhaiNiem(id=_KN_ID, thuat_ngu="Ví điện tử", dinh_nghia="Ví điện tử là…",
                    char_span_thuat_ngu=None, char_span_dinh_nghia=None)


def test_dinh_nghia_vao_prompt_va_co_verdict(monkeypatch):
    # Plan KHÔNG có actor-CU nhưng có định nghĩa (ca điều "Giải thích từ ngữ" của
    # hợp đồng — miss #13/#35): judge vẫn chạy, verdict mang id khái niệm.
    prompts = []

    def _fake(prompt, **_k):
        prompts.append(prompt)
        return {"phan_quyet": [{"cu_id": _KN_ID, "verdict": "vi_pham",
                                "can_cu": "định nghĩa lệch", "quote_hop_dong": "",
                                "quote_luat": ""}]}

    monkeypatch.setattr(judge_mod, "chat_json", _fake)
    plan = CUPlan(items=[], ghi_chu=[], dinh_nghia=[_kn()])
    ra = phan_dinh("Ví điện tử nghĩa là tài khoản nội bộ.", plan, _pg_rong())

    assert [r.cu_id for r in ra] == [_KN_ID]
    assert ra[0].verdict == "vi_pham"  # closure rỗng → override tự no-op
    assert "thuật ngữ=Ví điện tử" in prompts[0]
