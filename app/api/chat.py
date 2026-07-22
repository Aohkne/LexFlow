from fastapi import APIRouter, HTTPException

from app.core.schemas import ChatRequest, ChatResponse
from app.reasoning.answer import build_answer

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    try:
        return build_answer(req)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
