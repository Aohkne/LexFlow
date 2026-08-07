"""Pipeline ingest: nạp văn bản pháp lý → LanceDB (vector + full-text) và Neo4j.

Chạy:  uv run python -m app.ingestion [đường_dẫn_corpus.json]
Mặc định đọc data/corpus.sample.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.core import vectordb
from app.core.config import LANCEDB_TABLE, settings
from app.core.llm import EMBED_DIM, embed_documents
from app.core.schemas import CorpusDocument, Relationship, nhan_quan_he
from app.ingestion.versioning import effective_dates

_BATCH = 32


def load_corpus(path: str | Path) -> tuple[list[CorpusDocument], list[Relationship]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    docs = [CorpusDocument.model_validate(d) for d in raw.get("documents", [])]
    rels = [Relationship.model_validate(r) for r in raw.get("relationships", [])]
    return docs, rels


# Điều dài hơn ngưỡng này thì tách theo Khoản (giới hạn embedding + độ chính xác retrieval)
_MAX_CHUNK = 2000
_KHOAN_RE = re.compile(r"^(\d+)\.\s")


def _split_khoan(article: str, text: str) -> list[tuple[str, str]]:
    """Tách điều dài thành các chunk mức Khoản, gộp khoản liền kề tới ~_MAX_CHUNK.

    Trả về [(nhãn, text)] — nhãn kiểu "Điều 26 Khoản 1-3". Điều không có
    cấu trúc khoản thì cắt theo cửa sổ ký tự ("Điều 26 (phần 2)").
    """
    if len(text) <= _MAX_CHUNK:
        return [(article, text)]

    # Gom dòng theo khoản: phần mở đầu (tiêu đề điều...) dính vào khoản đầu tiên
    pieces: list[tuple[str | None, list[str]]] = [(None, [])]
    for ln in text.split("\n"):
        m = _KHOAN_RE.match(ln)
        if m:
            pieces.append((m.group(1), [ln]))
        else:
            pieces[-1][1].append(ln)
    khoan = [(num, "\n".join(lines).strip()) for num, lines in pieces if "\n".join(lines).strip()]

    if len(khoan) <= 1:  # không có cấu trúc khoản → cắt cửa sổ
        chunks = [text[i : i + _MAX_CHUNK] for i in range(0, len(text), _MAX_CHUNK)]
        return [(f"{article} (phần {i + 1})", t) for i, t in enumerate(chunks)]

    # Gộp khoản liền kề cho tới ngưỡng
    out: list[tuple[str, str]] = []
    buf: list[tuple[str | None, str]] = []
    size = 0
    for num, t in khoan:
        if buf and size + len(t) > _MAX_CHUNK:
            out.append((_khoan_label(article, buf), "\n".join(x for _, x in buf)))
            buf, size = [], 0
        buf.append((num, t))
        size += len(t)
    if buf:
        out.append((_khoan_label(article, buf), "\n".join(x for _, x in buf)))
    return out


def _khoan_label(article: str, buf: list[tuple[str | None, str]]) -> str:
    nums = [n for n, _ in buf if n]
    if not nums:
        return article
    return f"{article} Khoản {nums[0]}" if len(nums) == 1 else f"{article} Khoản {nums[0]}-{nums[-1]}"


def build_chunks(docs: list[CorpusDocument]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        for art in doc.articles:
            vf, vt, sup = effective_dates(
                art.valid_from, art.valid_to, art.superseded,
                doc.valid_from, doc.valid_to,
            )
            for label, chunk_text in _split_khoan(art.article, art.text):
                rows.append(
                    {
                        "id": f"{doc.doc_id}::{label}",
                        "doc_id": doc.doc_id,
                        "doc_title": doc.title,
                        "doc_type": doc.doc_type,
                        "source": doc.source,
                        "article": label,
                        "text": chunk_text,
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


# Nhãn lấy từ `app.core.schemas.REL_TYPES` — nguồn sự thật DUY NHẤT cho 13 quan hệ.
# Trước đây bảng này bị chép ở ba nơi nên sửa một chỗ không kéo theo hai chỗ kia.


def build_change_events(docs: list[CorpusDocument], rels: list[Relationship]) -> list[dict]:
    """Chuyển relationships của corpus thành sự kiện cảnh báo thay đổi (painpoint 4)."""
    titles = {d.doc_id: d.title for d in docs}
    events = []
    for r in rels:
        verb = nhan_quan_he(r.rel_type)
        desc = f"{titles.get(r.source_doc, r.source_doc)} {verb} {titles.get(r.target_doc, r.target_doc)}"
        if r.note:
            desc += f" — {r.note}"
        events.append(
            {
                "doc_id": r.target_doc,
                "source_doc_id": r.source_doc,
                "rel_type": r.rel_type,
                "description": desc,
                "effective_date": r.valid_from,
            }
        )
    return events


def ingest_docs(docs: list[CorpusDocument], rels: list[Relationship]) -> int:
    """Lõi ingest: chunks → LanceDB (+ Neo4j nếu có). Trả về số chunk."""
    rows = build_chunks(docs)
    print(f"[ingest] {len(docs)} văn bản → {len(rows)} chunk. Đang embedding (Gemini)...")
    n = write_lancedb(rows)
    target = settings.lancedb_uri if settings.lancedb_cloud_enabled else settings.lancedb_path
    print(f"[ingest] Đã ghi {n} chunk vào LanceDB ({target}), dim={EMBED_DIM}.")

    if settings.neo4j_enabled:
        from app.ingestion.bac_cau import quy_ve_doc_id
        from app.knowledge.graph import push_corpus

        # Quy cạnh về `doc_id` NGAY TRƯỚC khi nạp, không phải lúc đọc nguồn: cạnh đọc từ vbpl
        # khoá bằng số hiệu, và Cypher `MATCH` không khớp thì bỏ qua câu lệnh **trong im lặng**.
        canh, rong, cb = quy_ve_doc_id(rels, docs)
        for c in cb:
            print(f"[ingest] cảnh báo: {c}")
        push_corpus(docs, canh, rong)
        print(
            f"[ingest] Đã nạp {len(docs)} node + {len(rong)} node RỖNG (chưa có toàn văn) "
            f"+ {len(canh)} cạnh vào Neo4j Aura."
        )
    else:
        print("[ingest] Bỏ qua Neo4j (chưa cấu hình NEO4J_URI/PASSWORD).")
    return n


def main(corpus_path: str | None = None) -> tuple[list[CorpusDocument], list[Relationship]]:
    path = corpus_path or "data/corpus.sample.json"
    print(f"[ingest] Đọc corpus: {path}")
    docs, rels = load_corpus(path)
    ingest_docs(docs, rels)
    return docs, rels
