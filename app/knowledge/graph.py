"""Knowledge Graph trên Neo4j Aura: node văn bản + cạnh quan hệ.

Node:  (:Document {doc_id, title, doc_type, source, valid_from, valid_to})
Cạnh:  [:THAY_THE|:SUA_DOI|:HUONG_DAN|:DAN_CHIEU {valid_from, note}]
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from neo4j import GraphDatabase

from app.core.config import settings
from app.core.schemas import CorpusDocument, GraphData, GraphEdge, GraphNode, Relationship


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
            s.run(
                """
                MATCH (a:Document {doc_id: $src}), (b:Document {doc_id: $tgt})
                MERGE (a)-[e:REL {rel_type: $rt}]->(b)
                SET e.valid_from=$vf, e.note=$note
                """,
                src=r.source_doc, tgt=r.target_doc, rt=r.rel_type,
                vf=r.valid_from, note=r.note,
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
            "MATCH (a:Document)-[e:REL]->(b:Document) "
            "RETURN a.doc_id AS src, b.doc_id AS tgt, e.rel_type AS rt"
        ):
            edges.append(GraphEdge(source=rec["src"], target=rec["tgt"], rel_type=rec["rt"]))
    return GraphData(nodes=nodes, edges=edges)


def related_docs(doc_ids: list[str]) -> list[str]:
    """Mở rộng cross-reference: các văn bản liên quan trực tiếp tới doc_ids."""
    if not doc_ids:
        return []
    with session() as s:
        rec = s.run(
            "MATCH (a:Document)-[:REL]-(b:Document) "
            "WHERE a.doc_id IN $ids RETURN collect(DISTINCT b.doc_id) AS ids",
            ids=doc_ids,
        ).single()
        return rec["ids"] if rec else []
