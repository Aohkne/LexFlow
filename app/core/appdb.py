"""Ghi trạng thái ứng dụng (chat history, audit log) vào Supabase qua PostgREST.

Backend không giữ service-role key: mọi thao tác dùng chính JWT của user,
nên RLS trên Postgres vẫn được thực thi (user chỉ ghi/đọc dữ liệu của mình).
Ghi là best-effort — lỗi mạng/RLS không được làm hỏng response chat.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 5.0


def enabled() -> bool:
    return bool(settings.supabase_url and settings.supabase_anon_key)


def _post(path: str, token: str, body: Any) -> list[dict]:
    resp = httpx.post(
        settings.supabase_url.rstrip("/") + "/rest/v1" + path,
        json=body,
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {token}",
            "Prefer": "return=representation",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def create_session(token: str, user_id: str, title: str, mode: str) -> str:
    rows = _post(
        "/chat_sessions",
        token,
        {"user_id": user_id, "title": title[:80], "mode": mode},
    )
    return rows[0]["id"]


def save_chat_turn(
    token: str,
    user_id: str,
    session_id: str | None,
    query: str,
    mode: str,
    answer: str,
    citations: list[dict],
    conflicts: list[dict],
) -> str | None:
    """Lưu 1 lượt hỏi–đáp (tạo phiên nếu chưa có) + audit log. Trả về session_id."""
    try:
        if not session_id:
            session_id = create_session(token, user_id, title=query, mode=mode)
        # PostgREST bắt buộc mọi row trong bulk insert có cùng bộ key (PGRST102)
        _post(
            "/chat_messages",
            token,
            [
                {
                    "session_id": session_id,
                    "role": "user",
                    "content": query,
                    "citations": None,
                    "conflicts": None,
                },
                {
                    "session_id": session_id,
                    "role": "assistant",
                    "content": answer,
                    "citations": citations,
                    "conflicts": conflicts,
                },
            ],
        )
        log_audit(
            token,
            user_id,
            action="chat",
            detail={
                "session_id": session_id,
                "query": query,
                "cited_docs": sorted({c.get("doc_id", "") for c in citations}),
                "n_conflicts": len(conflicts),
            },
        )
        return session_id
    except httpx.HTTPError as exc:
        logger.warning("Không lưu được chat history vào Supabase: %s", exc)
        return session_id


def log_audit(token: str, user_id: str, action: str, detail: dict) -> None:
    try:
        _post("/audit_log", token, {"user_id": user_id, "action": action, "detail": detail})
    except httpx.HTTPError as exc:
        logger.warning("Không ghi được audit log: %s", exc)
