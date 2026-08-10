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
from typing import TYPE_CHECKING

from neo4j import GraphDatabase

from app.core.config import settings
from app.core.schemas import (
    REL_TYPES,
    CorpusDocument,
    GraphData,
    GraphEdge,
    GraphNode,
    Relationship,
    VanBanRong,
)

if TYPE_CHECKING:
    from app.ontology.dong_goi import GoiLopPhu

#: Khớp mọi cạnh quan hệ. Liệt kê tường minh thay vì `[e]` trần: một cạnh không thuộc 13
#: mã sẽ **không** lọt vào kết quả đọc, thay vì lặng lẽ đi tiếp như hồi còn `[:REL]`.
#: Cú pháp `:A|B|C` (một dấu hai chấm cho cả chuỗi): dạng cũ `:A|:B` bị Neo4j 5 bỏ khi có
#: biến `e` đứng trước — lỗi chỉ lộ ra ngày đầu tiên chạy trên server thật (05/08).
_MOI_CANH = ":" + "|".join(REL_TYPES)


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
    """Ràng buộc duy nhất cho MỌI nhãn node được `MERGE` theo khoá — không chỉ `Document`.

    `push_overlay` cũng gọi hàm này, và nó `MERGE (d:DonVi {khoa: …})` khoảng 470 lượt mỗi lần
    đẩy. Không có ràng buộc trên `DonVi.khoa` thì mỗi lượt là một **label scan** toàn bộ node
    `DonVi` — vừa chậm dần theo kích thước đồ thị, vừa là ứng viên rõ ràng cho lần rớt kết nối
    Aura giữa chừng. Ràng buộc `IS UNIQUE` tự kèm index, nên đây vừa là tính đúng đắn vừa là
    tốc độ.
    """
    with session() as s:
        s.run(
            "CREATE CONSTRAINT doc_id IF NOT EXISTS "
            "FOR (d:Document) REQUIRE d.doc_id IS UNIQUE"
        )
        s.run(
            "CREATE CONSTRAINT donvi_khoa IF NOT EXISTS "
            "FOR (d:DonVi) REQUIRE d.khoa IS UNIQUE"
        )


def push_corpus(
    docs: list[CorpusDocument],
    rels: list[Relationship],
    rong: list[VanBanRong] | None = None,
) -> None:
    """Nạp lại toàn bộ đồ thị. `rong` = node rỗng — xem `app.ingestion.bac_cau`.

    Node rỗng được **suy ra** từ đầu mút của cạnh, không ai soạn tay, nên nạp lại là cơ chế
    cập nhật đầy đủ: crawl xong một văn bản rồi đưa vào `docs` thì lần nạp sau nó ra node
    thật, node rỗng cũ không được sinh lại nữa. Đường nạp không xoá-sạch thì gọi
    `don_node_rong_da_co_toan_van()`.
    """
    ensure_constraints()
    with session() as s:
        # Xoá sạch để nạp lại (MVP)
        s.run("MATCH (d:Document) DETACH DELETE d")
        for d in docs:
            s.run(
                """
                MERGE (n:Document {doc_id: $doc_id})
                SET n.title=$title, n.doc_type=$doc_type, n.source=$source,
                    n.valid_from=$valid_from, n.valid_to=$valid_to,
                    n.so_hieu=$so_hieu, n.co_toan_van=true
                """,
                doc_id=d.doc_id, title=d.title, doc_type=d.doc_type,
                source=d.source, valid_from=d.valid_from, valid_to=d.valid_to,
                so_hieu=d.so_hieu,
            )
        for v in rong or []:
            # `co_toan_van=false` là thứ phân biệt DUY NHẤT, và nó phải nằm trên node chứ
            # không suy từ "không có chunk": tầng truy hồi và tầng hiển thị đọc từ hai chỗ khác
            # nhau, mà cả hai đều không được trích dẫn một văn bản chưa đọc.
            s.run(
                """
                MERGE (n:Document {doc_id: $doc_id})
                SET n.title=$title, n.doc_type=$doc_type, n.source='external',
                    n.so_hieu=$doc_id, n.co_toan_van=false
                """,
                doc_id=v.so_hieu, title=v.title or v.so_hieu,
                doc_type=v.doc_type or "Chưa rõ",
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


def push_overlay(goi: "GoiLopPhu") -> tuple[int, int]:
    """Đẩy node/cạnh lớp phủ lên Neo4j — chỉ để XEM, KHÔNG nằm trên đường trả lời.

    `MERGE` trên `khoa` nên chạy lại nhiều lần không nhân đôi. Cạnh `TAC_DONG` khoá theo bộ
    ba (nguồn, đích, thao_tac) — cùng một cặp đơn vị có thể vừa bị sửa vừa bị bãi bỏ ở hai
    thời điểm khác nhau, gộp chung thành một cạnh là mất thông tin.

    Cạnh `THUOC` nối `(:DonVi)` vào `(:Document)` chỉ khớp nếu văn bản đó đã có node
    `Document` (đã nằm trong corpus qua `push_corpus`). `MATCH ... MATCH ... MERGE` mà vế
    `MATCH` không khớp thì Neo4j **bỏ qua trong im lặng** — không lỗi, không cảnh báo. Nên
    hàm này đếm số cạnh `THUOC` MERGE được so với số nút overlay có `doc_id`, và in ra
    khoảng chênh thay vì để người chạy đoán.

    Ba câu `UNWIND`, không phải một câu mỗi hàng. Bản cũ chạy ~764 lượt round-trip riêng lẻ
    (293 nút + 293 `THUOC` + 178 cạnh) trong một session, và Aura free **rớt kết nối giữa
    chừng** — gặp thật 10/08: `SessionExpired` sau khi mới dựng lại 221/255 cạnh `THUOC`, tức
    đồ thị nằm lại đúng trạng thái nửa vời mà đoạn trên vừa mô tả. Gộp lô làm việc chạy lại
    được, nhưng quan trọng hơn là nó gần như không còn cửa để đứt giữa chừng.

    **Phải chạy lại SAU MỖI `push_corpus`.** `push_corpus` mở đầu bằng
    `MATCH (d:Document) DETACH DELETE d`, mà `DETACH` xoá **mọi** cạnh chạm các node đó — kể cả
    `THUOC` phát từ `(:DonVi)`. Node `DonVi` và cạnh `TAC_DONG` thì KHÔNG bị xoá (chúng không
    mang nhãn `Document`), nên đồ thị sau đó trông vẫn "có lớp phủ": đủ nút, đủ cạnh tác động,
    chỉ mất hết đường nối về văn bản. Không lỗi, không cảnh báo — đúng kiểu hỏng phải đọc mới
    thấy. (`push_corpus` không tự gọi hàm này trong đợt sửa 06/08; nối lại là việc của người
    chạy hoặc của một đợt sau.)
    """
    from app.ontology.hien_hanh import dung_overlay

    ensure_constraints()
    canh = [c.thanh_canh() for c in goi.canh]
    nodes = dung_overlay(canh)
    co_doc_id = sum(1 for n in nodes if n.doc_id)
    with session() as s:
        s.run(
            "UNWIND $hang AS h "
            "MERGE (d:DonVi {khoa: h.khoa}) SET d.doc_id = h.doc_id, d.vai = h.vai",
            hang=[{"khoa": n.khoa, "doc_id": n.doc_id, "vai": n.vai} for n in nodes],
        )
        rec = s.run(
            "UNWIND $hang AS h "
            "MATCH (d:DonVi {khoa: h.khoa}) MATCH (v:Document {doc_id: h.doc_id}) "
            "MERGE (d)-[r:THUOC]->(v) RETURN count(r) AS n",
            hang=[{"khoa": n.khoa, "doc_id": n.doc_id} for n in nodes if n.doc_id],
        ).single()
        thuoc_tao_duoc = rec["n"] if rec else 0
        s.run(
            "UNWIND $hang AS h "
            "MATCH (a:DonVi {khoa: h.nguon}) MATCH (b:DonVi {khoa: h.dich}) "
            "MERGE (a)-[r:TAC_DONG {thao_tac: h.thao_tac}]->(b) "
            "SET r.valid_from = h.valid_from",
            hang=[
                {
                    "nguon": c.nguon, "dich": c.dich,
                    "thao_tac": c.thao_tac, "valid_from": c.valid_from,
                }
                for c in canh
            ],
        )
    print(
        f"[push_overlay] THUOC: {thuoc_tao_duoc}/{co_doc_id} nút overlay có doc_id "
        f"nối được vào Document đã có trong corpus (chênh lệch = văn bản chưa crawl)."
    )
    return len(nodes), len(canh)


def get_graph() -> GraphData:
    """Toàn bộ đồ thị cho visualization."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    with session() as s:
        for rec in s.run(
            "MATCH (d:Document) RETURN d.doc_id AS id, d.title AS title, "
            "d.doc_type AS doc_type, d.valid_from AS vf, d.valid_to AS vt, "
            "d.co_toan_van AS ctv"
        ):
            nodes.append(
                GraphNode(
                    id=rec["id"], label=rec["title"], doc_type=rec["doc_type"],
                    valid_from=rec["vf"], valid_to=rec["vt"],
                    # `IS NOT false` chứ không phải `= true`: node nạp từ trước khi có trường
                    # này thì `co_toan_van` là null, và chúng đều CÓ toàn văn.
                    co_toan_van=rec["ctv"] is not False,
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


def related_docs(doc_ids: list[str], ke_ca_rong: bool = False) -> list[str]:
    """Mở rộng cross-reference: các văn bản liên quan trực tiếp tới doc_ids.

    **Mặc định loại node rỗng.** Hàm này cấp `doc_id` cho bước truy hồi đi lấy chunk, mà node
    rỗng không có chunk nào — để lọt thì hoặc lãng phí một lượt tìm, hoặc tệ hơn là có chỗ
    đem nó ra trích dẫn như một nguồn đã đọc. `related_edges` thì vẫn giữ, vì ở đó **chính
    cạnh** là thông tin: "văn bản này bị bãi bỏ bởi một văn bản ta chưa tải" vẫn đáng nói.
    """
    if not doc_ids:
        return []
    # `coalesce(…, true)`: node nạp trước khi có trường này mang null, và chúng đều CÓ toàn
    # văn. Viết `IS NOT false` là cú pháp Python lạc sang Cypher — Neo4j 5 từ chối.
    loc = "" if ke_ca_rong else "AND coalesce(b.co_toan_van, true) "
    with session() as s:
        rec = s.run(
            f"MATCH (a:Document)-[{_MOI_CANH}]-(b:Document) "
            f"WHERE a.doc_id IN $ids {loc}"
            "RETURN collect(DISTINCT b.doc_id) AS ids",
            ids=doc_ids,
        ).single()
        return rec["ids"] if rec else []


CYPHER_THIEU_TOAN_VAN = """
MATCH (r:Document) WHERE r.co_toan_van = false
OPTIONAL MATCH (r)-[e]-(:Document)
RETURN r.doc_id AS so_hieu, r.title AS title, r.doc_type AS doc_type,
       count(e) AS so_canh
ORDER BY so_canh DESC, so_hieu
"""


def thieu_toan_van() -> list[dict]:
    """Node rỗng, xếp theo số cạnh chạm tới — **danh sách cần crawl, sinh từ đồ thị**.

    Nhiều cạnh trỏ tới nghĩa là thiếu văn bản đó làm hổng nhiều chỗ hơn. Bản không cần Neo4j
    ở `app.ingestion.bac_cau.thieu_toan_van` cho cùng thứ tự.
    """
    with session() as s:
        return [dict(r) for r in s.run(CYPHER_THIEU_TOAN_VAN)]


def don_node_rong_da_co_toan_van() -> list[str]:
    """Node rỗng nào đã có văn bản thật nhận cùng số hiệu ⇒ **dời cạnh sang rồi xoá node rỗng**.

    `push_corpus` xoá sạch rồi nạp lại nên đường chính không cần hàm này. Nó tồn tại cho đường
    nạp bổ sung, và để cơ chế "có dữ liệu thật thì node rỗng biến mất" là thứ **gọi được và
    kiểm được**, chứ không phải một hệ quả phụ của việc xoá sạch.

    Lặp qua 13 mã thay vì dùng APOC: loại cạnh không tham số hoá được trong Cypher, và 13 là
    tập đóng nên vòng lặp này không bao giờ bỏ sót — thêm quan hệ mới vào `REL_TYPES` là nó tự
    được xử lý ở đây.
    """
    da_don: list[str] = []
    with session() as s:
        rec = s.run(
            "MATCH (rong:Document) WHERE rong.co_toan_van = false "
            "MATCH (that:Document) "
            "WHERE that.so_hieu = rong.doc_id AND coalesce(that.co_toan_van, true) "
            "RETURN collect(DISTINCT rong.doc_id) AS ids"
        ).single()
        ids = (rec["ids"] if rec else []) or []
        if not ids:
            return []
        for ma in REL_TYPES:
            for huong in ("(a)-[e:{ma}]->(rong)", "(rong)-[e:{ma}]->(a)"):
                cu = huong.format(ma=ma)
                moi = cu.replace("rong", "that").replace("[e:", "[m:")
                s.run(
                    f"""
                    MATCH (rong:Document) WHERE rong.doc_id IN $ids
                    MATCH (that:Document) WHERE that.so_hieu = rong.doc_id
                          AND coalesce(that.co_toan_van, true)
                    MATCH {cu}
                    MERGE {moi}
                    SET m += properties(e)
                    DELETE e
                    """,
                    ids=ids,
                )
        s.run("MATCH (rong:Document) WHERE rong.doc_id IN $ids DETACH DELETE rong", ids=ids)
        da_don = sorted(ids)
    return da_don
