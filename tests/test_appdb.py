"""Test ghi chat history + audit log qua PostgREST (mock _post, không gọi mạng)."""
from __future__ import annotations

import httpx
import pytest

from app.core import appdb
from app.core.config import settings


@pytest.fixture
def calls(monkeypatch):
    """Bắt mọi lời gọi PostgREST; trả id giả cho chat_sessions."""
    recorded: list[tuple[str, object]] = []

    def fake_post(path: str, token: str, body: object) -> list[dict]:
        recorded.append((path, body))
        if path == "/chat_sessions":
            return [{"id": "sess-123"}]
        return [{}]

    monkeypatch.setattr(appdb, "_post", fake_post)
    return recorded


def test_enabled_theo_cau_hinh(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "")
    assert not appdb.enabled()
    monkeypatch.setattr(settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "sb_publishable_x")
    assert appdb.enabled()


def test_luu_luot_chat_tao_phien_moi(calls):
    sid = appdb.save_chat_turn(
        token="tok", user_id="u1", session_id=None,
        query="Hạn mức ví điện tử?", mode="qa", answer="100 triệu",
        citations=[{"doc_id": "TT40-2024"}, {"doc_id": "ND52-2024"}],
        conflicts=[{"severity": "critical"}],
    )
    assert sid == "sess-123"
    paths = [p for p, _ in calls]
    assert paths == ["/chat_sessions", "/chat_messages", "/audit_log"]
    # 2 message: user + assistant (kèm citations/conflicts)
    messages = calls[1][1]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["citations"][0]["doc_id"] == "TT40-2024"
    # audit ghi các doc được trích dẫn
    audit = calls[2][1]
    assert audit["action"] == "chat"
    assert audit["detail"]["cited_docs"] == ["ND52-2024", "TT40-2024"]


def test_luu_luot_chat_dung_phien_cu(calls):
    sid = appdb.save_chat_turn(
        token="tok", user_id="u1", session_id="sess-cu",
        query="q", mode="qa", answer="a", citations=[], conflicts=[],
    )
    assert sid == "sess-cu"
    assert [p for p, _ in calls] == ["/chat_messages", "/audit_log"]


def test_loi_mang_khong_lam_hong_chat(monkeypatch):
    def boom(path, token, body):
        raise httpx.ConnectError("mất mạng")

    monkeypatch.setattr(appdb, "_post", boom)
    sid = appdb.save_chat_turn(
        token="tok", user_id="u1", session_id="sess-cu",
        query="q", mode="qa", answer="a", citations=[], conflicts=[],
    )
    assert sid == "sess-cu"  # không raise, trả lại session_id đang có


def test_audit_loi_khong_raise(monkeypatch):
    def boom(path, token, body):
        raise httpx.HTTPStatusError("403", request=None, response=None)

    monkeypatch.setattr(appdb, "_post", boom)
    appdb.log_audit("tok", "u1", action="ingest", detail={})  # không raise
