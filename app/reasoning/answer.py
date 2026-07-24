"""Sinh câu trả lời có trích dẫn từ các điều khoản đang hiệu lực."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.core.llm import chat, chat_stream
from app.core.schemas import ChatRequest, ChatResponse, Citation
from app.core.tracing import observe
from app.ingestion.versioning import today_iso
from app.knowledge.retrieval import hybrid_search
from app.reasoning.conflict import detect_conflicts

_QA_SYSTEM = (
    "Bạn là trợ lý pháp lý ngân hàng. Trả lời câu hỏi CHỈ dựa trên các điều khoản "
    "được cung cấp (đang hiệu lực). Luôn trích dẫn văn bản + điều/khoản trong ngoặc "
    "vuông, ví dụ [Thông tư 40/2024 — Điều 12 Khoản 1]. Nếu không đủ căn cứ, nói rõ "
    "là chưa tìm thấy quy định phù hợp. Trả lời bằng tiếng Việt, ngắn gọn, chính xác."
)

_CHECKLIST_SYSTEM = (
    "Bạn là trợ lý pháp lý ngân hàng. Người dùng mô tả một LUỒNG NGHIỆP VỤ thanh toán. "
    "Dựa trên các điều khoản đang hiệu lực được cung cấp, hãy lập CHECKLIST các quy định "
    "áp dụng, mỗi mục kèm trích dẫn [văn bản — điều/khoản]. Trả lời bằng tiếng Việt."
)

_NOT_FOUND = "Chưa tìm thấy quy định đang hiệu lực phù hợp với câu hỏi."


def _format_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[{c['doc_title']} — {c['article']}] (hiệu lực từ {c['valid_from'] or 'N/A'})\n{c['text']}"
        for c in chunks
    )


def _prepare(req: ChatRequest) -> tuple[list[dict], str, str]:
    """Retrieval + dựng prompt. Trả về (chunks, system, prompt)."""
    as_of = req.as_of or today_iso()
    chunks = hybrid_search(req.query, top_k=req.top_k, as_of=as_of, effective_only=True)
    system = _CHECKLIST_SYSTEM if req.mode == "checklist" else _QA_SYSTEM
    prompt = (
        f"Câu hỏi/luồng nghiệp vụ: {req.query}\n\n"
        f"Các điều khoản đang hiệu lực (tại {as_of}):\n{_format_context(chunks)}"
    )
    return chunks, system, prompt


def _citations(chunks: list[dict]) -> list[Citation]:
    return [
        Citation(
            doc_id=c["doc_id"], doc_title=c["doc_title"], doc_type=c["doc_type"],
            article=c["article"], valid_from=c["valid_from"] or None,
            valid_to=c["valid_to"] or None, snippet=c["text"][:280],
        )
        for c in chunks
    ]


@observe(name="answer.build")
def build_answer(req: ChatRequest) -> ChatResponse:
    chunks, system, prompt = _prepare(req)
    if not chunks:
        return ChatResponse(answer=_NOT_FOUND, citations=[], conflicts=[])
    answer = chat(prompt, system=system)
    return ChatResponse(
        answer=answer, citations=_citations(chunks), conflicts=detect_conflicts(chunks)
    )


@observe(
    name="answer.stream",
    transform_to_string=lambda events: "".join(d for k, d in events if k == "delta"),
)
def stream_answer(req: ChatRequest) -> Iterator[tuple[str, Any]]:
    """Bản streaming của build_answer — yield các sự kiện theo thứ tự UX:

    ("meta", {"citations": [...]}) → ("delta", str)* → ("conflicts", [...])

    Citations gửi trước để UI hiện nguồn ngay; conflicts cần gọi LLM riêng
    nên gửi sau khi câu trả lời đã stream xong.
    """
    chunks, system, prompt = _prepare(req)
    if not chunks:
        yield "meta", {"citations": []}
        yield "delta", _NOT_FOUND
        yield "conflicts", []
        return

    yield "meta", {"citations": [c.model_dump() for c in _citations(chunks)]}
    for piece in chat_stream(prompt, system=system):
        yield "delta", piece
    yield "conflicts", [c.model_dump() for c in detect_conflicts(chunks)]
