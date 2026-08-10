# T5 — Cho luồng `/admin` duyệt văn bản chạy được thật — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Duyệt một văn bản qua `/admin` chạy được trên production, và chỉ nạp lại đúng văn bản đó thay vì ghi đè cả bảng đang phục vụ.

**Architecture:** Ba thay đổi tách bạch. (1) RLS `is_admin()` đọc `app_metadata.role` trong JWT — cùng chỗ FastAPI và web đã đọc — nên "admin" chỉ còn một định nghĩa. (2) `ingest_one_doc` nạp một văn bản bằng `delete + add` trên LanceDB và `MERGE` một node trên Neo4j, không `DETACH DELETE` toàn đồ thị. (3) `approve_document` gọi hàm mới và trả lỗi đọc được khi bước nạp hỏng.

**Tech Stack:** FastAPI · Pydantic v2 · Supabase (Postgres + Storage, RLS) · LanceDB Cloud · Neo4j Aura · pytest · uv

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-10-t5-luong-duyet-van-ban-design.md`.
- Thông điệp commit **tiếng Anh**, theo `docs/COMMIT-CONVENTION.md`. Scope hợp lệ ở đây: `api`, `ingest`, `kg`, `docs`.
- Nhánh `feat/software`. `main` chỉ nhận qua PR.
- Trước mỗi commit: `uv run pytest -q` và `uv run ruff check .` phải xanh.
- Không đổi `ingest_docs` (đường nạp toàn bộ cho CLI) — nó vẫn đúng khi corpus đổi hàng loạt.
- Không tự động hoá việc cấp quyền admin bằng service-role key: dự án cố ý không giữ key đó (`app/core/appdb.py` docstring).
- Bộ ký tự `doc_id` hợp lệ, dùng nguyên văn ở mọi nơi: `^[A-Za-z0-9._-]+$`.
- Tên bảng LanceDB lấy từ `app.core.config.LANCEDB_TABLE` (`"chunks"`), không viết chuỗi thẳng.

---

## File Structure

| File | Trách nhiệm | Thao tác |
|---|---|---|
| `supabase/migrations/0007_vai_tro_mot_nguon.sql` | Định nghĩa lại `is_admin()`; ghi chú cột chết; sửa comment sai của 0001 | Tạo |
| `app/ingestion/pipeline.py` | `kiem_doc_id`, `ingest_one_doc` | Sửa |
| `app/knowledge/graph.py` | `push_one_doc` + ba helper `_merge_*` dùng chung với `push_corpus` | Sửa |
| `app/api/documents.py` | `approve_document` gọi `ingest_one_doc`, chặn `doc_id` bẩn, trả 502 khi nạp hỏng | Sửa `:206-256` |
| `tests/test_ingest_mot_van_ban.py` | Ca cho `kiem_doc_id` + `ingest_one_doc` (LanceDB và Neo4j) | Tạo |
| `tests/test_documents.py` | Sửa fixture và ca `approve` theo hành vi mới; thêm ca `doc_id` bẩn và ca nạp hỏng | Sửa `:43-63`, `:80-107` |
| `docs/ARCHITECTURE.md` | Mục "Cấp quyền admin" | Sửa |
| `docs/TASKLIST.md` | Đóng T5 sau bước nghiệm thu | Sửa |
| `docs/WORKLOG.md` | Ghi kết quả lượt chạy thật | Sửa |

---

### Task 1: Migration — `is_admin()` đọc JWT

**Files:**
- Create: `supabase/migrations/0007_vai_tro_mot_nguon.sql`

**Interfaces:**
- Consumes: không có.
- Produces: hàm SQL `public.is_admin() -> boolean`. Mọi policy RLS sẵn có gọi nó không phải sửa gì — `create or replace` giữ nguyên chữ ký.

Task này **không có test tự động**: không có Postgres local trong repo, và một ca kiểm nội dung file SQL chỉ là kiểm chính tả chứ không kiểm hành vi. Phép kiểm thật nằm ở Task 6, chạy trên Supabase.

- [ ] **Step 1: Viết migration**

```sql
-- 0007 — "admin" chỉ còn MỘT định nghĩa.
--
-- Trước migration này có hai, không cái nào ghi sang cái kia:
--   * FastAPI `require_admin`  -> app_metadata.role trong JWT   (app/core/auth.py:68)
--   * web, 4 chỗ               -> app_metadata.role trong JWT
--   * RLS `is_admin()`         -> public.profiles.role          (0001_init.sql:104)
--
-- Trigger `handle_new_user` luôn đặt profiles.role = 'staff', còn app_metadata thì không
-- đường nào tự đặt. Hệ quả: đặt profiles.role='admin' thì FastAPI chặn ở cửa (403); đặt
-- app_metadata.role='admin' thì FastAPI cho qua rồi RLS chặn lúc ghi Storage. Luồng /admin
-- chưa bao giờ qua nổi cửa đầu tiên — bucket legal-docs và bảng legal_documents đều rỗng.
--
-- Nay RLS hỏi đúng chỗ hai bên kia đang hỏi.
create or replace function public.is_admin()
returns boolean language sql stable set search_path = ''
as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', 'staff') = 'admin';
$$;

-- `security definer` bỏ đi cùng lúc: hàm không còn đọc bảng nào nên không cần mượn quyền.

-- public.profiles.role sau đây KHÔNG còn ai đọc — không backend, không web, không RLS.
-- Cố ý giữ cột lại: lỗ hổng leo thang quyền (policy "profiles: sửa của mình" ở 0001:110
-- thiếu `with check` nên user tự đặt được role='admin' cho chính mình) tồn tại CHỈ VÌ
-- is_admin() đọc cột này; đổi hàm là nó tắt theo. `drop column` là lệnh không lùi được
-- trên dữ liệu thật để đổi lấy sự gọn mắt.
comment on column public.profiles.role is
  'ĐÃ CHẾT từ migration 0007 — nguồn sự thật là app_metadata.role trong JWT. Đừng đọc cột này.';

-- Đính chính comment sai ở 0001_init.sql:91 ("Backend FastAPI dùng service-role key
-- (bypass RLS)"): quyết định đã đổi từ lâu — backend gọi PostgREST bằng chính JWT của
-- user, RLS được thực thi thật. Xem docstring app/core/appdb.py.

-- Cấp quyền admin (thao tác tay, cố ý — chỉ service-role đặt được app_metadata):
--   Supabase Dashboard -> Authentication -> Users -> chọn user -> Edit user
--   -> App Metadata -> {"role": "admin"} -> Save. Người dùng phải ĐĂNG NHẬP LẠI
--   để nhận JWT mới; token cũ vẫn mang role cũ tới lúc hết hạn.
-- Kiểm ngay trong SQL Editor sau khi áp (SQL Editor chạy dưới vai service-role, không có
--   JWT người dùng, nên hàm phải trả false):
--   select public.is_admin();   -- kỳ vọng: false
```

- [ ] **Step 2: Chạy lint và test cho chắc không vỡ gì**

Run: `uv run pytest -q; uv run ruff check .`
Expected: xanh như trước (migration chưa được mã Python nào đọc).

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0007_vai_tro_mot_nguon.sql
git commit -m "fix(api): give admin a single definition so the approval path can clear RLS"
```

---

### Task 2: `kiem_doc_id` + `ingest_one_doc` — phần LanceDB

**Files:**
- Modify: `app/ingestion/pipeline.py` (thêm sau `write_lancedb`, quanh dòng `258`)
- Test: `tests/test_ingest_mot_van_ban.py` (tạo)

**Interfaces:**
- Consumes: `build_chunks(docs) -> list[dict]`, `_embed_rows(rows) -> None`, `_FTS_OPTS: dict`, `LANCEDB_TABLE: str`, `app.core.vectordb.connect()` — đều đã có trong `pipeline.py`.
- Produces:
  - `kiem_doc_id(doc_id: str) -> str` — trả lại chính `doc_id` nếu hợp lệ, ném `ValueError` nếu không.
  - `ingest_one_doc(doc: CorpusDocument, rels: list[Relationship], tat_ca_docs: list[CorpusDocument]) -> int` — trả số chunk của riêng `doc`. Task 3 mở rộng thân hàm này; Task 4 gọi nó.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_ingest_mot_van_ban.py`:

```python
"""Nạp lại MỘT văn bản: chỉ đụng chunk của nó, không ghi đè cả bảng.

`write_lancedb` gọi `create_table(mode="overwrite")` — mỗi lần duyệt một văn bản là ghi đè
cả bảng đang phục vụ trong lúc người dùng đang tra, và embed lại toàn bộ chunk không hề đổi
(đo 10/08: 661 chunk ≈ 52s, so với 23 chunk ≈ 1,8s của một thông tư). Đường duyệt cần một
lối khác.
"""
from __future__ import annotations

import pytest

from app.core.schemas import CorpusDocument
from app.ingestion import pipeline


class _FakeTable:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.deleted: list[str] = []
        self.so_lan_dung_fts = 0

    def delete(self, where: str) -> None:
        self.deleted.append(where)
        self.rows = [r for r in self.rows if f"doc_id = '{r['doc_id']}'" != where]

    def add(self, rows) -> None:
        self.rows.extend(rows)

    def create_fts_index(self, cot: str, **kw) -> None:
        self.so_lan_dung_fts += 1


class _FakeDB:
    def __init__(self, bang: dict[str, _FakeTable]):
        self.bang = bang

    def list_tables(self):
        return list(self.bang)

    def open_table(self, ten: str) -> _FakeTable:
        return self.bang[ten]

    def create_table(self, ten: str, data) -> _FakeTable:
        self.bang[ten] = _FakeTable(data)
        return self.bang[ten]


def _doc(doc_id: str, text: str = "Nội dung.") -> CorpusDocument:
    return CorpusDocument.model_validate(
        {
            "doc_id": doc_id,
            "title": f"Văn bản {doc_id}",
            "doc_type": "Thông tư",
            "source": "external",
            "valid_from": "2026-01-01",
            "articles": [{"article": "Điều 1", "text": text}],
        }
    )


@pytest.fixture
def bang(monkeypatch) -> _FakeTable:
    """Bảng LanceDB giả, đã có sẵn chunk của hai văn bản khác."""
    co_san = [
        {"id": "TT01-2020::Điều 1", "doc_id": "TT01-2020", "text": "a"},
        {"id": "TT02-2021::Điều 1", "doc_id": "TT02-2021", "text": "b"},
    ]
    t = _FakeTable(co_san)
    monkeypatch.setattr("app.core.vectordb.connect", lambda: _FakeDB({pipeline.LANCEDB_TABLE: t}))
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    # Neo4j tắt: Task 3 mới đụng tới nhánh đó
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")
    return t


def test_chi_dung_chunk_cua_van_ban_duoc_nap(bang):
    n = pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert n == 1
    assert bang.deleted == ["doc_id = 'TT99-2026'"]
    con_lai = {r["doc_id"] for r in bang.rows}
    assert con_lai == {"TT01-2020", "TT02-2021", "TT99-2026"}


def test_nap_hai_lan_thi_thay_chu_khong_nhan_doi(bang):
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    pipeline.ingest_one_doc(_doc("TT99-2026", "Nội dung đã sửa."), [], [_doc("TT99-2026")])
    cua_no = [r for r in bang.rows if r["doc_id"] == "TT99-2026"]
    assert len(cua_no) == 1, "delete phải chạy trước add, nếu không chunk cũ nằm lại"
    assert cua_no[0]["text"] == "Nội dung đã sửa."


def test_bang_chua_ton_tai_thi_tao_kem_chi_muc_fts(monkeypatch):
    db = _FakeDB({})
    monkeypatch.setattr("app.core.vectordb.connect", lambda: db)
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])

    t = db.bang[pipeline.LANCEDB_TABLE]
    assert len(t.rows) == 1
    assert t.so_lan_dung_fts == 1, "bảng mới mà không dựng chỉ mục thì nhánh BM25 chết lặng"


@pytest.mark.parametrize("xau", ["TT99'; --", "TT 99", "TT99/2026", "", "TT99\n"])
def test_doc_id_ban_bi_chan(xau):
    with pytest.raises(ValueError):
        pipeline.kiem_doc_id(xau)


@pytest.mark.parametrize("tot", ["TT40-2024", "ND101-2012", "SHB.QD_01", "TT23-2019"])
def test_doc_id_that_van_qua(tot):
    assert pipeline.kiem_doc_id(tot) == tot


def test_doc_id_ban_khong_phat_lenh_delete_nao(bang):
    with pytest.raises(ValueError):
        pipeline.ingest_one_doc(_doc("TT99'; --"), [], [])
    assert bang.deleted == [], "phải chặn TRƯỚC khi chạm bảng"
```

- [ ] **Step 2: Chạy để chắc chắn nó thất bại**

Run: `uv run pytest tests/test_ingest_mot_van_ban.py -q`
Expected: FAIL — `AttributeError: module 'app.ingestion.pipeline' has no attribute 'kiem_doc_id'`.

- [ ] **Step 3: Cài đặt tối thiểu**

Trong `app/ingestion/pipeline.py`, thêm ngay sau `write_lancedb` (dòng `258`):

```python
#: `doc_id` đi thẳng vào chuỗi điều kiện của `tbl.delete(...)`, mà nó đến từ JSON admin sửa
#: được bằng tay — đây là biên tin cậy. Chặn bằng bộ ký tự cho phép chứ không thoát chuỗi:
#: bộ này phủ đủ mọi `doc_id` đang có (`TT40-2024`, `ND101-2012`, nhóm nội bộ SHB) và từ
#: chối phần còn lại, nên nó nói KHÔNG với thứ chưa từng thấy thay vì đoán cách xử.
_DOC_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


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
    return len(rows)
```

Kiểm phần đầu file đã có `import re`, `from app.core import vectordb`, `from app.core.config import LANCEDB_TABLE`, `from app.core.schemas import CorpusDocument, Relationship`. Thiếu cái nào thì thêm.

- [ ] **Step 4: Chạy test cho tới khi xanh**

Run: `uv run pytest tests/test_ingest_mot_van_ban.py -q`
Expected: PASS, 9 ca (5 + 4 tham số hoá).

- [ ] **Step 5: Toàn bộ test và lint**

Run: `uv run pytest -q; uv run ruff check .`
Expected: xanh. `ingest_docs` chưa bị đụng nên `tests/test_ingest_noi_lop_phu.py` phải giữ nguyên trạng thái xanh.

- [ ] **Step 6: Commit**

```bash
git add app/ingestion/pipeline.py tests/test_ingest_mot_van_ban.py
git commit -m "feat(ingest): add a per-document ingest that replaces only its own chunks"
```

---

### Task 3: `push_one_doc` — phần Neo4j của `ingest_one_doc`

**Files:**
- Modify: `app/knowledge/graph.py` (`push_corpus` ở `:94-150`)
- Modify: `app/ingestion/pipeline.py` (`ingest_one_doc` từ Task 2)
- Test: `tests/test_ingest_mot_van_ban.py` (bổ sung)

**Interfaces:**
- Consumes: `ensure_constraints()`, `session()`, `_kiem_ma(rel_type)`, `VanBanRong` — đã có trong `graph.py`. `quy_ve_doc_id(rels, docs) -> tuple[list[Relationship], list[VanBanRong], list[str]]` từ `app/ingestion/bac_cau.py`.
- Produces: `push_one_doc(doc: CorpusDocument, rels: list[Relationship], rong: list[VanBanRong] | None = None) -> None`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_ingest_mot_van_ban.py`:

```python
def _gia_lap_graph(monkeypatch) -> list[str]:
    """Ghi lại các bước chạm Neo4j, không gọi Aura thật."""
    da_goi: list[str] = []
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "neo4j+s://test")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "test")
    monkeypatch.setattr(
        "app.knowledge.graph.push_one_doc", lambda *a, **k: da_goi.append("push_one_doc")
    )
    monkeypatch.setattr(
        "app.knowledge.graph.push_corpus", lambda *a, **k: da_goi.append("push_corpus")
    )
    monkeypatch.setattr(
        "app.knowledge.graph.push_overlay", lambda goi: (da_goi.append("push_overlay"), (0, 0))[1]
    )
    return da_goi


def test_nap_mot_van_ban_khong_dung_toi_ca_do_thi(bang, monkeypatch):
    da_goi = _gia_lap_graph(monkeypatch)
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert da_goi == ["push_one_doc"], (
        "push_corpus mở đầu bằng DETACH DELETE toàn bộ Document — dùng nó ở đây là "
        "xoá sạch 254 cạnh THUOC của lớp phủ để thêm một văn bản"
    )


def test_khong_phai_day_lai_lop_phu(bang, monkeypatch):
    """Hệ quả tốt của việc không DETACH DELETE: THUOC là cạnh ĐI VÀO nên còn nguyên."""
    da_goi = _gia_lap_graph(monkeypatch)
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert "push_overlay" not in da_goi
```

- [ ] **Step 2: Chạy để chắc chắn nó thất bại**

Run: `uv run pytest tests/test_ingest_mot_van_ban.py -k do_thi -q`
Expected: FAIL — `AttributeError: <module 'app.knowledge.graph'> does not have the attribute 'push_one_doc'`.

- [ ] **Step 3: Tách ba helper trong `graph.py`, giữ nguyên hành vi `push_corpus`**

Thêm trước `push_corpus` (dòng `94`):

```python
def _merge_doc(s, d: CorpusDocument) -> None:
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


def _merge_rong(s, v: "VanBanRong") -> None:
    # `co_toan_van=false` là thứ phân biệt DUY NHẤT, và nó phải nằm trên node chứ không suy
    # từ "không có chunk": tầng truy hồi và tầng hiển thị đọc từ hai chỗ khác nhau, mà cả hai
    # đều không được trích dẫn một văn bản chưa đọc.
    s.run(
        """
        MERGE (n:Document {doc_id: $doc_id})
        SET n.title=$title, n.doc_type=$doc_type, n.source='external',
            n.so_hieu=$doc_id, n.co_toan_van=false
        """,
        doc_id=v.so_hieu, title=v.title or v.so_hieu,
        doc_type=v.doc_type or "Chưa rõ",
    )


def _merge_canh(s, r: Relationship) -> None:
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
```

Rồi thay ba vòng lặp trong `push_corpus` bằng lời gọi helper — thân vòng lặp cũ **xoá đi**, giữ nguyên thứ tự và điều kiện:

```python
        for d in docs:
            _merge_doc(s, d)
        for v in rong or []:
            _merge_rong(s, v)
        for r in rels:
            _merge_canh(s, r)
```

- [ ] **Step 4: Viết `push_one_doc`**

Thêm ngay sau `push_corpus`:

```python
def push_one_doc(
    doc: CorpusDocument,
    rels: list[Relationship],
    rong: list[VanBanRong] | None = None,
) -> None:
    """Nạp lại MỘT văn bản mà không đụng phần còn lại của đồ thị.

    Khác `push_corpus` ở đúng một chỗ, và chỗ đó có hậu quả lớn: **không**
    `MATCH (d:Document) DETACH DELETE d`. `DETACH` xoá mọi cạnh chạm node, kể cả `THUOC` phát
    từ `(:DonVi)` của lớp phủ — nên đường nạp toàn bộ buộc phải gọi lại `push_overlay` ngay
    sau đó (xem `pipeline._noi_lai_lop_phu`). Ở đây chỉ thay các cạnh **đi ra** của đúng văn
    bản này; `THUOC` là cạnh **đi vào** nên không bị đụng, và cái nợ ấy biến mất.

    Cạnh đi VÀO từ văn bản khác cũng không đụng: chúng thuộc về văn bản kia, sẽ được thay khi
    chính văn bản kia được duyệt lại.

    Giới hạn đã biết: văn bản vừa duyệt mà lại có mặt trong artefact lớp phủ thì cạnh `THUOC`
    của nó chưa được dựng — artefact sinh offline từ `data/raw/vbpl/raw/`, không có trong
    image. Ca này chưa từng xảy ra; gặp thì chạy `push_overlay` một lượt.
    """
    ensure_constraints()
    with session() as s:
        _merge_doc(s, doc)
        s.run(
            "MATCH (a:Document {doc_id: $doc_id})-[r]->(:Document) DELETE r",
            doc_id=doc.doc_id,
        )
        for v in rong or []:
            _merge_rong(s, v)
        for r in rels:
            _merge_canh(s, r)
```

- [ ] **Step 5: Nối vào `ingest_one_doc`**

Thêm vào cuối `ingest_one_doc`, ngay trước `return len(rows)`:

```python
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
```

- [ ] **Step 6: Chạy test**

Run: `uv run pytest tests/test_ingest_mot_van_ban.py -q`
Expected: PASS, 11 ca.

- [ ] **Step 7: Toàn bộ test và lint**

Run: `uv run pytest -q; uv run ruff check .`
Expected: xanh. `tests/test_ingest_noi_lop_phu.py` vẫn phải xanh — `push_corpus` đổi cấu trúc bên trong nhưng hành vi y nguyên.

- [ ] **Step 8: Commit**

```bash
git add app/knowledge/graph.py app/ingestion/pipeline.py tests/test_ingest_mot_van_ban.py
git commit -m "feat(kg): update one document in the graph without wiping every edge"
```

---

### Task 4: `approve_document` dùng đường nạp mới

**Files:**
- Modify: `app/api/documents.py:206-256`
- Modify: `tests/test_documents.py:43-63` (fixture `fake_store`) và `:80-107`

**Interfaces:**
- Consumes: `kiem_doc_id`, `ingest_one_doc` từ Task 2–3.
- Produces: không có API mới. Hành vi mới: 422 khi `doc_id` không hợp lệ, 502 khi bước nạp hỏng.

- [ ] **Step 1: Sửa fixture và ca test hiện có, thêm hai ca mới**

Trong `tests/test_documents.py`, thay khối `fake_ingest` (dòng `56-62`) bằng:

```python
    import app.ingestion.pipeline as pipeline

    def fake_ingest_one(doc, rels, tat_ca_docs):
        store["ingested"] = len(doc.articles)
        store["ingested_doc"] = doc.doc_id
        store["ingested_tat_ca"] = [d.doc_id for d in tat_ca_docs]
        return store["ingested"]

    monkeypatch.setattr(pipeline, "ingest_one_doc", fake_ingest_one)
```

Trong `test_approve_merge_vao_canonical`, thay dòng cuối (`:107`):

```python
    # Chỉ nạp lại VĂN BẢN VỪA DUYỆT, không nạp lại cả corpus — đây là điều phân biệt
    # đường tăng dần với đường ghi đè. Văn bản cũ ND00-2020 vẫn nằm trong canonical
    # (nên có mặt ở `ingested_tat_ca`) nhưng không bị embed lại.
    assert fake_store["ingested"] == 1
    assert fake_store["ingested_doc"] == "TT99-2026"
    assert set(fake_store["ingested_tat_ca"]) == {"ND00-2020", "TT99-2026"}
```

Thêm hai ca mới vào cuối file:

```python
def test_approve_doc_id_ban_bi_chan_truoc_khi_ghi_storage(client, fake_store):
    """`doc_id` đi vào chuỗi điều kiện của `delete` — chặn ở cửa, và chặn TRƯỚC khi ghi."""
    xau = {**_DOC, "doc_id": "TT99'; drop --"}
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "extracted": xau, "status": "pending"}

    r = client.post(
        "/documents/TT99-2026/approve",
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )
    assert r.status_code == 422, r.text
    assert "corpus.json" not in fake_store["storage"], "không được ghi canonical rồi mới từ chối"
    assert fake_store["rows"]["TT99-2026"]["status"] == "pending"


def test_approve_nap_hong_thi_502_va_giu_pending(client, fake_store, monkeypatch):
    """Canonical đã ghi mà chỉ mục chưa — phải nói ra, và để status ở pending để bấm lại."""
    import app.ingestion.pipeline as pipeline

    def no(doc, rels, tat_ca_docs):
        raise RuntimeError("LanceDB Cloud từ chối")

    monkeypatch.setattr(pipeline, "ingest_one_doc", no)
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "extracted": _DOC, "status": "pending"}

    r = client.post(
        "/documents/TT99-2026/approve",
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )
    assert r.status_code == 502, r.text
    assert "duyệt lại" in r.json()["detail"]
    assert fake_store["rows"]["TT99-2026"]["status"] == "pending"
    assert "corpus.json" in fake_store["storage"], "canonical đã ghi — thông báo phải nói đúng thế"
```

- [ ] **Step 2: Chạy để chắc chắn nó thất bại**

Run: `uv run pytest tests/test_documents.py -q`
Expected: FAIL — `test_approve_merge_vao_canonical` (fixture vá `ingest_one_doc` nhưng mã vẫn gọi `ingest_docs`), và hai ca mới.

- [ ] **Step 3: Sửa `approve_document`**

Trong `app/api/documents.py`, sau khối `try/except` validate (`:221-225`), thêm ngay:

```python
    from app.ingestion.pipeline import kiem_doc_id

    try:
        kiem_doc_id(doc.doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
```

Rồi thay khối ingest (`:241-245`) bằng:

```python
    from app.ingestion.pipeline import build_change_events, ingest_one_doc

    docs = [CorpusDocument.model_validate(d) for d in corpus["documents"]]
    rels = [Relationship.model_validate(r) for r in corpus.get("relationships", [])]
    try:
        n_chunks = ingest_one_doc(doc, rels, docs)
    except Exception as exc:  # noqa: BLE001 — mọi lỗi nạp đều cùng một cách xử
        # Canonical trên Storage đã cập nhật, chỉ mục thì chưa. Thứ tự này là cố ý: thư viện
        # thấy văn bản mà tra chưa ra thì chat đơn giản không trích dẫn nó — không có trích
        # dẫn gãy. Đảo lại mới tệ: retrieval có văn bản mà trang xem trả 404.
        raise HTTPException(
            status_code=502,
            detail=(
                f"Đã cập nhật corpus canonical nhưng chưa nạp được chỉ mục: {exc}. "
                "Bấm duyệt lại văn bản này — thao tác lặp lại vô hại."
            ),
        ) from exc
```

`status` chỉ chuyển sang `approved` ở dòng sau đó, nên nhánh lỗi tự khắc để nguyên `pending`.

- [ ] **Step 4: Chạy test**

Run: `uv run pytest tests/test_documents.py -q`
Expected: PASS.

- [ ] **Step 5: Toàn bộ test và lint**

Run: `uv run pytest -q; uv run ruff check .`
Expected: xanh.

- [ ] **Step 6: Commit**

```bash
git add app/api/documents.py tests/test_documents.py
git commit -m "fix(api): approve one document without rewriting the whole serving table"
```

---

### Task 5: Tài liệu

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: không có. Produces: không có.

- [ ] **Step 1: Thêm mục "Cấp quyền admin" vào `docs/ARCHITECTURE.md`**

Đặt cuối file:

```markdown
## Cấp quyền admin

"Admin" có **một** nguồn sự thật: `app_metadata.role` trong JWT Supabase. FastAPI
(`require_admin`), web (4 chỗ) và RLS (`is_admin()`, từ migration `0007`) đều đọc đúng chỗ đó.
`public.profiles.role` **đã chết** — còn trong schema nhưng không ai đọc.

Cấp quyền là thao tác tay, cố ý: chỉ service-role đặt được `app_metadata`, mà backend không
giữ service-role key (xem docstring `app/core/appdb.py`).

1. Supabase Dashboard → Authentication → Users → chọn user → Edit user
2. App Metadata → `{"role": "admin"}` → Save
3. **Đăng nhập lại** — JWT cũ vẫn mang role cũ tới lúc hết hạn

Không có bước 3 thì triệu chứng rất dễ đọc nhầm thành "migration hỏng": Dashboard hiển thị
role đúng, mà `/admin` vẫn 403.
```

- [ ] **Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: record how admin is granted, and that profiles.role is dead"
```

---

### Task 6: Nghiệm thu trên production

**Files:**
- Modify: `docs/TASKLIST.md` (đóng T5), `docs/WORKLOG.md` (mục hôm nay)

**Interfaces:** không có.

Đây là phần T5 thực sự đòi. Test xanh **không** chứng minh được điều nó hỏi. Các bước dưới cần
tài khoản Supabase và Cloud Run — **chủ repo chạy**, agent không có credentials.

- [ ] **Step 1: Áp migration**

Supabase Dashboard → SQL Editor → dán `supabase/migrations/0007_vai_tro_mot_nguon.sql` → Run.

Kiểm **cả hai nhánh** — nhánh `false` chỉ chứng minh hàm không nổ khi không có JWT, còn nhánh
`true` mới là toàn bộ tiền đề của migration này:

```sql
select public.is_admin();   -- kỳ vọng: false (SQL Editor chạy dưới service-role, không có JWT)

begin;
  set local role authenticated;
  set local request.jwt.claims = '{"app_metadata":{"role":"admin"}}';
  select public.is_admin();   -- kỳ vọng: true
rollback;
```

- [ ] **Step 2: Cấp quyền admin** theo ba bước ở `docs/ARCHITECTURE.md`, rồi đăng nhập lại web.

- [ ] **Step 3: Deploy** nhánh đã merge lên Cloud Run, ghi lại số revision.

- [ ] **Step 4: Chạy thật** — upload một văn bản nhỏ qua `/admin`, rồi Approve.

- [ ] **Step 5: Nghiệm thu bốn chỗ, trên chính dữ liệu đang phục vụ**

Không nhìn mã trả về của lời gọi approve — nó chỉ nói request không ném lỗi.

| Kiểm ở đâu | Kỳ vọng | Vì sao |
|---|---|---|
| Storage `legal-docs/corpus.json` | Tồn tại và chứa `doc_id` vừa duyệt | Trước đó bucket **rỗng** — đây là bằng chứng luồng đã chạy lần đầu |
| Bảng `legal_documents` | Có hàng, `status='approved'` | Trước đó bảng rỗng |
| LanceDB | Số hàng của `doc_id` đó = số chunk của nó, **và tổng số hàng của các văn bản khác không đổi** | Đây mới là thứ chứng minh "tăng dần" chứ không phải "nạp lại" |
| Neo4j | Có node `Document` của văn bản đó, **và số cạnh `THUOC` không đổi** (254 tính tới 10/08) | Chứng minh lớp phủ không bị `DETACH DELETE` cuốn theo |

- [ ] **Step 6: Ghi lại và đóng T5**

Cập nhật `docs/TASKLIST.md` (chuyển T5 xuống mục "Đã đóng", kèm số đo thật) và thêm mục vào
`docs/WORKLOG.md` theo template cuối file đó. Nếu bước 5 lộ ra vấn đề mới — rất có thể, vì
luồng này chưa ai chạy hết bao giờ — mở mục mới trong TASKLIST thay vì sửa cho khớp.

```bash
git add docs/TASKLIST.md docs/WORKLOG.md
git commit -m "docs: close T5 after running the approval path on production"
```
