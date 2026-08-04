"""Bản ghi vbpl đã crawl → `CorpusDocument`. Offline, đọc `data/raw/vbpl/`.

Điều đáng canh nhất là **đánh số khoản/điểm**, vì mất nó thì cả tầng ontology mất theo mà
**không lỗi nào bắn ra**: `parse_dieu` chỉ trả về 0 khoản, và một văn bản 0 khoản trông y hệt
một văn bản không chẻ khoản (25/267 điều thật sự như thế). Đo trên TT15/2024 — văn bản duy nhất
có ở cả corpus lẫn bản crawl nên so được: `articles[].text` của bản crawl cho **0/0**, còn
`noi_dung` thô cho **102 khoản / 57 điểm**.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingestion.vbpl_corpus import (
    dieu_tu_toan_van,
    doc_id_theo_corpus,
    doc_file,
    duong_dan_toan_van,
    phan_cap_tu_cay,
)
from app.ontology.parser import parse_dieu

_TT15 = Path(
    "data/raw/vbpl/thong-tu-so-15-2024-tt-nhnn-quy-dinh-ve-cung-ung-dich-vu-thanh-toan-"
    "khong-dung-t.corpus.json"
)
_VBHN = Path(
    "data/raw/vbpl/van-ban-hop-nhat-so-29-vbhn-nhnn-quy-dinh-ve-hoat-dong-cung-ung-dich-vu-"
    "trung-gi.corpus.json"
)
pytestmark = pytest.mark.skipif(not _TT15.exists(), reason="chưa crawl TT15/2024")


def _dem(arts, so_hieu="15/2024/TT-NHNN") -> tuple[int, int]:
    kh = di = 0
    for a in arts:
        d = parse_dieu(f"{a.article}. {a.text}", so_hieu)
        kh += len(d.khoan)
        di += sum(len(k.diem) for k in d.khoan)
    return kh, di


# --- 1. Ca đã hỏng: articles[] sẵn có mất sạch đánh số ------------------------


def test_articles_san_co_MAT_danh_so_nen_khong_duoc_dung():
    """Đây là lý do tồn tại của cả module. Nếu ngày nào bộ crawl sửa được, test này sẽ đỏ —
    và đỏ ở đây là **tin tốt**, đọc docstring rồi bỏ module đi.
    """
    raw = json.loads(_TT15.read_text(encoding="utf-8"))

    class _A:  # đủ dùng cho `_dem`, không cần dựng `Article`
        def __init__(self, d):
            self.article, self.text = d["article"], d["text"]

    assert _dem([_A(a) for a in raw["articles"]]) == (0, 0)


def test_toan_van_tho_LAY_LAI_du_danh_so():
    kq = doc_file(_TT15)
    assert kq.van_ban is not None
    assert _dem(kq.van_ban.articles) == (102, 57)


def test_toan_van_tho_la_TAP_CHA_cua_corpus_hien_co():
    """Không chỉ "nhiều hơn": mọi điều của corpus đều có mặt, và có thêm `Điều 19` corpus thiếu."""
    from app.ingestion.pipeline import load_corpus

    docs, _ = load_corpus("data/corpus.real.json")
    cu = next(d for d in docs if d.doc_id == "TT15-2024")
    moi = doc_file(_TT15).van_ban
    ten_cu = {a.article for a in cu.articles}
    ten_moi = {a.article for a in moi.articles}
    assert ten_cu < ten_moi
    assert ten_moi - ten_cu == {"Điều 19"}
    assert _dem(moi.articles) >= _dem(cu.articles)


# --- 2. Chương/Mục: việc duy nhất cây provisions làm được ---------------------


def test_chuong_muc_lay_tu_cay_dien_du_23_dieu():
    """`Article.chapter` khai đã lâu mà 0/278 điều có giá trị — nguồn vbpl có sẵn."""
    moi = doc_file(_TT15).van_ban
    assert all(a.chapter for a in moi.articles)
    assert next(a for a in moi.articles if a.article == "Điều 2").chapter == "Chương I. QUY ĐỊNH CHUNG"


def test_cay_rong_thi_khong_gan_bua_nhan_phan_cap():
    assert phan_cap_tu_cay([]) == {}
    arts = dieu_tu_toan_van("Điều 1. Phạm vi\nNội dung điều một.", [])
    assert len(arts) == 1 and arts[0].chapter is None and arts[0].section is None


# --- 3. doc_id: theo quy ước corpus, không sinh không gian tên thứ ba ---------


@pytest.mark.parametrize(
    ("so_hieu", "cho"),
    [
        ("101/2012/NĐ-CP", "ND101-2012"),   # khớp corpus đang có
        ("15/2024/TT-NHNN", "TT15-2024"),   # khớp corpus đang có
        ("29/VBHN-NHNN", "VBHN29-NHNN"),    # không năm ⇒ lấy cơ quan làm phần phân biệt
        ("59/2020/QH14", "L59-2020"),
        ("không phải số hiệu", None),
    ],
)
def test_doc_id_theo_quy_uoc_corpus(so_hieu, cho):
    assert doc_id_theo_corpus(so_hieu) == cho


def test_doc_id_trong_file_LECH_thi_bao_ra_va_theo_corpus():
    """Bộ crawl đặt `15-2024-TT-NHNN`, corpus dùng `TT15-2024`. Theo bộ crawl ⇒ **hai node cho
    một văn bản**, đúng kiểu hỏng mà cả lớp bắc cầu sinh ra để chặn.
    """
    kq = doc_file(_TT15)
    assert kq.doc_id_trong_file == "15-2024-TT-NHNN"
    assert kq.van_ban.doc_id == "TT15-2024"
    assert any("quy ước corpus" in c for c in kq.canh_bao)


# --- 4. Không có toàn văn thì KHÔNG giả vờ là có -----------------------------


@pytest.mark.skipif(not _VBHN.exists(), reason="chưa crawl 29/VBHN-NHNN")
def test_van_ban_khong_co_toan_van_thi_giu_lam_node_rong():
    kq = doc_file(_VBHN)
    assert kq.van_ban is None, "0 điều mà vẫn dựng CorpusDocument là khai khống"
    assert kq.so_hieu == "29/VBHN-NHNN"
    assert any("0 điều" in c for c in kq.canh_bao)


def test_thieu_ban_ghi_tho_thi_TU_CHOI_chu_khong_lui_ve_articles_san_co():
    """Lùi về `articles` sẵn có là lặng lẽ nạp một văn bản mất sạch khoản/điểm."""
    assert duong_dan_toan_van(_TT15).name.endswith("-t.json")
    assert not duong_dan_toan_van(_TT15).name.endswith(".corpus.json")
