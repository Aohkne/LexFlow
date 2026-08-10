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

#: Thang bậc cấu trúc MỊN DẦN, chỉ dùng khi `_KHOAN_RE` không chẻ được điều.
#: Ca thật: TT66-2025 Điều 6 (4313 ký tự) là điều *sửa đổi*, đánh số ở cấp điểm/tiểu mục
#: (`đ)`, `(i)`…`(vii)`, `- `) chứ không phải khoản — cắt cửa sổ ký tự làm vết cắt rơi vào
#: giữa câu, mà điều này lại nằm trên đường nóng của lớp phủ.
#:
#: Nhãn vẫn là `(phần k)` cho MỌI bậc dưới khoản: `đ)`/`(i)` trong một điều sửa đổi là chữ
#: TRÍCH của văn bản bị sửa (TT34-2024), không phải địa chỉ trong TT66-2025 — gắn nhãn
#: `"Điều 6 Điểm đ"` cho nó là khai man địa chỉ pháp lý. Thang bậc chọn CHỖ CẮT, không đặt tên.
_DIEM_RE = re.compile(r"^([a-zđêôơưáàảãạăâéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ])\)\s")
_TIEU_MUC_RE = re.compile(r"^\((\w+)\)\s")
_GACH_DAU_DONG_RE = re.compile(r"^([-–+•])\s")
_BAC_DU_PHONG = (_DIEM_RE, _TIEU_MUC_RE, _GACH_DAU_DONG_RE)

#: Ngắt câu để không cắt giữa câu khi một DÒNG tự nó dài hơn ngưỡng.
_RANH_CAU_RE = re.compile(r"(?<=[.;:!?])\s+")


def _gom_theo_mau(text: str, rx: re.Pattern[str]) -> list[tuple[str | None, str]]:
    """Gom dòng thành đơn vị theo `rx`; phần mở đầu (tiêu đề điều…) dính đơn vị đầu tiên."""
    pieces: list[tuple[str | None, list[str]]] = [(None, [])]
    for ln in text.split("\n"):
        m = rx.match(ln)
        if m:
            pieces.append((m.group(1), [ln]))
        else:
            pieces[-1][1].append(ln)
    return [(num, "\n".join(lines).strip()) for num, lines in pieces if "\n".join(lines).strip()]


def _gop_lien_ke(don_vi: list[tuple[str | None, str]]) -> list[list[tuple[str | None, str]]]:
    """Gộp đơn vị liền kề cho tới ~_MAX_CHUNK. Đơn vị tự nó quá ngưỡng thì đứng một mình."""
    nhom: list[list[tuple[str | None, str]]] = []
    buf: list[tuple[str | None, str]] = []
    size = 0
    for item in don_vi:
        if buf and size + len(item[1]) > _MAX_CHUNK:
            nhom.append(buf)
            buf, size = [], 0
        buf.append(item)
        size += len(item[1])
    if buf:
        nhom.append(buf)
    return nhom


def _cat_theo_khoang_trang(cau: str) -> list[str]:
    """Chặng cuối: một "câu" vẫn dài quá ngưỡng thì cắt ở KHOẢNG TRẮNG, không giữa từ."""
    ra: list[str] = []
    con = cau
    while len(con) > _MAX_CHUNK:
        cat = con.rfind(" ", 0, _MAX_CHUNK)
        if cat <= 0:  # một "từ" dài hơn cả ngưỡng (URL, chuỗi số) — hết cách
            cat = _MAX_CHUNK
        ra.append(con[:cat].rstrip())
        con = con[cat:].lstrip()
    if con:
        ra.append(con)
    return ra


def _cat_theo_dong(text: str) -> list[str]:
    """Lưới an toàn cuối: gom TRỌN dòng tới ngưỡng; dòng nào tự nó dài quá thì ngắt ở câu.

    Không bao giờ trả về mảnh mở đầu hay kết thúc bằng nửa từ. Khoảng trắng bên trong một
    dòng bị ngắt sẽ chuẩn hoá về một dấu cách — đó là cái giá của việc ghép lại theo câu.
    """
    manh: list[str] = []
    for dong in text.split("\n"):
        if len(dong) <= _MAX_CHUNK:
            manh.append(dong)
            continue
        cau_buf: list[str] = []
        size = 0
        for cau in filter(None, _RANH_CAU_RE.split(dong)):
            for phan in _cat_theo_khoang_trang(cau) if len(cau) > _MAX_CHUNK else [cau]:
                if cau_buf and size + len(phan) + 1 > _MAX_CHUNK:
                    manh.append(" ".join(cau_buf))
                    cau_buf, size = [], 0
                cau_buf.append(phan)
                size += len(phan) + 1
        if cau_buf:
            manh.append(" ".join(cau_buf))

    ra: list[str] = []
    buf: list[str] = []
    size = 0
    for m in manh:
        if buf and size + len(m) + 1 > _MAX_CHUNK:
            ra.append("\n".join(buf).strip())
            buf, size = [], 0
        buf.append(m)
        size += len(m) + 1
    if buf:
        ra.append("\n".join(buf).strip())
    return [x for x in ra if x]


def _cat_du_phong(text: str) -> list[str]:
    """Điều không chẻ được theo khoản: thử các bậc mịn hơn, cuối cùng mới cắt theo dòng/câu."""
    for rx in _BAC_DU_PHONG:
        don_vi = _gom_theo_mau(text, rx)
        if len(don_vi) > 1:
            return ["\n".join(t for _, t in nhom) for nhom in _gop_lien_ke(don_vi)]
    return _cat_theo_dong(text)


def _split_khoan(article: str, text: str) -> list[tuple[str, str]]:
    """Tách điều dài thành các chunk mức Khoản, gộp khoản liền kề tới ~_MAX_CHUNK.

    Trả về [(nhãn, text)] — nhãn kiểu "Điều 26 Khoản 1-3". Điều không có cấu trúc khoản thì
    chẻ theo bậc mịn hơn (điểm → tiểu mục → gạch đầu dòng), hết đường mới cắt theo ranh giới
    dòng/câu; những mảnh đó mang nhãn "Điều 26 (phần 2)".
    """
    if len(text) <= _MAX_CHUNK:
        return [(article, text)]

    khoan = _gom_theo_mau(text, _KHOAN_RE)
    if len(khoan) <= 1:
        return [
            (f"{article} (phần {i + 1})", t) for i, t in enumerate(_cat_du_phong(text))
        ]

    nhom = _gop_lien_ke(khoan)
    nhan = _lam_duy_nhat([_khoan_label(article, g) for g in nhom])
    return [(n, "\n".join(x for _, x in g)) for n, g in zip(nhan, nhom)]


def _khoan_label(article: str, buf: list[tuple[str | None, str]]) -> str:
    nums = [n for n, _ in buf if n]
    if not nums:
        return article
    if len(nums) == 1 or int(nums[0]) >= int(nums[-1]):
        # Số cuối không lớn hơn số đầu ⇒ đánh số đã khởi động lại giữa chừng (điều sửa đổi
        # chép nguyên văn nhiều điều của văn bản bị sửa). Nhãn dải `"Khoản 18-1"` khi đó NÓI
        # DỐI — nó tuyên bố một dải từ 18 đến 1. Lấy số đầu: chunk đúng là bắt đầu từ đó.
        return f"{article} Khoản {nums[0]}"
    return f"{article} Khoản {nums[0]}-{nums[-1]}"


def _lam_duy_nhat(nhan: list[str]) -> list[str]:
    """Nhãn trùng trong CÙNG một điều thì thêm hậu tố thứ tự: `"Điều 1 Khoản 2 (2)"`.

    Trùng xảy ra khi một điều chứa nhiều khối đánh số lặp lại — ca thật `TT23-2019 Điều 1`
    (55.902 ký tự, 27 mảnh) chép lại nguyên văn nhiều điều của TT39-2014, nên "Khoản 2" xuất
    hiện ba lần. Vì `id = f"{doc_id}::{nhãn}"`, ba chunk khác nhau lĩnh cùng một id; `_rrf`
    gom kết quả vào dict theo id nên một cái bị nuốt, và trích dẫn trỏ tới một địa chỉ mang
    ba nội dung khác nhau.

    Hậu tố là thứ phân biệt, KHÔNG phải địa chỉ pháp lý — `khoa_tu_chunk_id` bóc nó ra rồi rơi
    về khoá cấp điều, y như cách nó xử nhãn gộp nhiều khoản.
    """
    da_dung: set[str] = set()
    ra: list[str] = []
    for n in nhan:
        m, k = n, 1
        while m in da_dung:  # vòng lặp chứ không phải đếm: `"A (2)"` có thể đã tồn tại sẵn
            k += 1
            m = f"{n} ({k})"
        da_dung.add(m)
        ra.append(m)
    return ra


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


#: Tham số chỉ mục toàn văn (BM25). Mặc định của LanceDB dựng cho tiếng Anh; ba thay đổi:
#:
#: * `with_position=True` — lưu vị trí token, điều kiện BẮT BUỘC để `PhraseQuery` chạy được
#:   (không có nó, Storage trả 400 "position is not found"). Đo 10/08 trên 14 cụm có thật
#:   trong corpus: precision@10 của nhánh BM25 là **8.4/10**, trong đó ba cụm mà từng thành tố
#:   đều rất phổ biến rớt hẳn — `an toàn` 2/10, `giấy phép hoạt động` 3/10, `quy định nội bộ`
#:   4/10. Chunk rải rác "giấy phép" và "hoạt động" thắng chunk chứa đúng cụm.
#: * `stem=False` — stemmer Snowball tiếng Anh không có việc gì để làm trên tiếng Việt.
#: * `remove_stop_words=False` — danh sách stop-word tiếng Anh cũng vậy; và vì `ascii_folding`
#:   bỏ dấu TRƯỚC khi lọc, `thẻ`/`số`/`tổ` sẽ thành `the`/`so`/`to` và rơi đúng vào danh sách
#:   đó. (Đo 10/08: hiện chưa thấy thiệt hại thật, nhưng đây là mìn hẹn giờ chứ không phải
#:   thiết kế.)
#:
#: `ascii_folding` GIỮ `True`: người dùng gõ không dấu vẫn khớp được văn bản có dấu.
_FTS_OPTS = {
    "with_position": True,
    "stem": False,
    "remove_stop_words": False,
    "ascii_folding": True,
}


def write_lancedb(rows: list[dict]) -> int:
    if not rows:
        return 0
    _embed_rows(rows)
    db = vectordb.connect()
    tbl = db.create_table(LANCEDB_TABLE, data=rows, mode="overwrite")
    tbl.create_fts_index("text", replace=True, **_FTS_OPTS)
    return len(rows)


#: `doc_id` đi thẳng vào chuỗi điều kiện của `tbl.delete(...)`, mà nó đến từ JSON admin sửa
#: được bằng tay — đây là biên tin cậy. Chặn bằng bộ ký tự cho phép chứ không thoát chuỗi:
#: bộ này phủ đủ mọi `doc_id` đang có (`TT40-2024`, `ND101-2012`, nhóm nội bộ SHB) và từ
#: chối phần còn lại, nên nó nói KHÔNG với thứ chưa từng thấy thay vì đoán cách xử.
_DOC_ID_RE = re.compile(r"^[A-Za-z0-9._-]+\Z")


def kiem_doc_id(doc_id: str) -> str:
    if not _DOC_ID_RE.match(doc_id or ""):
        raise ValueError(
            f"doc_id không hợp lệ: {doc_id!r} — chỉ nhận chữ, số, dấu chấm, gạch dưới, gạch nối"
        )
    return doc_id


def ingest_one_doc(
    doc: CorpusDocument,
    rels: list[Relationship],
    tat_ca_docs: list[CorpusDocument],
) -> int:
    """Nạp lại ĐÚNG MỘT văn bản. Trả về số chunk của riêng nó.

    Khác `ingest_docs` ở chỗ không đụng phần còn lại: `delete` theo `doc_id` rồi `add`, thay
    vì `create_table(mode="overwrite")` ghi đè cả bảng đang phục vụ. Đo 10/08 trên LanceDB
    Cloud: một vòng delete+add của 23 hàng mất 1,23s, embed 23 chunk mất 1,79s — so với ~52s
    chỉ riêng phần embed nếu nạp lại toàn bộ 661 chunk.

    Cái giá đã đo và chấp nhận: chỉ mục FTS mất ~13 giây mới thấy hàng mới (nó tự cập nhật,
    không phải dựng lại). Nhánh vector thấy ngay, nên trong 13 giây đó truy hồi vẫn ra kết
    quả, chỉ thiếu một nhánh.

    `tat_ca_docs` là toàn bộ corpus sau khi đã gộp `doc` — cần cho `quy_ve_doc_id` dựng đủ
    bảng số hiệu, chứ không phải để nạp.
    """
    kiem_doc_id(doc.doc_id)
    rows = build_chunks([doc])
    if not rows:
        return 0
    _embed_rows(rows)

    db = vectordb.connect()
    if LANCEDB_TABLE in db.list_tables():
        tbl = db.open_table(LANCEDB_TABLE)
        tbl.delete(f"doc_id = '{doc.doc_id}'")
        tbl.add(rows)
    else:
        tbl = db.create_table(LANCEDB_TABLE, data=rows)
        tbl.create_fts_index("text", replace=True, **_FTS_OPTS)
    print(f"[ingest] {doc.doc_id}: {len(rows)} chunk vào LanceDB (thay tại chỗ).")

    if settings.neo4j_enabled:
        from app.ingestion.bac_cau import quy_ve_doc_id
        from app.knowledge.graph import push_one_doc

        # Quy cạnh về `doc_id` trên TOÀN BỘ rels rồi mới lọc: cạnh đọc từ vbpl khoá bằng số
        # hiệu, lọc trước khi quy là bỏ sót đúng những cạnh chưa được quy.
        canh_tat_ca, rong_tat_ca, cb = quy_ve_doc_id(rels, tat_ca_docs)
        for c in cb:
            print(f"[ingest] cảnh báo: {c}")
        canh = [c for c in canh_tat_ca if c.source_doc == doc.doc_id]
        dich = {c.target_doc for c in canh}
        rong = [v for v in rong_tat_ca if v.so_hieu in dich]
        push_one_doc(doc, canh, rong)
        print(f"[ingest] {doc.doc_id}: 1 node + {len(canh)} cạnh vào Neo4j (không xoá sạch).")
    else:
        print("[ingest] Bỏ qua Neo4j (chưa cấu hình NEO4J_URI/PASSWORD).")
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


#: Artefact lớp phủ — cùng đường dẫn `app.knowledge.lop_phu` dùng lúc chạy.
_DUONG_DAN_LOP_PHU = Path("data/overlay/lop_phu.json")


def _noi_lai_lop_phu() -> None:
    """Đẩy lại node/cạnh lớp phủ NGAY SAU `push_corpus`.

    Bắt buộc, không phải tuỳ chọn: `push_corpus` mở đầu bằng
    `MATCH (d:Document) DETACH DELETE d`, mà `DETACH` xoá **mọi** cạnh chạm các node đó — kể cả
    `THUOC` phát từ `(:DonVi)`. Node `DonVi` và cạnh `TAC_DONG` không mang nhãn `Document` nên
    sống sót, khiến đồ thị sau đó *trông vẫn có lớp phủ*: đủ nút, đủ cạnh tác động, chỉ mất
    sạch đường nối về văn bản. Không lỗi, không cảnh báo.

    Trước 10/08 đây là việc người chạy phải tự nhớ (xem docstring `push_overlay`) — tức là một
    bước bắt buộc nằm ngoài mã, loại thoả thuận chỉ đúng tới lần đầu có người quên.
    """
    from app.knowledge.graph import push_overlay
    from app.ontology.dong_goi import GoiLopPhu

    try:
        goi = GoiLopPhu.model_validate_json(
            _DUONG_DAN_LOP_PHU.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        print(
            f"[ingest] CẢNH BÁO: không đọc được lớp phủ {_DUONG_DAN_LOP_PHU} ({exc}). "
            "Đồ thị vừa nạp KHÔNG có cạnh THUOC nối đơn vị về văn bản."
        )
        return
    push_overlay(goi)


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
        _noi_lai_lop_phu()
    else:
        print("[ingest] Bỏ qua Neo4j (chưa cấu hình NEO4J_URI/PASSWORD).")
    return n


def main(corpus_path: str | None = None) -> tuple[list[CorpusDocument], list[Relationship]]:
    path = corpus_path or "data/corpus.sample.json"
    print(f"[ingest] Đọc corpus: {path}")
    docs, rels = load_corpus(path)
    ingest_docs(docs, rels)
    return docs, rels
