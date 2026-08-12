# Hoa Tiêu Pháp Lý (LexFlow)
> Dẫn đường qua rừng thông tư, nghị định

Trợ lý pháp lý **Advanced RAG + Knowledge Graph** tra cứu quy định ngân hàng tiếng Việt: trả lời có
trích dẫn đúng điều/khoản **đang hiệu lực**, phát hiện **mâu thuẫn** giữa tài liệu nội bộ và luật
hiện hành, và trực quan hóa **đồ thị quan hệ** văn bản. Dự án *Vietnam AI Innovation Challenge 2026 — đề SHB*.

## Tech stack

| Lớp | Công nghệ |
|---|---|
| Backend | Python 3.12 · **uv** · FastAPI |
| LLM + Embedding | **Google Gemini** (`google-genai`) — chat + `gemini-embedding-001` |
| Vector DB | **LanceDB** (nhúng, hybrid vector + BM25) |
| Knowledge Graph | **Neo4j Aura** (managed cloud) |
| App DB + Auth + Storage | **Supabase** (Postgres · GoTrue JWT · Storage) |
| Hàng đợi tác vụ | **ARQ + Redis** (ingest, change alerts) |
| Frontend | **Next.js 16** · TypeScript · Tailwind v4 · Cytoscape.js |
| Deploy | **Google Cloud Run** (stateless + LanceDB Cloud) · CI GitHub Actions |

Chi tiết kiến trúc, lý do chọn & lộ trình hạ tầng: xem **`docs/ARCHITECTURE.md`** (và `docs/SPEC.html` cho spec tính năng).

## Cấu trúc

Backend tổ chức theo **package chức năng**:

```text
app/
  main.py            # FastAPI app + wiring router
  core/              # hạ tầng dùng chung
    config.py          # cấu hình + hằng số (LANCEDB_TABLE)
    llm.py             # wrapper Gemini (chat/embed)
    schemas.py         # Pydantic models dùng chung
  ingestion/         # nạp dữ liệu
    pipeline.py        # load corpus → chunk → LanceDB + Neo4j
    versioning.py      # logic hiệu lực valid_from/valid_to
    __main__.py        # entrypoint: python -m app.ingestion
  knowledge/         # kho tri thức
    retrieval.py       # hybrid search + lọc hiệu lực (+ baseline benchmark)
    graph.py           # Neo4j Aura (node/cạnh quan hệ)
  reasoning/         # suy luận bằng LLM
    answer.py          # sinh câu trả lời có trích dẫn
    conflict.py        # Conflict Detector
  api/               # lớp router
    chat.py graph.py admin.py   # /chat /graph /health /ingest
  core/auth.py       # verify Supabase JWT + phân quyền admin/staff
  worker.py          # ARQ worker (tác vụ nền: ingest, alerts)
data/         # corpus.sample.json + LanceDB store
eval/         # bộ câu hỏi vàng + benchmark
supabase/     # migrations SQL (profiles, chat history, audit, doc workflow)
web/          # Next.js frontend (Tra cứu + Đồ thị)
```

## Cài đặt

### 1. Backend (uv)
```bash
uv sync                       # cài dependencies từ pyproject/lock
cp .env.example .env          # điền GEMINI_API_KEY + Neo4j Aura
```
- **Gemini key**: https://aistudio.google.com/apikey
- **Neo4j Aura Free**: https://console.neo4j.io → tạo instance → chép URI/username/password vào `.env`.
  (Có thể bỏ trống Neo4j — chatbot vẫn chạy, chỉ trang đồ thị tạm nghỉ.)

### 2. Nạp dữ liệu
```bash
uv run python -m app.ingestion           # dùng data/corpus.sample.json
# hoặc: uv run python -m app.ingestion đường_dẫn_corpus.json
```

### 3. Frontend
```bash
cd web
npm install
cp .env.local.example .env.local         # NEXT_PUBLIC_API_BASE
```

## Chạy

```bash
# Terminal 1 — backend  (http://localhost:8000, docs tại /docs)
uv run uvicorn app.main:app --reload

# Terminal 2 — frontend (http://localhost:3000)
cd web && npm run dev
```

### Docker (tuỳ chọn — CI/deploy, dev local không cần)

```bash
docker compose up --build       # api :8000 + worker + redis
```

## Deploy (Google Cloud Run)

Backend chạy **stateless** trên Cloud Run (LanceDB Cloud giữ vectors) — build trên Cloud Build,
máy local không cần Docker:

```bash
gcloud run deploy lexflow-api --source . --region asia-southeast1 --allow-unauthenticated
```

Máy local chỉ cần `next dev` trỏ `NEXT_PUBLIC_API_BASE` về URL Cloud Run.
Xem `docs/ARCHITECTURE.md` § Topology.

## Benchmark (chứng minh giá trị kiến trúc)

So sánh RAG vector thuần vs Hybrid + Versioning + Conflict:
```bash
uv run python eval/run_benchmark.py
uv run python eval/run_benchmark.py --bo eval/bo_cua_ban.jsonl   # thêm bộ câu hỏi khác
```
Đo hai tầng:

- **Sản phẩm**: độ chính xác trích dẫn, tỷ lệ tránh văn bản hết hiệu lực, tỷ lệ phát hiện mâu thuẫn.
- **Truy hồi (IR)**: R@{1,2,5,10,20}, P@k, MRR@k, F2@k cho 6 cột — BM25 · Naive RAG · Advanced RAG
  (tái lập baseline của bài báo SBV-LawGraph) và LexFlow hybrid · +graph · +router. Cách đo, định
  dạng nhãn vàng và các cảnh báo khi đọc số: `docs/EVAL-IR.md`.

**Đo theo thời điểm** — cùng một câu hỏi, đổi `as_of` thì nhãn vàng đổi theo:
```bash
uv run python eval/chuyen_tvpl.py        # data/evaluate/ → 2 bộ (đúng-thời / hiện-nay)
uv run python -u eval/run_benchmark.py --bo eval/bo_tvpl_dung_thoi.jsonl --bo eval/bo_tvpl_hien_nay.jsonl
```
Ba cột baseline không có khái niệm `as_of` nên trả cùng kết quả ở cả hai bộ — xem `docs/EVAL-IR.md` §6.

**Kết quả** — 76 câu hỏi curate từ thuvienphapluat.vn, hỏi về luật đã bị thay thế
(`bo_tvpl_hien_nay`, đo 12/08; 74/76 câu chạy được, 2 câu rơi vì lỗi mạng LanceDB):

| | tránh văn bản hết hiệu lực | citation accuracy | F2@2 |
|---|---|---|---|
| BM25 | — | — | 0.07 |
| Naive RAG (dense thuần) | **11/74** | 64/74 | 0.48 |
| Advanced RAG (75% BM25) | — | — | 0.11 |
| **LexFlow hybrid** | **74/74** | 69/74 | **0.77** |
| **LexFlow +graph** | **74/74** | **74/74** | 0.77 |

Baseline trả về văn bản đã hết hiệu lực ở **63/74** câu; LexFlow không câu nào. BM25 gần như không
đúng ở hạng 1 (R@1 = 0.02) vì câu hỏi được viết *từ* văn bản cũ nên khớp từ vựng bị hút về đúng
văn bản đã chết.

Chính điều đó dẫn tới một thay đổi retrieval. Bảng ở **mức điều** (bộ `bo_tvpl_dung_thoi`) ban đầu
nói ngược hẳn bảng mức văn bản: LexFlow tìm đúng *văn bản* sớm nhưng đẩy đúng *điều* lên muộn, vì
nhánh BM25 gần như vô dụng ở mức đó (R@20 = 0.22) nên kéo các điều sai của đúng văn bản lên. Quét
trọng số nhánh thưa trên cả ba bộ câu hỏi (`uv run python eval/quet_trong_so.py`) rồi hạ
`TRONG_SO_THUA` 1.0 → 0.1:

| R@1 | mức điều (TVPL) | mức văn bản (TVPL) | mức văn bản (36 câu) |
|---|---|---|---|
| trọng số 1.0 | 0.15 | 0.51 | 0.72 |
| **trọng số 0.1** | **0.38** | **0.60** | **0.78** |

Ở mức điều, LexFlow từ chỗ thua Naive RAG ở mọi k ≤ 10 thành hơn ở **mọi** k, trong khi ba cột
baseline đứng yên (chúng không phụ thuộc trọng số — đó cũng là phép kiểm nhiễu). Gate hồi quy giữ
nguyên (stale-avoidance 36/36).

**Bộ test của bài báo** — 100 câu SBV-LawGraph, corpus phủ 29 (`eval/bo_sbv.jsonl`, đo 12/08).
Đây là bộ duy nhất hỏi về luật **đang hiệu lực**; ba bộ trên đều hỏi về luật đã chết từ 2024-07.
71 câu còn lại dẫn văn bản corpus không có ⇒ mọi cột ăn 0, nên bảng trên đúng 100 câu của bài báo
chỉ là bảng 29 câu **× 0.29** — con số đó nói về corpus, không nói về truy hồi (`docs/EVAL-IR.md`
§11).

Cách đo, mẫu số và các cảnh báo: `docs/EVAL-IR.md` §6–§7.

## Định dạng corpus

`data/corpus.sample.json`:
```jsonc
{
  "documents": [
    { "doc_id": "TT40-2024", "title": "...", "doc_type": "Thông tư",
      "source": "external", "valid_from": "2024-07-01", "valid_to": null,
      "so_hieu": "40/2024/TT-NHNN",
      "articles": [ { "article": "Điều 12 Khoản 1", "text": "..." } ] }
  ],
  "relationships": [
    { "source_doc": "TT40-2024", "target_doc": "TT39-2014",
      "rel_type": "THAY_THE", "valid_from": "2024-07-01" }
  ]
}
```
`rel_type` thuộc **tập đóng 13 quan hệ** của KG v0.5 §6 — nguồn sự thật duy nhất là
`app/core/schemas.py::REL_TYPES`, và `Relationship` từ chối mọi mã ngoài tập ngay lúc nạp.
Soát dữ liệu có sẵn: `uv run python -m app.ingestion.kiem_quan_he`.

`so_hieu` là trường **bắc cầu**: nguồn chính thống (lược đồ vbpl.vn, dẫn chiếu trong văn bản)
khoá bằng số hiệu, còn corpus khoá bằng `doc_id`. Đầu mút chưa có toàn văn thành **node rỗng**
— xem `app/ingestion/bac_cau.py`.
Thay corpus mẫu bằng 9 văn bản lõi phạm vi thanh toán khi có.
