"""ARQ worker — tác vụ nền (compose/self-host; Cloud Run dùng sync ingest hoặc Jobs).

Chạy:  arq app.worker.WorkerSettings
Tác vụ hiện có: ingest_corpus. Sẽ thêm: change alerts định kỳ (painpoint 4).
"""
from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

from app.core.config import settings


async def ingest_corpus(ctx: dict[str, Any], corpus_path: str | None = None) -> dict:
    from app.ingestion.pipeline import main as run_ingest

    run_ingest(corpus_path)
    return {"status": "ok", "corpus": corpus_path or "data/corpus.sample.json"}


class WorkerSettings:
    functions = [ingest_corpus]
    redis_settings = RedisSettings.from_dsn(settings.redis_url or "redis://localhost:6379")
    # Ingest embedding cả corpus qua Gemini có thể lâu — nới timeout
    job_timeout = 1800
