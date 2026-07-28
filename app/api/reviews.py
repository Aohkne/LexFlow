"""API kiểm tra tuân thủ tài liệu nội bộ (màn Kiểm tra trên web)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core import appdb, corpus as corpus_store
from app.core.auth import AuthUser, get_current_user
from app.core.schemas import CorpusDocument, ReviewRequest, ReviewResponse
from app.ingestion.versioning import is_effective, today_iso
from app.reasoning.review import run_review

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=ReviewResponse)
def create_review(req: ReviewRequest, user: AuthUser = Depends(get_current_user)) -> ReviewResponse:
    """Đối chiếu tài liệu nội bộ với văn bản pháp luật tại một mốc thời gian."""
    corpus = corpus_store.get_corpus_cached(user.token)
    docs = {d["doc_id"]: d for d in corpus.get("documents", [])}

    raw = docs.get(req.internal_doc_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Không có văn bản {req.internal_doc_id}")
    internal = CorpusDocument.model_validate(raw)
    if internal.source != "internal":
        raise HTTPException(
            status_code=400, detail=f"{req.internal_doc_id} không phải tài liệu nội bộ"
        )

    as_of = req.as_of or today_iso()
    against = req.against_doc_ids or [
        d["doc_id"]
        for d in docs.values()
        if d.get("source") == "external"
        and is_effective(d.get("valid_from"), d.get("valid_to"), False, as_of)
    ]
    unknown = [i for i in against if i not in docs]
    if unknown:
        raise HTTPException(status_code=404, detail=f"Không có văn bản {', '.join(unknown)}")

    try:
        resp = run_review(internal, against, as_of)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Lưu phiên + audit best-effort (user.token rỗng ở dev mode)
    if appdb.enabled() and user.token:
        resp.session_id = appdb.save_review_session(
            user.token,
            user.id,
            internal_doc_id=resp.internal_doc_id,
            internal_title=resp.internal_title,
            against_doc_ids=resp.against_doc_ids,
            as_of=resp.as_of,
            score=resp.score,
            counts=resp.counts,
            findings=[f.model_dump() for f in resp.findings],
        )
        appdb.log_audit(
            user.token, user.id, action="review_run",
            detail={
                "internal_doc_id": resp.internal_doc_id,
                "against": resp.against_doc_ids,
                "as_of": resp.as_of,
                "score": resp.score,
                "counts": resp.counts,
            },
        )
    return resp
