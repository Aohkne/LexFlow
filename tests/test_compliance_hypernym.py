"""Hypernym mapping: cosine trên KhaiNiem + LLM xác nhận, dưới ngưỡng thì thôi."""
from app.compliance import hypernym
from app.compliance.hypernym import TuVungLuat, map_hypernym


class _PG:
    class _KN:
        def __init__(self, t):
            self.thuat_ngu = t
            self.dinh_nghia = f"định nghĩa {t}"

    khai_niem = [_KN("dịch vụ cổng thanh toán điện tử"), _KN("đại lý thanh toán")]
    premise = []


def _tv():
    # embed fake: từ đầu tiên quyết định vector
    vecs = {"dịch": [1.0, 0.0], "đại": [0.0, 1.0]}
    return TuVungLuat.tu_policy_graph(
        _PG(), embed=lambda ts: [vecs[t.split()[0]] for t in ts])


def test_map_qua_nguong(monkeypatch):
    monkeypatch.setattr(hypernym, "embed_query", lambda t: [1.0, 0.0])
    monkeypatch.setattr(hypernym, "chat_json", lambda *a, **k: {
        "hypernym": "dịch vụ cổng thanh toán điện tử", "do_tin": 0.9})
    ra = map_hypernym(["cổng thanh toán PAYX"], _tv())
    assert ra["cổng thanh toán PAYX"].hypernym == "dịch vụ cổng thanh toán điện tử"


def test_duoi_nguong_khong_ep(monkeypatch):
    monkeypatch.setattr(hypernym, "embed_query", lambda t: [1.0, 0.0])
    monkeypatch.setattr(hypernym, "chat_json", lambda *a, **k: {
        "hypernym": "dịch vụ cổng thanh toán điện tử", "do_tin": 0.2})
    assert map_hypernym(["thuật ngữ lạ"], _tv())["thuật ngữ lạ"] is None


def test_hypernym_ngoai_ung_vien_bi_bo(monkeypatch):
    monkeypatch.setattr(hypernym, "embed_query", lambda t: [1.0, 0.0])
    monkeypatch.setattr(hypernym, "chat_json", lambda *a, **k: {
        "hypernym": "thuật ngữ LLM bịa", "do_tin": 0.99})
    assert map_hypernym(["x"], _tv())["x"] is None
