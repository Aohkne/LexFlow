"""Sinh câu trả lời có trích dẫn từ các điều khoản đang hiệu lực."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.core.config import settings
from app.core.llm import chat, chat_stream
from app.core.schemas import ChatRequest, ChatResponse, Citation, nhan_quan_he
from app.core.tracing import observe
from app.ingestion.versioning import today_iso
from app.knowledge.lop_phu import ChuThichHieuLuc, chu_thich_ket_qua
from app.knowledge.retrieval import graph_augmented_search, hybrid_search, search_in_docs
from app.reasoning.conflict import detect_conflicts
from app.reasoning.postcheck import hau_kiem

_QA_SYSTEM = (
    "Bạn là trợ lý pháp lý ngân hàng. Trả lời câu hỏi CHỈ dựa trên các điều khoản "
    "được cung cấp (đang hiệu lực). Luôn trích dẫn văn bản + điều/khoản trong ngoặc "
    "vuông, ví dụ [Thông tư 40/2024 — Điều 12 Khoản 1]. Nếu một căn cứ được ghi chú là đã "
    "bị sửa đổi hoặc bãi bỏ, phải nói rõ điều đó và ưu tiên phần 'Bản hiện hành' nếu có — "
    "không trình bày lời văn cũ như đang có hiệu lực. Nếu không đủ căn cứ, nói rõ "
    "là chưa tìm thấy quy định phù hợp. "
    # T109 Phase 1: lỗi chủ đạo là trích-xuất-THIẾU từ điều đã lấy đúng (chẩn đoán 16/08,
    # 18/19 câu "thiếu" của judge SBV). Bỏ "ngắn gọn" (thủ phạm lược bớt); ép liệt-kê-đủ,
    # kèm vế chặn để completeness không đẻ ra nội dung ngoài căn cứ (EvidenceMismatch).
    "Khi điều được dẫn liệt kê nhiều khoản/điểm/trường hợp/điều kiện, phải nêu ĐẦY ĐỦ tất cả "
    "các mục đó — không tự lược bớt mục nào; nhưng KHÔNG thêm nội dung nằm ngoài các điều khoản "
    "được cung cấp. "
    # T109 Phase 1b: "đủ ý" ban đầu khiến model KHẲNG ĐỊNH phủ định (qid 19, 33: "không có quy
    # định") cho chi tiết có thật nhưng không được retrieve → thiếu (an toàn) hoá sai (mâu thuẫn).
    # Rào: thiếu căn cứ thì nói CHƯA NÊU, không nói KHÔNG TỒN TẠI.
    "Nếu câu hỏi hỏi một chi tiết mà các điều khoản được cung cấp không nêu, hãy nói rõ 'các căn "
    "cứ hiện có chưa nêu chi tiết này' — TUYỆT ĐỐI không khẳng định chi tiết đó không tồn tại hay "
    "không được pháp luật quy định. Trả lời bằng tiếng Việt, chính xác, đủ ý."
)

_CHECKLIST_SYSTEM = (
    "Bạn là trợ lý pháp lý ngân hàng. Người dùng mô tả một LUỒNG NGHIỆP VỤ thanh toán. "
    "Dựa trên các điều khoản đang hiệu lực được cung cấp, hãy lập CHECKLIST các quy định "
    "áp dụng, mỗi mục kèm trích dẫn [văn bản — điều/khoản]. Trả lời bằng tiếng Việt."
)

_NOT_FOUND = "Chưa tìm thấy quy định đang hiệu lực phù hợp với câu hỏi."


def _format_context(chunks: list[dict], ct: dict[str, ChuThichHieuLuc]) -> str:
    khoi = []
    for c in chunks:
        t = ct.get(c["id"])
        dau = f"[{c['doc_title']} — {c['article']}] (hiệu lực từ {c['valid_from'] or 'N/A'})"
        if t is not None and t.trang_thai != "nguyen_ven":
            dau += f" — {t.trich_dan_dung_chu}"
        than = c["text"]
        if t is not None and t.ban_hien_hanh:
            xx = f"{t.sua_boi_doc_id} {t.sua_boi_article}".strip()
            than += f"\n\nBản hiện hành (theo {xx}):\n{t.ban_hien_hanh}"
        khoi.append(f"{dau}\n{than}")
    return "\n\n".join(khoi)


# Nhãn lấy từ `app.core.schemas.REL_TYPES` — nguồn sự thật DUY NHẤT cho 13 quan hệ.


def _prepare(req: ChatRequest) -> tuple[list[dict], dict[str, ChuThichHieuLuc], str, str]:
    """Retrieval (+ graph, + lớp phủ) + dựng prompt. Trả (chunks, chú thích, system, prompt)."""
    as_of = req.as_of or today_iso()
    edges: list[dict] = []
    if req.doc_ids:
        # Người dùng giới hạn phạm vi → chỉ tìm trong các văn bản đã chọn
        chunks = search_in_docs(
            req.query, req.doc_ids, top_k=req.top_k, as_of=as_of, effective_only=True
        )
    elif settings.graph_augment and settings.neo4j_enabled:
        chunks, edges = graph_augmented_search(req.query, top_k=req.top_k, as_of=as_of, effective_only=True)
    else:
        chunks = hybrid_search(req.query, top_k=req.top_k, as_of=as_of, effective_only=True)

    ct: dict[str, ChuThichHieuLuc] = {}
    if settings.overlay_router:
        # `pham_vi` = đúng phạm vi người dùng đã chọn: lớp phủ có thể KÉO THÊM chunk lời văn
        # mới về, và chunk đó không được đến từ một văn bản người dùng vừa loại ra khỏi câu hỏi.
        chunks, ct = chu_thich_ket_qua(
            chunks, as_of, pham_vi=set(req.doc_ids) if req.doc_ids else None
        )

    system = _CHECKLIST_SYSTEM if req.mode == "checklist" else _QA_SYSTEM
    prompt = (
        f"Câu hỏi/luồng nghiệp vụ: {req.query}\n\n"
        f"Các điều khoản đang hiệu lực (tại {as_of}):\n{_format_context(chunks, ct)}"
    )
    if edges:
        rel_lines = "\n".join(
            f"- {e['src']} {nhan_quan_he(e['rel_type'])} {e['tgt']}"
            + (f" ({e['note']})" if e.get("note") else "")
            for e in edges
        )
        prompt += f"\n\nQuan hệ giữa các văn bản (theo knowledge graph):\n{rel_lines}"
    return chunks, ct, system, prompt


def _citations(chunks: list[dict], ct: dict[str, ChuThichHieuLuc]) -> list[Citation]:
    ra = []
    for c in chunks:
        t = ct.get(c["id"])
        ra.append(
            Citation(
                doc_id=c["doc_id"], doc_title=c["doc_title"], doc_type=c["doc_type"],
                article=c["article"], valid_from=c["valid_from"] or None,
                valid_to=c["valid_to"] or None, snippet=c["text"][:280],
                trang_thai=t.trang_thai if t else None,
                chu_thich=t.trich_dan_dung_chu if t else None,
                sua_boi_doc_id=t.sua_boi_doc_id if t else None,
                sua_boi_article=t.sua_boi_article if t else None,
                ban_hien_hanh=t.ban_hien_hanh if t else None,
            )
        )
    return ra


@observe(name="answer.build")
def build_answer(req: ChatRequest) -> ChatResponse:
    chunks, ct, system, prompt = _prepare(req)
    if not chunks:
        return ChatResponse(answer=_NOT_FOUND, citations=[], conflicts=[])
    answer = chat(prompt, system=system)
    return ChatResponse(
        answer=answer,
        citations=_citations(chunks, ct),
        conflicts=detect_conflicts(chunks),
        canh_bao=hau_kiem(answer, chunks, not_found=_NOT_FOUND),
    )


@observe(
    name="answer.stream",
    transform_to_string=lambda events: "".join(d for k, d in events if k == "delta"),
)
def stream_answer(req: ChatRequest) -> Iterator[tuple[str, Any]]:
    """Bản streaming của build_answer — yield các sự kiện theo thứ tự UX:

    ("meta", {"citations": [...]}) → ("delta", str)* → ("conflicts", [...]) → ("canh_bao", [...])

    Citations gửi trước để UI hiện nguồn ngay; conflicts cần gọi LLM riêng nên gửi sau. Cờ hậu
    kiểm (`canh_bao`, T109 Phase 2) cần TOÀN VĂN câu trả lời nên gộp delta lại rồi kiểm ở cuối.
    """
    chunks, ct, system, prompt = _prepare(req)
    if not chunks:
        yield "meta", {"citations": []}
        yield "delta", _NOT_FOUND
        yield "conflicts", []
        yield "canh_bao", []
        return

    yield "meta", {"citations": [c.model_dump() for c in _citations(chunks, ct)]}
    phan = []
    for piece in chat_stream(prompt, system=system):
        phan.append(piece)
        yield "delta", piece
    yield "conflicts", [c.model_dump() for c in detect_conflicts(chunks)]
    yield "canh_bao", hau_kiem("".join(phan), chunks, not_found=_NOT_FOUND)
