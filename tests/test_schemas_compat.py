"""Schema mở rộng (anchors, chapter/section) phải tương thích ngược với corpus hiện có."""
from __future__ import annotations

from app.core.schemas import Article, RelAnchor, Relationship
from app.ingestion.pipeline import load_corpus


def test_corpus_real_van_validate():
    docs, rels = load_corpus("data/corpus.real.json")
    assert len(docs) >= 10
    assert all(isinstance(r.anchors, list) for r in rels)


def test_relationship_khong_anchors_mac_dinh_rong():
    r = Relationship(source_doc="A", target_doc="B", rel_type="SUA_DOI")
    assert r.anchors == []
    assert r.model_dump()["anchors"] == []


def test_relationship_round_trip_anchors():
    r = Relationship(
        source_doc="A", target_doc="B", rel_type="SUA_DOI",
        anchors=[RelAnchor(source_article="Điều 1", target_article="Điều 9", detail="Sửa khoản 2")],
    )
    r2 = Relationship.model_validate(r.model_dump())
    assert r2.anchors[0].target_article == "Điều 9"


def test_article_chapter_section_tuy_chon():
    a = Article(article="Điều 1", text="x")
    assert a.chapter is None and a.section is None
    b = Article.model_validate({"article": "Điều 2", "text": "y", "chapter": "Chương I"})
    assert b.chapter == "Chương I"


def test_anchor_seed_khop_dieu_that():
    """Mọi target_article trong anchors phải tồn tại trong văn bản đích (chống typo)."""
    docs, rels = load_corpus("data/corpus.real.json")
    articles_by_doc = {d.doc_id: {a.article for a in d.articles} for d in docs}
    for r in rels:
        targets = articles_by_doc.get(r.target_doc, set())
        for anchor in r.anchors:
            if anchor.target_article:
                assert anchor.target_article in targets, (
                    f"{r.source_doc}->{r.target_doc}: '{anchor.target_article}' không có trong văn bản đích"
                )
