"""Retrieval hybrid: vector (Gemini) + BM25 (LanceDB FTS) → RRF → lọc hiệu lực.

Đây là điểm khác biệt với RAG vector thuần: chỉ trả về điều khoản ĐANG hiệu lực
tại thời điểm `as_of`, và có thể mở rộng qua knowledge graph (cross-reference).
"""
from __future__ import annotations

import logging
import re
import time
from functools import lru_cache

from app.core import vectordb
from app.core.config import LANCEDB_TABLE
from app.core.llm import embed_query
from app.core.tracing import observe
from app.ingestion.versioning import is_effective

logger = logging.getLogger(__name__)

_RRF_K = 60  # hằng số Reciprocal Rank Fusion


def _truy_van_fts(query: str):
    """Truy vấn BM25: giữ độ phủ của túi-từ, cộng điểm cho chunk chứa NGUYÊN cụm đã hỏi.

    `MatchQuery` chấm điểm từng token độc lập, nên một chunk rải rác "giấy phép" và "hoạt
    động" nhiều lần thắng chunk chứa đúng cụm "giấy phép hoạt động" một lần. Đo 10/08 trên 14
    cụm có thật trong corpus: `giấy phép hoạt động` **3/10**, `quy định nội bộ` **4/10**.

    `PhraseQuery` đứng cạnh nó ở mức `SHOULD` chứ không phải `MUST`: chunk khớp cả hai mệnh đề
    được cộng dồn điểm nên nổi lên trên, còn câu hỏi dài dạng tự nhiên — thứ gần như không bao
    giờ xuất hiện nguyên văn trong luật — không khớp mệnh đề cụm và **không mất gì**. Đo lại
    sau khi đổi: 9.0 → **9.9/10** trên cùng bộ cụm, và hai câu hỏi dài trả về đúng 6/6 hit cũ.

    Cần chỉ mục có `with_position=True` (xem `pipeline._FTS_OPTS`); chỉ mục thiếu vị trí thì
    Storage trả 400 và nhánh BM25 tắt — nay có log, xem `_bat_fts`.
    """
    from lancedb.query import BooleanQuery, MatchQuery, Occur, PhraseQuery

    return BooleanQuery(
        queries=[
            (Occur.SHOULD, MatchQuery(query, column="text")),
            (Occur.SHOULD, PhraseQuery(query, column="text")),
        ]
    )


def _thu_lai_loi_mang(goi):
    """Retry quanh lỗi MẠNG LanceDB Cloud, hết lượt thì ném lỗi thật.

    Client chỉ tự retry lỗi HTTP có mã (429/5xx); "connection reset" giữa chừng bị ném
    thẳng thành `HttpError` — một batch dài 50 phút chết vì đúng một request (đo 13/08,
    hai lần cùng một callsite). Dùng chung cho CẢ HAI nhánh hybrid: T29 (đo 19/08) cho
    thấy để BM25 fail-open khi blip mạng thì RRF chỉ còn vector, top-8 đổi → plan
    compliance ±3 CU → verdict biên lật ÂM THẦM. Batch nào cũng có checkpoint nên
    chết-rồi-resume tốt hơn kết quả đổi lặng lẽ.
    """
    from lancedb.remote.errors import HttpError, RetryError

    for cho in (5, 15, 45, None):
        try:
            return goi()
        except (HttpError, RetryError) as exc:
            if cho is None:
                raise
            logger.warning("LanceDB lỗi mạng, thử lại sau %ss: %s", cho, exc)
            time.sleep(cho)
    raise AssertionError("unreachable")


def _bat_fts(tbl, query: str, *, pool: int, where: str | None = None) -> list[dict]:
    """Nhánh BM25. Lỗi mạng → retry-rồi-raise (helper); lỗi khác (index hỏng, thiếu
    with_position…) mới fail-open trả rỗng để vector gánh — nhưng KÊU chứ không im:
    nuốt trong im lặng thì nửa hệ thống truy hồi có thể chết hàng tuần mà không ai biết.
    """
    from lancedb.remote.errors import HttpError, RetryError

    def _goi():
        q = tbl.search(_truy_van_fts(query), query_type="fts")
        if where:
            q = q.where(where, prefilter=True)
        return q.limit(pool).to_list()

    try:
        return _thu_lai_loi_mang(_goi)
    except (HttpError, RetryError):
        raise
    except Exception as exc:  # noqa: BLE001 — xem docstring
        logger.warning("Nhánh BM25 không chạy được, chỉ còn vector: %s", exc)
        return []


def _open_table():
    return vectordb.connect().open_table(LANCEDB_TABLE)


def _vector_hits(tbl, qv: list[float], *, pool: int, where: str | None = None) -> list[dict]:
    """Nhánh vector — không có ai gánh nên lỗi mạng phải retry rồi mới được phép chết."""

    def _goi():
        q = tbl.search(qv)
        if where:
            q = q.where(where, prefilter=True)
        return q.limit(pool).to_list()

    return _thu_lai_loi_mang(_goi)


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
    vector_hits = _vector_hits(tbl, qv, pool=pool)
    fts_hits = _bat_fts(tbl, query, pool=pool)

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

    vector_hits = _vector_hits(tbl, list(_qv(query)), pool=pool, where=where)
    fts_hits = _bat_fts(tbl, query, pool=pool, where=where)

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


#: Số chunk tối đa lấy về cho MỘT điều xuất xứ. Điều dài bị `_split_khoan` chẻ nhiều mảnh
#: (TT66-2025 Điều 12 = 7217 ký tự → 6 mảnh); lấy hết là nhồi cả điều vào prompt cho một chú
#: thích phụ trợ. Lấy hai mảnh ĐẦU theo thứ tự nhãn: mệnh lệnh sửa ("Sửa đổi khoản N như
#: sau:") và khối lời văn mới đầu tiên nằm ở đầu điều.
_TOI_DA_MANH_MOI_DIEU = 2

#: Trần quét mỗi văn bản khi tra theo tiền tố. Văn bản dày nhất của corpus thật là 92 chunk
#: (TT40-2024); 300 để còn dư khi corpus lớn lên mà vẫn không kéo về cả bảng.
_TRAN_QUET_MOI_DOC = 300

_SO_DAU_RE = re.compile(r"\d+")


def _sap_nhan(nhan: str) -> tuple:
    """Thứ tự TỰ NHIÊN của nhãn chunk: `"Điều 1"` < `"Điều 1 Khoản 2"` < `"Điều 1 Khoản 10"`."""
    return tuple(int(s) for s in _SO_DAU_RE.findall(nhan))


def lay_chunk_theo_tien_to(
    tien_to: list[str], *, moi_tien_to: int = _TOI_DA_MANH_MOI_DIEU
) -> list[dict]:
    """Tra chunk theo TIỀN TỐ `"{doc_id}::{nhãn điều}"` — không tìm kiếm, không embedding.

    Vì sao tiền tố chứ không phải id chính xác: `app/ingestion/pipeline.py` mint id là
    `"{doc_id}::{label}"`, mà `label` của một điều dài hơn `_MAX_CHUNK` là `"Điều N Khoản a-b"`
    hoặc `"Điều N (phần k)"` — **id cấp điều không tồn tại**. Lớp phủ chỉ biết địa chỉ tới cấp
    ĐIỀU (`articles[]` của corpus chỉ tới đó), nên tra đúng id thì 31/40 ca khớp 0 hàng và
    fail-open nuốt mất (đo 06/08 trên `data/overlay/lop_phu.json` + `data/corpus.real.json`).

    Ranh giới tiền tố là DẤU CÁCH, không phải `startswith` trần: `"Điều 3"` phải khớp
    `"Điều 3 Khoản 1-6"` và `"Điều 3 (phần 2)"` nhưng KHÔNG được khớp `"Điều 30"` — corpus
    thật có đủ cặp Điều 1/Điều 10..19, Điều 3/Điều 30..39 để cái nhầm đó xảy ra hằng ngày.

    Lọc `doc_id` đẩy xuống LanceDB (`doc_id IN (...)` — cú pháp đã dùng ở `search_in_docs`,
    không mượn thêm phương ngữ SQL nào); khớp tiền tố làm ở Python, nơi luật ranh giới kiểm
    được. Lỗi (bảng chưa có, filter khác cú pháp) ⇒ trả rỗng: đây là phần THÊM cho câu trả
    lời, không được làm hỏng nó.
    """
    cap: list[tuple[str, str]] = []
    for t in tien_to:
        doc_id, sep, nhan = (t or "").partition("::")
        if sep and doc_id and nhan:
            cap.append((doc_id, nhan))
    if not cap:
        return []

    docs = sorted({d for d, _ in cap})
    trong = ", ".join("'" + d.replace("'", "''") + "'" for d in docs)
    try:
        hang = (
            _open_table()
            .search()
            .where(f"doc_id IN ({trong})")
            .limit(len(docs) * _TRAN_QUET_MOI_DOC)
            .to_list()
        )
    except Exception:  # noqa: BLE001 — xem docstring
        return []

    ra: list[dict] = []
    da_co: set[str] = set()
    for doc_id, nhan in cap:
        khop = sorted(
            (
                r for r in hang
                if r.get("doc_id") == doc_id
                and ((a := (r.get("article") or "")) == nhan or a.startswith(nhan + " "))
            ),
            key=lambda r: _sap_nhan(r.get("article") or ""),
        )
        for r in khop[:moi_tien_to]:
            if r.get("id") not in da_co:
                da_co.add(r.get("id"))
                ra.append(r)
    return ra


def baseline_vector_search(query: str, *, top_k: int = 6) -> list[dict]:
    """RAG vector thuần (KHÔNG lọc hiệu lực, KHÔNG hybrid) — dùng cho benchmark."""
    tbl = _open_table()
    return tbl.search(list(_qv(query))).limit(top_k).to_list()
