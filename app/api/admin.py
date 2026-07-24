"""Endpoint vận hành: kích hoạt ingest, kiểm tra sức khoẻ."""
from fastapi import APIRouter, Depends, HTTPException

from app.core import appdb
from app.core.auth import AuthUser, require_admin
from app.core.config import settings

router = APIRouter(tags=["admin"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "gemini_configured": bool(settings.gemini_api_key),
        "neo4j_configured": settings.neo4j_enabled,
        "supabase_auth": settings.supabase_auth_enabled,
        "queue": settings.queue_enabled,
        "lancedb": "cloud" if settings.lancedb_cloud_enabled else "local",
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
        from app.ingestion.pipeline import main as run_ingest

        run_ingest(corpus_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if appdb.enabled() and user.token:
        appdb.log_audit(
            user.token, user.id, action="ingest",
            detail={"corpus": corpus_path or "data/corpus.sample.json"},
        )
    return {"status": "ok", "corpus": corpus_path or "data/corpus.sample.json"}
