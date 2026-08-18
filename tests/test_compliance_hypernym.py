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


class _Premise:
    def __init__(self, alias, raw_text):
        self.alias = alias
        self.raw_text = raw_text


def test_premise_alias_mang_theo_dinh_nghia():
    # Ca thật 18/08: "Ngân hàng" map bậy sang ĐVCNT (0.9) vì alias được embed
    # TRẦN — premise.jsonl có sẵn raw_text định nghĩa mà tu_policy_graph vứt đi.
    # Alias phải được embed kèm định nghĩa (bỏ số thứ tự khoản đầu chuỗi).
    pg = _PG()
    pg.premise = [_Premise("ĐVCNT", "21. Đơn vị chấp nhận thẻ (viết tắt là ĐVCNT) "
                                    "là đơn vị chấp nhận thanh toán…")]
    nhan: list[str] = []

    def _embed(ts):
        nhan.extend(ts)
        return [[1.0, 0.0] for _ in ts]

    TuVungLuat.tu_policy_graph(pg, embed=_embed)
    assert "ĐVCNT: Đơn vị chấp nhận thẻ (viết tắt là ĐVCNT) là đơn vị chấp nhận " \
           "thanh toán…" in nhan


def test_alias_tu_corpus_bat_mau_goi_tat_va_dedupe():
    from types import SimpleNamespace

    from app.compliance.hypernym import alias_tu_corpus
    art1 = SimpleNamespace(text=(
        "1. Tổ chức cung ứng dịch vụ thanh toán bao gồm:\n"
        "a) Ngân hàng Nhà nước Việt Nam (sau đây gọi tắt là Ngân hàng Nhà nước);\n"
        "b) Ngân hàng thương mại."))
    art2 = SimpleNamespace(text=(
        "Xây dựng bộ tiêu chí nhận diện dấu hiệu nghi ngờ gian lận, lừa đảo, "
        "vi phạm pháp luật (sau đây gọi tắt là Bộ tiêu chí) trên cơ sở tham khảo."))
    art3 = SimpleNamespace(text="Nhắc lại (sau đây gọi tắt là Bộ tiêu chí) lần nữa.")
    docs = [SimpleNamespace(articles=[art1, art2]), SimpleNamespace(articles=[art3])]

    ra = alias_tu_corpus(docs)

    assert ("Ngân hàng Nhà nước", "Ngân hàng Nhà nước Việt Nam", True) in ra
    bo = [r for r in ra if r[0] == "Bộ tiêu chí"]
    assert len(bo) == 1                       # dedupe giữa các văn bản
    assert "gian lận" in bo[0][1]             # dạng đầy đủ lấy từ ngữ cảnh đứng trước


def test_tu_policy_graph_gop_them_khong_trung():
    pg = _PG()
    pg.premise = [_Premise("ĐVCNT", "Đơn vị chấp nhận thẻ…")]
    nhan: list[str] = []

    def _embed(ts):
        nhan.extend(ts)
        return [[1.0, 0.0] for _ in ts]

    TuVungLuat.tu_policy_graph(pg, embed=_embed, them=[
        ("đvcnt", "trùng alias premise, phải bỏ", True),
        ("Bộ tiêu chí", "bộ tiêu chí nhận diện gian lận", True),
    ])
    assert "Bộ tiêu chí: bộ tiêu chí nhận diện gian lận" in nhan
    assert not any("phải bỏ" in t for t in nhan)


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
