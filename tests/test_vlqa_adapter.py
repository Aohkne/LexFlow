"""Adapter VLQA (T117) — aid round-trip + chuyển đổi corpus. Thuần hàm, không mạng."""
import json

from eval.vlqa_adapter import aid_toi_da, aid_tu_chunk, nap_corpus


def test_aid_round_trip_qua_nhan_da_che():
    # _split_khoan giữ article làm tiền tố → aid recover được cả khi chunk bị chẻ
    assert aid_tu_chunk({"article": "0"}) == 0
    assert aid_tu_chunk({"article": "53877"}) == 53877
    assert aid_tu_chunk({"article": "12 Khoản 1-3"}) == 12
    assert aid_tu_chunk({"article": "7 (phần 2)"}) == 7


def test_aid_khong_hop_le_tra_none():
    assert aid_tu_chunk({"article": ""}) is None
    assert aid_tu_chunk({"article": "Điều 5"}) is None  # nhãn LexFlow, không phải aid VLQA
    assert aid_tu_chunk({}) is None


def test_nap_corpus_giu_aid_va_bo_doc_rong(tmp_path):
    corpus = [
        {"id": 0, "law_id": "14/2022/TT-NHNN", "content": [
            {"aid": 0, "content_Article": "Nội dung điều 0."},
            {"aid": 1, "content_Article": "Nội dung điều 1."},
        ]},
        {"id": 1, "law_id": "99/2099/QH", "content": []},  # doc rỗng → phải bỏ
        {"id": 2, "law_id": "52/2014/QH13", "content": [
            {"aid": 2, "content_Article": "Nội dung điều 2."},
        ]},
    ]
    p = tmp_path / "legal_corpus.json"
    p.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")

    docs = nap_corpus(p)
    assert [d.doc_id for d in docs] == ["VLQA-0", "VLQA-2"]  # doc rỗng bị loại
    assert docs[0].articles[0].article == "0"  # aid vào nhãn
    assert docs[0].articles[1].article == "1"
    assert docs[0].title == "14/2022/TT-NHNN"
    assert aid_toi_da(docs) == 2


def test_gioi_han_lay_n_doc_dau(tmp_path):
    corpus = [{"id": i, "law_id": f"{i}/2020", "content": [
        {"aid": i, "content_Article": f"điều {i}"}]} for i in range(5)]
    p = tmp_path / "c.json"
    p.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    assert [d.doc_id for d in nap_corpus(p, gioi_han=2)] == ["VLQA-0", "VLQA-1"]
