"""Knowledge Graph trên Neo4j Aura: node văn bản + cạnh quan hệ.

Node:  (:Document {doc_id, title, doc_type, source, valid_from, valid_to})
Cạnh:  [:<một trong 13 mã REL_TYPES> {rel_type, valid_from, note, anchors}]

Cạnh **có kiểu**, không phải `[:REL {rel_type}]` như bản trước. Khác biệt không phải
thẩm mỹ: mọi truy vấn Cypher trong KG v0.5 viết theo tên cạnh
(`-[:QUY_DINH_CHI_TIET_HUONG_DAN]-`), nên với một kiểu cạnh duy nhất thì **không truy vấn
nào của spec chạy được**. Cụ thể, ca kiểm chứng bắt buộc ở §6.2 — tìm văn bản bị `BAI_BO`
mà **không** có `THAY_THE` nào trỏ tới, tức một *khoảng trống lập pháp* — cần `BAI_BO`
tồn tại như một **loại cạnh**, không phải như một giá trị chuỗi.

Vẫn giữ `rel_type` làm property để đọc ngược ra mã mà không cần suy từ tên cạnh.

Tên cạnh đi thẳng vào chuỗi Cypher (Neo4j không cho tham số hoá loại cạnh), nên nó
**phải** được kiểm trước — `_kiem_ma()` chặn ở đây, cộng với validator của
`Relationship.rel_type` chặn ở biên dữ liệu vào.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from functools import lru_cache

from neo4j import GraphDatabase

from app.core.config import settings
from app.core.schemas import (
    REL_TYPES,
    CorpusDocument,
    GraphData,
    GraphEdge,
    GraphNode,
    Relationship,
)

#: Khớp mọi cạnh quan hệ. Liệt kê tường minh thay vì `[e]` trần: một cạnh không thuộc 13
#: mã sẽ **không** lọt vào kết quả đọc, thay vì lặng lẽ đi tiếp như hồi còn `[:REL]`.
_MOI_CANH = "|".join(f":{m}" for m in REL_TYPES)


def _kiem_ma(rel_type: str) -> str:
    """Tên cạnh nội suy thẳng vào Cypher ⇒ phải chặn trước khi ghép chuỗi."""
    if rel_type not in REL_TYPES:
        raise ValueError(
            f"rel_type {rel_type!r} không thuộc 13 quan hệ của KG v0.5. "
            f"Hợp lệ: {', '.join(sorted(REL_TYPES))}"
        )
    return rel_type


@lru_cache
def get_driver():
    if not settings.neo4j_enabled:
        raise RuntimeError("Chưa cấu hình Neo4j (NEO4J_URI / NEO4J_PASSWORD).")
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )


@contextmanager
def session():
    with get_driver().session() as s:
        yield s


def ensure_constraints() -> None:
    with session() as s:
        s.run(
            "CREATE CONSTRAINT doc_id IF NOT EXISTS "
            "FOR (d:Document) REQUIRE d.doc_id IS UNIQUE"
        )


def push_corpus(docs: list[CorpusDocument], rels: list[Relationship]) -> None:
    ensure_constraints()
    with session() as s:
        # Xoá sạch để nạp lại (MVP)
        s.run("MATCH (d:Document) DETACH DELETE d")
        for d in docs:
            s.run(
                """
                MERGE (n:Document {doc_id: $doc_id})
                SET n.title=$title, n.doc_type=$doc_type, n.source=$source,
                    n.valid_from=$valid_from, n.valid_to=$valid_to
                """,
                doc_id=d.doc_id, title=d.title, doc_type=d.doc_type,
                source=d.source, valid_from=d.valid_from, valid_to=d.valid_to,
            )
        for r in rels:
            # Neo4j chỉ nhận property nguyên thủy → anchors mức điều lưu dạng JSON string
            anchors_json = (
                json.dumps([a.model_dump() for a in r.anchors], ensure_ascii=False)
                if r.anchors else None
            )
            ma = _kiem_ma(r.rel_type)
            s.run(
                f"""
                MATCH (a:Document {{doc_id: $src}}), (b:Document {{doc_id: $tgt}})
                MERGE (a)-[e:{ma}]->(b)
                SET e.rel_type=$rt, e.valid_from=$vf, e.note=$note, e.anchors=$anchors
                """,
                src=r.source_doc, tgt=r.target_doc, rt=ma,
                vf=r.valid_from, note=r.note, anchors=anchors_json,
            )


def get_graph() -> GraphData:
    """Toàn bộ đồ thị cho visualization."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    with session() as s:
        for rec in s.run(
            "MATCH (d:Document) RETURN d.doc_id AS id, d.title AS title, "
            "d.doc_type AS doc_type, d.valid_from AS vf, d.valid_to AS vt"
        ):
            nodes.append(
                GraphNode(
                    id=rec["id"], label=rec["title"], doc_type=rec["doc_type"],
                    valid_from=rec["vf"], valid_to=rec["vt"],
                )
            )
        for rec in s.run(
            f"MATCH (a:Document)-[e{_MOI_CANH}]->(b:Document) "
            "RETURN a.doc_id AS src, b.doc_id AS tgt, type(e) AS rt"
        ):
            edges.append(GraphEdge(source=rec["src"], target=rec["tgt"], rel_type=rec["rt"]))
    return GraphData(nodes=nodes, edges=edges)


CYPHER_KHOANG_TRONG = """
MATCH (moi:Document)-[:BAI_BO]->(cu:Document)
WHERE NOT (cu)<-[:THAY_THE]-(:Document)
RETURN cu.doc_id AS doc_id, cu.title AS title,
       collect(DISTINCT moi.doc_id) AS bi_bai_bo_boi
ORDER BY doc_id
"""


def khoang_trong_lap_phap() -> list[dict]:
    """Văn bản bị BÃI BỎ mà KHÔNG có văn bản nào THAY THẾ — *legislative void* (v0.5 §6.2).

    Đây là ca kiểm chứng **bắt buộc** của v0.5, và là lý do 13 cạnh phải có kiểu: với một
    kiểu cạnh duy nhất thì câu này không viết được. Khác biệt có hệ quả thật — *thay thế*
    nghĩa là có văn bản kế nhiệm, nghĩa vụ di trú sang chỗ mới; *bãi bỏ* thì nghĩa vụ có
    thể **biến mất hoàn toàn**. Tiền lệ: Colombo, Cambria & Invernici (EDBT/ICDT 2025) đo
    được tương quan r = 0,394 (p = 0,02) giữa cảnh báo loại này và can thiệp lập pháp sau đó.

    **Corpus hiện có 0 cạnh `BAI_BO`, nên hàm này trả về rỗng.** Rỗng vì chưa có dữ liệu,
    KHÁC hẳn rỗng vì không có khoảng trống nào — ghi ra đây để không ai đọc nhầm kết quả
    thành một kết luận pháp lý.
    """
    with session() as s:
        return [dict(r) for r in s.run(CYPHER_KHOANG_TRONG)]


def related_edges(doc_ids: list[str]) -> list[dict]:
    """Các cạnh (kèm nhãn quan hệ) chạm tới doc_ids — cho graph-augmented retrieval."""
    if not doc_ids:
        return []
    with session() as s:
        return [
            {"src": r["src"], "tgt": r["tgt"], "rel_type": r["rt"], "note": r["note"]}
            for r in s.run(
                f"MATCH (a:Document)-[e{_MOI_CANH}]->(b:Document) "
                "WHERE a.doc_id IN $ids OR b.doc_id IN $ids "
                "RETURN a.doc_id AS src, b.doc_id AS tgt, type(e) AS rt, e.note AS note",
                ids=doc_ids,
            )
        ]


def related_docs(doc_ids: list[str]) -> list[str]:
    """Mở rộng cross-reference: các văn bản liên quan trực tiếp tới doc_ids."""
    if not doc_ids:
        return []
    with session() as s:
        rec = s.run(
            f"MATCH (a:Document)-[{_MOI_CANH}]-(b:Document) "
            "WHERE a.doc_id IN $ids RETURN collect(DISTINCT b.doc_id) AS ids",
            ids=doc_ids,
        ).single()
        return rec["ids"] if rec else []
