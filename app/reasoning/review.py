"""Kiểm tra tuân thủ: đối chiếu từng điều của tài liệu nội bộ với luật hiện hành.

Mỗi điều nội bộ → retrieval các điều luật liên quan (chỉ trong phạm vi văn bản
đối chiếu, chỉ bản đang hiệu lực tại as_of) → Gemini phán định JSON
(violation | warning | pass) kèm trích dẫn hai phía → tổng hợp findings + điểm.

Không tìm thấy căn cứ → verdict `not_assessed` (loại khỏi mẫu số điểm) —
"không biết" phải khác "đạt". Phán định chạy temperature=0 + self-consistency
(2 lần, bất đồng → lần 3 lấy đa số) để điểm ổn định giữa các lần chạy.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

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
    "- verdict=warning: không trái trực tiếp nhưng THIẾU một ràng buộc mà điều luật "
    "được cung cấp bắt buộc, hoặc căn cứ chưa đủ rõ để kết luận.\n"
    "- verdict=pass: phù hợp với quy định pháp luật.\n"
    "Quy tắc ranh giới (áp dụng nhất quán):\n"
    "1. Nội bộ đặt con số/điều kiện KHÁC điều luật → violation "
    "(ví dụ: hạn mức 150 triệu khi luật quy định trần 100 triệu).\n"
    "2. Nội bộ im lặng về một nghĩa vụ mà điều luật được cung cấp bắt buộc phải có "
    "→ warning, nêu rõ nghĩa vụ còn thiếu.\n"
    "3. Nội bộ chỉ nhắc lại luật hoặc CHẶT HƠN luật (hạn mức thấp hơn trần, điều kiện "
    "nghiêm hơn) → pass, KHÔNG phải warning.\n"
    "4. Điều luật cung cấp không liên quan tới nội dung điều nội bộ → pass, ghi rõ "
    "trong summary là không có căn cứ liên quan trực tiếp.\n"
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
NOT_ASSESSED = "not_assessed"
# Trọng số điểm — not_assessed KHÔNG có mặt: loại khỏi mẫu số, không phải điểm 0
_WEIGHT = {"pass": 1.0, "warning": 0.5, "violation": 0.0}
# Chặn tài liệu bất thường (nội bộ thực tế chỉ vài điều)
MAX_ARTICLES = 30
# Số điều phán định song song (mỗi điều 2-3 lần gọi Gemini do self-consistency)
_MAX_WORKERS = 4


def _score(findings: list[ReviewFinding]) -> int:
    """Điểm 0-100 trên các điều ĐÃ đối chiếu được; không có điều nào → 0 (UI hiện '—')."""
    assessed = [f for f in findings if f.verdict in _WEIGHT]
    if not assessed:
        return 0
    return round(100 * sum(_WEIGHT[f.verdict] for f in assessed) / len(assessed))


def _normalize_verdict(data: dict) -> str:
    verdict = data.get("verdict", "warning")
    return verdict if verdict in _VERDICTS else "warning"


def _judge(prompt: str) -> dict:
    """Self-consistency: chạy 2 lần (temperature=0); bất đồng verdict → lần 3 lấy đa số.

    Ba lần ra ba verdict khác nhau → lấy warning (mức giữa, buộc người rà soát nhìn lại).
    """
    votes = [chat_json(prompt, system=_SYSTEM, temperature=0.0) for _ in range(2)]
    if _normalize_verdict(votes[0]) != _normalize_verdict(votes[1]):
        votes.append(chat_json(prompt, system=_SYSTEM, temperature=0.0))
    for data in votes:
        if sum(_normalize_verdict(d) == _normalize_verdict(data) for d in votes) >= 2:
            return data
    # Ba lần ra ba verdict khác nhau → chắc chắn có warning trong đó (3 mức distinct)
    return next(d for d in votes if _normalize_verdict(d) == "warning")


def _review_article(
    article_label: str, article_text: str, against_ids: list[str], as_of: str
) -> ReviewFinding:
    chunks = search_in_docs(
        f"{article_label}: {article_text}", against_ids, top_k=4, as_of=as_of, effective_only=True
    )
    if not chunks:
        return ReviewFinding(
            verdict=NOT_ASSESSED,
            article=article_label,
            title="Chưa đối chiếu được — không tìm thấy căn cứ pháp lý liên quan",
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
    data = _judge(prompt)

    by_id = {c["id"]: c for c in chunks}
    legal = by_id.get(data.get("legal_chunk_id")) or chunks[0]
    return ReviewFinding(
        verdict=_normalize_verdict(data),
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
    articles = internal.articles[:MAX_ARTICLES]
    # Song song theo điều — bù lại chi phí self-consistency (2-3 lần gọi mỗi điều)
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        findings = list(
            pool.map(lambda a: _review_article(a.article, a.text, against_ids, as_of), articles)
        )
    counts = {
        v: sum(1 for f in findings if f.verdict == v)
        for v in ("violation", "warning", "pass", NOT_ASSESSED)
    }
    return ReviewResponse(
        internal_doc_id=internal.doc_id,
        internal_title=internal.title,
        as_of=as_of,
        against_doc_ids=against_ids,
        score=_score(findings),
        counts=counts,
        findings=findings,
    )
