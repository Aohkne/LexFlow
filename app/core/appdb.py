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


def _post(path: str, token: str, body: Any, *, prefer: str = "return=representation") -> list[dict]:
    resp = httpx.post(
        settings.supabase_url.rstrip("/") + "/rest/v1" + path,
        json=body,
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {token}",
            "Prefer": prefer,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json() if resp.content else []


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
    scope: list[str] | None = None,
    as_of: str | None = None,
) -> str | None:
    """Lưu 1 lượt hỏi–đáp (tạo phiên nếu chưa có) + audit log. Trả về session_id."""
    try:
        if not session_id:
            session_id = create_session(token, user_id, title=query, mode=mode)
        # PostgREST bắt buộc mọi row trong bulk insert có cùng bộ key (PGRST102)
        row_user = {
            "session_id": session_id,
            "role": "user",
            "content": query,
            "citations": None,
            "conflicts": None,
        }
        row_asst = {
            "session_id": session_id,
            "role": "assistant",
            "content": answer,
            "citations": citations,
            "conflicts": conflicts,
        }
        extras = {"scope": scope or None, "as_of": as_of}
        try:
            _post("/chat_messages", token, [row_user | extras, row_asst | extras])
        except httpx.HTTPStatusError:
            # Migration 0005 chưa chạy (cột scope/as_of chưa có) → lưu bản tối thiểu
            _post("/chat_messages", token, [row_user, row_asst])
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


def save_review_session(
    token: str,
    user_id: str,
    *,
    internal_doc_id: str,
    internal_title: str,
    against_doc_ids: list[str],
    as_of: str,
    score: int,
    counts: dict,
    findings: list[dict],
) -> str | None:
    """Lưu kết quả một phiên kiểm tra tuân thủ. Best-effort — trả id hoặc None."""
    try:
        rows = _post(
            "/review_sessions",
            token,
            {
                "user_id": user_id,
                "internal_doc_id": internal_doc_id,
                "internal_title": internal_title,
                "against_doc_ids": against_doc_ids,
                "as_of": as_of,
                "score": score,
                "counts": counts,
                "findings": findings,
            },
        )
        return rows[0]["id"]
    except httpx.HTTPError as exc:
        logger.warning("Không lưu được review session (migration 0005 đã chạy chưa?): %s", exc)
        return None


def record_change_events(token: str, events: list[dict]) -> int:
    """Ghi các sự kiện thay đổi văn bản (ingest lại không tạo trùng nhờ on_conflict)."""
    if not events:
        return 0
    try:
        _post(
            "/change_events?on_conflict=doc_id,source_doc_id,rel_type",
            token,
            events,
            prefer="return=minimal,resolution=ignore-duplicates",
        )
        return len(events)
    except httpx.HTTPError as exc:
        logger.warning("Không ghi được change events: %s", exc)
        return 0


def log_audit(token: str, user_id: str, action: str, detail: dict) -> None:
    try:
        _post("/audit_log", token, {"user_id": user_id, "action": action, "detail": detail})
    except httpx.HTTPError as exc:
        logger.warning("Không ghi được audit log: %s", exc)


# ---------- Workflow duyệt văn bản (legal_documents + Storage) ----------

_BUCKET = "legal-docs"


def _storage_url(path: str) -> str:
    return settings.supabase_url.rstrip("/") + f"/storage/v1/object/{_BUCKET}/{path}"


def upload_storage(token: str, path: str, content: bytes, content_type: str) -> None:
    """Upload/ghi đè file trong bucket legal-docs (RLS: admin)."""
    resp = httpx.post(
        _storage_url(path),
        content=content,
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        timeout=60.0,
    )
    resp.raise_for_status()


def download_storage(token: str, path: str) -> bytes | None:
    """Tải file từ bucket legal-docs; None nếu chưa tồn tại."""
    resp = httpx.get(
        _storage_url(path),
        headers={"apikey": settings.supabase_anon_key, "Authorization": f"Bearer {token}"},
        timeout=60.0,
    )
    if resp.status_code == 404 or resp.status_code == 400:
        return None
    resp.raise_for_status()
    return resp.content


def insert_document(token: str, row: dict) -> None:
    """Thêm/cập nhật bản ghi legal_documents (upsert theo doc_id)."""
    _post(
        "/legal_documents?on_conflict=doc_id",
        token,
        row,
        prefer="return=minimal,resolution=merge-duplicates",
    )


def update_document(token: str, doc_id: str, patch: dict) -> None:
    resp = httpx.patch(
        settings.supabase_url.rstrip("/") + f"/rest/v1/legal_documents?doc_id=eq.{doc_id}",
        json=patch,
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {token}",
            "Prefer": "return=minimal",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


def get_document(token: str, doc_id: str) -> dict | None:
    resp = httpx.get(
        settings.supabase_url.rstrip("/") + f"/rest/v1/legal_documents?doc_id=eq.{doc_id}&select=*",
        headers={"apikey": settings.supabase_anon_key, "Authorization": f"Bearer {token}"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None
