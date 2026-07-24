"""Test sinh sự kiện cảnh báo thay đổi từ relationships của corpus."""
from __future__ import annotations

import httpx

from app.core import appdb
from app.core.schemas import Article, CorpusDocument, Relationship
from app.ingestion.pipeline import build_change_events

_DOCS = [
    CorpusDocument(doc_id="TT40-2024", title="Thông tư 40/2024", doc_type="Thông tư",
                   articles=[Article(article="Điều 1", text="x")]),
    CorpusDocument(doc_id="TT23-2019", title="Thông tư 23/2019", doc_type="Thông tư",
                   articles=[]),
]


def test_build_change_events():
    rels = [
        Relationship(source_doc="TT40-2024", target_doc="TT23-2019",
                     rel_type="THAY_THE", valid_from="2024-07-01", note="toàn bộ"),
        Relationship(source_doc="TT40-2024", target_doc="XX-9999", rel_type="SUA_DOI"),
    ]
    events = build_change_events(_DOCS, rels)
    assert len(events) == 2
    assert events[0]["doc_id"] == "TT23-2019"
    assert events[0]["source_doc_id"] == "TT40-2024"
    assert "thay thế" in events[0]["description"]
    assert "toàn bộ" in events[0]["description"]
    assert events[0]["effective_date"] == "2024-07-01"
    # doc không có trong corpus → dùng doc_id thay title
    assert "XX-9999" in events[1]["description"]


def test_record_change_events_upsert(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_post(path, token, body, *, prefer=""):
        calls.append((path, prefer))
        return []

    monkeypatch.setattr(appdb, "_post", fake_post)
    n = appdb.record_change_events("tok", [{"doc_id": "a"}])
    assert n == 1
    assert "on_conflict=doc_id,source_doc_id,rel_type" in calls[0][0]
    assert "ignore-duplicates" in calls[0][1]


def test_record_change_events_rong_va_loi(monkeypatch):
    assert appdb.record_change_events("tok", []) == 0

    def boom(path, token, body, *, prefer=""):
        raise httpx.ConnectError("mất mạng")

    monkeypatch.setattr(appdb, "_post", boom)
    assert appdb.record_change_events("tok", [{"doc_id": "a"}]) == 0  # không raise
