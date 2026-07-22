"""Unit test cho logic lõi (không gọi API): versioning, RRF, ingest."""
from app.ingestion.pipeline import build_chunks, load_corpus
from app.ingestion.versioning import is_effective
from app.knowledge.retrieval import _rrf


def test_versioning_expired_document():
    # TT39 hết hiệu lực 2024-06-30
    assert is_effective("2015-03-01", "2024-06-30", False, "2025-01-01") is False


def test_versioning_current_document():
    assert is_effective("2024-07-01", None, False, "2025-01-01") is True


def test_versioning_not_yet_effective():
    assert is_effective("2024-07-01", None, False, "2024-01-01") is False


def test_versioning_superseded():
    assert is_effective("2020-01-01", None, True, "2025-01-01") is False


def test_rrf_fuses_rankings():
    v = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    f = [{"id": "c"}, {"id": "a"}, {"id": "d"}]
    order = [r["id"] for r in _rrf(v, f, 4)]
    assert order[0] == "a"  # xếp cao ở cả hai bảng
    assert set(order) == {"a", "b", "c", "d"}


def test_build_chunks_sample_corpus():
    docs, rels = load_corpus("data/corpus.sample.json")
    rows = build_chunks(docs)
    assert len(docs) == 5
    assert len(rels) == 4
    assert len(rows) == 8
    # Có nguồn nội bộ để phát hiện mâu thuẫn
    assert any(r["source"] == "internal" for r in rows)
    # Điều khoản kế thừa hiệu lực từ văn bản
    tt40 = [r for r in rows if r["doc_id"] == "TT40-2024"][0]
    assert tt40["valid_from"] == "2024-07-01"
