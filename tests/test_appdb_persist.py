"""Test appdb: lưu scope/as_of theo lượt chat (fallback khi thiếu migration 0005)
và lưu review session (best-effort)."""
from __future__ import annotations

import httpx

from app.core import appdb


def _status_error() -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "https://x.supabase.co/rest/v1/chat_messages")
    resp = httpx.Response(400, request=req)
    return httpx.HTTPStatusError("400", request=req, response=resp)


def test_save_chat_turn_ghi_scope_as_of(monkeypatch):
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(appdb, "_post", lambda path, tok, body, **kw: calls.append((path, body)) or [])
    monkeypatch.setattr(appdb, "log_audit", lambda *a, **kw: None)

    sid = appdb.save_chat_turn(
        "tok", "u1", "s1", "q?", "qa", "a.", [], [],
        scope=["TT40-2024"], as_of="2025-01-01",
    )
    assert sid == "s1"
    path, body = calls[0]
    assert path == "/chat_messages"
    assert body[0]["scope"] == ["TT40-2024"]
    assert body[1]["as_of"] == "2025-01-01"


def test_save_chat_turn_fallback_khi_thieu_cot(monkeypatch):
    """Migration 0005 chưa chạy → insert kèm scope lỗi 400 → thử lại bản tối thiểu."""
    calls: list[object] = []

    def fake_post(path, tok, body, **kw):
        calls.append(body)
        if len(calls) == 1:
            raise _status_error()
        return []

    monkeypatch.setattr(appdb, "_post", fake_post)
    monkeypatch.setattr(appdb, "log_audit", lambda *a, **kw: None)

    sid = appdb.save_chat_turn(
        "tok", "u1", "s1", "q?", "qa", "a.", [], [], scope=["TT40-2024"], as_of=None
    )
    assert sid == "s1"
    assert len(calls) == 2
    assert "scope" in calls[0][0]
    assert "scope" not in calls[1][0]  # bản tối thiểu không có cột mới


def test_save_review_session_fail_open(monkeypatch):
    def boom(path, tok, body, **kw):
        raise _status_error()

    monkeypatch.setattr(appdb, "_post", boom)
    rid = appdb.save_review_session(
        "tok", "u1",
        internal_doc_id="SHB-QD-VI-2023", internal_title="t", against_doc_ids=[],
        as_of="2026-07-28", score=50, counts={}, findings=[],
    )
    assert rid is None  # lỗi không được ném ra ngoài


def test_save_review_session_tra_id(monkeypatch):
    monkeypatch.setattr(appdb, "_post", lambda path, tok, body, **kw: [{"id": "rs-1"}])
    rid = appdb.save_review_session(
        "tok", "u1",
        internal_doc_id="SHB-QD-VI-2023", internal_title="t", against_doc_ids=["TT40-2024"],
        as_of="2026-07-28", score=50, counts={"violation": 1}, findings=[{"verdict": "violation"}],
    )
    assert rid == "rs-1"
