# Kiến trúc production — LexFlow (Hoa Tiêu Pháp Lý)

> Tài liệu chốt tech stack & topology triển khai. Cập nhật lần cuối: 2026-07-23.

## Nguyên tắc chọn stack

1. **Máy local yếu → đẩy tối đa lên cloud.** Local chỉ chạy `next dev`; mọi compute nặng
   (LLM, embedding, ingestion, retrieval) chạy trên cloud services hoặc Cloud Run.
2. **Không đập code đang chạy.** Lõi RAG (FastAPI + LanceDB + Neo4j + Gemini) đã hoạt động
   và có benchmark — chỉ bổ sung phần production còn thiếu, không viết lại retrieval.
3. **Ít service phải tự vận hành nhất có thể.** Ưu tiên managed free tier: Supabase,
   Neo4j Aura, Gemini API, Railway.

## Sơ đồ tổng thể

```text
Máy local (dev UI):   next dev ──────────► API trên Cloud Run
                                                │
Trình duyệt ──► Next.js 16 ──► Supabase Auth (login, session JWT)
                   │  SSE + REST (Bearer JWT)
                   ▼
Cloud Run (asia-southeast1) ┌──────────────────────────┐
                            │ FastAPI (stateless,      │
                            │ scale-to-zero, Dockerfile│
                            │ build qua Cloud Build)   │
                            └──────────────────────────┘
                   │
                   ├──► LanceDB Cloud      — chunks + vectors + BM25 (retrieval)
                   ├──► Supabase Postgres  — users, chat history, audit log, doc workflow
                   ├──► Supabase Storage   — file PDF văn bản gốc
                   ├──► Neo4j Aura         — đồ thị văn bản (THAY_THE/SUA_DOI/…)
                   └──► Gemini API         — chat + embedding (+ Langfuse tracing)
```

## Stack chốt & lý do

| Lớp | Công nghệ | Lý do |
|---|---|---|
| Backend | Python 3.12 · uv · FastAPI | Đã có, chuẩn ngành AI backend |
| LLM + Embedding | Google Gemini (`google-genai`) | Tiếng Việt tốt, rẻ, không cần GPU local |
| Retrieval | **LanceDB** (hybrid vector + BM25, RRF) — nhúng hoặc **LanceDB Cloud** | ~5–10 MB cho corpus 9 văn bản. Có `LANCEDB_URI`+`LANCEDB_API_KEY` → tự chuyển sang Cloud (backend stateless); để trống → nhúng local. Code đã chạy + có benchmark |
| Knowledge Graph | Neo4j Aura free tier | Đúng công cụ cho quan hệ văn bản, managed |
| App DB + Auth + Storage | **Supabase** (Postgres · GoTrue · Storage) | Một service thay ba mảnh: users/audit/chat history, JWT auth có sẵn, lưu PDF gốc |
| Hàng đợi tác vụ | **ARQ + Redis** (tuỳ chọn — compose/local) | Cloud Run không có Redis rẻ → `/ingest` chạy đồng bộ (dev-mode có sẵn); nâng cấp Cloud Run Jobs khi corpus lớn |
| Frontend | Next.js 16 · React 19 · Tailwind v4 · Cytoscape.js | Đã có |
| Deploy | **Google Cloud Run** (asia-southeast1) | Free tier 2M req/tháng, scale-to-zero, build trên Cloud Build (máy local không build Docker); backend stateless nhờ LanceDB Cloud. (Railway bị loại: trial hết hạn) |
| CI | GitHub Actions | ruff + pytest + eslint + next build; benchmark suite làm regression gate |
| Observability | Langfuse (LLM tracing) + structured logging | Trace query → chunks → prompt → citation; bắt buộc với sản phẩm "trả lời sai = rủi ro pháp lý" |

### Các quyết định đã cân nhắc (ADR tóm tắt)

- **Qdrant — chưa dùng.** Corpus quá nhỏ so với sức Qdrant; chuyển sang = viết lại retrieval
  + re-benchmark mà không được gì. Trở thành lựa chọn đúng khi corpus vượt phạm vi thanh toán
  (hàng chục nghìn văn bản) hoặc cần nhiều writer đồng thời. Retrieval gói trong
  `app/knowledge/retrieval.py` nên chi phí chuyển sau này thấp. Đường lui: Qdrant Cloud free 1 GB.
- **pgvector (Supabase) — không thay LanceDB.** Postgres FTS không có config tiếng Việt,
  hybrid search phải tự viết. Ranh giới rõ: Supabase = trạng thái ứng dụng, LanceDB = retrieval.
- **Supabase free tier tự pause sau ~1 tuần idle** → cron ping hàng ngày bằng GitHub Actions;
  cân nhắc nâng Pro giai đoạn sát ngày thi.
- **Auth:** Supabase GoTrue phát JWT; FastAPI chỉ verify (HS256 legacy secret hoặc JWKS
  ES256/RS256) + đọc role từ `app_metadata`. Role: `admin` (duyệt văn bản, ingest) / `staff`.
  Chỗ cắm OIDC/SSO ngân hàng để sau.
- **Ghi Postgres không dùng service-role key:** backend gọi PostgREST bằng chính JWT
  của user → RLS vẫn thực thi, bớt một secret phải quản lý. Đổi lại audit_log cần policy
  INSERT cho user (migration 0002); khi cần audit chống giả mạo tuyệt đối thì nâng cấp
  sang service-role key + thu hồi policy đó.

## Phân vai dữ liệu

| Dữ liệu | Nơi lưu |
|---|---|
| Chunks + vectors + BM25 index | LanceDB (volume Railway) |
| Node/cạnh văn bản pháp lý | Neo4j Aura |
| Users, roles | Supabase Auth + bảng `profiles` |
| Lịch sử hội thoại, citations | Supabase Postgres (`chat_sessions`, `chat_messages`) |
| Audit log (ai hỏi gì, trả lời dựa văn bản nào) | Supabase Postgres (`audit_log`) |
| Workflow duyệt văn bản (painpoint 3) | Supabase Postgres (`legal_documents`) |
| File PDF gốc | Supabase Storage |
| Đăng ký nhận cảnh báo (painpoint 4) | Supabase Postgres (`alert_subscriptions`) |

Migrations SQL nằm ở `supabase/migrations/`, apply bằng SQL Editor trên dashboard Supabase
hoặc `supabase db push`.

## Topology triển khai

- **Cloud Run service `lexflow-api`** (region `asia-southeast1`, gần VN): deploy bằng
  `gcloud run deploy lexflow-api --source .` — Cloud Build build từ `Dockerfile`, máy local
  không cần Docker. Backend **stateless** (LanceDB Cloud giữ vectors) → scale-to-zero an toàn.
  Env vars set qua `--set-env-vars` / Secret Manager.
- **Không có Redis trên Cloud Run** (Memorystore đắt): để trống `REDIS_URL` → `/ingest`
  chạy đồng bộ. Khi corpus lớn, nâng cấp sang **Cloud Run Jobs** cho ingestion.
  ARQ worker + compose vẫn dùng được khi self-host/chạy máy khác.
- **Frontend**: dev chạy local trỏ `NEXT_PUBLIC_API_BASE` về URL Cloud Run; production
  deploy Vercel sau.
- **Dev local không cần Docker**: `uv run uvicorn` + `bun dev`/`npm run dev`; ingestion chạy
  CLI `python -m app.ingestion` (không cần Redis). Docker chỉ dùng cho CI + Cloud Build.

## Biến môi trường

Xem `.env.example`. Nhóm mới so với skeleton ban đầu:

```
SUPABASE_URL=            # https://<ref>.supabase.co
SUPABASE_JWT_SECRET=     # (legacy HS256) — để trống nếu project dùng JWT signing keys
SUPABASE_ANON_KEY=       # cho frontend
REDIS_URL=               # redis://... — để trống ở local dev (ingest chạy đồng bộ)
LANGFUSE_PUBLIC_KEY=     # tracing LLM (tuỳ chọn) — cloud.langfuse.com
LANGFUSE_SECRET_KEY=     # để trống = tắt tracing
```

Không cấu hình Supabase → backend chạy **dev mode**: auth no-op (user giả role admin),
`/ingest` chạy đồng bộ. Đủ để dev/test không cần mạng.

## Lộ trình hạ tầng

1. ✅ Kiến trúc + docs (tài liệu này)
2. ✅ Auth middleware (Supabase JWT) + bảo vệ endpoint admin
3. ✅ ARQ worker + Redis cho ingest; Dockerfile + compose; CI GitHub Actions
4. ✅ Deploy backend lên Google Cloud Run — project GCP `lexflow-shb-2026`, service
   `lexflow-api` (asia-southeast1): https://lexflow-api-209912003726.asia-southeast1.run.app
5. ✅ Supabase project `ytjzskwlpusenodafkvy` + migrations applied; frontend login
   (`@supabase/ssr`, `web/proxy.ts` chặn trang chưa đăng nhập, JWT gắn vào request API)
6. ✅ Lưu chat history + audit log từ `/chat` (`app/core/appdb.py` — PostgREST bằng
   JWT của user, RLS thực thi, không cần service-role key; migration 0002)
7. ✅ SSE streaming: `POST /chat/stream` (meta/citations → delta → conflicts → done);
   web parse SSE thuần qua fetch reader (không cần Vercel AI SDK), câu trả lời hiện dần
8. ✅ Langfuse tracing (`app/core/tracing.py` — no-op khi chưa có key): trace lồng nhau
   answer.build → retrieval.hybrid → gemini.chat → conflict.detect; flush khi app tắt
9. ✅ Change alerts (painpoint 4): ingest phát hiện quan hệ THAY_THE/SUA_DOI →
   ghi `change_events` (migration 0003, idempotent); trang `/alerts` hiện danh sách
   + đăng ký nhận cảnh báo (`alert_subscriptions`). Gửi email thật = nâng cấp sau
   (Resend/SMTP + Cloud Run Jobs định kỳ khi có nguồn crawl văn bản).

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
