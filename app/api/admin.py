"""Endpoint vận hành: kích hoạt ingest, kiểm tra sức khoẻ."""
from fastapi import APIRouter, Depends, HTTPException

from app.core import appdb
from app.core.auth import AuthUser, require_admin
from app.core.config import settings

router = APIRouter(tags=["admin"])


@router.get("/health")
def health() -> dict:
    """Tình trạng vận hành. HTTP luôn 200 — đây là tín hiệu cho người đọc sau mỗi deploy
    (`docs/ROADMAP-SPRINT.md`), không phải probe của Cloud Run.

    `status` xuống `degraded` khi lớp phủ được BẬT mà artefact không nạp được: mọi thứ khác
    vẫn chạy (fail-open có chủ đích), nhưng badge hiệu lực cấp khoản vắng mặt trên toàn sản
    phẩm — thứ trước đây không có cách nào phát hiện ngoài việc tự đi hỏi một câu.
    """
    from app.knowledge.lop_phu import tinh_trang

    overlay = tinh_trang()
    return {
        "status": "degraded" if overlay.get("bat") and not overlay.get("nap") else "ok",
        "gemini_configured": bool(settings.gemini_api_key),
        "neo4j_configured": settings.neo4j_enabled,
        "supabase_auth": settings.supabase_auth_enabled,
        "queue": settings.queue_enabled,
        "lancedb": "cloud" if settings.lancedb_cloud_enabled else "local",
        "overlay": overlay,
    }


@router.post("/ingest")
async def ingest_endpoint(
    corpus_path: str | None = None,
    user: AuthUser = Depends(require_admin),
) -> dict:
    if settings.queue_enabled:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            job = await pool.enqueue_job("ingest_corpus", corpus_path)
        finally:
            await pool.aclose()
        return {"status": "queued", "job_id": job.job_id if job else None}

    # Dev mode (không có Redis): chạy đồng bộ
    try:
        from app.ingestion.pipeline import build_change_events, main as run_ingest

        docs, rels = run_ingest(corpus_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    n_events = 0
    if appdb.enabled() and user.token:
        # Painpoint 4: quan hệ THAY_THE/SUA_DOI trong corpus → sự kiện cảnh báo
        n_events = appdb.record_change_events(user.token, build_change_events(docs, rels))
        appdb.log_audit(
            user.token, user.id, action="ingest",
            detail={"corpus": corpus_path or "data/corpus.sample.json", "n_events": n_events},
        )
    return {
        "status": "ok",
        "corpus": corpus_path or "data/corpus.sample.json",
        "change_events": n_events,
    }
