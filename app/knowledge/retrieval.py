"""Retrieval hybrid: vector (Gemini) + BM25 (LanceDB FTS) → RRF → lọc hiệu lực.

Đây là điểm khác biệt với RAG vector thuần: chỉ trả về điều khoản ĐANG hiệu lực
tại thời điểm `as_of`, và có thể mở rộng qua knowledge graph (cross-reference).
"""
from __future__ import annotations

from functools import lru_cache

from app.core import vectordb
from app.core.config import LANCEDB_TABLE
from app.core.llm import embed_query
from app.core.tracing import observe
from app.ingestion.versioning import is_effective

_RRF_K = 60  # hằng số Reciprocal Rank Fusion


def _open_table():
    return vectordb.connect().open_table(LANCEDB_TABLE)


@lru_cache(maxsize=256)
def _qv(query: str) -> tuple[float, ...]:
    """Cache embedding câu hỏi — hybrid + graph-augment dùng chung 1 lần gọi Gemini."""
    return tuple(embed_query(query))


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


@observe(name="retrieval.hybrid", as_type="retriever")
def hybrid_search(
    query: str, *, top_k: int = 6, as_of: str | None = None, effective_only: bool = True
) -> list[dict]:
    tbl = _open_table()
    pool = max(top_k * 3, 15)

    qv = list(_qv(query))
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


def search_in_docs(
    query: str, doc_ids: list[str], *, top_k: int = 3,
    as_of: str | None = None, effective_only: bool = True,
) -> list[dict]:
    """Hybrid search (vector + BM25, RRF) giới hạn trong một nhóm văn bản.

    Đường retrieval của review tuân thủ + mở rộng qua graph — cần cả nhánh từ khoá
    chính xác ("150 triệu", tên định chế) chứ không chỉ tương đồng ngữ nghĩa.
    """
    if not doc_ids:
        return []
    tbl = _open_table()
    ids = ", ".join(f"'{d}'" for d in doc_ids)
    where = f"doc_id IN ({ids})"
    pool = max(top_k * 2, 8)

    vector_hits = (
        tbl.search(list(_qv(query))).where(where, prefilter=True).limit(pool).to_list()
    )
    try:
        fts_hits = (
            tbl.search(query, query_type="fts").where(where, prefilter=True).limit(pool).to_list()
        )
    except Exception:
        fts_hits = []  # FTS chưa sẵn sàng → chỉ dùng vector

    hits = _rrf(vector_hits, fts_hits, pool)
    if effective_only:
        hits = [
            r for r in hits
            if is_effective(r.get("valid_from"), r.get("valid_to"), r.get("superseded", False), as_of)
        ]
    return hits[:top_k]


@observe(name="retrieval.graph_augmented", as_type="retriever")
def graph_augmented_search(
    query: str, *, top_k: int = 6, as_of: str | None = None,
    effective_only: bool = True, extra_k: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Hybrid search + mở rộng 1-hop qua knowledge graph.

    Trả (chunks, edges): chunks gồc + tối đa `extra_k` chunk từ văn bản liên quan
    (vẫn lọc hiệu lực); edges là các quan hệ THAY_THE/SUA_DOI/... để đưa vào prompt.
    Graph lỗi/chưa cấu hình → trả kết quả hybrid như thường (không làm hỏng chat).
    """
    base = hybrid_search(query, top_k=top_k, as_of=as_of, effective_only=effective_only)
    try:
        from app.knowledge.graph import related_edges

        seed = sorted({r["doc_id"] for r in base})
        edges = related_edges(seed)
    except Exception:  # noqa: BLE001 — Neo4j down không được chặn câu trả lời
        return base, []
    related = sorted(({e["src"] for e in edges} | {e["tgt"] for e in edges}) - set(seed))
    extra = search_in_docs(query, related, top_k=extra_k, as_of=as_of, effective_only=effective_only)
    seen = {r["id"] for r in base}
    merged = base + [r for r in extra if r["id"] not in seen]
    return merged, edges


def baseline_vector_search(query: str, *, top_k: int = 6) -> list[dict]:
    """RAG vector thuần (KHÔNG lọc hiệu lực, KHÔNG hybrid) — dùng cho benchmark."""
    tbl = _open_table()
    return tbl.search(list(_qv(query))).limit(top_k).to_list()
