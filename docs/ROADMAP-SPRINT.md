# LexFlow — Lộ trình 6 tuần / 3 sprint (đến kỳ đánh giá tại SHB, ~04/09/2026)

## Context

Hạ tầng roadmap 1–9 đã xong (Cloud Run, Supabase auth + history + audit, LanceDB Cloud, Neo4j, SSE, Langfuse, change alerts, CI). Giai đoạn tiếp theo: biến khung hạ tầng thành sản phẩm **được đánh giá thực tế tại doanh nghiệp** — 1 người làm, trọng tâm cả 3 trục: (a) chất lượng RAG + corpus thật, (b) tính năng sản phẩm, (c) demo + số liệu thuyết phục.

Khoảng trống lớn nhất hiện tại (đã khảo sát):
- Corpus chỉ là 5 văn bản minh hoạ; **chưa có parser PDF** (pypdf/bs4 trong deps nhưng không dùng; `DATA_RAW_PATH` bỏ trống)
- Eval chỉ **4 case**, in stdout, không lưu kết quả, chưa LLM-judge
- Bảng `legal_documents` (workflow duyệt) + Storage bucket `legal-docs` **chưa có code nào dùng**
- `related_docs()` (graph 1-hop) tồn tại nhưng **answer.py không gọi** — graph chưa tham gia reasoning
- Chưa có UI lịch sử chat, chưa có admin dashboard, frontend chưa deploy (chỉ `next dev` local)

## Quyết định kỹ thuật chốt

1. **Extract PDF bán tự động**: pypdf → regex tách "Điều N" → Gemini structured output ép về schema `CorpusDocument` có sẵn → **người duyệt JSON trước khi ingest**. Không viết parser thuần (hố đen thời gian); bước duyệt tay = câu chuyện maker-checker cho ngân hàng.
2. **Corpus thật trước (Sprint 1, CLI), admin workflow sau (Sprint 2, bọc UI)** — mọi thứ khác phụ thuộc dữ liệu thật.
3. **Eval 30–40 case** là đủ thuyết phục; LLM-judge bằng Gemini để Sprint 3.
4. **Graph-augmented retrieval làm ở Sprint 2** (1-hop, có cờ tắt, đo delta bằng eval) — điểm phân biệt "RAG + KG" của đề, hiện graph chỉ để vẽ.
5. **Vercel deploy cuối Sprint 1** — để người SHB dùng thử sớm 3–4 tuần trước đánh giá.
6. **Không làm incremental ingest**: corpus <50 văn bản → re-ingest full khi approve (LanceDB `mode="overwrite"` giữ nguyên).

---

## Sprint 1 (tuần 1–2): Corpus thật + Eval có số liệu + lên mạng

**Mục tiêu:** LexFlow trả lời đúng từ ≥10 văn bản pháp luật thanh toán THẬT + 3–5 quy định nội bộ mô phỏng (có cài mâu thuẫn chủ đích), benchmark ≥30 case lưu file, chạy trên URL Vercel.

| # | Hạng mục | Files | Cỡ |
|---|---|---|---|
| 1 | Chọn ~10–12 văn bản external (NĐ 52/2024, TT 40/2024, TT 15/17/18-2024, + TT 39/2014, TT 46/2014 đã hết hiệu lực để nuôi versioning/stale) + 3–5 quy định nội bộ mô phỏng; tải về `data/raw/` (ưu tiên bản DOC/HTML từ thuvienphapluat — sạch hơn PDF) | `data/raw/*`, danh mục trong `docs/` | S |
| 2 | **Extractor bán tự động** `app/ingestion/extract.py`: pypdf → regex Điều → Gemini structured output → `data/corpus.real.json`; CLI `python -m app.ingestion.extract <file>`; quan hệ THAY_THE/SUA_DOI gán tay trong JSON | mới `app/ingestion/extract.py`; dùng `data_raw_path` trong config | **L** |
| 3 | Duyệt tay JSON → ingest thật → tinh chỉnh chunking (tách mức Khoản nếu Điều dài) trong `build_chunks`; kiểm as_of/conflict/citation trên dữ liệu thật | `app/ingestion/pipeline.py`, `data/corpus.real.json` | M |
| 4 | Eval 30–40 case (sinh nháp bằng Gemini, duyệt tay; đủ nhóm: tra cứu / hiệu lực thời điểm / mâu thuẫn) + lưu kết quả `eval/results/<date>.json` | `eval/questions.jsonl`, `eval/run_benchmark.py` | M |
| 5 | Deploy web lên Vercel (env trỏ Cloud Run + Supabase; sửa CORS `app/main.py` thêm origin Vercel; test SSE) | cấu hình Vercel, `app/main.py` | S |
| 6 | [cắt được] Eval smoke 5 case trong CI, fail nếu citation_accuracy tụt | `.github/workflows/ci.yml` | S |

**DoD:** Trên Vercel đăng nhập hỏi 10 câu nghiệp vụ thật → trích dẫn đúng điều/khoản; ≥2 mâu thuẫn nội bộ-vs-luật phát hiện tự động; `eval/results/` có bảng baseline vs LexFlow ≥30 case.

**Rủi ro:** PDF bẩn/scan → dùng bản text thuvienphapluat, Gemini chịu lỗi tốt; kẹt thì hạ còn 8 văn bản. Viết case eval lâu → Gemini sinh nháp, người duyệt.

---

## Sprint 2 (tuần 3–4): Luồng quản trị văn bản end-to-end + Graph vào reasoning

**Mục tiêu:** Demo luồng khép kín trên UI: admin upload PDF → extract → duyệt JSON → ingest → văn bản mới xuất hiện trong câu trả lời + change alert; câu trả lời tăng cường bằng graph (đo delta bằng eval).

| # | Hạng mục | Files | Cỡ |
|---|---|---|---|
| 1 | **API quản lý văn bản**: upload PDF → Storage `legal-docs` + row `legal_documents` (pending); extract (sync trước, arq nếu queue bật); approve/reject → cập nhật status + `reviewed_by` + audit; approve merge JSON vào corpus canonical → re-ingest full | `app/api/admin.py` (hoặc `documents.py` mới), `app/core/appdb.py`, `app/worker.py` | **L** |
| 2 | **Admin dashboard** `web/app/admin/`: danh sách theo status, upload, xem/sửa JSON extract (textarea đủ), nút approve→ingest; ẩn menu với staff | mới `web/app/admin/*`; `web/lib/api.ts`, layout | M/L |
| 3 | **Graph-augmented retrieval**: trong `_prepare()` gọi `related_docs()` 1-hop → thêm 2–3 chunks từ văn bản liên quan (vẫn lọc as_of) kèm nhãn quan hệ; cờ config bật/tắt; benchmark thêm cột graph-ON/OFF | `app/reasoning/answer.py`, `app/knowledge/graph.py`, `eval/run_benchmark.py` | M |
| 4 | **UI lịch sử chat**: sidebar phiên đọc `chat_sessions`/`chat_messages` qua Supabase client (RLS sẵn), click mở lại phiên | `web/app/page.tsx` | M |
| 5 | [cắt được] Graph UI: click node hiện chi tiết + change events; filter loại quan hệ | `web/app/graph/page.tsx`, `app/api/graph.py` | S/M |
| 6 | [cắt được] Audit viewer trong admin (nếu cắt → dồn Sprint 3, không bỏ) | `web/app/admin/*` | S |

**DoD:** Trên Vercel: upload 1 thông tư mới → duyệt → ingest → chat trích dẫn được văn bản mới + change alert hiện trong feed; benchmark có cột graph-ON với delta rõ. Mời 1–2 người dùng thử cuối sprint.

**Rủi ro:** Hạng mục 1 phình to → làm sync, bỏ arq; extract chạy CLI local rồi upload JSON qua UI vẫn "liền" về demo. Graph augmentation gây nhiễu → giới hạn 2–3 chunk, cờ tắt, eval làm lưới an toàn.

---

## Sprint 3 (tuần 5–6): Chất lượng đo được + tuân thủ + đóng gói đánh giá

**Mục tiêu:** Buổi đánh giá tại SHB chạy trơn: 3 kịch bản demo cloud, báo cáo benchmark hoàn chỉnh (kèm LLM-judge), ≥2 người pilot có phản hồi được xử lý.

| # | Hạng mục | Files | Cỡ |
|---|---|---|---|
| 1 | **Mời pilot NGAY đầu tuần 5**: seed tài khoản, gửi URL + 5 câu gợi ý cho mentor/nhân viên SHB | — | S |
| 2 | **LLM-judge Gemini**: groundedness / citation correctness / completeness cho từng câu trả lời benchmark, kết quả vào `eval/results/` | `eval/judge.py` mới, `eval/run_benchmark.py` | M |
| 3 | **Buffer 3–4 ngày sửa lỗi từ phản hồi pilot** — không lấp bằng feature mới | — | M |
| 4 | Câu chuyện tuân thủ: audit viewer (nếu S2 cắt), rà phân quyền admin/staff mọi endpoint + trang, trang "Nguồn dữ liệu" liệt kê văn bản + hiệu lực | `web/app/admin/*`, `app/api/*` | S/M |
| 5 | **Đóng gói**: kịch bản demo 3 màn (tra cứu + as_of / mâu thuẫn / upload→duyệt→alert), one-pager số liệu (baseline vs LexFlow vs graph-ON + judge + quy mô corpus), slide; tổng duyệt cloud ≥2 lần | `docs/` | M |
| 6 | [cắt được] Email alerts qua Resend (free 100 mail/ngày) khi có change_event mới | `app/core/appdb.py`, ingest flow | S |
| 7 | [cắt được] Partial supersession điều→điều — CHỈ nếu corpus thật có case "sửa đổi một số điều" gây trả lời sai | `app/ingestion/versioning.py`, `schemas.py` | M |

**DoD:** Tổng duyệt demo cloud không lỗi 2 lần liên tiếp; one-pager benchmark 3 cột + điểm judge; ≥2 người ngoài dùng thử, phản hồi đã sửa hoặc ghi nhận; mọi hành vi truy vết được qua audit log.

**Rủi ro:** Pilot không phản hồi → mời từ cuối S2, nhắc đầu tuần 5, tự đóng vai chấm 20 câu nếu cần; demo live rớt mạng → video backup từng kịch bản + tài khoản dự phòng.

---

## Nguyên tắc cắt khi thiếu giờ (hy sinh theo thứ tự)

Resend email → partial supersession → graph UI nâng cấp → eval trong CI → audit viewer (hoãn, không bỏ) → lịch sử chat.

**Không được cắt:** corpus thật · eval ≥30 case lưu kết quả · Vercel · luồng upload→duyệt→ingest · graph-augmented retrieval.

## Verification tổng thể

- Cuối mỗi sprint chạy: `uv run pytest`, `uv run ruff check .`, `npm run build` (web), `uv run python eval/run_benchmark.py` → so `eval/results/` với lần trước
- Sau mỗi deploy: `/health` + 1 câu hỏi e2e qua `/chat/stream` với token thật, kiểm tra rows mới trong `chat_messages` + trace Langfuse
- Việc cần user tự làm (không code): cấp `app_metadata.role=admin` cho tài khoản của mình; tạo project Vercel + Resend (nếu làm email); GitHub Actions cron ping Supabase trước tuần đánh giá
