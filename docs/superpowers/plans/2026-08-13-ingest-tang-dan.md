# Ingest tăng dần cho LanceDB — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `write_lancedb` chỉ embed và ghi những văn bản thật sự đổi, thay vì dựng lại cả bảng 661 chunk mỗi lượt.

**Architecture:** Tách `write_lancedb` thành *quyết định ghi gì* (`_doc_can_nap` — so vân tay hàng đọc từ chính bảng) và *ghi* (`merge_insert` theo `id`, rồi xoá id mồ côi). Không thêm module: cả hai chỉ có nghĩa cạnh `build_chunks` trong `app/ingestion/pipeline.py`. Neo4j giữ nguyên `DETACH DELETE` + nạp lại.

**Tech Stack:** Python 3.12 · uv · pytest · ruff · lancedb 0.34.0 (`RemoteTable` trên LanceDB Cloud) · Gemini `gemini-embedding-001`

**Spec:** `docs/superpowers/specs/2026-08-13-ingest-tang-dan-design.md`

## Global Constraints

- Message commit **tiếng Anh**, Conventional Commits — `docs/COMMIT-CONVENTION.md`.
- Test: `uv run pytest -q`. Lint: `uv run ruff check .`. Cả hai phải sạch trước mỗi commit.
- **Không test nào được chạm LanceDB Cloud.** Bảng giả, dựng từ `build_chunks` trên corpus tracked.
- Comment và docstring **tiếng Việt**, theo đúng giọng file đang sửa: nói *vì sao*, không kể lại *cái gì*.
- **Không đụng `app/knowledge/graph.py`** — Neo4j ngoài phạm vi.
- Mặc định của mọi tham số mới phải **an toàn**: `ep=frozenset()`, `xoa_doc_du=False`. `app/api/documents.py:245` gọi `ingest_docs(docs, rels)` trần.
- Đã đo 13/08 trên bảng thật, dùng lại chứ đừng đo lại: `count_rows()=661` · `.select()` loại được cột `vector` · quét toàn bảng không vector 5.29s · index FTS tên `text_idx`, `num_indexed_rows=661`.

---

### Task 1: Xác minh `merge_insert().execute()` chạy được trên `RemoteTable`

**GATE — nếu task này thất bại, dừng lại và báo chủ repo.** Toàn bộ Task 3 dựa vào giả định
`merge_insert` chạy được từ xa. Hiện mới chứng minh được là *dựng builder* được
(`LanceMergeInsertBuilder`), chưa chứng minh *chạy* được. Phương án lùi (`delete` theo `doc_id`
rồi `add`) đã bị chủ repo loại ở bước brainstorm vì nó tạo cửa sổ thiếu dữ liệu — nên nếu gate
này đỏ thì thiết kế phải mở lại, không được tự ý đổi.

**Files:**
- Create: `scripts/do_merge_insert_remote.py`

**Interfaces:**
- Consumes: `app.core.vectordb.connect`, `app.core.config.settings`
- Produces: không có API cho task sau; chỉ một kết luận đỏ/xanh ghi vào spec

- [ ] **Step 1: Viết script đo trên BẢNG NHÁP**

Bảng nháp tên có tiền tố rõ ràng và bị drop ở `finally`. **Không đụng `LANCEDB_TABLE`.**

```python
"""Đo: `merge_insert().execute()` có chạy trên LanceDB Cloud không.

Chạy trên một BẢNG NHÁP rồi drop — không đụng bảng đang phục vụ. Lý do phải đo: `hasattr` và
việc dựng được `LanceMergeInsertBuilder` chỉ chứng minh thuộc tính tồn tại, không chứng minh
backend từ xa cài đặt nó. Cả thiết kế ingest tăng dần đứng trên câu trả lời này.

Chạy: uv run python scripts/do_merge_insert_remote.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import vectordb  # noqa: E402
from app.core.config import settings  # noqa: E402

BANG_NHAP = "nhap_do_merge_insert"


def _hang(id_: str, text: str) -> dict:
    return {"id": id_, "doc_id": "NHAP", "text": text, "vector": [0.1, 0.2, 0.3]}


def main() -> int:
    print(f"cloud enabled: {settings.lancedb_cloud_enabled}")
    db = vectordb.connect()
    if BANG_NHAP in db.table_names():
        db.drop_table(BANG_NHAP)

    tbl = db.create_table(BANG_NHAP, data=[_hang("a", "cũ"), _hang("b", "giữ")])
    try:
        print(f"lớp bảng: {type(tbl).__name__} · {tbl.count_rows()} hàng")

        (
            tbl.merge_insert("id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute([_hang("a", "MỚI"), _hang("c", "thêm")])
        )

        sau = {r["id"]: r["text"] for r in tbl.search().select(["id", "text"]).limit(99).to_list()}
        print(f"sau merge_insert: {sau}")
        assert sau == {"a": "MỚI", "b": "giữ", "c": "thêm"}, f"merge_insert sai ngữ nghĩa: {sau}"

        tbl.delete("id IN ('b')")
        con = {r["id"] for r in tbl.search().select(["id"]).limit(99).to_list()}
        print(f"sau delete: {con}")
        assert con == {"a", "c"}, f"delete sai: {con}"
    finally:
        db.drop_table(BANG_NHAP)
        print(f"đã drop {BANG_NHAP}")

    print("\nXANH — merge_insert + delete chạy được trên bảng từ xa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Chạy script**

Run: `uv run python scripts/do_merge_insert_remote.py`

Expected: in ra `XANH — merge_insert + delete chạy được trên bảng từ xa.`

Nếu ném `NotImplementedError` / `LanceDBClientError` / HTTP 4xx: **DỪNG**, chép nguyên văn lỗi
vào spec mục "Điều chưa chắc", báo chủ repo. Không tự chuyển sang `delete`+`add`.

- [ ] **Step 3: Ghi kết quả vào spec**

Trong `docs/superpowers/specs/2026-08-13-ingest-tang-dan-design.md`, thay trọn mục
`## Điều chưa chắc, phải xử ở bước đầu của plan` bằng:

```markdown
## Đã xác minh (13/08)

`merge_insert(...).execute()` và `delete(...)` chạy đúng ngữ nghĩa trên `RemoteTable` — đo bằng
`scripts/do_merge_insert_remote.py` trên một bảng nháp rồi drop. Hàng khớp `id` được cập nhật,
hàng mới được chèn, hàng không nhắc tới giữ nguyên.
```

- [ ] **Step 4: Lint + commit**

```bash
uv run ruff check .
git add scripts/do_merge_insert_remote.py docs/superpowers/specs/2026-08-13-ingest-tang-dan-design.md
git commit -m "test(ingest): verify merge_insert works against a remote LanceDB table"
```

---

### Task 2: Phát hiện văn bản đã đổi — `_doc_can_nap`

**Files:**
- Modify: `app/ingestion/pipeline.py` (thêm hàm mới, chưa đụng `write_lancedb`)
- Create: `tests/test_ingest_tang_dan.py`

**Interfaces:**
- Consumes: `build_chunks`, `load_corpus` (đã có)
- Produces:
  - `_cot_du_lieu(tbl) -> list[str]`
  - `_van_tay(r: dict, cot: list[str]) -> tuple`
  - `_doc_can_nap(tbl, rows: list[dict]) -> tuple[set[str], set[str], dict[str, set[str]]]`
    trả `(doc cần nạp, doc dư trong bảng, doc_id → id đang có trong bảng)`
  - `class DocDuTrongBang(RuntimeError)` với thuộc tính `.doc_ids: list[str]`
  - Bảng giả `_BangGia` trong `tests/test_ingest_tang_dan.py` — Task 3 dùng lại nguyên vẹn

- [ ] **Step 1: Viết bảng giả + test thất bại**

Bảng giả viết **đủ cả phần ghi ngay từ đầu** để Task 3 không phải sửa lại nó.

Tạo `tests/test_ingest_tang_dan.py`:

```python
"""Ingest tăng dần: chỉ embed và ghi văn bản thật sự đổi.

Bảng giả ở đây KHÔNG mock hàm đang thử — nó mô phỏng đúng những lời gọi LanceDB mà `pipeline`
được phép dùng, rồi để hàm thật chạy trên đó. Mock `_doc_can_nap` rồi khẳng định nó đúng thì
chứng minh được gì; cùng lý do đã ghi ở `tests/test_lay_chunk_tien_to.py`.

Vân tay so CẢ HÀNG trừ `vector`, không phải mình `text`. Luật hết hiệu lực thì cái đổi là
`valid_to`/`superseded` — đúng hai trường bộ lọc `as_of` đọc. So mỗi `text` thì văn bản vừa
chết bị coi là "không đổi" và hệ thống tiếp tục trả nó, không lỗi, không cảnh báo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pytest

from app.ingestion import pipeline

_LOC_ID_RE = re.compile(r"^id IN \((.*)\)$")

_COT = [
    "id", "doc_id", "doc_title", "doc_type", "source",
    "article", "text", "valid_from", "valid_to", "superseded",
]


@dataclass
class _Truong:
    name: str


@dataclass
class _ChiMucGia:
    name: str
    num_indexed_rows: int


class _TruyVanGia:
    """Chỉ hiểu đúng cú pháp mà `_doc_can_nap` được phép dùng."""

    def __init__(self, hang: list[dict]) -> None:
        self._hang = hang
        self._cot: list[str] | None = None
        self._gioi_han: int | None = None

    def select(self, cot: list[str]):
        self._cot = list(cot)
        return self

    def limit(self, n: int):
        self._gioi_han = n
        return self

    def to_list(self) -> list[dict]:
        ra = self._hang[: self._gioi_han] if self._gioi_han else list(self._hang)
        if self._cot is None:
            return [dict(r) for r in ra]
        return [{k: r[k] for k in self._cot} for r in ra]


class _MergeGia:
    def __init__(self, bang: "_BangGia") -> None:
        self._bang = bang

    def when_matched_update_all(self):
        return self

    def when_not_matched_insert_all(self):
        return self

    def execute(self, rows: list[dict]) -> None:
        self._bang.nhat_ky.append(f"merge_insert:{len(rows)}")
        for r in rows:
            self._bang.hang[r["id"]] = dict(r)


@dataclass
class _BangGia:
    """Bảng LanceDB giả: đủ đọc cho `_doc_can_nap`, đủ ghi cho `write_lancedb`."""

    hang: dict[str, dict]
    co_index: bool = True
    #: Số hàng index FTS báo là đã phủ. `None` = phủ đủ. Đặt số nhỏ hơn để dựng ca index chạy sau.
    index_phu: int | None = None
    nhat_ky: list[str] = field(default_factory=list)

    @property
    def schema(self) -> list[_Truong]:
        return [_Truong(k) for k in [*_COT, "vector"]]

    def count_rows(self) -> int:
        return len(self.hang)

    def search(self, *a, **kw) -> _TruyVanGia:
        return _TruyVanGia([dict(r) for r in self.hang.values()])

    def list_indices(self) -> list[_ChiMucGia]:
        if not self.co_index:
            return []
        phu = len(self.hang) if self.index_phu is None else self.index_phu
        return [_ChiMucGia("text_idx", phu)]

    def wait_for_index(self, ten, *a, **kw) -> None:
        self.nhat_ky.append(f"wait_for_index:{','.join(ten)}")

    def merge_insert(self, khoa: str) -> _MergeGia:
        assert khoa == "id", f"khoá merge phải là id, không phải {khoa!r}"
        return _MergeGia(self)

    def delete(self, dieu_kien: str) -> None:
        m = _LOC_ID_RE.match(dieu_kien)
        assert m, f"cú pháp delete lạ, cloud có thể không nhận: {dieu_kien!r}"
        ids = {s.strip()[1:-1].replace("''", "'") for s in m.group(1).split(", ")}
        self.nhat_ky.append(f"delete:{len(ids)}")
        for i in ids:
            self.hang.pop(i, None)

    def create_fts_index(self, cot: str, **kw) -> None:
        self.nhat_ky.append("create_fts_index")


def _hang(doc_id: str, article: str, text: str, valid_to: str = "") -> dict:
    return {
        "id": f"{doc_id}::{article}", "doc_id": doc_id, "doc_title": f"VB {doc_id}",
        "doc_type": "Thông tư", "source": "vbpl", "article": article, "text": text,
        "valid_from": "2024-01-01", "valid_to": valid_to, "superseded": False,
    }


def _bang(rows: list[dict]) -> _BangGia:
    return _BangGia(hang={r["id"]: {**r, "vector": [0.0]} for r in rows})


# --- phát hiện thay đổi ---------------------------------------------------------------------

def test_khong_doi_thi_khong_doc_nao_can_nap():
    rows = [_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")]
    can_nap, du, _ = pipeline._doc_can_nap(_bang(rows), rows)
    assert can_nap == set()
    assert du == set()


def test_doi_text_thi_doc_do_can_nap():
    cu = [_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA"), _hang("B", "Điều 1", "y")]
    can_nap, _, _ = pipeline._doc_can_nap(_bang(cu), moi)
    assert can_nap == {"A"}


def test_doi_valid_to_ma_text_y_nguyen_van_can_nap():
    """Luật hết hiệu lực đổi `valid_to` chứ không đổi chữ — so mỗi text là bỏ sót đúng ca này."""
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x", valid_to="2026-01-01")]
    can_nap, _, _ = pipeline._doc_can_nap(_bang(cu), moi)
    assert can_nap == {"A"}


def test_doc_moi_hoan_toan_thi_can_nap():
    cu = [_hang("A", "Điều 1", "x")]
    moi = [*cu, _hang("MOI", "Điều 1", "z")]
    can_nap, du, _ = pipeline._doc_can_nap(_bang(cu), moi)
    assert can_nap == {"MOI"}
    assert du == set()


def test_doc_co_trong_bang_ma_khong_co_trong_corpus_la_du():
    cu = [_hang("A", "Điều 1", "x"), _hang("BI_GO", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x")]
    can_nap, du, _ = pipeline._doc_can_nap(_bang(cu), moi)
    assert can_nap == set()
    assert du == {"BI_GO"}


def test_tra_ve_id_cu_de_khoi_quet_bang_lan_hai():
    cu = [_hang("A", "Điều 1", "x"), _hang("A", "Điều 2", "x2")]
    can_nap, _, id_cu = pipeline._doc_can_nap(_bang(cu), cu)
    assert id_cu["A"] == {"A::Điều 1", "A::Điều 2"}
    assert can_nap == set()


def test_bang_rong_thi_moi_doc_deu_can_nap():
    moi = [_hang("A", "Điều 1", "x")]
    can_nap, du, id_cu = pipeline._doc_can_nap(_bang([]), moi)
    assert can_nap == {"A"}
    assert du == set() and id_cu == {}


def test_van_tay_khong_dung_cot_vector():
    """Vector là HỆ QUẢ của text — đưa nó vào vân tay là so 768 float để biết điều text đã nói."""
    assert "vector" not in pipeline._cot_du_lieu(_bang([_hang("A", "Điều 1", "x")]))
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

Run: `uv run pytest tests/test_ingest_tang_dan.py -q`

Expected: FAIL — `AttributeError: module 'app.ingestion.pipeline' has no attribute '_doc_can_nap'`

- [ ] **Step 3: Cài đặt**

Trong `app/ingestion/pipeline.py`, chèn **ngay trên** `def write_lancedb`:

```python
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
```

- [ ] **Step 4: Chạy test, xác nhận XANH**

Run: `uv run pytest tests/test_ingest_tang_dan.py -q`
Expected: 8 passed

- [ ] **Step 5: Chạy toàn bộ test + lint**

Run: `uv run pytest -q; uv run ruff check .`
Expected: tất cả xanh, ruff không báo gì (chưa đụng `write_lancedb` nên chưa test nào hỏng)

- [ ] **Step 6: Commit**

```bash
git add app/ingestion/pipeline.py tests/test_ingest_tang_dan.py
git commit -m "feat(ingest): detect which documents changed by fingerprinting table rows"
```

---

### Task 3: `write_lancedb` ghi tăng dần + xoá chunk mồ côi

**Files:**
- Modify: `app/ingestion/pipeline.py:229-240` (`write_lancedb`)
- Modify: `tests/test_ingest_tang_dan.py` (thêm ca; bảng giả giữ nguyên)
- Modify: `tests/test_ingest_noi_lop_phu.py:40` (chữ ký `write_lancedb` đổi ⇒ mock cũ sai)

**Interfaces:**
- Consumes: `_doc_can_nap`, `DocDuTrongBang`, `_cot_du_lieu` (Task 2); `_embed_rows` (đã có)
- Produces:
  - `write_lancedb(rows, ep=frozenset(), xoa_doc_du=False) -> tuple[int, int]`
    trả `(số chunk vừa ghi, tổng chunk trong bảng)`
  - `_loc_id(ids: list[str]) -> str`
  - `_tao_bang_moi(db, rows) -> tuple[int, int]`
  - `_cho_index(tbl) -> None` — task này cho nó **giữ nguyên hành vi hiện tại** (dựng index
    như `write_lancedb` cũ vẫn làm). Task 4 đổi sang chờ. Không để lại thân rỗng: một commit
    không được chứa hàm chết, và mỗi task phải tự đứng được nếu dừng lại ở đó.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_ingest_tang_dan.py`:

```python
# --- ghi tăng dần ---------------------------------------------------------------------------

@pytest.fixture
def khong_goi_mang(monkeypatch):
    """Đếm số hàng đi qua embedding. Gọi Gemini trong test là hỏng, không phải chậm."""
    da_embed: list[int] = []

    def _gia(rows):
        da_embed.append(len(rows))
        for r in rows:
            r["vector"] = [0.0]

    monkeypatch.setattr(pipeline, "_embed_rows", _gia)
    return da_embed


def _noi_bang(monkeypatch, bang: _BangGia) -> None:
    """Bắt `vectordb.connect()` trả về DB giả đã có sẵn bảng."""

    class _DbGia:
        def table_names(self):
            return [pipeline.LANCEDB_TABLE]

        def open_table(self, ten):
            assert ten == pipeline.LANCEDB_TABLE
            return bang

    monkeypatch.setattr(pipeline.vectordb, "connect", lambda: _DbGia())


def test_khong_doi_gi_thi_khong_embed_hang_nao(monkeypatch, khong_goi_mang, capsys):
    rows = [_hang("A", "Điều 1", "x")]
    bang = _bang(rows)
    _noi_bang(monkeypatch, bang)

    n_ghi, n_tong = pipeline.write_lancedb(rows)

    assert khong_goi_mang == [], "corpus không đổi mà vẫn gọi embedding"
    assert (n_ghi, n_tong) == (0, 1)
    assert not [x for x in bang.nhat_ky if x.startswith("merge_insert")]
    assert "Không văn bản nào đổi" in capsys.readouterr().out


def test_chi_embed_va_ghi_doc_da_doi(monkeypatch, khong_goi_mang):
    cu = [_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA"), _hang("B", "Điều 1", "y")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    n_ghi, n_tong = pipeline.write_lancedb(moi)

    assert khong_goi_mang == [1], "chỉ 1 chunk của A được embed"
    assert (n_ghi, n_tong) == (1, 2)
    assert bang.hang["A::Điều 1"]["text"] == "x ĐÃ SỬA"
    assert bang.hang["B::Điều 1"]["text"] == "y"


def test_che_ra_it_manh_hon_thi_id_mo_coi_bi_xoa(monkeypatch, khong_goi_mang):
    """`merge_insert` chỉ biết id ta đưa vào — nhãn cũ không còn phải bị xoá riêng.

    Ca thật: `label` suy từ nội dung, nên chẻ lại có thể sinh ít mảnh hơn (T2 thêm hậu tố
    `(2)` đã đổi cả tập nhãn của TT23-2019). Không xoá thì nhãn cũ nằm lại vĩnh viễn — chunk
    ma, vẫn được truy hồi, vẫn được trích dẫn.
    """
    cu = [_hang("A", "Điều 1 Khoản 1", "p"), _hang("A", "Điều 1 Khoản 2", "q")]
    moi = [_hang("A", "Điều 1", "p q")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    assert set(bang.hang) == {"A::Điều 1"}
    assert "delete:2" in bang.nhat_ky


def test_doc_du_thi_nem_chu_khong_xoa(monkeypatch, khong_goi_mang):
    cu = [_hang("A", "Điều 1", "x"), _hang("BI_GO", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    with pytest.raises(pipeline.DocDuTrongBang) as e:
        pipeline.write_lancedb(moi)

    assert e.value.doc_ids == ["BI_GO"]
    assert "BI_GO::Điều 1" in bang.hang, "ném rồi mà vẫn xoá — mất dữ liệu"
    assert khong_goi_mang == [], "ném rồi mà vẫn đốt embedding"


def test_co_co_xoa_doc_du_thi_moi_xoa(monkeypatch, khong_goi_mang):
    cu = [_hang("A", "Điều 1", "x"), _hang("BI_GO", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    n_ghi, n_tong = pipeline.write_lancedb(moi, xoa_doc_du=True)

    assert set(bang.hang) == {"A::Điều 1"}
    assert (n_ghi, n_tong) == (0, 1)


def test_co_ep_nap_lai_du_van_tay_khop(monkeypatch, khong_goi_mang):
    rows = [_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")]
    bang = _bang(rows)
    _noi_bang(monkeypatch, bang)

    n_ghi, _ = pipeline.write_lancedb(rows, ep=frozenset({"A"}))

    assert khong_goi_mang == [1] and n_ghi == 1


def test_ep_doc_khong_co_trong_corpus_thi_canh_bao(monkeypatch, khong_goi_mang, capsys):
    rows = [_hang("A", "Điều 1", "x")]
    _noi_bang(monkeypatch, _bang(rows))

    pipeline.write_lancedb(rows, ep=frozenset({"KHONG-CO"}))

    assert "KHONG-CO" in capsys.readouterr().out


def test_bang_chua_ton_tai_thi_dung_duong_cu(monkeypatch, khong_goi_mang):
    """Lần đầu (máy mới, local, CI) không có bảng để so — phải dựng như trước."""
    da_tao: list[str] = []

    class _DbTrong:
        def table_names(self):
            return []

        def create_table(self, ten, data, mode):
            da_tao.append(f"{ten}:{mode}:{len(data)}")
            return _bang(data)

    monkeypatch.setattr(pipeline.vectordb, "connect", lambda: _DbTrong())
    rows = [_hang("A", "Điều 1", "x")]

    n_ghi, n_tong = pipeline.write_lancedb(rows)

    assert da_tao == [f"{pipeline.LANCEDB_TABLE}:overwrite:1"]
    assert (n_ghi, n_tong) == (1, 1)
    assert khong_goi_mang == [1]


def test_id_co_nhay_don_khong_lam_vo_bo_loc():
    """Nhãn điều đến từ văn bản luật — một dấu nháy lọt vào là câu lọc SQL vỡ."""
    assert pipeline._loc_id(["A::Điều 1", "B::Đi'ều"]) == "id IN ('A::Điều 1', 'B::Đi''ều')"


def test_quet_bang_hong_thi_nem_chu_khong_roi_ve_ghi_de(monkeypatch, khong_goi_mang):
    """Mạng trục trặc KHÔNG được biến thành ghi đè cả bảng.

    Rơi về `create_table(mode="overwrite")` cho "an toàn" nghĩa là một lần rớt kết nối thoáng
    qua thành hoá đơn embedding 661 chunk — mà kết quả cuối vẫn đúng, nên không ai biết. Đây là
    loại dự phòng phải CỐ Ý không viết.
    """
    rows = [_hang("A", "Điều 1", "x")]
    bang = _bang(rows)

    def _no(*a, **kw):
        raise RuntimeError("LanceDB Cloud lỗi")

    bang.search = _no
    _noi_bang(monkeypatch, bang)

    with pytest.raises(RuntimeError, match="LanceDB Cloud lỗi"):
        pipeline.write_lancedb(rows)

    assert khong_goi_mang == [], "quét hỏng mà vẫn embed — đúng cái đang phòng"
    assert "create_fts_index" not in bang.nhat_ky


def test_chay_lai_lan_hai_khong_embed_gi_them(monkeypatch, khong_goi_mang):
    """Tính bình ổn: chết giữa chừng rồi chạy lại phải tự lành, không nạp lại vô hạn."""
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)
    assert khong_goi_mang == [1]

    pipeline.write_lancedb(moi)
    assert khong_goi_mang == [1], "lượt hai vẫn embed ⇒ vân tay không khớp lại được sau khi ghi"
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

Run: `uv run pytest tests/test_ingest_tang_dan.py -q`
Expected: FAIL — `write_lancedb() got an unexpected keyword argument 'ep'` và `no attribute '_loc_id'`

- [ ] **Step 3: Cài đặt**

Thay trọn `write_lancedb` (`app/ingestion/pipeline.py:229-240`) bằng:

```python
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
    if LANCEDB_TABLE not in db.table_names():
        return _tao_bang_moi(db, rows)

    tbl = db.open_table(LANCEDB_TABLE)
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
    """Giữ nguyên hành vi index của `write_lancedb` cũ. Task 4 đổi sang chờ thay vì dựng lại."""
    if settings.lancedb_cloud_enabled:
        tbl.create_fts_index("text")
    else:
        tbl.create_fts_index("text", replace=True)
```

Và sửa `tests/test_ingest_noi_lop_phu.py` dòng 40 — chữ ký `write_lancedb` vừa đổi nên mock cũ
sai cả tham số lẫn kiểu trả về. Thay:

```python
    monkeypatch.setattr(pipeline, "write_lancedb", lambda rows: len(rows))
```

bằng:

```python
    monkeypatch.setattr(pipeline, "write_lancedb", lambda rows, **kw: (len(rows), len(rows)))
```

Và trong `ingest_docs`, mở gói tuple — không thì commit này để lại một hàm in ra
`(3, 661) chunk`. Chữ ký và kiểu trả về của `ingest_docs` **chưa đổi** ở task này (Task 5 lo đó).
Thay:

```python
    n = write_lancedb(rows)
    target = settings.lancedb_uri if settings.lancedb_cloud_enabled else settings.lancedb_path
    print(f"[ingest] Đã ghi {n} chunk vào LanceDB ({target}), dim={EMBED_DIM}.")
```

bằng:

```python
    n_ghi, n_tong = write_lancedb(rows)
    target = settings.lancedb_uri if settings.lancedb_cloud_enabled else settings.lancedb_path
    print(f"[ingest] Đã ghi {n_ghi} chunk, bảng có {n_tong} chunk ({target}), dim={EMBED_DIM}.")
```

và dòng cuối `return n` thành `return n_ghi`.

- [ ] **Step 4: Chạy test, xác nhận XANH**

Run: `uv run pytest tests/test_ingest_tang_dan.py -q`
Expected: 19 passed (8 của Task 2 + 11 của task này)

- [ ] **Step 5: Toàn bộ test + lint**

Run: `uv run pytest -q; uv run ruff check .`

Expected: **tất cả xanh.** Suite không được đỏ sau bất kỳ commit nào (Global Constraints) — nếu
`test_ingest_noi_lop_phu.py` còn đỏ thì Step 3 chưa sửa xong mock ở dòng 40.

- [ ] **Step 6: Commit**

```bash
git add app/ingestion/pipeline.py tests/test_ingest_tang_dan.py tests/test_ingest_noi_lop_phu.py
git commit -m "feat(ingest): write only changed documents via merge_insert"
```

---

### Task 4: Index FTS — chờ thay vì dựng lại mỗi lượt

**Files:**
- Modify: `app/ingestion/pipeline.py` (`_cho_index`)
- Modify: `tests/test_ingest_tang_dan.py` (thêm ca)

**Interfaces:**
- Consumes: `settings.lancedb_cloud_enabled`
- Produces: `_cho_index(tbl) -> None` (thân thật)

Lý do task này tách riêng: `write_lancedb` hiện gọi `create_fts_index` **mỗi lượt** — bắt buộc
khi bảng vừa bị `overwrite` dựng lại, nhưng với ghi tăng dần thì thành **reindex toàn bảng mỗi
lần**, đắt hơn chính thứ đang đi tiết kiệm. Quên chỗ này thì mọi thứ vẫn *đúng*, chỉ đắt — sẽ
không ai phát hiện.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_ingest_tang_dan.py`:

```python
# --- index FTS ------------------------------------------------------------------------------

def test_bang_da_co_index_thi_khong_dung_lai(monkeypatch, khong_goi_mang):
    """Dựng lại index mỗi lượt là reindex toàn bảng — đắt hơn chính thứ đang tiết kiệm."""
    monkeypatch.setattr(pipeline.settings, "lancedb_uri", "db://x")
    monkeypatch.setattr(pipeline.settings, "lancedb_api_key", "k")
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    assert "create_fts_index" not in bang.nhat_ky
    assert "wait_for_index:text_idx" in bang.nhat_ky


def test_bang_chua_co_index_thi_dung(monkeypatch, khong_goi_mang):
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    bang.co_index = False
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    assert "create_fts_index" in bang.nhat_ky


def test_index_phu_thieu_hang_thi_canh_bao(monkeypatch, khong_goi_mang, capsys):
    """Hàng chưa vào index là hàng nhánh BM25 mù — im lặng ở đây là nửa hybrid chết."""
    monkeypatch.setattr(pipeline.settings, "lancedb_uri", "db://x")
    monkeypatch.setattr(pipeline.settings, "lancedb_api_key", "k")
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA"), _hang("B", "Điều 1", "y")]
    bang = _bang(cu)
    bang.index_phu = 1  # index đứng yên ở 1 hàng dù bảng sắp có 2
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    ra = capsys.readouterr().out
    assert "CẢNH BÁO" in ra and "1/2" in ra
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

Run: `uv run pytest tests/test_ingest_tang_dan.py -k index -q`
Expected: FAIL — bản Task 3 của `_cho_index` dựng index mỗi lượt, nên
`"create_fts_index" not in bang.nhat_ky` đỏ và `wait_for_index` không bao giờ được gọi

- [ ] **Step 3: Cài đặt**

Thay trọn thân `_cho_index` (Task 3 để nó dựng index như cũ) bằng:

```python
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
```

- [ ] **Step 4: Chạy test, xác nhận XANH**

Run: `uv run pytest tests/test_ingest_tang_dan.py -q`
Expected: 22 passed

- [ ] **Step 5: Lint**

Run: `uv run ruff check .`
Expected: sạch

- [ ] **Step 6: Commit**

```bash
git add app/ingestion/pipeline.py tests/test_ingest_tang_dan.py
git commit -m "perf(ingest): wait for the FTS index instead of rebuilding it each run"
```

---

### Task 5: `ingest_docs` truyền cờ, `n_chunks` đổi nghĩa

**Files:**
- Modify: `app/ingestion/pipeline.py:300-325` (`ingest_docs`)
- Modify: `app/api/documents.py:245`, `:254`
- Modify: `tests/test_documents.py:58-60`

(`tests/test_ingest_noi_lop_phu.py` đã được Task 3 sửa — nó mock `write_lancedb`, không mock
`ingest_docs`, nên chữ ký mới ở task này không chạm tới nó.)

**Interfaces:**
- Consumes: `write_lancedb(rows, ep, xoa_doc_du) -> tuple[int, int]` (Task 3)
- Produces: `ingest_docs(docs, rels, ep=frozenset(), xoa_doc_du=False) -> tuple[int, int]`

- [ ] **Step 1: Sửa test cũ cho khớp kiểu trả về mới**

Trong `tests/test_documents.py`, dòng 58-60, thay:

```python
    def fake_ingest(docs, rels):
        store["ingested"] = sum(len(d.articles) for d in docs)
        return store["ingested"]
```

bằng:

```python
    def fake_ingest(docs, rels, **kw):
        store["ingested"] = sum(len(d.articles) for d in docs)
        return store["ingested"], store["ingested"]
```

- [ ] **Step 2: Viết test thất bại cho việc truyền cờ**

Thêm vào cuối `tests/test_ingest_tang_dan.py`:

```python
# --- ingest_docs ----------------------------------------------------------------------------

def test_ingest_docs_chuyen_tiep_co_xuong_write(monkeypatch):
    """Cờ phải đi hết đường xuống; nuốt mất thì `--doc` im lặng không làm gì."""
    from app.core.schemas import CorpusDocument

    nhan: dict = {}

    def _gia(rows, ep=frozenset(), xoa_doc_du=False):
        nhan.update(ep=ep, xoa_doc_du=xoa_doc_du)
        return len(rows), 99

    monkeypatch.setattr(pipeline, "write_lancedb", _gia)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    docs = [
        CorpusDocument.model_validate({
            "doc_id": "A", "title": "VB A", "doc_type": "Thông tư", "source": "vbpl",
            "valid_from": "2024-01-01", "so_hieu": "1/2024/TT-NHNN",
            "articles": [{"article": "Điều 1", "text": "Nội dung."}],
        })
    ]

    n_ghi, n_tong = pipeline.ingest_docs(docs, [], ep=frozenset({"A"}), xoa_doc_du=True)

    assert nhan == {"ep": frozenset({"A"}), "xoa_doc_du": True}
    assert (n_ghi, n_tong) == (1, 99)


def test_ingest_docs_mac_dinh_khong_ep_khong_xoa(monkeypatch):
    """`app/api/documents.py` gọi trần — mặc định phải không bao giờ xoá được gì."""
    from app.core.schemas import CorpusDocument

    nhan: dict = {}

    def _gia(rows, ep=frozenset(), xoa_doc_du=False):
        nhan.update(ep=ep, xoa_doc_du=xoa_doc_du)
        return len(rows), 1

    monkeypatch.setattr(pipeline, "write_lancedb", _gia)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    docs = [
        CorpusDocument.model_validate({
            "doc_id": "A", "title": "VB A", "doc_type": "Thông tư", "source": "vbpl",
            "valid_from": "2024-01-01", "so_hieu": "1/2024/TT-NHNN",
            "articles": [{"article": "Điều 1", "text": "Nội dung."}],
        })
    ]
    pipeline.ingest_docs(docs, [])

    assert nhan == {"ep": frozenset(), "xoa_doc_du": False}
```

- [ ] **Step 3: Chạy test, xác nhận ĐỎ**

Run: `uv run pytest tests/test_ingest_tang_dan.py -k ingest_docs -q`
Expected: FAIL — `ingest_docs() got an unexpected keyword argument 'ep'`

- [ ] **Step 4: Sửa `ingest_docs`**

Trong `app/ingestion/pipeline.py`, thay phần đầu của `ingest_docs` (Task 3 đã sửa hai dòng
`print`/`write_lancedb` bên trong; task này đổi **chữ ký, docstring và kiểu trả về**):

```python
def ingest_docs(docs: list[CorpusDocument], rels: list[Relationship]) -> int:
    """Lõi ingest: chunks → LanceDB (+ Neo4j nếu có). Trả về số chunk."""
    rows = build_chunks(docs)
    print(f"[ingest] {len(docs)} văn bản → {len(rows)} chunk. Đang embedding (Gemini)...")
    n_ghi, n_tong = write_lancedb(rows)
    target = settings.lancedb_uri if settings.lancedb_cloud_enabled else settings.lancedb_path
    print(f"[ingest] Đã ghi {n_ghi} chunk, bảng có {n_tong} chunk ({target}), dim={EMBED_DIM}.")
```

bằng:

```python
def ingest_docs(
    docs: list[CorpusDocument],
    rels: list[Relationship],
    ep: frozenset[str] = frozenset(),
    xoa_doc_du: bool = False,
) -> tuple[int, int]:
    """Lõi ingest: chunks → LanceDB (+ Neo4j nếu có). Trả `(số chunk vừa ghi, tổng trong bảng)`.

    Mặc định của `ep`/`xoa_doc_du` phải an toàn: `app/api/documents.py` gọi hàm này trần, nên
    một lỗi đồng bộ ở corpus canonical không được phép biến thành xoá dữ liệu ở LanceDB.
    """
    rows = build_chunks(docs)
    print(f"[ingest] {len(docs)} văn bản → {len(rows)} chunk.")
    n_ghi, n_tong = write_lancedb(rows, ep=ep, xoa_doc_du=xoa_doc_du)
    target = settings.lancedb_uri if settings.lancedb_cloud_enabled else settings.lancedb_path
    print(
        f"[ingest] Đã ghi {n_ghi} chunk, bảng có {n_tong} chunk "
        f"({target}), dim={EMBED_DIM}."
    )
```

Và dòng cuối `return n_ghi` (Task 3 để lại) thành `return n_ghi, n_tong`.

- [ ] **Step 5: Sửa `app/api/documents.py`**

Dòng 245, thay `n_chunks = ingest_docs(docs, rels)` bằng:

```python
    # `n_chunks` giờ là số chunk VỪA GHI cho văn bản vừa duyệt, không phải tổng corpus như
    # trước. Với thao tác "duyệt một văn bản" thì đây mới là con số đúng; tổng đi vào audit
    # dưới khoá riêng để vẫn tra ngược được.
    n_chunks, n_chunks_bang = ingest_docs(docs, rels)
```

Dòng 254, thay `detail=` bằng:

```python
        detail={
            "doc_id": doc.doc_id, "n_chunks": n_chunks,
            "n_chunks_bang": n_chunks_bang, "n_events": n_events,
        },
```

- [ ] **Step 6: Chạy toàn bộ test**

Run: `uv run pytest -q`
Expected: tất cả xanh, gồm `test_ingest_noi_lop_phu.py` và `test_documents.py`

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check .
git add app/ingestion/pipeline.py app/api/documents.py tests/test_ingest_tang_dan.py tests/test_ingest_noi_lop_phu.py tests/test_documents.py
git commit -m "feat(ingest): thread force and prune flags through ingest_docs"
```

---

### Task 6: CLI — `argparse` thay cho `sys.argv[1]`

**Files:**
- Modify: `app/ingestion/__main__.py`
- Modify: `app/ingestion/pipeline.py` (`main`)
- Modify: `tests/test_ingest_tang_dan.py` (thêm ca)

**Interfaces:**
- Consumes: `ingest_docs(docs, rels, ep, xoa_doc_du) -> tuple[int, int]` (Task 5)
- Produces: `main(corpus_path=None, ep=frozenset(), xoa_doc_du=False) -> tuple[list, list]`

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_ingest_tang_dan.py`:

```python
# --- CLI ------------------------------------------------------------------------------------

def test_cli_doc_lap_lai_duoc_va_mac_dinh_khong_xoa():
    from app.ingestion.__main__ import phan_tich

    a = phan_tich(["data/corpus.real.json", "--doc", "TT66-2025", "--doc", "TT23-2019"])
    assert a.corpus == "data/corpus.real.json"
    assert set(a.doc) == {"TT66-2025", "TT23-2019"}
    assert a.xoa_doc_du is False


def test_cli_khong_tham_so_thi_giu_mac_dinh_cu():
    from app.ingestion.__main__ import phan_tich

    a = phan_tich([])
    assert a.corpus == "data/corpus.sample.json"
    assert a.doc == [] and a.xoa_doc_du is False


def test_cli_bat_duoc_co_xoa():
    from app.ingestion.__main__ import phan_tich

    assert phan_tich(["c.json", "--xoa-doc-du"]).xoa_doc_du is True
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

Run: `uv run pytest tests/test_ingest_tang_dan.py -k cli -q`
Expected: FAIL — `cannot import name 'phan_tich'`

- [ ] **Step 3: Viết lại `app/ingestion/__main__.py`**

```python
"""uv run python -m app.ingestion [corpus.json] [--doc ID]... [--xoa-doc-du]"""
from __future__ import annotations

import argparse
import sys

from app.ingestion.pipeline import DocDuTrongBang, main


def phan_tich(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m app.ingestion")
    p.add_argument("corpus", nargs="?", default="data/corpus.sample.json")
    p.add_argument(
        "--doc", action="append", default=[],
        help="ép nạp lại văn bản này dù vân tay khớp (lặp lại được)",
    )
    p.add_argument(
        "--xoa-doc-du", action="store_true",
        help="xoá khỏi bảng những văn bản không còn trong corpus",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    a = phan_tich(sys.argv[1:])
    try:
        main(a.corpus, ep=frozenset(a.doc), xoa_doc_du=a.xoa_doc_du)
    except DocDuTrongBang as exc:
        # Ca hay gặp nhất của lỗi này là gõ nhầm đường dẫn corpus, nên nói thẳng ra.
        print(f"[ingest] DỪNG: {exc}", file=sys.stderr)
        print(f"[ingest] corpus đang dùng: {a.corpus}", file=sys.stderr)
        raise SystemExit(1) from exc
```

- [ ] **Step 4: Sửa `main` trong `pipeline.py`**

Thay chữ ký và lời gọi (dòng 328-333):

```python
def main(
    corpus_path: str | None = None,
    ep: frozenset[str] = frozenset(),
    xoa_doc_du: bool = False,
) -> tuple[list[CorpusDocument], list[Relationship]]:
    path = corpus_path or "data/corpus.sample.json"
    print(f"[ingest] Đọc corpus: {path}")
    docs, rels = load_corpus(path)
    ingest_docs(docs, rels, ep=ep, xoa_doc_du=xoa_doc_du)
    return docs, rels
```

- [ ] **Step 5: Chạy test + lint**

Run: `uv run pytest -q; uv run ruff check .`
Expected: tất cả xanh

- [ ] **Step 6: Commit**

```bash
git add app/ingestion/__main__.py app/ingestion/pipeline.py tests/test_ingest_tang_dan.py
git commit -m "feat(ingest): add --doc and --xoa-doc-du flags via argparse"
```

---

### Task 7: Kiểm trên dữ liệu thật (chỉ đọc) + tài liệu

**Files:**
- Create: `scripts/soi_doc_can_nap.py`
- Modify: `docs/TASKLIST.md`
- Modify: `docs/WORKLOG.md`

**Interfaces:**
- Consumes: `_doc_can_nap` (Task 2), `build_chunks` / `load_corpus` (đã có)
- Produces: không có API; một kết luận về tính đúng đắn trên dữ liệu thật

Test dùng bảng giả nên **không** bắt được lệch KIỂU giữa cái `build_chunks` sinh ra và cái
LanceDB trả về (`None` so với `""`, bool so với numpy bool). Lệch kiểu làm mọi vân tay khác nhau
⇒ `can_nap` = toàn bộ corpus ⇒ ingest tăng dần âm thầm thoái hoá về ingest toàn bộ, vẫn đúng
kết quả, chỉ đắt y như cũ. Chỉ dữ liệu thật mới lộ ra.

- [ ] **Step 1: Viết script soi, chỉ ĐỌC**

```python
"""Đối chiếu `data/corpus.real.json` với bảng LanceDB đang phục vụ. CHỈ ĐỌC, không ghi gì.

Không có bước này thì một lệch kiểu (`None` so với `""`) làm mọi vân tay khác nhau, `can_nap`
thành toàn bộ corpus, và ingest tăng dần thoái hoá về ingest toàn bộ — vẫn ra kết quả đúng,
vẫn tốn đúng ngần ấy tiền, không ai biết.

Chạy: uv run python scripts/soi_doc_can_nap.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import vectordb  # noqa: E402
from app.core.config import LANCEDB_TABLE  # noqa: E402
from app.ingestion.pipeline import _doc_can_nap, build_chunks, load_corpus  # noqa: E402

docs, _ = load_corpus("data/corpus.real.json")
rows = build_chunks(docs)
tbl = vectordb.connect().open_table(LANCEDB_TABLE)

can_nap, du, id_cu = _doc_can_nap(tbl, rows)

print(f"corpus:  {len(docs)} văn bản → {len(rows)} chunk")
print(f"bảng:    {tbl.count_rows()} chunk / {len(id_cu)} văn bản")
print(f"\ncần nạp ({len(can_nap)}): {', '.join(sorted(can_nap)) or '(không có)'}")
print(f"dư      ({len(du)}): {', '.join(sorted(du)) or '(không có)'}")

n = sum(len(r['id']) > 0 for r in rows if r["doc_id"] in can_nap)
print(f"\nnếu chạy ingest bây giờ: embed {n}/{len(rows)} chunk")
```

- [ ] **Step 2: Chạy và ĐỌC KỸ kết quả**

Run: `uv run python scripts/soi_doc_can_nap.py`

Đối chiếu với ba điều đã biết trước:

| Nếu thấy | Nghĩa là |
|---|---|
| `cần nạp` chứa `TT66-2025` | **Đúng như mong đợi** — `docs/TASKLIST.md` T1 ghi chunk `TT66-2025 Điều 6` trong bảng là bản cắt hỏng từ trước bản vá `8dd53f0`. Phát hiện được đúng ca này là bằng chứng mạnh nhất rằng vân tay hoạt động. |
| `cần nạp` **rỗng** | **ĐỎ** — không thể rỗng, vì T1 nói bảng đang lệch. Vân tay đang so nhầm cái gì đó. Dừng, báo chủ repo. |
| `cần nạp` = **toàn bộ** văn bản | **ĐỎ** — gần như chắc chắn lệch kiểu. Chạy `python -c` in ra một hàng của `build_chunks` cạnh một hàng `tbl.search().select(...)` cùng `id`, so từng cột, tìm cột khác kiểu. Sửa bằng chuẩn hoá **trong `_van_tay`**, kèm test ghim, chứ không phải nới lỏng phép so. |
| `dư` chứa 23 văn bản cào 12/08 | **Không** phải lỗi — chúng chưa vào `corpus.real.json` (T23). Nhưng chúng phải nằm ở `cần nạp` sau khi gộp corpus, không phải ở `dư`. |

- [ ] **Step 3: Commit script kèm kết quả đo**

Chép nguyên văn output vào docstring của script, dưới dòng `Chạy: ...`, dạng:

```
Kết quả 13/08: cần nạp = TT66-2025 (N chunk / 661), dư = (không có).
```

```bash
uv run ruff check .
git add scripts/soi_doc_can_nap.py
git commit -m "test(ingest): check change detection against the live table"
```

- [ ] **Step 4: Cập nhật `docs/TASKLIST.md`**

Trong **T1**, thay trọn gạch đầu dòng:

```markdown
- Giá phải trả: `write_lancedb` **embed lại toàn bộ 661 chunk** rồi
  `create_table(mode="overwrite")` — không có đường cập nhật 3 hàng riêng lẻ. Tức là tốn
  embedding cho cả bảng và ghi đè bảng đang phục vụ.
```

bằng:

```markdown
- Giá phải trả: **không còn là cả bảng.** Ingest tăng dần (13/08) chỉ embed văn bản có vân tay
  lệch, và ghi bằng `merge_insert` chứ không ghi đè bảng đang phục vụ. Số đo thật của lượt này
  ở `scripts/soi_doc_can_nap.py`.
```

Giữ nguyên dòng `- **Chờ duyệt** (ghi lên cloud).` đang có — nó vẫn đúng, chỉ là lý do
"quá đắt" đã hết chứ không phải rào duyệt đã hết.

Thêm hai mục mới ở cuối phần chưa làm:

```markdown
### [ ] T24 · Index FTS đang gấp dấu tiếng Việt (`ascii_folding: True`)

`list_indices()` trên bảng thật (13/08) cho `text_idx` chạy `ascii_folding: True`,
`language: 'English'`, `stem: False`, `remove_stop_words: False`. Tức BM25 gấp "điều"→"dieu",
"ngân"→"ngan" **trước** khi khớp.

- Vì sao quan trọng: câu hỏi và văn bản đều bị gấp nên vẫn khớp được, nhưng phân biệt dấu bị
  xoá — và đây đúng là nhánh mà **T21** đang chỉnh trọng số (`TRONG_SO_THUA`). Chỉnh trọng số
  của một nhánh mà chưa biết nó đang tokenise thế nào là chỉnh mù.
- Bước đầu: chạy `tbl.search("...", query_type="fts")` với một cặp truy vấn chỉ khác nhau ở
  dấu (ví dụ "hạn mức" so với "han muc") và so tập id trả về. Giống nhau ⇒ xác nhận đang gấp.

### [ ] T25 · Cân nhắc `create_scalar_index("doc_id")`

`where("doc_id IN (...)")` giờ nằm trên đường ingest (mỗi lượt) chứ không chỉ đường tra lớp phủ.

- Đo 13/08: 0.61s cho một doc, 5.29s quét toàn bảng 661 hàng — **chưa cần**.
- Bước đầu: khi bảng vượt ~5.000 chunk hoặc lượt quét vượt 15s thì chạy
  `tbl.create_scalar_index("doc_id")` rồi đo lại. Ghi số vào đây, đừng làm sớm.
```

Trong **T23**, ở gạch đầu dòng bắt đầu bằng `Còn lại: 23 văn bản đã cào **chưa vào**`, thay câu
cuối `— **T1 đang chặn đúng chỗ đó** (re-ingest ghi lên cloud, cần duyệt).` bằng:

```markdown
  — T1 vẫn chặn (ghi lên cloud, cần duyệt), nhưng từ 13/08 lượt ghi đó chỉ còn tốn embedding
  của đúng 23 văn bản mới thay vì cả 661 chunk (ingest tăng dần).
```

- [ ] **Step 5: Cập nhật `docs/WORKLOG.md`**

Chạy `/worklog` cho mục hôm nay (13/08). Nội dung phải nêu: `write_lancedb` giờ tăng dần · con
số đo được từ `scripts/soi_doc_can_nap.py` · T1 hết lý do "quá đắt" nhưng vẫn chờ duyệt ·
T24/T25 mở mới.

- [ ] **Step 6: Commit**

```bash
git add docs/TASKLIST.md docs/WORKLOG.md
git commit -m "docs: record incremental ingest results and open T24/T25"
```

---

## Sau khi hết plan — KHÔNG tự chạy

Bước tiếp theo tự nhiên là `uv run python -m app.ingestion data/corpus.real.json` để đẩy bản vá
chunking lên bảng thật. **Đó là T1 và nó đang chờ chủ repo duyệt** — ghi lên cloud. Plan này chỉ
làm cho lượt ghi đó rẻ đi, không tự thực hiện nó.
