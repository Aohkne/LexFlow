"""Ghép thuộc tính bản crawl vbpl.vn vào corpus canonical."""
from __future__ import annotations

import json

import pytest

from scripts.enrich_corpus_from_vbpl import enrich, enrich_thu_muc


def _corpus() -> dict:
    return {
        "documents": [
            {
                "doc_id": "TT40-2024",
                "title": "Thông tư 40/2024/TT-NHNN",
                "doc_type": "Thông tư",
                "source": "external",
                "valid_from": "2024-07-17",
                "so_hieu": "40/2024/TT-NHNN",
                "articles": [{"article": "Điều 1", "text": "…đã curate tay…"}],
            },
            {
                "doc_id": "SHB-QD-VI-2023",
                "title": "Quy định nội bộ",
                "doc_type": "Nội bộ",
                "source": "internal",
                "articles": [],
            },
        ],
        "relationships": [],
    }


def _crawled(doc_id: str = "TT40-2024") -> dict:
    return {
        "doc_id": doc_id,
        "title": "Thông tư 40/2024/TT-NHNN của Ngân hàng Nhà nước Việt Nam",
        "valid_from": "2027-07-01",  # nguồn có chỗ sai — không được chép sang
        "so_hieu": "40/2024/TT-NHNN",
        "co_quan_ban_hanh": "Ngân hàng Nhà nước Việt Nam",
        "nguoi_ky": "Phạm Tiến Dũng",
        "chuc_danh": "Phó Thống đốc",
        "linh_vuc": "",  # rỗng ⇒ bỏ qua, không ghi None đè
        "ngay_ban_hanh": "2024-07-17",
        "tinh_trang_hieu_luc": "Hết hiệu lực một phần",
        "source_url": "https://vbpl.vn/van-ban/chi-tiet/thong-tu-so-40-2024-tt-nhnn--168578",
        "provisions": [{"cap": "dieu", "so": "1", "tieu_de": "Phạm vi", "con": []}],
        "source_files": [
            {"ten": "TT40.pdf", "kich_thuoc": "4.89MB", "url": "https://…/download"}
        ],
        "articles": [{"article": "Điều 1", "text": "…bản crawl thô…"}],
    }


def test_chep_thuoc_tinh_va_file_goc_khong_dung_toan_van() -> None:
    corpus = _corpus()
    changed = enrich(corpus, _crawled(), "TT40-2024")

    doc = corpus["documents"][0]
    assert doc["co_quan_ban_hanh"] == "Ngân hàng Nhà nước Việt Nam"
    assert doc["nguoi_ky"] == "Phạm Tiến Dũng"
    assert doc["tinh_trang_hieu_luc"] == "Hết hiệu lực một phần"
    assert [f["ten"] for f in doc["source_files"]] == ["TT40.pdf"]
    assert changed["source_files"] == "1 file gốc"
    assert changed["provisions"] == "1 nút gốc"

    # articles / title / hiệu lực là bản curate tay — bản crawl không được đụng vào
    assert doc["title"] == "Thông tư 40/2024/TT-NHNN"
    assert doc["valid_from"] == "2024-07-17"
    assert doc["articles"] == [{"article": "Điều 1", "text": "…đã curate tay…"}]
    assert "linh_vuc" not in doc  # trường rỗng bên crawl thì giữ nguyên trạng thái thiếu


def test_doc_id_khong_co_trong_corpus_thi_dung_han() -> None:
    with pytest.raises(SystemExit, match="TT99-2099"):
        enrich(_corpus(), _crawled("TT99-2099"), "TT99-2099")


def test_ghep_ca_thu_muc_bo_qua_ban_crawl_ngoai_corpus(tmp_path) -> None:
    (tmp_path / "tt40.json").write_text(
        json.dumps(_crawled(), ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "vbhn.json").write_text(
        json.dumps(_crawled("VBHN08-NHNN"), ensure_ascii=False), encoding="utf-8"
    )

    corpus = _corpus()
    thay_doi, ngoai_corpus = enrich_thu_muc(corpus, tmp_path)

    assert set(thay_doi) == {"TT40-2024"}
    assert ngoai_corpus == ["VBHN08-NHNN"]
    assert corpus["documents"][0]["nguoi_ky"] == "Phạm Tiến Dũng"
    # văn bản nội bộ không có bản crawl ⇒ không bị chạm tới
    assert corpus["documents"][1] == _corpus()["documents"][1]


def test_ghep_lai_lan_hai_khong_bao_thay_doi(tmp_path) -> None:
    (tmp_path / "tt40.json").write_text(
        json.dumps(_crawled(), ensure_ascii=False), encoding="utf-8"
    )
    corpus = _corpus()
    enrich_thu_muc(corpus, tmp_path)
    thay_doi, _ = enrich_thu_muc(corpus, tmp_path)
    assert thay_doi == {}
