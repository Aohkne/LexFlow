"""Endpoint vận hành: kích hoạt ingest, kiểm tra sức khoẻ."""
from fastapi import APIRouter, HTTPException

from app.core.config import settings

router = APIRouter(tags=["admin"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "gemini_configured": bool(settings.gemini_api_key),
        "neo4j_configured": settings.neo4j_enabled,
    }


@router.post("/ingest")
def ingest_endpoint(corpus_path: str | None = None) -> dict:
    try:
        from app.ingestion.pipeline import main as run_ingest

        run_ingest(corpus_path)
        return {"status": "ok", "corpus": corpus_path or "data/corpus.sample.json"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
