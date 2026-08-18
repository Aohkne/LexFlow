"""Retrieval hybrid: vector (Gemini) + BM25 (LanceDB FTS) → RRF → lọc hiệu lực.

Đây là điểm khác biệt với RAG vector thuần: chỉ trả về điều khoản ĐANG hiệu lực
tại thời điểm `as_of`, và có thể mở rộng qua knowledge graph (cross-reference).
"""
from __future__ import annotations

import logging
import re
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


def _bat_fts(tbl, query: str, *, pool: int, where: str | None = None) -> list[dict]:
    """Nhánh BM25. Hỏng thì trả rỗng để vector gánh tiếp — nhưng KÊU chứ không im.

    Fail-open ở đây là đúng (một nửa của hybrid vẫn hơn không có câu trả lời), nhưng nuốt
    trong im lặng thì nửa hệ thống truy hồi có thể chết hàng tuần mà không ai biết.
    """
    try:
        q = tbl.search(_truy_van_fts(query), query_type="fts")
        if where:
            q = q.where(where, prefilter=True)
        return q.limit(pool).to_list()
    except Exception as exc:  # noqa: BLE001 — xem docstring
        logger.warning("Nhánh BM25 không chạy được, chỉ còn vector: %s", exc)
        return []


def _open_table(table: str = LANCEDB_TABLE):
    return vectordb.connect().open_table(table)


@lru_cache(maxsize=256)
def _qv(query: str) -> tuple[float, ...]:
    """Cache embedding câu hỏi — hybrid + graph-augment dùng chung 1 lần gọi Gemini."""
    return tuple(embed_query(query))


#: Đóng góp của nhánh BM25 vào điểm RRF; nhánh vector luôn 1.0. RRF gốc dùng 1.0 cho cả hai.
#:
#: Hạ xuống 0.1 ngày 11/08 sau khi quét trên ba bộ câu hỏi (`eval/quet_trong_so.py`,
#: `docs/EVAL-IR.md` §7): ở trọng số cân bằng, nhánh thưa **kéo kết quả sai lên** trên cả ba.
#: Nặng nhất ở mức điều — R@1 0.17 → 0.38 khi hạ xuống 0.1 — vì BM25 tìm ra đúng văn bản nhưng
#: không phân biệt nổi điều nào trong đó (R@20 mức điều chỉ 0.21), nên hợp nhất ngang trọng số
#: đẩy các điều SAI của ĐÚNG văn bản lên top.
#:
#: Không đặt 0: ba bộ đo đều là câu hỏi diễn đạt tự nhiên, chưa ép loại truy vấn mà khớp từ khoá
#: chính xác mới có giá trị (số hiệu, số tiền, tên định chế). Giữ 0.1 để nhánh thưa còn là điểm
#: phá hoà, và để T8 (sửa index BM25) còn chỗ chứng minh.
TRONG_SO_THUA = 0.1


def _rrf(
    vector_hits: list[dict],
    fts_hits: list[dict],
    k: int,
    *,
    trong_so_thua: float = TRONG_SO_THUA,
) -> list[dict]:
    """Trộn 2 bảng xếp hạng bằng Reciprocal Rank Fusion.

    `trong_so_thua` nhân vào đóng góp của nhánh BM25; nhánh vector luôn là 1.0, nên chỉ **tỷ lệ**
    giữa hai nhánh có nghĩa. Trọng số 0 thì bỏ hẳn nhánh thưa — không phải cộng 0 điểm, vì như thế
    các hit chỉ có ở nhánh thưa vẫn lọt vào đuôi bảng xếp hạng với điểm 0.
    """
    scores: dict[str, float] = {}
    rows: dict[str, dict] = {}
    for ranked, w in ((vector_hits, 1.0), (fts_hits, trong_so_thua)):
        if w == 0:
            continue
        for rank, row in enumerate(ranked):
            rid = row["id"]
            scores[rid] = scores.get(rid, 0.0) + w / (_RRF_K + rank)
            rows[rid] = row
    ordered = sorted(scores, key=lambda r: scores[r], reverse=True)
    out = []
    for r in ordered[:k]:
        rows[r]["_rrf_score"] = scores[r]  # tầng eval đọc để ước tin cậy; không đổi thứ hạng
        out.append(rows[r])
    return out


@observe(name="retrieval.hybrid", as_type="retriever")
def hybrid_search(
    query: str, *, top_k: int = 6, as_of: str | None = None, effective_only: bool = True,
    table: str = LANCEDB_TABLE,
) -> list[dict]:
    # `table` != mặc định chỉ dùng cho nhánh eval tách corpus (VLQA, T117) — đường sản phẩm
    # không truyền nên vẫn đọc bảng "chunks", hành vi không đổi.
    tbl = _open_table(table)
    pool = max(top_k * 3, 15)

    qv = list(_qv(query))
    vector_hits = tbl.search(qv).limit(pool).to_list()
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

    vector_hits = (
        tbl.search(list(_qv(query))).where(where, prefilter=True).limit(pool).to_list()
    )
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


def khop_tien_to(nhan: str, tien_to: str) -> bool:
    """`nhan` có nằm dưới `tien_to` không — ranh giới là DẤU CÁCH, không phải `startswith` trần.

    `"Điều 3"` phải khớp `"Điều 3 Khoản 1-6"` và `"Điều 3 (phần 2)"` nhưng KHÔNG được khớp
    `"Điều 30"`: corpus thật có đủ cặp Điều 1/Điều 10..19, Điều 3/Điều 30..39 để cái nhầm đó
    xảy ra hằng ngày. Tách ra khỏi `lay_chunk_theo_tien_to` vì tầng đo (`eval/metrics.py`) cần
    ĐÚNG luật này để so nhãn vàng với nhãn chunk — chép lại là mở đường cho hai luật lệch nhau.
    """
    return nhan == tien_to or nhan.startswith(tien_to + " ")


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
                and khop_tien_to(r.get("article") or "", nhan)
            ),
            key=lambda r: _sap_nhan(r.get("article") or ""),
        )
        for r in khop[:moi_tien_to]:
            if r.get("id") not in da_co:
                da_co.add(r.get("id"))
                ra.append(r)
    return ra


def baseline_vector_search(query: str, *, top_k: int = 6) -> list[dict]:
    """RAG vector thuần (KHÔNG lọc hiệu lực, KHÔNG hybrid) — dùng cho benchmark.

    Tương ứng cột **NaiveRAG** của bài báo SBV-LawGraph (§5.2): dense embedding, cosine, không
    rerank.
    """
    tbl = _open_table()
    return tbl.search(list(_qv(query))).limit(top_k).to_list()


def bm25_search(query: str, *, top_k: int = 6) -> list[dict]:
    """BM25 thuần (LanceDB FTS), KHÔNG lọc hiệu lực — cột **BM25** của bài báo (§5.2).

    FTS chưa sẵn sàng ⇒ trả rỗng thay vì ném: benchmark còn nhiều cột khác, một cột thiếu
    index không được giết cả lượt đo. Rỗng hiện ra thành recall 0, không thành lỗi im lặng —
    người đọc bảng thấy ngay.
    """
    try:
        return _open_table().search(query, query_type="fts").limit(top_k).to_list()
    except Exception:  # noqa: BLE001 — xem docstring
        return []


#: Trọng số của cột AdvancedRAG trong bài báo (§5.2): "75% BM25, 25% semantic".
_TRONG_SO_BM25 = 0.75

#: Tên trường điểm LanceDB trả về. Vector search trả KHOẢNG CÁCH (nhỏ = gần), FTS trả điểm
#: BM25 (lớn = hợp). Dò theo danh sách thay vì ghim một tên: đổi phiên bản LanceDB mà tên
#: trường đổi theo thì hợp điểm có trọng số lặng lẽ thành ngẫu nhiên — nên không tìm thấy
#: trường nào là LỖI CỨNG, không phải mặc định 0.
_TRUONG_KHOANG_CACH = ("_distance", "_dist")
_TRUONG_DIEM_FTS = ("_score", "score", "_relevance_score")


def _lay_diem(row: dict, ten: tuple[str, ...]) -> float:
    for t in ten:
        v = row.get(t)
        if v is not None:
            return float(v)
    raise KeyError(
        f"Hàng LanceDB không có trường điểm nào trong {ten}; có: {sorted(row)}. "
        "Không đoán giá trị — hợp điểm có trọng số sai sẽ không lộ ra ở bảng kết quả."
    )


def _chuan_hoa(rows: list[dict], ten: tuple[str, ...], *, dao_chieu: bool) -> dict[str, float]:
    """Điểm thô → [0, 1] bằng min-max. `dao_chieu=True` cho khoảng cách (nhỏ = tốt).

    Mọi hàng cùng điểm (hoặc chỉ một hàng) ⇒ trả 1.0 cho tất cả: min-max không xác định ở đó,
    mà cho 0 thì cả nhánh biến mất khỏi tổng hợp — sai theo hướng khó thấy hơn.
    """
    if not rows:
        return {}
    tho = {r["id"]: _lay_diem(r, ten) for r in rows}
    if dao_chieu:
        tho = {k: -v for k, v in tho.items()}
    lo, hi = min(tho.values()), max(tho.values())
    if hi - lo < 1e-12:
        return dict.fromkeys(tho, 1.0)
    return {k: (v - lo) / (hi - lo) for k, v in tho.items()}


def advanced_rag_search(query: str, *, top_k: int = 6) -> list[dict]:
    """**AdvancedRAG** của bài báo (§5.2): hợp điểm có trọng số 75% BM25 + 25% dense.

    Khác `hybrid_search` ở hai chỗ, và cả hai đều có chủ đích — đây là cột SO SÁNH, không phải
    một biến thể của đường sản phẩm: (1) hợp điểm có trọng số thay vì RRF; (2) KHÔNG lọc hiệu
    lực, đúng như baseline trong bài báo (bài báo không có khái niệm `as_of`).
    """
    tbl = _open_table()
    pool = max(top_k * 3, 15)

    vector_hits = tbl.search(list(_qv(query))).limit(pool).to_list()
    try:
        fts_hits = tbl.search(query, query_type="fts").limit(pool).to_list()
    except Exception:  # noqa: BLE001 — FTS chưa sẵn sàng ⇒ cột này thành dense thuần
        fts_hits = []

    d_vec = _chuan_hoa(vector_hits, _TRUONG_KHOANG_CACH, dao_chieu=True)
    d_fts = _chuan_hoa(fts_hits, _TRUONG_DIEM_FTS, dao_chieu=False)

    rows = {r["id"]: r for r in vector_hits}
    rows.update({r["id"]: r for r in fts_hits})
    diem = {
        rid: _TRONG_SO_BM25 * d_fts.get(rid, 0.0) + (1 - _TRONG_SO_BM25) * d_vec.get(rid, 0.0)
        for rid in rows
    }
    xep = sorted(diem, key=lambda r: diem[r], reverse=True)
    return [rows[r] for r in xep[:top_k]]
