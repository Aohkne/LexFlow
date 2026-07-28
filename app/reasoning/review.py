"""Kiểm tra tuân thủ: đối chiếu từng điều của tài liệu nội bộ với luật hiện hành.

Mỗi điều nội bộ → retrieval các điều luật liên quan (chỉ trong phạm vi văn bản
đối chiếu, chỉ bản đang hiệu lực tại as_of) → Gemini phán định JSON
(violation | warning | pass) kèm trích dẫn hai phía → tổng hợp findings + điểm.
"""
from __future__ import annotations

from app.core.llm import chat_json
from app.core.schemas import CorpusDocument, ReviewFinding, ReviewResponse
from app.core.tracing import observe
from app.ingestion.versioning import today_iso
from app.knowledge.retrieval import search_in_docs

_SYSTEM = (
    "Bạn là chuyên gia pháp chế ngân hàng. Nhiệm vụ: đánh giá MỘT điều trong quy "
    "định nội bộ có tuân thủ các điều luật được cung cấp không.\n"
    "- verdict=violation: nội dung nội bộ TRÁI với quy định pháp luật (khác hạn mức, "
    "điều kiện, cho phép điều luật cấm...).\n"
    "- verdict=warning: không trái trực tiếp nhưng có rủi ro/thiếu ràng buộc mà luật "
    "yêu cầu, hoặc căn cứ chưa đủ rõ.\n"
    "- verdict=pass: phù hợp với quy định pháp luật.\n"
    "Chỉ kết luận dựa trên các điều luật được cung cấp, không suy diễn từ kiến thức "
    "ngoài. Trích dẫn nguyên văn phần liên quan ở cả hai phía. Trả lời tiếng Việt, JSON."
)

_SCHEMA_HINT = (
    'Định dạng JSON: {"verdict": "violation|warning|pass", '
    '"title": "<tiêu đề ngắn nêu vấn đề hoặc kết luận>", '
    '"summary": "<1-2 câu tóm tắt đánh giá>", '
    '"internal_quote": "<trích nguyên văn phần liên quan trong điều nội bộ>", '
    '"legal_chunk_id": "<id điều luật làm căn cứ chính, hoặc null>", '
    '"legal_quote": "<trích nguyên văn phần liên quan của điều luật đó>", '
    '"suggestion": "<đề xuất chỉnh sửa nếu violation/warning, ngược lại null>"}'
)

_VERDICTS = {"violation", "warning", "pass"}
_WEIGHT = {"pass": 1.0, "warning": 0.5, "violation": 0.0}
# Chặn tài liệu bất thường (nội bộ thực tế chỉ vài điều)
MAX_ARTICLES = 30


def _score(findings: list[ReviewFinding]) -> int:
    if not findings:
        return 0
    return round(100 * sum(_WEIGHT.get(f.verdict, 0.5) for f in findings) / len(findings))


def _review_article(
    article_label: str, article_text: str, against_ids: list[str], as_of: str
) -> ReviewFinding:
    chunks = search_in_docs(
        f"{article_label}: {article_text}", against_ids, top_k=4, as_of=as_of, effective_only=True
    )
    if not chunks:
        return ReviewFinding(
            verdict="pass",
            article=article_label,
            title="Không tìm thấy quy định pháp luật liên quan trực tiếp",
            summary=(
                "Không đối chiếu được với văn bản nào trong phạm vi đã chọn — "
                "cần pháp chế xác nhận điều này không thuộc phạm vi điều chỉnh."
            ),
            internal_quote=article_text[:280],
        )

    listing = "\n".join(
        f"- id={c['id']} | {c['doc_title']} — {c['article']}"
        f" (hiệu lực từ {c['valid_from'] or 'N/A'}): {c['text']}"
        for c in chunks
    )
    prompt = (
        f"{_SCHEMA_HINT}\n\n"
        f"Điều nội bộ cần đánh giá ({article_label}):\n{article_text}\n\n"
        f"Các điều luật đang hiệu lực (tại {as_of}) để đối chiếu:\n{listing}"
    )
    data = chat_json(prompt, system=_SYSTEM)

    by_id = {c["id"]: c for c in chunks}
    legal = by_id.get(data.get("legal_chunk_id")) or chunks[0]
    verdict = data.get("verdict", "warning")
    if verdict not in _VERDICTS:
        verdict = "warning"
    return ReviewFinding(
        verdict=verdict,
        article=article_label,
        title=data.get("title") or f"Đánh giá {article_label}",
        summary=data.get("summary") or "",
        internal_quote=data.get("internal_quote") or article_text[:280],
        legal_doc_id=legal["doc_id"],
        legal_ref=f"{legal['doc_title']} — {legal['article']}",
        legal_quote=data.get("legal_quote") or legal["text"][:280],
        legal_live=not legal.get("valid_to"),
        suggestion=data.get("suggestion") or None,
    )


@observe(name="review.run")
def run_review(
    internal: CorpusDocument, against_ids: list[str], as_of: str | None = None
) -> ReviewResponse:
    as_of = as_of or today_iso()
    findings = [
        _review_article(a.article, a.text, against_ids, as_of)
        for a in internal.articles[:MAX_ARTICLES]
    ]
    counts = {v: sum(1 for f in findings if f.verdict == v) for v in ("violation", "warning", "pass")}
    return ReviewResponse(
        internal_doc_id=internal.doc_id,
        internal_title=internal.title,
        as_of=as_of,
        against_doc_ids=against_ids,
        score=_score(findings),
        counts=counts,
        findings=findings,
    )
