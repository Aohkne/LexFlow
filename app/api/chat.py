from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core import appdb
from app.core.auth import AuthUser, get_current_user
from app.core.schemas import ChatRequest, ChatResponse
from app.reasoning.answer import build_answer, stream_answer

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest, user: AuthUser = Depends(get_current_user)) -> ChatResponse:
    try:
        resp = build_answer(req)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Lưu hội thoại + audit log (best-effort — user.token rỗng ở dev mode)
    if appdb.enabled() and user.token:
        resp.session_id = appdb.save_chat_turn(
            token=user.token,
            user_id=user.id,
            session_id=req.session_id,
            query=req.query,
            mode=req.mode,
            answer=resp.answer,
            citations=[c.model_dump() for c in resp.citations],
            conflicts=[c.model_dump() for c in resp.conflicts],
            scope=req.doc_ids,
            as_of=req.as_of,
        )
    return resp


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
def chat_stream_endpoint(
    req: ChatRequest, user: AuthUser = Depends(get_current_user)
) -> StreamingResponse:
    """SSE: meta (citations) → delta (từng mẩu câu trả lời) → conflicts → canh_bao → done."""

    def gen() -> Iterator[str]:
        parts: list[str] = []
        citations: list[dict] = []
        conflicts: list[dict] = []
        try:
            for kind, data in stream_answer(req):
                if kind == "delta":
                    parts.append(data)
                    yield _sse("delta", {"text": data})
                elif kind == "meta":
                    citations = data["citations"]
                    yield _sse("meta", data)
                elif kind == "conflicts":
                    conflicts = data
                    yield _sse("conflicts", {"conflicts": data})
                elif kind == "canh_bao":
                    yield _sse("canh_bao", {"canh_bao": data})
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"detail": str(exc)})
            return

        session_id = req.session_id
        if appdb.enabled() and user.token:
            session_id = appdb.save_chat_turn(
                token=user.token,
                user_id=user.id,
                session_id=req.session_id,
                query=req.query,
                mode=req.mode,
                answer="".join(parts),
                citations=citations,
                conflicts=conflicts,
                scope=req.doc_ids,
                as_of=req.as_of,
            )
        yield _sse("done", {"session_id": session_id})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
