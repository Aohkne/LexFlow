"""Retrieval hybrid: vector (Gemini) + BM25 (LanceDB FTS) → RRF → lọc hiệu lực.

Đây là điểm khác biệt với RAG vector thuần: chỉ trả về điều khoản ĐANG hiệu lực
tại thời điểm `as_of`, và có thể mở rộng qua knowledge graph (cross-reference).
"""
from __future__ import annotations

import lancedb

from app.core.config import LANCEDB_TABLE, settings
from app.core.llm import embed_query
from app.ingestion.versioning import is_effective

_RRF_K = 60  # hằng số Reciprocal Rank Fusion


def _open_table():
    db = lancedb.connect(settings.lancedb_path)
    return db.open_table(LANCEDB_TABLE)


def _rrf(vector_hits: list[dict], fts_hits: list[dict], k: int) -> list[dict]:
    """Trộn 2 bảng xếp hạng bằng Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    rows: dict[str, dict] = {}
    for ranked in (vector_hits, fts_hits):
        for rank, row in enumerate(ranked):
            rid = row["id"]
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (_RRF_K + rank)
            rows[rid] = row
    ordered = sorted(scores, key=lambda r: scores[r], reverse=True)
    return [rows[r] for r in ordered[:k]]


def hybrid_search(
    query: str, *, top_k: int = 6, as_of: str | None = None, effective_only: bool = True
) -> list[dict]:
    tbl = _open_table()
    pool = max(top_k * 3, 15)

    qv = embed_query(query)
    vector_hits = tbl.search(qv).limit(pool).to_list()
    try:
        fts_hits = tbl.search(query, query_type="fts").limit(pool).to_list()
    except Exception:
        fts_hits = []  # FTS chưa sẵn sàng → chỉ dùng vector

    merged = _rrf(vector_hits, fts_hits, pool)

    if effective_only:
        merged = [
            r
            for r in merged
            if is_effective(r.get("valid_from"), r.get("valid_to"), r.get("superseded", False), as_of)
        ]
    return merged[:top_k]


def baseline_vector_search(query: str, *, top_k: int = 6) -> list[dict]:
    """RAG vector thuần (KHÔNG lọc hiệu lực, KHÔNG hybrid) — dùng cho benchmark."""
    tbl = _open_table()
    qv = embed_query(query)
    return tbl.search(qv).limit(top_k).to_list()
