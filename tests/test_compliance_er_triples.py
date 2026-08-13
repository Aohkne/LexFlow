"""ER-triple S-A-O từ điều hợp đồng; entity phải nằm nguyên văn trong text."""
from app.compliance import er_triples


def test_giu_triple_hop_le_bo_triple_bia(monkeypatch):
    monkeypatch.setattr(er_triples, "chat_json", lambda *a, **k: {"triples": [
        {"chu_the": "Bên B", "hanh_vi": "thanh toán", "doi_tuong": "phí dịch vụ"},
        {"chu_the": "Ngân hàng Nhà nước", "hanh_vi": "cấp", "doi_tuong": "Giấy phép"},
    ]})
    triples, canh_bao = er_triples.trich_triples(
        "Bên B thanh toán phí dịch vụ trong 05 ngày.")
    assert [t.chu_the for t in triples] == ["Bên B"]  # NHNN không có trong text → bỏ
    assert len(canh_bao) == 1 and "không nằm trong" in canh_bao[0]


def test_bo_triple_entity_rong(monkeypatch):
    # "" là substring của mọi text — không chặn thì entity rỗng xuống tới embed.
    monkeypatch.setattr(er_triples, "chat_json", lambda *a, **k: {"triples": [
        {"chu_the": "", "hanh_vi": "thanh toán", "doi_tuong": "phí dịch vụ"},
        {"chu_the": "Bên B", "hanh_vi": "trả", "doi_tuong": "   "},
    ]})
    triples, canh_bao = er_triples.trich_triples("Bên B thanh toán phí dịch vụ.")
    assert triples == [] and len(canh_bao) == 2


def test_json_hong_tra_rong(monkeypatch):
    monkeypatch.setattr(er_triples, "chat_json", lambda *a, **k: {"sai": 1})
    triples, canh_bao = er_triples.trich_triples("Bên A cung cấp dịch vụ.")
    assert triples == [] and canh_bao == []
