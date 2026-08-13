# Nạp văn bản vbpl qua `/admin` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload thẳng file `corpus/<slug>.json` do trình cào vbpl sinh ra, không để extractor đoán lại một thứ đã đọc chính xác.

**Architecture:** Một nhánh trong `upload_document`: đuôi `.json` mà validate được thành `CorpusDocument` thì dùng thẳng, còn lại giữ nguyên đường `extract_document`. Cả hai nhánh cùng cho ra một `CorpusDocument`, nên phần sau — lưu Storage, bản ghi `pending`, trang duyệt, Approve, `ingest_one_doc` — không đổi một dòng.

**Tech Stack:** FastAPI · Pydantic v2 · Supabase Storage + PostgREST · pytest · uv

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-10-nap-van-ban-vbpl-qua-admin-design.md`.
- Thông điệp commit **tiếng Anh**, Conventional Commits theo `docs/COMMIT-CONVENTION.md`. Scope hợp lệ ở đây: `api`, `docs`.
- Nhánh `feat/software`. `main` chỉ nhận qua PR.
- Trước mỗi commit: `uv run pytest -q` và `uv run ruff check .` phải xanh. Mốc hiện tại: **776 test xanh**.
- Comment và docstring viết **tiếng Việt**, theo nếp repo.
- **Không** thêm endpoint mới. Không đụng `extract_document`, `approve_document`, `ingest_one_doc`.
- Test dùng **file thật** trong `data/raw/vbpl/corpus/` (22 file đang tracked), không bịa dữ liệu.
- File dùng làm mẫu, đường dẫn nguyên văn:
  `data/raw/vbpl/corpus/thong-tu-21-2026-tt-nhnn-sua-doi-bo-sung-dieu-15-thong-tu-so-15-2024-tt-nhnn-quy.json`
  — `doc_id` `TT21-2026`, `so_hieu` `21/2026/TT-NHNN`, 3 `articles`, 3 `provisions`,
  `co_quan_ban_hanh` `Ngân hàng Nhà nước Việt Nam`, `articles[0].char_start` = `958`.

---

## File Structure

| File | Trách nhiệm | Thao tác |
|---|---|---|
| `app/api/documents.py` | `upload_document` chọn nhánh theo đuôi file; `kiem_doc_id` gác chung cho cả hai nhánh | Sửa `:144-198` |
| `tests/test_documents.py` | Bốn ca cho nhánh JSON | Sửa (thêm cuối file) |
| `docs/ARCHITECTURE.md` | Mục "Nạp văn bản từ vbpl" | Sửa |
| `docs/TASKLIST.md` | T23 — corpus đóng gói trôi xa canonical, mà `dong_goi` đọc bản đóng gói | Sửa |

---

### Task 1: Nhánh JSON trong `upload_document`

**Files:**
- Modify: `app/api/documents.py:144-198`
- Test: `tests/test_documents.py` (thêm cuối file)

**Interfaces:**
- Consumes: `CorpusDocument` (đã import sẵn ở đầu `documents.py`); `app.ingestion.pipeline.kiem_doc_id(doc_id: str) -> str` — ném `ValueError` nếu `doc_id` không khớp `^[A-Za-z0-9._-]+\Z`.
- Produces: không có API mới. Hành vi mới: `.json` đúng khuôn → dùng thẳng; `.json` hỏng → 422; `doc_id` bẩn → 422.

- [ ] **Step 1: Viết bốn ca test thất bại**

Thêm vào cuối `tests/test_documents.py`. Đầu file đã có `from app.core import appdb`; thêm
`from app.core.schemas import CorpusDocument` vào khối import nếu chưa có.

```python
# --- Nạp thẳng bản đã crawl từ vbpl (không qua extractor) ---

#: File thật trong repo, không bịa: 3 điều, 3 nút cây, có bảng thuộc tính và char_span.
_FILE_CRAWL = (
    "data/raw/vbpl/corpus/"
    "thong-tu-21-2026-tt-nhnn-sua-doi-bo-sung-dieu-15-thong-tu-so-15-2024-tt-nhnn-quy.json"
)


def _cam_extractor(monkeypatch):
    """Bắt quả tang nếu extractor chạy — chạy là mất provisions/so_hieu/char_span."""
    import app.ingestion.extract as extract_mod

    def _no(*_a, **_kw):
        raise AssertionError("extract_document chạy trên file đã đúng khuôn CorpusDocument")

    monkeypatch.setattr(extract_mod, "extract_document", _no)


def test_upload_json_da_crawl_giu_nguyen_cay_va_thuoc_tinh(client, fake_store, monkeypatch):
    """Bản crawl giàu hơn hẳn bản extract — đẩy nó qua regex + Gemini là vứt hết rồi đoán lại."""
    from pathlib import Path

    _cam_extractor(monkeypatch)
    noi_dung = Path(_FILE_CRAWL).read_bytes()

    r = client.post(
        "/documents/upload",
        files={"file": (Path(_FILE_CRAWL).name, noi_dung, "application/json")},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["doc_id"] == "TT21-2026"
    luu = fake_store["rows"]["TT21-2026"]["extracted"]
    assert luu["so_hieu"] == "21/2026/TT-NHNN"
    assert len(luu["provisions"]) == 3, "cây điều khoản phải sống sót"
    assert luu["co_quan_ban_hanh"] == "Ngân hàng Nhà nước Việt Nam"
    assert luu["articles"][0]["char_start"] == 958, "char_span phải giữ nguyên từng con số"


def test_upload_json_hong_thi_422_chu_khong_roi_ve_extractor(client, fake_store, monkeypatch):
    """Rơi về extractor là biến một file hỏng thành văn bản trông như thật với vài điều rỗng."""
    _cam_extractor(monkeypatch)

    r = client.post(
        "/documents/upload",
        files={"file": ("hong.json", b'{"doc_id": "TT99-2026"}', "application/json")},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )

    assert r.status_code == 422, r.text
    assert "title" in r.text, "phải nói rõ thiếu trường nào, không nuốt lý do"
    assert fake_store["rows"] == {}, "không được tạo bản ghi pending cho file hỏng"


def test_upload_json_doc_id_ban_bi_chan(client, fake_store, monkeypatch):
    """`doc_id` chảy vào chuỗi điều kiện của `tbl.delete` ở bước duyệt — chặn từ cửa vào."""
    import json

    _cam_extractor(monkeypatch)
    xau = json.dumps({**_DOC, "doc_id": "TT99'; --"}, ensure_ascii=False).encode("utf-8")

    r = client.post(
        "/documents/upload",
        files={"file": ("xau.json", xau, "application/json")},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )

    assert r.status_code == 422, r.text
    assert fake_store["rows"] == {}


def test_upload_pdf_van_di_duong_extractor(client, fake_store, monkeypatch):
    """Đường cũ không được đụng: văn bản nội bộ SHB không có trang vbpl để cào."""
    import app.ingestion.extract as extract_mod

    duoi_da_thay: list[str] = []

    def _gia(path, source="external"):
        duoi_da_thay.append(path.suffix)
        return CorpusDocument.model_validate(_DOC)

    monkeypatch.setattr(extract_mod, "extract_document", _gia)

    r = client.post(
        "/documents/upload",
        files={"file": ("quy-dinh.pdf", b"%PDF-1.7 gia", "application/pdf")},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )

    assert r.status_code == 200, r.text
    assert duoi_da_thay == [".pdf"], "file không phải .json vẫn phải qua extractor"
    assert fake_store["rows"]["TT99-2026"]["status"] == "pending"
```

- [ ] **Step 2: Chạy để chắc chắn nó thất bại**

Run: `uv run pytest tests/test_documents.py -q -k "json or extractor"`
Expected: FAIL — ba ca `.json` đỏ vì mã hiện tại luôn gọi `extract_document`, nên `_cam_extractor` nổ `AssertionError`. Ca `.pdf` xanh ngay từ đầu (đường cũ chưa đổi) — đó là đúng kỳ vọng, nó là lưới canh hồi quy chứ không phải tính năng mới.

- [ ] **Step 3: Cài đặt**

Trong `app/api/documents.py`, thay khối extract (`:161-173`) bằng:

```python
    # Bản crawl vbpl mang cây `provisions`, `char_span`, `so_hieu` và bảng thuộc tính. Đẩy nó
    # qua `extract_document` (regex tách Điều + Gemini đoán metadata) là VỨT hết rồi đoán lại
    # một thứ đã đọc được chính xác. File `.json` đúng khuôn thì dùng thẳng.
    if Path(filename).suffix.lower() == ".json":
        from pydantic import ValidationError

        try:
            doc = CorpusDocument.model_validate_json(content)
        except ValidationError as exc:
            # KHÔNG rơi về extractor. Rơi về là biến một file hỏng thành một văn bản trông
            # như thật với vài điều rỗng — hỏng phải đọc kỹ mới thấy.
            raise HTTPException(
                status_code=422, detail=f"JSON không đúng khuôn CorpusDocument: {exc}"
            ) from exc
    else:
        # Extract (tái dùng extractor CLI) — ghi file tạm đúng đuôi để chọn parser
        from app.ingestion.extract import extract_document

        suffix = Path(filename).suffix or ".txt"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            doc = extract_document(tmp_path, source=source)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Extract thất bại: {exc}") from exc
        finally:
            tmp_path.unlink(missing_ok=True)

    # Gác CHUNG cho cả hai nhánh: `doc_id` chảy vào chuỗi điều kiện của `tbl.delete(...)` ở
    # bước duyệt, và nó có thể đến từ JSON sửa tay HOẶC từ metadata Gemini đoán.
    from app.ingestion.pipeline import kiem_doc_id

    try:
        kiem_doc_id(doc.doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
```

Đọc lại đầu file để chắc `CorpusDocument`, `Path`, `tempfile`, `HTTPException` đã có sẵn — nếu thiếu thì thêm import.

- [ ] **Step 4: Chạy test cho tới khi xanh**

Run: `uv run pytest tests/test_documents.py -q`
Expected: PASS toàn bộ file.

- [ ] **Step 5: Toàn bộ test và lint**

Run: `uv run pytest -q; uv run ruff check .`
Expected: xanh, 780 test (776 + 4).

- [ ] **Step 6: Commit**

```bash
git add app/api/documents.py tests/test_documents.py
git commit -m "feat(api): accept an already-crawled document instead of re-deriving it"
```

---

### Task 2: Tài liệu thao tác và mục nợ

**Files:**
- Modify: `docs/ARCHITECTURE.md` (thêm cuối file, sau mục "Cấp quyền admin")
- Modify: `docs/TASKLIST.md` (thêm vào mục "Nợ kỹ thuật", sau T22)

**Interfaces:** không có.

- [ ] **Step 1: Thêm mục "Nạp văn bản từ vbpl" vào `docs/ARCHITECTURE.md`**

```markdown
## Nạp văn bản từ vbpl

Nguồn thật của corpus là **crawl vbpl.vn**, không phải upload PDF. Bản crawl mang cây
`provisions`, `char_span` khớp từng ký tự, `so_hieu` và bảng thuộc tính — thứ mà
`extract_document` (regex + Gemini) không dựng lại được.

Crawl **chạy trên máy chủ repo, không trên server**: vbpl nạp nội dung Điều/Khoản qua Server
Action sau khi JS chạy, nên phải có Playwright + Chromium. Image production cài gói Python
`playwright` nhưng không có binary trình duyệt, và Cloud Run ở 512Mi thì dưới mức Chromium
headless cần.

```powershell
# 1 — crawl (máy chủ repo)
uv run python scripts/crawl_vbpl_batch.py danh_sach_url.txt
#     → data/raw/vbpl/raw/<slug>.json  và  data/raw/vbpl/corpus/<slug>.json

# 2 — upload `corpus/<slug>.json` ở /admin → xem JSON → gán relationships nếu có → Approve
```

`/documents/upload` nhận file `.json` đúng khuôn `CorpusDocument` và **bỏ qua extractor**.
Không đúng khuôn thì 422 kèm lý do Pydantic — không âm thầm rơi về extractor.

Quan hệ (`THAY_THE`/`BAI_BO`/…) vẫn **gán tay**, có chủ đích: mỗi cạnh trong
`app/ingestion/nap_corpus.py::CANH_MOI` kèm `note` trích nguyên văn làm bằng chứng. Gán chúng
trong ô `relationships` lúc bấm Approve.

**Lớp phủ — giới hạn cần biết.** `data/overlay/lop_phu.json` dựng offline bởi
`python -m app.ontology.dong_goi`, đọc `data/raw/vbpl` và `data/corpus.real.json` — cả hai chỉ
có trên máy chủ repo. Nên văn bản vừa duyệt có chunk và có node, nhưng **không cạnh `TAC_DONG`
nào** cho tới khi artefact được dựng lại và deploy: huy hiệu "điều bị tác động" không hiện gì,
không lỗi, không cảnh báo.

Chỉ cần khi văn bản mới **sửa đổi hoặc bãi bỏ** văn bản khác:

```powershell
uv run python -m app.ingestion.nap_corpus     # trộn vào corpus.real.json
uv run python -m app.ontology.dong_goi        # dựng lại lop_phu.json
gcloud run deploy lexflow-api --source . --region asia-southeast1 --allow-unauthenticated
```
```

- [ ] **Step 2: Thêm T23 vào `docs/TASKLIST.md`**

Đặt ngay sau mục T22, trước dòng `---` kết thúc phần "Nợ kỹ thuật":

```markdown
### [ ] T23 · `dong_goi` dựng lớp phủ từ corpus KHÔNG phải corpus đang phục vụ

Từ khi T5 đưa canonical lên Supabase Storage, production đọc `legal-docs/corpus.json`, còn
`data/corpus.real.json` trong image tụt xuống làm bản dự phòng — và nó là **ảnh chụp của lần
build cuối**, không nhận được văn bản nào duyệt qua `/admin` sau đó.

`app/ontology/dong_goi.main()` đọc đúng file đóng gói ấy (`Path("data/corpus.real.json")`).
Nghĩa là artefact lớp phủ đang được dựng từ một corpus **không phải** corpus đang phục vụ, và
khoảng cách lớn dần theo mỗi lượt duyệt.

- Vì sao quan trọng: cạnh `TAC_DONG` là thứ sinh ra huy hiệu "điều bị tác động" và modal đối
  chiếu. Dựng nó từ một corpus cũ nghĩa là văn bản duyệt sau lần build cuối **không tồn tại**
  với tầng lớp phủ, và không có gì báo.
- Hôm nay chưa đau vì mới có ít lượt duyệt. Nó lớn tuyến tính theo số lượt.
- **Bước đầu tiên:** cho `dong_goi` nhận đường dẫn corpus qua tham số (mặc định giữ nguyên
  `data/corpus.real.json`), rồi thêm một lối tải canonical từ Storage về file tạm trước khi
  dựng. Có `scripts/sync_corpus_storage.py` làm mẫu cho phần tải.
```

- [ ] **Step 3: Chạy test và lint cho chắc không rơi rớt**

Run: `uv run pytest -q; uv run ruff check .`
Expected: xanh.

- [ ] **Step 4: Commit**

```bash
git add docs/ARCHITECTURE.md docs/TASKLIST.md
git commit -m "docs: record the vbpl import path and the corpus the overlay is built from"
```
