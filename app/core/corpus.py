"""Corpus canonical dùng chung cho luồng duyệt và API đọc văn bản.

Nguồn sự thật: `legal-docs/corpus.json` trên Supabase Storage; fallback về
`data/corpus.real.json` đóng gói trong image (fail-open khi Storage lỗi/RLS chặn).
Cache TTL ngắn để mỗi lượt xem trang không tốn một round-trip Storage.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.core import appdb

CANONICAL = "corpus.json"
LOCAL_FALLBACK = Path("data/corpus.real.json")

_CACHE_TTL = 60.0  # giây
_cache: tuple[float, dict] | None = None  # (loaded_at, corpus)


def load_canonical(token: str) -> dict:
    """Đọc corpus canonical (không cache): Storage → fallback file local → rỗng."""
    raw = None
    if appdb.enabled():
        try:
            raw = appdb.download_storage(token, CANONICAL)
        except Exception:  # noqa: BLE001 — Storage lỗi mạng/RLS: fail-open về file local
            raw = None
    if raw is not None:
        return json.loads(raw.decode("utf-8"))
    if LOCAL_FALLBACK.exists():
        return json.loads(LOCAL_FALLBACK.read_text(encoding="utf-8"))
    return {"documents": [], "relationships": []}


def get_corpus_cached(token: str) -> dict:
    """Bản cache của corpus (nội dung không phụ thuộc user — 1 entry toàn cục)."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _CACHE_TTL:
        return _cache[1]
    corpus = load_canonical(token)
    _cache = (now, corpus)
    return corpus


def invalidate_cache() -> None:
    """Gọi sau khi approve ghi corpus mới lên Storage."""
    global _cache
    _cache = None
