"""Luồng duyệt văn bản (maker-checker):

upload (PDF/HTML → Storage + extract → pending) → admin xem/sửa JSON →
approve (merge corpus canonical trên Storage → re-ingest full) / reject.

Corpus canonical: `legal-docs/corpus.json` trên Supabase Storage; nếu chưa có,
khởi điểm từ `data/corpus.real.json` đóng gói trong image.
"""
from __future__ import annotations

import json
import mimetypes
import tempfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel

from app.core import appdb, corpus as corpus_store
from app.core.auth import AuthUser, get_current_user, require_admin
from app.core.config import settings
from app.core.schemas import (
    CorpusDocument,
    DocumentDetail,
    DocumentSummary,
    Relationship,
    SourceFile,
)
from app.ingestion.versioning import is_effective

router = APIRouter(prefix="/documents", tags=["documents"])

_CANONICAL = corpus_store.CANONICAL


def _require_supabase() -> None:
    if not appdb.enabled():
        raise HTTPException(status_code=503, detail="Luồng duyệt văn bản cần cấu hình Supabase")


@router.get("", response_model=list[DocumentSummary])
def list_documents(user: AuthUser = Depends(get_current_user)) -> list[DocumentSummary]:
    """Thư viện văn bản: metadata + trạng thái hiệu lực (mọi user đăng nhập)."""
    corpus = corpus_store.get_corpus_cached(user.token)
    out = []
    for d in corpus.get("documents", []):
        effective = is_effective(d.get("valid_from"), d.get("valid_to"), False)
        out.append(
            DocumentSummary(
                doc_id=d["doc_id"],
                title=d.get("title", d["doc_id"]),
                doc_type=d.get("doc_type", ""),
                source=d.get("source", "external"),
                valid_from=d.get("valid_from"),
                valid_to=d.get("valid_to"),
                n_articles=len(d.get("articles", [])),
                status="con_hieu_luc" if effective else "het_hieu_luc",
            )
        )
    return out


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document_detail(doc_id: str, user: AuthUser = Depends(get_current_user)) -> DocumentDetail:
    """Toàn văn một văn bản + quan hệ hai chiều (cho trình xem/lược đồ)."""
    corpus = corpus_store.get_corpus_cached(user.token)
    docs = {d["doc_id"]: d for d in corpus.get("documents", [])}
    raw = docs.get(doc_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Không có văn bản {doc_id}")

    rels = [Relationship.model_validate(r) for r in corpus.get("relationships", [])]
    rels_out = [r for r in rels if r.source_doc == doc_id]
    rels_in = [r for r in rels if r.target_doc == doc_id]
    related_ids = {r.source_doc for r in rels_in} | {r.target_doc for r in rels_out}
    titles = {i: docs[i].get("title", i) for i in related_ids if i in docs}

    doc = CorpusDocument.model_validate(raw)
    meta = doc.model_dump(exclude={"articles", "provisions", "source_files"})

    tac_dong = []
    if settings.overlay_router:
        from app.ingestion.versioning import today_iso
        from app.knowledge.lop_phu import tac_dong_cua_van_ban

        tac_dong = tac_dong_cua_van_ban(doc_id, today_iso())

    return DocumentDetail(
        **meta,
        source_files=doc.source_files + _uploaded_original(user, doc_id),
        articles=doc.articles,
        provisions=doc.provisions,
        relationships_out=rels_out,
        relationships_in=rels_in,
        doc_titles=titles,
        tac_dong=tac_dong,
    )


def _uploaded_original(user: AuthUser, doc_id: str) -> list[SourceFile]:
    """File gốc đã upload qua luồng duyệt (nếu có) — trỏ về endpoint tải của chính API này.

    Không có Supabase thì bỏ qua: thư viện vẫn xem được, chỉ là không có bản gốc để tải.
    """
    if not appdb.enabled():
        return []
    try:
        row = appdb.get_document(user.token, doc_id)
    except Exception:  # noqa: BLE001 — thiếu bản ghi không được làm hỏng trang xem
        return []
    path = (row or {}).get("storage_path")
    if not path:
        return []
    return [
        SourceFile(
            ten=Path(path).name,
            url=f"/documents/{quote(doc_id, safe='')}/download",
        )
    ]


@router.get("/{doc_id}/download")
def download_original(doc_id: str, user: AuthUser = Depends(get_current_user)) -> Response:
    """Tải file gốc đã upload cho văn bản này."""
    _require_supabase()
    row = appdb.get_document(user.token, doc_id)
    path = (row or {}).get("storage_path")
    if not path:
        raise HTTPException(status_code=404, detail=f"Văn bản {doc_id} chưa có file gốc")
    content = appdb.download_storage(user.token, path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Không đọc được file gốc của {doc_id}")
    name = Path(path).name
    media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        # filename* (RFC 5987) vì tên file văn bản luật hay có dấu tiếng Việt
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )


@router.post("/upload")
async def upload_document(
    file: UploadFile,
    source: str = "external",
    user: AuthUser = Depends(require_admin),
) -> dict:
    """Upload file văn bản → lưu Storage + extract → bản ghi pending chờ duyệt."""
    _require_supabase()
    if source not in {"external", "internal"}:
        raise HTTPException(status_code=400, detail="source phải là external|internal")
    content = await file.read()
    filename = file.filename or "upload.bin"
    storage_path = f"uploads/{filename}"
    appdb.upload_storage(
        user.token, storage_path, content, file.content_type or "application/octet-stream"
    )

    # Extract (tái dùng extractor CLI) — ghi file tạm đúng đuôi để chọn parser
    from app.ingestion.extract import extract_document

    suffix = Path(filename).suffix or ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        doc = extract_document(tmp_path, source=source)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Extract thất bại: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    appdb.insert_document(
        user.token,
        {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "doc_type": doc.doc_type,
            "source": source,
            "status": "pending",
            "valid_from": doc.valid_from,
            "storage_path": storage_path,
            "uploaded_by": user.id,
            "extracted": doc.model_dump(),
        },
    )
    appdb.log_audit(
        user.token, user.id, action="doc_upload",
        detail={"doc_id": doc.doc_id, "file": filename, "n_articles": len(doc.articles)},
    )
    return {
        "doc_id": doc.doc_id,
        "title": doc.title,
        "n_articles": len(doc.articles),
        "status": "pending",
    }


class ApproveRequest(BaseModel):
    document: dict | None = None  # JSON đã được admin sửa; None = dùng bản extracted
    relationships: list[dict] = []  # quan hệ mới (THAY_THE/SUA_DOI/...) gán khi duyệt


@router.post("/{doc_id}/approve")
def approve_document(
    doc_id: str,
    body: ApproveRequest | None = None,
    user: AuthUser = Depends(require_admin),
) -> dict:
    """Duyệt văn bản: merge vào corpus canonical → re-ingest → approved + audit."""
    _require_supabase()
    row = appdb.get_document(user.token, doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Không có bản ghi {doc_id}")
    doc_json = (body.document if body else None) or row.get("extracted")
    if not doc_json:
        raise HTTPException(status_code=400, detail="Chưa có JSON extracted để duyệt")

    try:
        doc = CorpusDocument.model_validate(doc_json)
        new_rels = [Relationship.model_validate(r) for r in (body.relationships if body else [])]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"JSON không hợp lệ: {exc}") from exc

    from app.ingestion.pipeline import kiem_doc_id

    try:
        kiem_doc_id(doc.doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    corpus = corpus_store.load_canonical(user.token)
    corpus["documents"] = [d for d in corpus.get("documents", []) if d.get("doc_id") != doc.doc_id]
    corpus["documents"].append(doc.model_dump())
    existing = {(r["source_doc"], r["target_doc"], r["rel_type"]) for r in corpus.get("relationships", [])}
    for r in new_rels:
        if (r.source_doc, r.target_doc, r.rel_type) not in existing:
            corpus.setdefault("relationships", []).append(r.model_dump())

    appdb.upload_storage(
        user.token, _CANONICAL,
        json.dumps(corpus, ensure_ascii=False, indent=1).encode("utf-8"), "application/json",
    )
    corpus_store.invalidate_cache()

    from app.ingestion.pipeline import build_change_events, ingest_one_doc

    docs = [CorpusDocument.model_validate(d) for d in corpus["documents"]]
    rels = [Relationship.model_validate(r) for r in corpus.get("relationships", [])]
    try:
        n_chunks = ingest_one_doc(doc, rels, docs)
    except Exception as exc:  # noqa: BLE001 — mọi lỗi nạp đều cùng một cách xử
        # Canonical trên Storage đã cập nhật, chỉ mục thì chưa. Thứ tự này là cố ý: thư viện
        # thấy văn bản mà tra chưa ra thì chat đơn giản không trích dẫn nó — không có trích
        # dẫn gãy. Đảo lại mới tệ: retrieval có văn bản mà trang xem trả 404.
        raise HTTPException(
            status_code=502,
            detail=(
                f"Đã cập nhật corpus canonical nhưng chưa nạp được chỉ mục: {exc}. "
                "Bấm duyệt lại văn bản này — thao tác lặp lại vô hại."
            ),
        ) from exc

    appdb.update_document(
        user.token, doc.doc_id,
        {"status": "approved", "reviewed_by": user.id, "extracted": doc.model_dump()},
    )
    n_events = appdb.record_change_events(user.token, build_change_events(docs, rels))
    appdb.log_audit(
        user.token, user.id, action="doc_approve",
        detail={"doc_id": doc.doc_id, "n_chunks": n_chunks, "n_events": n_events},
    )
    return {"status": "approved", "doc_id": doc.doc_id, "chunks": n_chunks, "change_events": n_events}


@router.post("/{doc_id}/reject")
def reject_document(doc_id: str, user: AuthUser = Depends(require_admin)) -> dict:
    _require_supabase()
    if appdb.get_document(user.token, doc_id) is None:
        raise HTTPException(status_code=404, detail=f"Không có bản ghi {doc_id}")
    appdb.update_document(user.token, doc_id, {"status": "rejected", "reviewed_by": user.id})
    appdb.log_audit(user.token, user.id, action="doc_reject", detail={"doc_id": doc_id})
    return {"status": "rejected", "doc_id": doc_id}
