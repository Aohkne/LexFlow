"""Pipeline ingest: nạp văn bản pháp lý → LanceDB (vector + full-text) và Neo4j.

Chạy:  uv run python -m app.ingestion [đường_dẫn_corpus.json]
Mặc định đọc data/corpus.sample.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core import vectordb
from app.core.config import LANCEDB_TABLE, settings
from app.core.llm import EMBED_DIM, embed_documents
from app.core.schemas import CorpusDocument, Relationship
from app.ingestion.versioning import effective_dates

_BATCH = 32


def load_corpus(path: str | Path) -> tuple[list[CorpusDocument], list[Relationship]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    docs = [CorpusDocument.model_validate(d) for d in raw.get("documents", [])]
    rels = [Relationship.model_validate(r) for r in raw.get("relationships", [])]
    return docs, rels


def build_chunks(docs: list[CorpusDocument]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        for art in doc.articles:
            vf, vt, sup = effective_dates(
                art.valid_from, art.valid_to, art.superseded,
                doc.valid_from, doc.valid_to,
            )
            rows.append(
                {
                    "id": f"{doc.doc_id}::{art.article}",
                    "doc_id": doc.doc_id,
                    "doc_title": doc.title,
                    "doc_type": doc.doc_type,
                    "source": doc.source,
                    "article": art.article,
                    "text": art.text,
                    "valid_from": vf or "",
                    "valid_to": vt or "",
                    "superseded": bool(sup),
                }
            )
    return rows


def _embed_rows(rows: list[dict]) -> None:
    for i in range(0, len(rows), _BATCH):
        batch = rows[i : i + _BATCH]
        vectors = embed_documents([f"{r['doc_title']} — {r['article']}: {r['text']}" for r in batch])
        for r, v in zip(batch, vectors):
            r["vector"] = v


def write_lancedb(rows: list[dict]) -> int:
    if not rows:
        return 0
    _embed_rows(rows)
    db = vectordb.connect()
    tbl = db.create_table(LANCEDB_TABLE, data=rows, mode="overwrite")
    # Full-text (BM25) index cho hybrid search — cloud dùng FTS native, không nhận replace=
    if settings.lancedb_cloud_enabled:
        tbl.create_fts_index("text")
    else:
        tbl.create_fts_index("text", replace=True)
    return len(rows)


def main(corpus_path: str | None = None) -> None:
    path = corpus_path or "data/corpus.sample.json"
    print(f"[ingest] Đọc corpus: {path}")
    docs, rels = load_corpus(path)
    rows = build_chunks(docs)
    print(f"[ingest] {len(docs)} văn bản → {len(rows)} chunk. Đang embedding (Gemini)...")
    n = write_lancedb(rows)
    target = settings.lancedb_uri if settings.lancedb_cloud_enabled else settings.lancedb_path
    print(f"[ingest] Đã ghi {n} chunk vào LanceDB ({target}), dim={EMBED_DIM}.")

    if settings.neo4j_enabled:
        from app.knowledge.graph import push_corpus

        push_corpus(docs, rels)
        print(f"[ingest] Đã nạp {len(docs)} node + {len(rels)} cạnh vào Neo4j Aura.")
    else:
        print("[ingest] Bỏ qua Neo4j (chưa cấu hình NEO4J_URI/PASSWORD).")
