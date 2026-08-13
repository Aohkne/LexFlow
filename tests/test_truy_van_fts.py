"""Nhánh BM25: cộng điểm cho cụm nguyên văn, và kêu lên khi tắt.

Đo 10/08 trên 14 cụm CÓ THẬT trong `data/corpus.real.json` (precision@10 của riêng nhánh
BM25, tự nghiệm — "top-10 có thật sự chứa cụm đã hỏi không", không cần đáp án vàng):

    chỉ mục cũ  + MatchQuery            8.4/10
    chỉ mục mới + MatchQuery            9.0/10   (`an toàn` 2→10, nhờ tắt stem/stop-word Anh)
    chỉ mục mới + Match + Phrase        9.9/10   (`giấy phép hoạt động` 3→9, `quy định nội bộ` 4→10)

Hai câu hỏi dài dạng tự nhiên trả về đúng 6/6 hit cũ ⇒ mệnh đề cụm không ăn mất độ phủ.
"""
from __future__ import annotations

import logging

from lancedb.query import BooleanQuery, MatchQuery, Occur, PhraseQuery

from app.knowledge import retrieval


def test_truy_van_gom_ca_tui_tu_lan_cum():
    q = retrieval._truy_van_fts("giấy phép hoạt động")
    assert isinstance(q, BooleanQuery)

    loai = {type(con) for _occur, con in q.queries}
    assert loai == {MatchQuery, PhraseQuery}, "thiếu một trong hai mệnh đề"
    assert all(occur is Occur.SHOULD for occur, _ in q.queries), (
        "PhraseQuery ở mức MUST sẽ giết mọi câu hỏi dài — luật không chứa nguyên văn câu hỏi"
    )


def test_fts_hong_thi_tra_rong_va_ghi_log(caplog):
    """Fail-open là đúng, nuốt trong im lặng thì không.

    Nửa hệ thống truy hồi có thể chết hàng tuần mà không ai biết — đúng lớp khuyết tật đã
    dọn ở `/health` hôm 09/08.
    """

    class _BangHong:
        def search(self, *_a, **_k):
            raise RuntimeError("position is not found")

    with caplog.at_level(logging.WARNING, logger="app.knowledge.retrieval"):
        ra = retrieval._bat_fts(_BangHong(), "ví điện tử", pool=10)

    assert ra == []
    assert "BM25" in caplog.text


def test_co_where_thi_day_xuong_bang(monkeypatch):
    """Lọc `doc_id` phải đi kèm `prefilter=True` — hậu lọc sẽ ăn mất hit của nhóm đã giới hạn."""
    ghi: dict = {}

    class _TruyVan:
        def where(self, dk, prefilter=False):
            ghi["where"], ghi["prefilter"] = dk, prefilter
            return self

        def limit(self, n):
            ghi["limit"] = n
            return self

        def to_list(self):
            return [{"id": "x"}]

    class _Bang:
        def search(self, _q, query_type=None):
            ghi["query_type"] = query_type
            return _TruyVan()

    ra = retrieval._bat_fts(_Bang(), "ví điện tử", pool=8, where="doc_id IN ('TT40-2024')")

    assert ra == [{"id": "x"}]
    assert ghi["query_type"] == "fts"
    assert ghi["prefilter"] is True
    assert ghi["limit"] == 8


def test_vector_hong_tam_thoi_thi_thu_lai(monkeypatch):
    """"connection reset" giữa batch dài không được giết cả run — retry rồi mới chết.

    Client LanceDB chỉ tự retry lỗi có mã HTTP; lỗi tầng kết nối ném thẳng `HttpError`
    (đo 13/08: hai run compliance chết cùng một callsite vector search).
    """
    import pytest
    from lancedb.remote.errors import HttpError

    monkeypatch.setattr(retrieval.time, "sleep", lambda _s: None)
    dem = {"n": 0}

    class _TruyVan:
        def where(self, _dk, prefilter=False):
            return self

        def limit(self, _n):
            return self

        def to_list(self):
            dem["n"] += 1
            if dem["n"] < 3:
                raise HttpError("connection reset", "req-test")
            return [{"id": "x"}]

    class _Bang:
        def search(self, _q, **_k):
            return _TruyVan()

    ra = retrieval._vector_hits(_Bang(), [0.1], pool=8, where="doc_id IN ('TT40-2024')")
    assert ra == [{"id": "x"}]
    assert dem["n"] == 3

    dem["n"] = -99  # không bao giờ hồi phục ⇒ hết 4 lượt phải ném lỗi thật
    with pytest.raises(HttpError):
        retrieval._vector_hits(_Bang(), [0.1], pool=8)
