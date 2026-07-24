from fastapi import APIRouter, Depends, HTTPException

from app.core import appdb
from app.core.auth import AuthUser, get_current_user
from app.core.schemas import ChatRequest, ChatResponse
from app.reasoning.answer import build_answer

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
        )
    return resp
