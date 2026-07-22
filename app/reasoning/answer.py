"""Sinh câu trả lời có trích dẫn từ các điều khoản đang hiệu lực."""
from __future__ import annotations

from app.core.llm import chat
from app.core.schemas import ChatRequest, ChatResponse, Citation
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


def _format_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[{c['doc_title']} — {c['article']}] (hiệu lực từ {c['valid_from'] or 'N/A'})\n{c['text']}"
        for c in chunks
    )


def build_answer(req: ChatRequest) -> ChatResponse:
    as_of = req.as_of or today_iso()
    chunks = hybrid_search(req.query, top_k=req.top_k, as_of=as_of, effective_only=True)

    if not chunks:
        return ChatResponse(
            answer="Chưa tìm thấy quy định đang hiệu lực phù hợp với câu hỏi.",
            citations=[], conflicts=[],
        )

    system = _CHECKLIST_SYSTEM if req.mode == "checklist" else _QA_SYSTEM
    prompt = (
        f"Câu hỏi/luồng nghiệp vụ: {req.query}\n\n"
        f"Các điều khoản đang hiệu lực (tại {as_of}):\n{_format_context(chunks)}"
    )
    answer = chat(prompt, system=system)

    citations = [
        Citation(
            doc_id=c["doc_id"], doc_title=c["doc_title"], doc_type=c["doc_type"],
            article=c["article"], valid_from=c["valid_from"] or None,
            valid_to=c["valid_to"] or None, snippet=c["text"][:280],
        )
        for c in chunks
    ]
    conflicts = detect_conflicts(chunks)
    return ChatResponse(answer=answer, citations=citations, conflicts=conflicts)
