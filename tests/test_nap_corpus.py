"""Bộ nạp corpus: thay/thêm văn bản, cạnh đủ hai đầu, lặp lại không nhân đôi. Offline."""
from __future__ import annotations

from app.core.schemas import Article, CorpusDocument
from app.ingestion.nap_corpus import CANH_MOI, GHI_DE_CO_CAN_CU, nap, tron_canh, tron_van_ban
from app.ingestion.vbpl_corpus import KetQuaDoc


def _vb(doc_id="TT99-2020", so_hieu="99/2020/TT-NHNN", **doi) -> CorpusDocument:
    goc = dict(
        doc_id=doc_id, title="Thử", doc_type="Thông tư", source="external",
        valid_from="2020-01-01", so_hieu=so_hieu,
        articles=[Article(article="Điều 1", text="Phạm vi điều chỉnh\nNội dung.")],
    )
    return CorpusDocument(**{**goc, **doi})


def _corpus(**doi) -> dict:
    return {"documents": [], "relationships": [], **doi}


def test_them_moi_va_thay_giu_ngay_corpus():
    corpus = _corpus()
    nk = tron_van_ban(corpus, _vb())
    assert len(corpus["documents"]) == 1 and nk == ["thêm TT99-2020: 1 điều"]

    # vbpl nói ngày khác (ca ND52: thuộc tính ghi 2027, Điều 37 của chính nó ghi 2024)
    nk = tron_van_ban(corpus, _vb(valid_from="2027-07-01",
                                  articles=[Article(article="Điều 1", text="Mới."),
                                            Article(article="Điều 2", text="Thêm.")]))
    assert len(corpus["documents"]) == 1, "thay chứ không nhân đôi"
    assert corpus["documents"][0]["valid_from"] == "2020-01-01", "ngày corpus thắng"
    assert len(corpus["documents"][0]["articles"]) == 2, "articles lấy bản mới"
    assert any("GIỮ corpus" in d for d in nk)


def test_canh_thieu_dau_mut_thi_BO_co_noi_ly_do():
    """Cạnh nửa vời đẩy xuống Neo4j bị `MATCH…MATCH` nuốt im lặng — chặn từ ngoài file."""
    corpus = _corpus(documents=[_vb().model_dump()])
    canh = {"source_doc": "TT99-2020", "target_doc": "KHONG-CO", "rel_type": "CAN_CU"}
    nk = tron_canh(corpus, canh)
    assert corpus["relationships"] == []
    assert nk and "BỎ cạnh" in nk[0] and "KHONG-CO" in nk[0]


def test_canh_khong_nhan_doi_khi_nap_lai():
    corpus = _corpus(documents=[_vb().model_dump(), _vb("ND1-2020", "1/2020/NĐ-CP").model_dump()])
    canh = {"source_doc": "TT99-2020", "target_doc": "ND1-2020", "rel_type": "CAN_CU"}
    assert tron_canh(corpus, canh) != []
    assert tron_canh(corpus, dict(canh)) == []
    assert len(corpus["relationships"]) == 1


def test_nap_ap_ghi_de_co_can_cu_va_bo_qua_node_rong():
    corpus = _corpus()
    ket_qua = [
        KetQuaDoc(duong_dan="x.json", so_hieu="80/2016/NĐ-CP", van_ban=_vb("ND80-2016", "80/2016/NĐ-CP")),
        KetQuaDoc(duong_dan="y.json", so_hieu="29/VBHN-NHNN", canh_bao=["0 điều — không có toàn văn"]),
    ]
    nk = nap(corpus, ket_qua)
    nd80 = next(d for d in corpus["documents"] if d["doc_id"] == "ND80-2016")
    assert nd80["valid_to"] == GHI_DE_CO_CAN_CU["ND80-2016"]["valid_to"]
    assert any("ghi đè ND80-2016" in d for d in nk)
    assert any(d.startswith("bỏ qua 29/VBHN-NHNN") for d in nk), "node rỗng không vào corpus"
    assert len(corpus["documents"]) == 1


def test_moi_muc_ghi_de_deu_co_can_cu():
    assert all("can_cu" in gd and gd["can_cu"].strip() for gd in GHI_DE_CO_CAN_CU.values())


def test_moi_canh_moi_deu_co_note_va_ten_hop_le():
    from app.core.schemas import REL_TYPES

    for c in CANH_MOI:
        assert c["rel_type"] in REL_TYPES, c
        assert c.get("note", "").strip(), f"cạnh không bằng chứng: {c}"
