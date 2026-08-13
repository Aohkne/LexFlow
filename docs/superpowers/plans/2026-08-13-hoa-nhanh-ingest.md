# Hoà `feat/ai` với `main` — một cơ chế ghi chunk duy nhất

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoà `origin/main` vào `feat/ai` và rút cả hai đường ghi chunk (`ingest_one_doc` của main, `write_lancedb` tăng dần của `feat/ai`) về **một** hàm ghi dùng chung.

**Architecture:** Tách `_ghi_chunk(tbl, pham_vi, rows, id_cu)` làm tầng ghi duy nhất — xoá id mồ côi, `merge_insert`, chờ index. Tầng *quyết định ghi gì* giữ nguyên và vẫn tách đôi: đường API biết sẵn văn bản nào đổi, đường corpus dùng `_doc_can_nap` để tìm ra.

**Tech Stack:** Python 3.12 · uv · pytest · ruff · lancedb 0.34.0 (`RemoteTable`) · FastAPI · Next.js 16 (`web/`)

**Spec:** `docs/superpowers/specs/2026-08-13-hoa-nhanh-ingest-design.md`

## Global Constraints

- Message commit **tiếng Anh**, Conventional Commits — `docs/COMMIT-CONVENTION.md`.
- `uv run pytest -q` (không giới hạn file) và `uv run ruff check .` phải sạch **trước mỗi commit**.
- **Không test nào được chạm LanceDB Cloud / Neo4j Aura.** Sau Task 1 sẽ có `tests/conftest.py` chặn ở tầng thấp nhất — đừng gỡ.
- Comment và docstring **tiếng Việt**, nói *vì sao* chứ không kể lại *cái gì*.
- **Không rebase.** Nhánh đã push; quy ước repo (`docs/COMMIT-CONVENTION.md`, Push rules 2 và 5) bắt merge `main` vào thay vì rebase.
- **Không chạy `python -m app.ingestion`** và **không chạy `scripts/soi_doc_can_nap.py` / `scripts/do_merge_insert_remote.py`** — chúng nối vào LanceDB Cloud thật, và một trong ba ghi lên bảng đang phục vụ.
- Mọi lời gọi `create_fts_index` phải truyền `**_FTS_OPTS`.
- Tip của `feat/ai` trước khi merge là **`d1f5f93`**. Nội dung `docs/TASKLIST.md` bản `feat/ai` lấy lại bằng `git show d1f5f93:docs/TASKLIST.md`.
- Suite có sẵn đúng **1 cảnh báo** (`StarletteDeprecationWarning` từ `fastapi/testclient.py`) có trước cả hai nhánh. Cảnh báo MỚI là lỗi.

---

### Task 1: Merge `origin/main`, giải xung đột theo luật, suite xanh

**Files:**
- Merge: `app/ingestion/pipeline.py` (hợp thủ công)
- Merge: `app/api/documents.py` (lấy bản của **main**)
- Merge: `tests/test_documents.py` (lấy bản của **main**)
- Merge: `docs/TASKLIST.md` (lấy bản của **main**)
- Merge: `docs/WORKLOG.md` (giữ **cả hai**)
- Modify: `web/lib/api.ts`, `web/app/(app)/admin/page.tsx` (hoàn nguyên `chunks_bang`)

**Interfaces:**
- Consumes: không có (task đầu)
- Produces: cây mã có đủ `_FTS_OPTS`, `_DOC_ID_RE`, `kiem_doc_id`, `ingest_one_doc` (từ main) **và** `DocDuTrongBang`, `_cot_du_lieu`, `_van_tay`, `_doc_can_nap`, `_loc_id`, `_tao_bang_moi`, `write_lancedb(rows, ep, xoa_doc_du) -> tuple[int,int]`, `_TIMEOUT_CHO_INDEX`, `_cho_index`, `ingest_docs(docs, rels, ep, xoa_doc_du) -> tuple[int,int]` (từ `feat/ai`); `tests/conftest.py` và `tests/test_ingest_mot_van_ban.py` từ main

**Vì sao `app/api/documents.py` lấy bản của main, không hợp:** bản main đi trước hẳn một bậc trên chính file đó — nó có `kiem_doc_id` → 422, `load_canonical(strict=True)` với 502 + audit khi đọc hỏng (fail-open ở đó nghĩa là đè bản corpus đóng gói trong image lên `corpus.json` thật, xoá mọi văn bản đã duyệt, im lặng), và một khối `try/except` quanh bước ingest trả 502 kèm *"bấm duyệt lại — thao tác lặp lại vô hại"*. Bản `feat/ai` dựng trên bản cũ hơn bản đó. Khối 502 kia cũng **bao trùm** cái `HTTPException(409)` mà `feat/ai` thêm: `/approve` sau hoà gọi `ingest_one_doc`, mà hàm đó không bao giờ ném `DocDuTrongBang` (kiểm văn bản dư là việc của `write_lancedb`, đường corpus).

**Kéo theo — phải hoàn nguyên `web/`:** bản `feat/ai` render `${r.chunks_bang}` và khai trường đó trong TypeScript, nhưng `approve_document` của main trả `{status, doc_id, chunks, change_events}` — **không có `chunks_bang`**. Để nguyên là toast hiện `undefined`. Và dưới `ingest_one_doc`, `chunks` đã đúng nghĩa "số chunk của văn bản vừa duyệt", nên `chunks_bang` không còn lý do tồn tại.

- [ ] **Step 1: Ghi lại điểm xuất phát và chạy merge**

```powershell
git fetch origin
git rev-parse HEAD   # ghi lại: phải là d1f5f93
git merge origin/main
```

Kỳ vọng: merge dừng lại với xung đột ở 5 file. `git status --short` cho `UU` ở
`app/api/documents.py`, `app/ingestion/pipeline.py`, `docs/TASKLIST.md`, `docs/WORKLOG.md`,
`tests/test_documents.py`.

Trong lúc merge, **`--ours` là `feat/ai`, `--theirs` là `origin/main`**.

- [ ] **Step 2: Lấy bản của main cho ba file**

```powershell
git checkout --theirs app/api/documents.py tests/test_documents.py docs/TASKLIST.md
git add app/api/documents.py tests/test_documents.py docs/TASKLIST.md
```

- [ ] **Step 3: `docs/WORKLOG.md` — giữ cả hai bên**

Mở file, xoá mọi dấu `<<<<<<<`, `=======`, `>>>>>>>`, và **giữ trọn cả hai khối**. Đây là sổ ghi
theo ngày: hai nhánh ghi các mục khác nhau, không bên nào sai. Sắp các mục theo ngày giảm dần
đúng như phần còn lại của file đã làm. Không sửa nội dung mục nào.

- [ ] **Step 4: `app/ingestion/pipeline.py` — hợp thủ công**

Mọi định nghĩa từ đầu file tới `_embed_rows` giống hệt nhau ở hai bên; xung đột chỉ ở phần sau.
Thứ tự đích, từ trên xuống:

| Định nghĩa | Lấy từ |
|---|---|
| `_FTS_OPTS` (kèm nguyên khối chú thích của nó) | main |
| `DocDuTrongBang` | feat/ai |
| `_cot_du_lieu`, `_van_tay`, `_doc_can_nap` | feat/ai |
| `_loc_id`, `_tao_bang_moi` | feat/ai |
| `write_lancedb(rows, ep, xoa_doc_du) -> tuple[int, int]` | feat/ai |
| `_TIMEOUT_CHO_INDEX`, `_cho_index` | feat/ai |
| `_DOC_ID_RE`, `kiem_doc_id` | main |
| `ingest_one_doc` | main (nguyên si ở task này) |
| `build_change_events`, `_DUONG_DAN_LOP_PHU`, `_noi_lai_lop_phu` | giống nhau, giữ nguyên |
| `ingest_docs(docs, rels, ep, xoa_doc_du) -> tuple[int, int]` | feat/ai |
| `main(corpus_path, ep, xoa_doc_du)` | feat/ai |

**Không sửa hành vi gì ở task này** — chỉ đặt cạnh nhau. `ingest_one_doc` vẫn `delete`+`add` và
vẫn `table_names()`; Task 3 và 4 mới đổi.

Kiểm phần `import`: bản `feat/ai` cần `from datetime import timedelta`; bản main cần `re` (đã có).
Giữ đủ cả hai, và bỏ import nào không còn ai dùng — `ruff` sẽ bắt.

- [ ] **Step 5: Hoàn nguyên `web/`**

`web/lib/api.ts` dòng 159 — thay:

```ts
): Promise<{ status: string; chunks: number; chunks_bang: number; change_events: number }> {
```

bằng:

```ts
): Promise<{ status: string; chunks: number; change_events: number }> {
```

`web/app/(app)/admin/page.tsx` dòng 93 — thay:

```tsx
        `✅ Đã duyệt ${docId}: ${r.chunks} chunk mới / ${r.chunks_bang} trong bảng, ` +
```

bằng:

```tsx
        `✅ Đã duyệt ${docId}: ${r.chunks} chunk, ` +
```

Giữ nguyên phần còn lại của chuỗi (đoạn `change_events`) đúng như đang có.

- [ ] **Step 6: Chạy suite, chưa commit**

Run: `uv run pytest -q`
Expected: **tất cả xanh**, đúng 1 cảnh báo cũ.

Nếu đỏ, ba chỗ đáng nghi trước tiên:
- `tests/conftest.py` (mới từ main) vá `app.core.vectordb.connect`; các ca của `feat/ai` vá
  `pipeline.vectordb.connect`. Hai cái trỏ cùng một đối tượng module và lệnh của ca test chạy
  **sau** fixture `autouse`, nên phải đè được. Nếu không đè được thì báo, đừng gỡ conftest.
- `tests/test_ingest_mot_van_ban.py::_FakeDB` chỉ hiểu `table_names`/`list_tables`; nếu nó đỏ ở
  task này thì Step 4 đã lỡ tay đổi `ingest_one_doc`.
- `import` thiếu hoặc thừa sau khi hợp thủ công.

- [ ] **Step 7: Lint và commit merge**

```powershell
uv run ruff check .
git add -A
git commit --no-edit
git log --oneline -1
git status --short
```

`--no-edit` giữ message merge mặc định của git. `git status --short` phải rỗng.

---

### Task 2: `_FTS_OPTS` cho mọi lời gọi `create_fts_index`

**Files:**
- Modify: `app/ingestion/pipeline.py` (`_tao_bang_moi`, `_cho_index`)
- Modify: `tests/test_ingest_tang_dan.py` (`_BangGia.create_fts_index` + ca mới)

**Interfaces:**
- Consumes: `_FTS_OPTS` (từ main, có sau Task 1)
- Produces: không có API mới

Task này đứng ngay sau merge vì nó là **lỗi sống** kể từ khoảnh khắc Task 1 vào: `_tao_bang_moi`
và `_cho_index` của `feat/ai` gọi `create_fts_index("text")` trần, nên bất kỳ lượt dựng lại index
nào cũng sinh index mang tham số tokenizer khác index đang chạy — nhánh BM25 đổi hành vi mà diff
không cho thấy gì.

- [ ] **Step 1: Viết test thất bại**

Sửa `_BangGia.create_fts_index` trong `tests/test_ingest_tang_dan.py` để ghi lại cả tham số:

```python
    def create_fts_index(self, cot: str, replace: bool = False, **kw) -> None:
        # Ghi cả `kw`: đây là chỗ `_FTS_OPTS` có thể rơi rụng mà không ca nào thấy, vì index
        # sai tham số vẫn dựng được và vẫn trả kết quả — chỉ là kết quả khác.
        self.nhat_ky.append(f"create_fts_index:replace={replace}:opts={sorted(kw)}")
```

Cập nhật mọi assertion đang so chuỗi `create_fts_index:replace=…` cho khớp dạng mới, rồi thêm vào
cuối file:

```python
def test_moi_lan_dung_index_deu_mang_fts_opts(monkeypatch, khong_goi_mang):
    """Index dựng thiếu tham số vẫn chạy và vẫn trả kết quả — chỉ là kết quả KHÁC.

    `_FTS_OPTS` giữ `stem=False` và `remove_stop_words=False` vì `ascii_folding` bỏ dấu TRƯỚC
    khi lọc, nên `thẻ`/`số`/`tổ` thành `the`/`so`/`to` và rơi đúng vào danh sách stop-word
    tiếng Anh. Rơi mất tham số ở đây là gài lại quả mìn đó.
    """
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    bang.co_index = False          # ép đi vào nhánh dựng index
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    dung = [x for x in bang.nhat_ky if x.startswith("create_fts_index")]
    assert dung, "không có lời gọi dựng index nào để kiểm"
    for x in dung:
        assert f"opts={sorted(pipeline._FTS_OPTS)}" in x, f"thiếu _FTS_OPTS: {x}"
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

Run: `uv run pytest tests/test_ingest_tang_dan.py -k fts_opts -q`
Expected: FAIL — `thiếu _FTS_OPTS: create_fts_index:replace=False:opts=[]`

- [ ] **Step 3: Truyền `_FTS_OPTS` ở cả ba chỗ**

Trong `_tao_bang_moi`, thay:

```python
    if settings.lancedb_cloud_enabled:
        tbl.create_fts_index("text")
    else:
        tbl.create_fts_index("text", replace=True)
```

bằng:

```python
    # `**_FTS_OPTS` KHÔNG được bỏ: index thiếu tham số vẫn dựng được, vẫn trả kết quả, chỉ là
    # kết quả khác index đang phục vụ — không lỗi, không cảnh báo, chỉ lệch.
    if settings.lancedb_cloud_enabled:
        tbl.create_fts_index("text", **_FTS_OPTS)
    else:
        tbl.create_fts_index("text", replace=True, **_FTS_OPTS)
```

Trong `_cho_index`, thay `tbl.create_fts_index("text")` bằng `tbl.create_fts_index("text", **_FTS_OPTS)`
và `tbl.create_fts_index("text", replace=True)` bằng
`tbl.create_fts_index("text", replace=True, **_FTS_OPTS)`.

- [ ] **Step 4: Chạy test, xác nhận XANH**

Run: `uv run pytest tests/test_ingest_tang_dan.py -q`
Expected: tất cả xanh

- [ ] **Step 5: Suite đầy đủ + lint**

Run: `uv run pytest -q; uv run ruff check .`
Expected: tất cả xanh, 1 cảnh báo cũ

- [ ] **Step 6: Commit**

```powershell
git add app/ingestion/pipeline.py tests/test_ingest_tang_dan.py
git commit -m "fix(ingest): pass _FTS_OPTS on every create_fts_index call"
```

---

### Task 3: `_id_dang_co` + `_ghi_chunk` — tầng ghi dùng chung

**Files:**
- Modify: `app/ingestion/pipeline.py` (thêm hai hàm; `write_lancedb` gọi hàm mới)
- Modify: `tests/test_ingest_tang_dan.py` (ca mới)

**Interfaces:**
- Consumes: `_loc_id`, `_cho_index`, `_embed_rows`, `kiem_doc_id`, `_cot_du_lieu` (đã có sau Task 1)
- Produces:
  - `_id_dang_co(tbl, doc_ids: set[str]) -> dict[str, set[str]]`
  - `_ghi_chunk(tbl, pham_vi: set[str], rows: list[dict], id_cu: dict[str, set[str]]) -> int`

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_ingest_tang_dan.py`:

```python
# --- tầng ghi dùng chung ---------------------------------------------------------------------

def test_ghi_chunk_thay_tai_cho_khong_dung_van_ban_khac(khong_goi_mang):
    bang = _bang([_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")])
    id_cu = {"A": {"A::Điều 1"}}
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]

    n = pipeline._ghi_chunk(bang, {"A"}, moi, id_cu)

    assert n == 1
    assert bang.hang["A::Điều 1"]["text"] == "x ĐÃ SỬA"
    assert bang.hang["B::Điều 1"]["text"] == "y", "văn bản ngoài phạm vi bị đụng"


def test_ghi_chunk_van_ban_rong_thi_xoa_het_chunk_cu(khong_goi_mang):
    """Admin xoá hết Điều rồi bấm duyệt — chunk cũ PHẢI biến khỏi bảng đang phục vụ.

    Bản trước của `ingest_one_doc` về sớm khi `rows` rỗng, và đó là lỗi: truy hồi vẫn trả đúng
    đoạn văn vừa bị xoá trong khi API trả 200 `approved`. Ở đây ca đó không cần cờ riêng — nó
    là luật mồ côi với `rows` rỗng.
    """
    bang = _bang([_hang("A", "Điều 1", "x"), _hang("A", "Điều 2", "x2"), _hang("B", "Điều 1", "y")])
    id_cu = {"A": {"A::Điều 1", "A::Điều 2"}}

    n = pipeline._ghi_chunk(bang, {"A"}, [], id_cu)

    assert n == 0
    assert set(bang.hang) == {"B::Điều 1"}
    assert khong_goi_mang == [], "không có hàng nào để embed mà vẫn gọi embedding"


def test_ghi_chunk_che_ra_it_manh_hon_thi_xoa_mo_coi(khong_goi_mang):
    bang = _bang([_hang("A", "Điều 1 Khoản 1", "p"), _hang("A", "Điều 1 Khoản 2", "q")])
    id_cu = {"A": {"A::Điều 1 Khoản 1", "A::Điều 1 Khoản 2"}}

    pipeline._ghi_chunk(bang, {"A"}, [_hang("A", "Điều 1", "p q")], id_cu)

    assert set(bang.hang) == {"A::Điều 1"}


def test_id_dang_co_chi_doc_dung_pham_vi(khong_goi_mang):
    bang = _bang([_hang("A", "Điều 1", "x"), _hang("A", "Điều 2", "x2"), _hang("B", "Điều 1", "y")])

    ra = pipeline._id_dang_co(bang, {"A"})

    assert ra == {"A": {"A::Điều 1", "A::Điều 2"}}


def test_id_dang_co_tu_choi_doc_id_ban():
    """`doc_id` đi vào vị từ `where` — đây là biên tin cậy, kiểm ở tầng này chứ không tin caller."""
    bang = _bang([_hang("A", "Điều 1", "x")])
    with pytest.raises(ValueError, match="doc_id không hợp lệ"):
        pipeline._id_dang_co(bang, {"A' OR '1'='1"})
```

Bảng giả cần hiểu `where doc_id IN (...)`. Thêm vào `_TruyVanGia` (cạnh `select`/`limit`):

```python
    def where(self, dieu_kien: str):
        m = re.match(r"^doc_id IN \((.*)\)$", dieu_kien)
        assert m, f"cú pháp where lạ, cloud có thể không nhận: {dieu_kien!r}"
        ids = {s.strip()[1:-1] for s in m.group(1).split(", ")}
        self._hang = [r for r in self._hang if r.get("doc_id") in ids]
        return self
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

Run: `uv run pytest tests/test_ingest_tang_dan.py -k "ghi_chunk or id_dang_co" -q`
Expected: FAIL — `AttributeError: module 'app.ingestion.pipeline' has no attribute '_ghi_chunk'`

- [ ] **Step 3: Cài đặt hai hàm**

Chèn **ngay trên** `def write_lancedb` trong `app/ingestion/pipeline.py`:

```python
def _loc_doc_id(doc_ids: set[str]) -> str:
    """`"doc_id IN ('A', 'B')"`. Mỗi id đi qua `kiem_doc_id` trước khi vào vị từ.

    Kiểm ở tầng này chứ không tin người gọi: `approve_document` có kiểm rồi, nhưng CLI, script
    và test thì không — mà chuỗi này đi thẳng vào `where` của LanceDB.
    """
    return "doc_id IN (" + ", ".join(f"'{kiem_doc_id(d)}'" for d in sorted(doc_ids)) + ")"


def _id_dang_co(tbl, doc_ids: set[str]) -> dict[str, set[str]]:
    """doc_id → tập id đang có trong bảng, CHỈ cho các văn bản được hỏi.

    Bản có phạm vi của phép đọc mà `_doc_can_nap` làm trên toàn bảng. Đường API dùng bản này vì
    nó đã biết văn bản nào đổi — bắt nó quét cả bảng (5,29s, đo 13/08) để suy ra một điều nó
    biết sẵn là trả giá đúng chỗ không nên trả, trên một đường HTTP đồng bộ.
    """
    if not doc_ids:
        return {}
    ra: dict[str, set[str]] = {}
    for h in (
        tbl.search().where(_loc_doc_id(doc_ids)).select(["id", "doc_id"]).limit(tbl.count_rows()).to_list()
    ):
        ra.setdefault(h["doc_id"], set()).add(h["id"])
    return ra


def _ghi_chunk(tbl, pham_vi: set[str], rows: list[dict], id_cu: dict[str, set[str]]) -> int:
    """Ghi chunk cho đúng các văn bản trong `pham_vi`. Trả số chunk vừa ghi.

    KHÔNG tự quyết văn bản nào cần ghi — người gọi đã biết. Đường API biết vì admin vừa duyệt
    đúng văn bản đó; đường corpus biết nhờ `_doc_can_nap`.

    Id nào đang có trong bảng thuộc `pham_vi` mà không có trong `rows` thì bị xoá. Một luật phủ
    cả hai ca: văn bản chẻ lại ra ít mảnh hơn, VÀ văn bản không còn điều nào (admin xoá hết Điều
    rồi bấm duyệt) — ca sau chỉ là ca trước với `rows` rỗng.

    Xoá TRƯỚC rồi mới `merge_insert`. Ràng buộc thật là "không chunk nào còn tồn tại sau lượt
    ghi mà lại vắng mặt giữa chừng"; id mồ côi theo định nghĩa là id sẽ không còn, nên xoá trước
    không vi phạm — và chết giữa chừng để lại đúng "nội dung cũ trừ phần sắp bỏ" thay vì để lại
    hàng thừa.
    """
    mo_coi = {i for d in pham_vi for i in id_cu.get(d, set())} - {r["id"] for r in rows}
    if mo_coi:
        tbl.delete(_loc_id(list(mo_coi)))
        print(f"[ingest] Đã xoá {len(mo_coi)} chunk không còn trong bản chẻ mới.")

    if rows:
        _embed_rows(rows)
        (
            tbl.merge_insert("id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )

    _cho_index(tbl)
    return len(rows)
```

- [ ] **Step 4: Rút `write_lancedb` về gọi `_ghi_chunk`**

Trong `write_lancedb`, thay khối từ `_embed_rows(nap)` tới hết phần xoá mồ côi và `_cho_index(tbl)`
bằng một dòng:

```python
    n_ghi = _ghi_chunk(tbl, can_nap, nap, id_cu)
    return n_ghi, tbl.count_rows()
```

Giữ nguyên phần trên nó: `_doc_can_nap`, `ep & co_that`, cảnh báo `--doc` không có trong corpus,
nhánh `du` ném `DocDuTrongBang`, và nhánh `not nap` in "không có gì đổi". Nhánh `not nap` vẫn phải
gọi `_cho_index(tbl)` rồi trả `(0, tbl.count_rows())` như cũ — đừng để nó rơi xuống `_ghi_chunk`
với `can_nap` rỗng, vì hai chỗ đó in ra hai thông điệp khác nhau.

- [ ] **Step 5: Chạy test, xác nhận XANH**

Run: `uv run pytest tests/test_ingest_tang_dan.py -q`
Expected: tất cả xanh — 5 ca mới cộng toàn bộ ca cũ (`write_lancedb` đổi ruột nhưng không đổi
hành vi quan sát được, nên ca cũ là lưới an toàn cho lần rút này)

- [ ] **Step 6: Suite đầy đủ + lint + commit**

```powershell
uv run pytest -q
uv run ruff check .
git add app/ingestion/pipeline.py tests/test_ingest_tang_dan.py
git commit -m "refactor(ingest): extract the shared chunk writer behind _ghi_chunk"
```

---

### Task 4: `ingest_one_doc` dùng chung tầng ghi

**Files:**
- Modify: `app/ingestion/pipeline.py` (`ingest_one_doc`, phần ghi LanceDB)
- Modify: `tests/test_ingest_mot_van_ban.py` (`_FakeDB`, `_FakeTable`, ca mới)

**Interfaces:**
- Consumes: `_id_dang_co`, `_ghi_chunk` (Task 3); `_tao_bang_moi` (có sau Task 1)
- Produces: `ingest_one_doc(doc, rels, tat_ca_docs) -> int` — chữ ký **không đổi**

**ĐỌC `tests/test_ingest_mot_van_ban.py` TRƯỚC KHI SỬA.** Nó đã có sẵn `_FakeTable`, `_FakeDB`,
hàm `_doc(doc_id, text)`, fixture `bang(monkeypatch)` và `_bat_push_one_doc(monkeypatch)`. Dùng
lại chúng, đừng dựng helper mới song song.

**Ca "văn bản không còn điều nào" đã có sẵn trên main** —
`test_van_ban_khong_con_dieu_nao_van_xoa_chunk_cu_va_len_do_thi` (dòng ~275). **Đừng viết ca trùng.**
Bản của main mạnh hơn bất kỳ ca nào viết mới ở đây, vì nó khẳng định thêm rằng node vẫn lên đồ thị
dù văn bản không còn chunk nào. Nó chính là lưới an toàn cho lần rút này: nếu `_ghi_chunk` làm hỏng
ngữ nghĩa đó, ca của main đỏ.

**Việc thật của Step 1 là đổi `_FakeTable`**, vì hình dạng vị từ xoá đổi: bản cũ của
`ingest_one_doc` xoá bằng `doc_id = 'X'`, bản mới xoá bằng `id IN ('X::Điều 1', …)`. `_FakeTable`
hiện tại phân tích đúng dạng cũ, nên nếu để nguyên thì nó **không xoá gì cả** và các ca sẽ đỏ vì
lý do sai.

- [ ] **Step 1: Đổi bảng giả sang khớp tầng ghi mới**

Thay `_FakeTable` và `_FakeDB` bằng:

```python
class _FakeTable:
    """Bảng giả khoá theo `id` — khớp `_ghi_chunk`, vốn xoá bằng `id IN (…)` chứ không phải
    `doc_id = …`. Giữ `deleted` để ca test còn khẳng định được phạm vi xoá."""

    def __init__(self, rows=None):
        self.hang = {r["id"]: dict(r) for r in (rows or [])}
        self.deleted: list[str] = []
        self.so_lan_dung_fts = 0

    # --- đọc ---
    @property
    def schema(self):
        return [SimpleNamespace(name=k) for k in ("id", "doc_id", "text", "vector")]

    def count_rows(self) -> int:
        return len(self.hang)

    def search(self, *a, **kw):
        return _FakeTruyVan(list(self.hang.values()))

    def list_indices(self):
        return [SimpleNamespace(name="text_idx", index_type="FTS", num_indexed_rows=len(self.hang))]

    def wait_for_index(self, ten, **kw) -> None:
        pass

    # --- ghi ---
    def delete(self, where: str) -> None:
        self.deleted.append(where)
        m = re.match(r"^id IN \((.*)\)$", where)
        assert m, f"cú pháp delete lạ, cloud có thể không nhận: {where!r}"
        for i in {s.strip()[1:-1].replace("''", "'") for s in m.group(1).split(", ")}:
            self.hang.pop(i, None)

    def merge_insert(self, khoa: str):
        assert khoa == "id", f"khoá merge phải là id, không phải {khoa!r}"
        return _FakeMerge(self)

    def add(self, rows) -> None:
        for r in rows:
            self.hang[r["id"]] = dict(r)

    def create_fts_index(self, cot: str, **kw) -> None:
        self.so_lan_dung_fts += 1


class _FakeTruyVan:
    def __init__(self, hang): self._hang, self._cot = hang, None

    def where(self, dieu_kien: str):
        m = re.match(r"^doc_id IN \((.*)\)$", dieu_kien)
        assert m, f"cú pháp where lạ: {dieu_kien!r}"
        ids = {s.strip()[1:-1] for s in m.group(1).split(", ")}
        self._hang = [r for r in self._hang if r.get("doc_id") in ids]
        return self

    def select(self, cot): self._cot = list(cot); return self
    def limit(self, n): return self
    def to_list(self):
        if self._cot is None:
            return [dict(r) for r in self._hang]
        return [{k: r[k] for k in self._cot} for r in self._hang]


class _FakeMerge:
    def __init__(self, bang): self._bang = bang
    def when_matched_update_all(self): return self
    def when_not_matched_insert_all(self): return self
    def execute(self, rows) -> None:
        for r in rows:
            self._bang.hang[r["id"]] = dict(r)


class _FakeDB:
    def __init__(self, bang: dict[str, _FakeTable]):
        self.bang = bang
        self.da_goi_table_names = False

    def table_names(self):
        # Không còn ai được phép gọi: phép dò giờ là `open_table`. Cờ này để ca test NÓI RA
        # điều đó thay vì im lặng chấp nhận.
        self.da_goi_table_names = True
        return list(self.bang)

    def list_tables(self):
        # Ghim finding critical fix round 1 (10/08): `list_tables()` ném HttpError 400 thật
        # trên LanceDB Cloud của dự án — "PgCatalog::open_database() requires a table name".
        raise AssertionError(
            "ingest_one_doc không được gọi list_tables() — nó 400 thật trên LanceDB Cloud"
        )

    def open_table(self, ten: str) -> _FakeTable:
        if ten not in self.bang:
            # Đúng loại và đúng thông điệp lancedb ném thật — đo 13/08 trên CẢ nhúng lẫn cloud,
            # cùng khung `lancedb/db.py:1722`.
            raise ValueError(f"Table '{ten}' was not found")
        return self.bang[ten]

    def create_table(self, ten: str, data, **kw) -> _FakeTable:
        self.bang[ten] = _FakeTable(data)
        return self.bang[ten]
```

Thêm `import re` và `from types import SimpleNamespace` ở đầu file nếu chưa có.

Fixture `bang` dựng `_FakeTable(co_san)` với danh sách hàng — vẫn dùng được vì hàm khởi tạo mới
nhận đúng danh sách đó. Nhưng mọi ca đọc `bang.rows` phải chuyển sang `bang.hang`; chạy
`Select-String -Path tests/test_ingest_mot_van_ban.py -Pattern "\.rows"` để tìm hết.

- [ ] **Step 2: Sửa các khẳng định ghim HÌNH DẠNG vị từ**

Vài ca khẳng định nguyên văn `bang.deleted == ["doc_id = 'TT99-2026'"]`. Hình dạng đó đổi một cách
hợp lệ. **Đừng xoá khẳng định — đổi nó sang ghim TÍNH CHẤT**, vì tính chất mới là thứ đáng giữ:
lệnh xoá chỉ được chạm chunk của đúng văn bản đang nạp.

Ví dụ cho `test_van_ban_khong_con_dieu_nao_van_xoa_chunk_cu_va_len_do_thi`, thay:

```python
    assert bang.deleted == ["doc_id = 'TT99-2026'"]
    assert [r["doc_id"] for r in bang.rows] == ["TT01-2020", "TT02-2021"]
```

bằng:

```python
    # Ghim TÍNH CHẤT chứ không ghim chuỗi: vị từ đổi từ `doc_id = …` sang `id IN (…)` khi tầng
    # ghi dùng chung với `write_lancedb`. Cái phải đúng mãi là phạm vi, không phải cú pháp.
    assert len(bang.deleted) == 1
    assert all("TT99-2026::" in x for x in bang.deleted[0].split(", ")), bang.deleted
    assert sorted(r["doc_id"] for r in bang.hang.values()) == ["TT01-2020", "TT02-2021"]
```

Rà cả file cho mọi ca khác đụng `bang.deleted` hoặc `bang.rows` và sửa cùng kiểu. Đặc biệt kiểm
`test_doc_id_ban_khong_phat_lenh_delete_nao` — nó phải **vẫn xanh**, vì `_loc_doc_id` gọi
`kiem_doc_id` trước khi dựng bất kỳ vị từ nào, nên `doc_id` bẩn ném trước khi chạm bảng.

- [ ] **Step 3: Thêm hai ca cho phép dò bảng**

```python
def test_ingest_one_doc_khong_goi_table_names_cung_khong_goi_list_tables(bang, monkeypatch):
    """Phép dò bảng là `open_table`, không phải liệt kê rồi so tên.

    `list_tables()` ném HttpError 400 thật trên LanceDB Cloud của dự án (đo 10/08);
    `table_names()` thì deprecated và có phân trang, nên "không thấy tên" lẫn với "bảng không
    tồn tại" — mà nhánh sau dẫn thẳng tới dựng đè bảng đang phục vụ. `open_table` tránh cả hai.
    """
    db = pipeline.vectordb.connect()
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert db.da_goi_table_names is False


def test_loi_tam_thoi_luc_mo_bang_thi_nem_chu_khong_dung_de_bang_moi(monkeypatch):
    """Trục trặc mạng KHÔNG được hiểu thành "bảng chưa có" rồi dựng đè bảng thật.

    `ValueError` là built-in dùng cho vô số lý do; bắt trần nó là mở đúng cánh cửa này.
    """
    class _DbHong:
        def open_table(self, ten):
            raise ValueError("connection reset by peer")
        def create_table(self, *a, **kw):
            raise AssertionError("không được dựng bảng mới khi lỗi chưa chắc là thiếu bảng")

    monkeypatch.setattr("app.core.vectordb.connect", lambda: _DbHong())
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    with pytest.raises(ValueError, match="connection reset"):
        pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
```

Ca đầu cần `pipeline.vectordb.connect()` trả về **cùng** đối tượng `_FakeDB` mà fixture đã vá —
kiểm fixture: nó vá bằng `lambda: _FakeDB({...})`, tức mỗi lần gọi là một đối tượng MỚI. Sửa
fixture để dựng `_FakeDB` một lần rồi `lambda: db`, và trả cả `db` ra cho ca test dùng. Nếu không
thấy cách gọn, đổi ca test sang khẳng định qua `bang` thay vì `db` — nhưng **phải nói ra trong
report** là đã đổi cách và vì sao.

- [ ] **Step 4: Chạy test, xác nhận ĐỎ**

Run: `uv run pytest tests/test_ingest_mot_van_ban.py -q`
Expected: FAIL — bản `ingest_one_doc` hiện tại vẫn gọi `table_names()` (ca mới đỏ) và vẫn xoá
bằng `doc_id = …` (bảng giả mới `assert` cú pháp `id IN (…)`).

- [ ] **Step 5: Rút phần ghi LanceDB của `ingest_one_doc`**

Thay khối từ `db = vectordb.connect()` tới dòng `print(f"[ingest] {doc.doc_id}: …")` bằng:

```python
    db = vectordb.connect()
    try:
        tbl = db.open_table(LANCEDB_TABLE)
    except ValueError as e:
        # Phép dò bảng là `open_table`, không phải liệt kê: `list_tables()` ném HttpError 400
        # thật trên LanceDB Cloud của dự án (đo 10/08), `table_names()` thì deprecated và có
        # phân trang. Bộ lọc thông điệp CHỊU LỰC — `ValueError` là built-in dùng cho vô số lý
        # do, bắt trần nó biến một trục trặc bất kỳ thành "bảng chưa có" rồi dựng đè bảng thật.
        if "not found" not in str(e).lower():
            raise
        n = _tao_bang_moi(db, rows)[0] if rows else 0
        print(f"[ingest] {doc.doc_id}: {n} chunk vào LanceDB (bảng mới).")
        return n

    n = _ghi_chunk(tbl, {doc.doc_id}, rows, _id_dang_co(tbl, {doc.doc_id}))
    print(f"[ingest] {doc.doc_id}: {n} chunk vào LanceDB (thay tại chỗ).")
```

Giữ nguyên `kiem_doc_id(doc.doc_id)`, `rows = build_chunks([doc])`, toàn bộ khối Neo4j
(`push_one_doc`) và `return n` ở cuối hàm. Cập nhật docstring: bỏ đoạn tả `delete`+`add`, ghi rằng
phần ghi giờ dùng chung `_ghi_chunk` với `write_lancedb`. **Giữ** đoạn đo 10/08 (delete+add 23
hàng 1,23s, embed 1,79s, so với ~52s nạp lại toàn bộ) — nó vẫn là lý do đường này tồn tại.

- [ ] **Step 6: Chạy test, xác nhận XANH**

Run: `uv run pytest tests/test_ingest_mot_van_ban.py -q`
Expected: tất cả xanh, gồm cả `test_van_ban_khong_con_dieu_nao_van_xoa_chunk_cu_va_len_do_thi`
của main — ca đó là bằng chứng chính rằng lần rút này không làm mất ngữ nghĩa nào.

- [ ] **Step 7: Suite đầy đủ + lint + commit**

```powershell
uv run pytest -q
uv run ruff check .
git add app/ingestion/pipeline.py tests/test_ingest_mot_van_ban.py
git commit -m "refactor(ingest): route ingest_one_doc through the shared writer"
```

---

### Task 5: Số hiệu TASKLIST, luật dải, WORKLOG

**Files:**
- Modify: `docs/TASKLIST.md`
- Modify: `docs/COMMIT-CONVENTION.md` (mục "Push rules")
- Modify: `docs/WORKLOG.md`

**Interfaces:** không có API

Sau Task 1, `docs/TASKLIST.md` là bản của main. Task này thêm lại 8 mục của `feat/ai` với số mới.
Lấy **nguyên văn thân mục** từ bản trước merge: `git show d1f5f93:docs/TASKLIST.md`.

- [ ] **Step 1: Ghi luật dải vào `docs/COMMIT-CONVENTION.md`**

Trong mục "Push rules", ngay sau bảng Track/Branch/Worktree, chèn:

```markdown
   **Số hiệu `TN` trong `docs/TASKLIST.md` chia theo dải**, vì hai nhánh dài hạn cùng nối vào một
   danh sách đánh số tuần tự thì chắc chắn đâm nhau — lần đầu (13/08) tốn 9 mục trùng số khác nghĩa:

   | Dải | Ai dùng |
   |---|---|
   | T1–T99 | đã tồn tại trên `main` — không đánh lại, 13 commit message đã dẫn tới chúng |
   | T100+ | `feat/ai` |
   | T200+ | `feat/software` |
   | T300+ | `feat/ai-compliance` |

   Mục mới lấy số kế tiếp **trong dải của nhánh mình**, không phải số kế tiếp của cả file.
```

- [ ] **Step 2: Thêm lại 8 mục với số mới**

Chép nguyên văn thân từng mục từ `git show d1f5f93:docs/TASKLIST.md`, chỉ đổi số ở dòng tiêu đề:

| Cũ | Mới | Tiêu đề |
|---|---|---|
| T25 | T100 | Cân nhắc `create_scalar_index("doc_id")` |
| T26 | T101 | `count_rows()` sau `merge_insert` trên bảng từ xa có tươi không? |
| T27 | T102 | Vân tay chunk lệch khi ghi bằng `merge_insert` |
| T28 | T103 | `StarletteDeprecationWarning` từ `fastapi/testclient` lúc import |
| T21 | T104 | Trọng số nhánh thưa có thể lệch giữa luật đã chết và luật hiện hành |
| T22 | T105 | `HttpError` thoáng qua từ LanceDB Cloud làm rớt câu khi benchmark |
| T23 | T106 | `so_hieu` dính dấu cách thừa… — ĐÃ SỬA 12/08 (giữ `[x]`, để mục đã đóng) |
| T18 | T107 | Nhận diện viện dẫn trong CÂU HỎI → anchor đồ thị |

**Không thêm lại `T24`** (`ascii_folding`) — khối chú thích `_FTS_OPTS` trên main đã phủ, và phủ
đúng hơn: nó chỉ ra rằng `ascii_folding` bỏ dấu **trước** khi lọc stop-word nên `thẻ`/`số`/`tổ`
thành `the`/`so`/`to`, và đặt `remove_stop_words: False` để tháo. Ghi một dòng vào WORKLOG rằng
mục này bị bỏ vì lý do đó, để không ai mở lại.

Trong thân các mục vừa chép, sửa mọi tham chiếu chéo tới số cũ cho khớp số mới (ví dụ T100 nhắc
`T25`, T105 nhắc `T21`). Sau khi sửa xong, chạy:

```powershell
Select-String -Path docs/TASKLIST.md -Pattern "\bT(1|2|17|18|21|22|23|24|25|26|27|28)\b" | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" }
```

và đọc từng dòng: mỗi lần xuất hiện phải trỏ đúng mục của **main**, không phải mục cũ của `feat/ai`.

- [ ] **Step 3: Cập nhật ghi chú `T18` của main — phép dò bảng không còn là `table_names`**

`T18` của main (`create_fts_index` đã deprecated từ lancedb 0.25) mang một gạch đầu dòng dặn
**đừng** đổi `table_names()` → `list_tables()` vì `list_tables()` ném HttpError 400 thật. Lời dặn
đó vẫn đúng, nhưng nó đã hết đối tượng: sau Task 4 không còn ai gọi cái nào. Thêm vào cuối gạch
đầu dòng ấy:

```markdown
  **Cập nhật 13/08:** cả hai đường ghi giờ dò bảng bằng `db.open_table(...)` trong `try`, bắt
  `ValueError` có lọc thông điệp `"not found"` — không còn lời gọi `table_names()` hay
  `list_tables()` nào trên đường ingest. Cách này tránh luôn cả HttpError 400 lẫn phân trang của
  `list_tables()`. Đo 13/08: cả LanceDB nhúng lẫn LanceDB Cloud đều ném
  `ValueError("Table 'x' was not found")`, cùng khung `lancedb/db.py:1722`. Bộ lọc thông điệp là
  thứ CHỊU LỰC — `ValueError` là built-in dùng cho vô số lý do, bắt trần nó biến một trục trặc
  mạng thoáng qua thành "bảng chưa có" rồi dựng đè bảng đang phục vụ.
```

Ca `_FakeDB.list_tables` ném `AssertionError` **giữ nguyên** — nó vẫn canh đúng thứ cần canh.

- [ ] **Step 4: `docs/WORKLOG.md` — mục 13/08**

Thêm vào mục 13/08 (đã có sau Task 1, giữ nguyên phần cũ) ba việc:

- Đã hoà `main` vào `feat/ai`; `ingest_one_doc` và `write_lancedb` giờ dùng chung `_ghi_chunk`.
- Phép đo 13/08 chuyển từ T1 sang đây: bảng thật khớp `build_chunks` **0 ô lệch trên 661 hàng ×
  10 cột**; chunk `TT66-2025 Điều 6` cắt ở đúng ranh giới `(v)`/`(vii)`. T1 đã được main đóng từ
  10/08 — tiền đề "bảng còn giữ bản cắt hỏng" mà plan `2026-08-13-ingest-tang-dan` dựa vào là bản
  chụp trước lúc đóng.
- `T24` (`ascii_folding`) bị bỏ vì `_FTS_OPTS` của main đã phủ và phủ đúng hơn.

Viết theo đúng định dạng file đó mô tả; **đọc file trước khi sửa**.

- [ ] **Step 5: Suite + lint + commit**

```powershell
uv run pytest -q
uv run ruff check .
git add docs/TASKLIST.md docs/COMMIT-CONVENTION.md docs/WORKLOG.md
git commit -m "docs: renumber feat/ai tasklist items and reserve a range per branch"
```

---

### Task 6: Viết lại mô tả PR #24

**Files:** không có file trong repo — chỉ mô tả PR trên GitHub.

**Interfaces:** không có

- [ ] **Step 1: Push**

```powershell
git push origin feat/ai
git status --short
```

- [ ] **Step 2: Viết mô tả mới ra file rồi cập nhật PR**

Viết vào một file tạm ngoài repo, rồi:

```powershell
gh pr edit 24 --body-file <đường-dẫn-file-tạm>
```

Mô tả phải nói đúng trạng thái **sau hoà**, không phải trạng thái lúc mở PR:

- Phần main đã có từ 10/08: `ingest_one_doc`, `/approve` per-document, `push_one_doc`.
- Phần PR này thêm: phát hiện-đổi bằng vân tay (`_doc_can_nap`), ghi không-cửa-sổ bằng
  `merge_insert`, dọn chunk mồ côi, chặn xoá văn bản dư (`DocDuTrongBang` + `--xoa-doc-du`),
  chính sách index FTS (`_cho_index`, timeout 30s, chỉ chờ index FTS), CLI `--doc`.
- Phần PR này **hợp nhất**: cả hai đường ghi giờ đi qua `_ghi_chunk`; `ingest_one_doc` bỏ
  `delete`+`add` nên hết cửa sổ văn bản vắng mặt khỏi bảng.
- Ghi rõ: `_FTS_OPTS` được truyền ở mọi lời gọi `create_fts_index`; phép dò bảng là `open_table`
  chứ không phải `table_names`/`list_tables`.
- Số hiệu TASKLIST của `feat/ai` đã dời sang T100–T107; luật dải ghi ở `docs/COMMIT-CONVENTION.md`.
- Bỏ mọi câu cũ nói `n_chunks` đổi nghĩa và `chunks_bang` — chúng đã bị hoàn nguyên ở Task 1.

- [ ] **Step 3: Kiểm CI**

```powershell
gh pr checks 24
```

CI có job `web` chạy `npm ci` + `lint` + `build` — đó là chỗ duy nhất kiểm phần `web/` bị sửa ở
Task 1, vì worktree này không cài `node_modules`. Nếu CI đỏ, sửa ngay bằng một commit mới (quy ước
repo, Push rules 4).

---

## Sau khi hết plan

Merge PR là việc của chủ repo. Đừng tự merge, đừng tự đóng PR.
