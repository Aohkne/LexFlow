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


class DocDuTrongBang(RuntimeError):
    """Bảng còn văn bản mà corpus không có.

    Không tự xoá: `main()` mặc định đọc `data/corpus.sample.json`, nên xoá tự động biến một lần
    gõ thiếu tham số thành xoá sạch corpus thật. Ghi đè bằng sample thì thấy ngay; xoá âm thầm
    thì không.
    """

    def __init__(self, doc_ids: set[str]) -> None:
        self.doc_ids = sorted(doc_ids)
        super().__init__(
            "bảng còn văn bản không có trong corpus: " + ", ".join(self.doc_ids)
            + " — chạy lại với --xoa-doc-du nếu thật sự muốn xoá chúng"
        )


def _cot_du_lieu(tbl) -> list[str]:
    """Tên cột trừ `vector`, lấy từ schema chứ KHÔNG viết tay.

    Viết tay thì thêm cột mới mà quên cập nhật danh sách ⇒ cột đó rơi khỏi vân tay và mọi thay
    đổi trên nó thành vô hình — bảng vẫn có số, chỉ là số cũ.
    """
    return [f.name for f in tbl.schema if f.name != "vector"]


def _van_tay(r: dict, cot: list[str]) -> tuple:
    """Vân tay một hàng. Thứ tự khoá lấy từ `cot` nên hai phía luôn so cùng một trật tự."""
    return tuple((k, r.get(k)) for k in cot)


def _doc_can_nap(tbl, rows: list[dict]) -> tuple[set[str], set[str], dict[str, set[str]]]:
    """(doc cần nạp, doc dư trong bảng, doc_id → id đang có trong bảng).

    Một lượt quét toàn bảng, KHÔNG kèm `where`. Lọc `doc_id IN (<corpus>)` nghe tiết kiệm hơn
    nhưng loại bỏ đúng thứ cần tìm: doc *dư* theo định nghĩa là doc không có trong corpus. Và
    nó cũng không tiết kiệm thật — corpus với bảng gần như cùng một tập doc_id. Đo 13/08:
    5.29s cho 661 hàng.

    Thành phần thứ ba tồn tại để bước xoá mồ côi không phải quét bảng lần hai.
    """
    cot = _cot_du_lieu(tbl)
    moi: dict[str, set[tuple]] = {}
    for r in rows:
        moi.setdefault(r["doc_id"], set()).add(_van_tay(r, cot))

    cu: dict[str, set[tuple]] = {}
    id_cu: dict[str, set[str]] = {}
    n = tbl.count_rows()
    if n:  # `limit(0)` có backend hiểu là "không giới hạn" — đừng để nó có cơ hội
        for h in tbl.search().select(cot).limit(n).to_list():
            cu.setdefault(h["doc_id"], set()).add(_van_tay(h, cot))
            id_cu.setdefault(h["doc_id"], set()).add(h["id"])

    return {d for d, v in moi.items() if cu.get(d) != v}, set(cu) - set(moi), id_cu


def _loc_id(ids: list[str]) -> str:
    """`"id IN ('a', 'b')"`. Nháy đơn phải nhân đôi — id chứa nhãn lấy từ văn bản luật."""
    return "id IN (" + ", ".join("'" + i.replace("'", "''") + "'" for i in sorted(ids)) + ")"


def _tao_bang_moi(db, rows: list[dict]) -> tuple[int, int]:
    """Đường lần-đầu: chưa có bảng thì không có gì để so, dựng và index như trước."""
    _embed_rows(rows)
    tbl = db.create_table(LANCEDB_TABLE, data=rows, mode="overwrite")
    if settings.lancedb_cloud_enabled:
        tbl.create_fts_index("text")
    else:
        tbl.create_fts_index("text", replace=True)
    return len(rows), len(rows)


def write_lancedb(
    rows: list[dict],
    ep: frozenset[str] = frozenset(),
    xoa_doc_du: bool = False,
) -> tuple[int, int]:
    """Ghi chunk vào LanceDB, chỉ embed văn bản thật sự đổi. Trả `(số vừa ghi, tổng trong bảng)`.

    `merge_insert` theo `id` TRƯỚC rồi mới xoá id mồ côi, chứ không `delete` theo `doc_id` rồi
    `add`: giữa `delete` và `add` cả văn bản biến khỏi bảng, và truy vấn rơi vào đúng khoảng đó
    được trả lời như thể luật ấy không tồn tại. `create_table(mode="overwrite")` cũ KHÔNG có
    cửa sổ này (Lance đánh version) — đổi sang tăng dần không được đánh mất nó.
    """
    if not rows:
        return 0, 0

    db = vectordb.connect()
    try:
        tbl = db.open_table(LANCEDB_TABLE)
    except ValueError as e:
        # `open_table` LÀ phép dò bảng tồn tại — không liệt kê rồi so tên. `list_tables()` có
        # phân trang (`page_token`) mà không đọc hết trang thì "không thấy tên" và "bảng thật
        # sự không tồn tại" lẫn vào nhau, chảy thẳng xuống `_tao_bang_moi` → ghi đè cả bảng.
        #
        # Cả hai backend ném `ValueError` với thông điệp chứa "was not found" khi mở bảng không
        # tồn tại, cùng qua `lancedb/db.py:1722` (lancedb 0.34.0). Đo trực tiếp 13/08: local
        # (embedded, DB tạm trong `.venv`) VÀ remote (LanceDB Cloud thật) — không phải suy đoán.
        #
        # Bộ lọc thông điệp dưới đây CHỊU LỰC, không phải phòng thủ thừa: `ValueError` là
        # built-in dùng cho vô số lý do, bắt trần nó thì MỘT `ValueError` bất kỳ từ `open_table`
        # (đối số sai, ...) sẽ bị hiểu nhầm thành "bảng chưa có" rồi ghi đè cả bảng thật. Chuỗi
        # "not found" vì thế là một hợp đồng ngầm với lancedb — nâng phiên bản thì đo lại; muốn
        # bỏ nó thì phải thay bằng một phép phân biệt chặt tương đương, không phải xoá suông.
        if "not found" not in str(e).lower():
            raise
        return _tao_bang_moi(db, rows)

    can_nap, du, id_cu = _doc_can_nap(tbl, rows)

    co_that = {r["doc_id"] for r in rows}
    can_nap |= ep & co_that
    for d in sorted(ep - co_that):
        print(f"[ingest] CẢNH BÁO: --doc {d} không có trong corpus, bỏ qua.")

    if du:
        # Ném TRƯỚC khi embed: sai corpus thì không được đốt tiền rồi mới báo.
        if not xoa_doc_du:
            raise DocDuTrongBang(du)
        tbl.delete(_loc_id([i for d in du for i in id_cu[d]]))
        print(f"[ingest] Đã xoá {len(du)} văn bản dư khỏi bảng: {', '.join(sorted(du))}")

    nap = [r for r in rows if r["doc_id"] in can_nap]
    if not nap:
        print("[ingest] Không văn bản nào đổi — bỏ qua embedding.")
        _cho_index(tbl)
        return 0, tbl.count_rows()

    _embed_rows(nap)
    (
        tbl.merge_insert("id")
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute(nap)
    )

    mo_coi = {i for d in can_nap for i in id_cu.get(d, set())} - {r["id"] for r in nap}
    if mo_coi:
        tbl.delete(_loc_id(list(mo_coi)))
        print(f"[ingest] Đã xoá {len(mo_coi)} chunk mồ côi (lần chẻ mới cho ít mảnh hơn).")

    _cho_index(tbl)
    return len(nap), tbl.count_rows()


def _cho_index(tbl) -> None:
    """Chờ index FTS phủ hết hàng vừa ghi, rồi KÊU nếu chưa phủ hết.

    Không gọi `create_fts_index` khi index đã có: với `overwrite` thì bắt buộc (bảng vừa bị dựng
    lại), nhưng với ghi tăng dần nó thành reindex toàn bảng mỗi lượt.

    Phần chưa vào index là phần nhánh sparse mù — không lỗi, chỉ kém đi. Đó là kiểu hỏng chỉ lộ
    ra ở bảng đo, nên phải kêu thành chữ.
    """
    chi_muc = tbl.list_indices()
    if not chi_muc:
        # Bảng có nhưng chưa từng index (tạo tay, hoặc create_fts_index từng lỗi).
        tbl.create_fts_index("text")
        return

    if not settings.lancedb_cloud_enabled:
        # LanceDB nhúng KHÔNG tự đưa hàng mới vào index FTS. Chờ ở đây là chờ một thứ không bao
        # giờ tới — dựng lại thẳng. Cục bộ nên chỉ tốn CPU, không tốn API.
        tbl.create_fts_index("text", replace=True)
        return

    ten = [c.name for c in chi_muc]
    try:
        tbl.wait_for_index(ten)
    except Exception as exc:  # noqa: BLE001 — chờ hỏng không được làm hỏng lượt ghi đã xong
        print(f"[ingest] CẢNH BÁO: chờ index {ten} lỗi ({exc}).")

    tong = tbl.count_rows()
    for c in tbl.list_indices():
        if c.num_indexed_rows != tong:
            print(
                f"[ingest] CẢNH BÁO: index {c.name} mới phủ {c.num_indexed_rows}/{tong} hàng "
                "— nhánh BM25 đang mù với phần còn lại."
            )


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
    n_ghi, n_tong = write_lancedb(rows)
    target = settings.lancedb_uri if settings.lancedb_cloud_enabled else settings.lancedb_path
    print(f"[ingest] Đã ghi {n_ghi} chunk, bảng có {n_tong} chunk ({target}), dim={EMBED_DIM}.")

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
    return n_ghi


def main(corpus_path: str | None = None) -> tuple[list[CorpusDocument], list[Relationship]]:
    path = corpus_path or "data/corpus.sample.json"
    print(f"[ingest] Đọc corpus: {path}")
    docs, rels = load_corpus(path)
    ingest_docs(docs, rels)
    return docs, rels
