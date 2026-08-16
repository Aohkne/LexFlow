"""Test SSE /chat/stream (dev mode, mock retrieval + LLM — không gọi mạng)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.reasoning import answer as answer_mod

_CHUNK = {
    "id": "TT40-2024::Điều 12 Khoản 1",
    "doc_id": "TT40-2024", "doc_title": "Thông tư 40/2024", "doc_type": "Thông tư",
    "article": "Điều 12 Khoản 1", "text": "Hạn mức 100 triệu đồng/tháng.",
    "valid_from": "2024-07-01", "valid_to": "",
}


@pytest.fixture
def client(monkeypatch):
    # Dev mode: không Supabase → auth no-op, không persistence; tắt graph để mock hybrid_search
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(settings, "graph_augment", False)
    monkeypatch.setattr(answer_mod, "hybrid_search", lambda *a, **kw: [_CHUNK])
    monkeypatch.setattr(answer_mod, "chat_stream", lambda *a, **kw: iter(["Hạn mức ", "100 triệu."]))
    monkeypatch.setattr(answer_mod, "detect_conflicts", lambda chunks: [])
    return TestClient(app)


def _events(text: str) -> list[tuple[str, str]]:
    out = []
    for block in text.strip().split("\n\n"):
        event, data = "message", ""
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data += line[6:]
        out.append((event, data))
    return out


def test_stream_thu_tu_su_kien(client):
    resp = client.post("/chat/stream", json={"query": "Hạn mức ví?"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _events(resp.text)
    kinds = [e for e, _ in events]
    assert kinds == ["meta", "delta", "delta", "conflicts", "canh_bao", "done"]
    assert "TT40-2024" in events[0][1]
    assert "100 triệu" in events[2][1]
    # câu trả lời mock không kèm [văn bản — điều] → hậu kiểm gắn cờ thiếu_trích_dẫn
    assert "thiếu_trích_dẫn" in events[4][1]


def test_stream_khong_tim_thay(client, monkeypatch):
    monkeypatch.setattr(answer_mod, "hybrid_search", lambda *a, **kw: [])
    resp = client.post("/chat/stream", json={"query": "abc"})
    kinds = [e for e, _ in _events(resp.text)]
    assert kinds == ["meta", "delta", "conflicts", "canh_bao", "done"]


def test_doc_ids_gioi_han_pham_vi(client, monkeypatch):
    """Có doc_ids → dùng search_in_docs (giới hạn văn bản), không dùng hybrid_search."""
    called = {}

    def fake_scoped(query, doc_ids, **kw):
        called["doc_ids"] = doc_ids
        return [_CHUNK]

    monkeypatch.setattr(answer_mod, "search_in_docs", fake_scoped)
    monkeypatch.setattr(
        answer_mod, "hybrid_search",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("không được gọi hybrid")),
    )
    resp = client.post("/chat/stream", json={"query": "Hạn mức?", "doc_ids": ["TT40-2024"]})
    assert resp.status_code == 200
    assert called["doc_ids"] == ["TT40-2024"]


def test_stream_loi_llm_tra_event_error(client, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("Gemini sập")
        yield  # generator

    monkeypatch.setattr(answer_mod, "chat_stream", boom)
    resp = client.post("/chat/stream", json={"query": "abc"})
    events = _events(resp.text)
    assert events[-1][0] == "error"
    assert "Gemini sập" in events[-1][1]
