# Worklog — LexFlow (VAIC 2026, đề SHB)

> Nhật ký công việc hằng ngày, dùng để tổng hợp báo cáo mentor cho giai đoạn 3 sprint (mốc đánh giá tại SHB ~04/09/2026, lộ trình gốc trong `docs/ROADMAP-SPRINT.md`).
>
> **Cách ghi:** mỗi ngày một mục, mới nhất trên cùng. Mỗi mục gồm: việc đã xong (Done), trạng thái deploy (Ship), quyết định quan trọng (Decision), việc kế tiếp (Next). Cuối tuần/cuối sprint chỉ cần gộp các mục lại là thành báo cáo.

---

## 2026-07-28 (T3)

**Giai đoạn:** sau Sprint 2 — hoàn thiện UX + backend kiểm tra tuân thủ.

- **Done:**
  - **Backend kiểm tra tuân thủ `POST /reviews`** (nợ lớn nhất trong DESIGN-GAP): mỗi điều nội bộ → retrieval điều luật trong phạm vi chọn (lọc hiệu lực tại as-of) → Gemini phán định violation/warning/pass kèm trích dẫn hai phía → findings + điểm tuân thủ. 7 test offline. Màn `/review` bỏ dữ liệu minh họa, chọn tài liệu nội bộ thật (4 văn bản SHB), gọi API thật, deep-link căn cứ sang trình xem. **Verify prod:** SHB-QD-VI-2023 ↔ TT40-2024 → bắt đúng 2 mâu thuẫn cài chủ đích (hạn mức 150tr vs Điều 26; nộp tiền mặt vs Điều 25), điểm 33/100.
  - Hạ tầng vận hành: workflow **Supabase keep-alive** (ping mỗi 2 ngày, tự cảnh báo khi project bị pause — đã verify run xanh); nhật ký `docs/WORKLOG.md` + lệnh `/worklog`; quy ước commit tiếng Anh + CLAUDE.md.
  - **Lưu trữ phiên (migration 0005)**: bảng `review_sessions` (sidebar Kiểm tra hiện lịch sử, mở lại qua `?session=`) + cột `scope`/`as_of` trong `chat_messages` (mở lại phiên chat khôi phục đúng chip Phạm vi và mốc "tra tại" theo lượt). Code có fallback khi chưa migrate — **user cần chạy 0005 trong SQL Editor để kích hoạt**.
  - Tích hợp mascot **Lexi** (con cú, 8 trạng thái) từ design handoff v2: avatar động theo vòng đời câu hỏi ở màn Tra cứu (searching → found/conflict), pha "đang đối chiếu" ở màn Kiểm tra (reading), chào ở Landing (greeting), trang lỗi/404 (error), favicon mới.
  - Review handoff phát hiện lỗi (SVG thiếu keyframes) → designer sửa theo kiến trúc "hoạt ảnh trong CSS, SVG tĩnh"; ô lỗi chat có thêm nút **Thử lại**.
  - Chốt **quy ước commit** (`docs/COMMIT-CONVENTION.md`): Conventional Commits, message tiếng Anh; tạo `CLAUDE.md` gốc repo.
- **Ship:** commits `3e73992` → `9480eb3` — Cloud Run rev 00014 + Vercel production, CI xanh.
- **Decision:** không dùng Lexi làm logo sidebar (linh vật ≠ logo, theo designer); greeting đặt ở Landing vì "chỉ chào một lần"; điểm tuân thủ = trung bình (pass=1, warning=0.5, violation=0) theo điều.
- **Next:** user chạy migration 0005; thêm `issuer/issued_date/field` vào schema (gộp vào đợt KB mới); follow-up chips.

## 2026-07-27 (T2)

**Giai đoạn:** kế hoạch mới sau Sprint 2 (3 tính năng chờ KB + redesign).

- **Done:**
  - **Sáng:** schema quan hệ mức Điều (`RelAnchor`), API đọc văn bản (GET /documents, /documents/{id} + cache TTL 60s), trang Thư viện `/docs`, **trình xem toàn văn** `/docs/[docId]` (tab Nội dung + Lược đồ kiểu thuvienphapluat, highlight điều bị sửa đổi/thay thế, banner hết hiệu lực), seed anchors thật (TT23-2019/TT20-2016 → TT39-2014), citation chat deep-link `#dieu-N`, Neo4j lưu anchors trên cạnh.
  - **Chiều:** redesign toàn bộ UI theo design handoff (style giấy ấm + clay + serif Newsreader): 5 màn — Tra cứu (trust bar, mâu thuẫn accordion, trích dẫn superscript, **bộ chọn phạm vi** + as-of), Thư viện 3 cột, Kiểm tra tuân thủ (UI, kết quả minh họa), Auth 2 cột, Landing. Backend thêm `ChatRequest.doc_ids` → retrieval giới hạn trong văn bản chọn (verify trên prod).
  - Viết `docs/DESIGN-GAP.md` — đối chiếu design ↔ hệ thống, xếp ưu tiên việc còn thiếu.
- **Ship:** commits `ba0c5dc` → `0a87627`; Cloud Run rev 00012; Vercel aliased; 50 pytest + lint/build xanh.
- **Decision:** mở rộng app hiện có (không làm FE mới từ đầu); lược đồ theo từng văn bản; "Điều" là đơn vị neo quan hệ (khớp nghiên cứu cấu trúc luật VN của mình).
- **Next:** backend /reviews; migration lưu scope+as_of theo lượt chat; thêm issuer/field vào schema khi làm KB mới.

## 2026-07-24 (T6)

**Giai đoạn:** Sprint 1 + 1.5 + 2 (kế hoạch 4 tuần — làm xong trong 1 ngày).

- **Done:**
  - **Sprint 1 — corpus thật & benchmark:** 15 văn bản / 449 chunk (11 văn bản luật thanh toán–ví điện tử + 4 quy định nội bộ SHB mô phỏng có cài mâu thuẫn chủ đích); extractor tách Điều bằng regex + Gemini metadata; chunking mức Khoản; **benchmark 36 case: stale-avoidance 36/36** (baseline 21/36), phát hiện mâu thuẫn 7/7.
  - **Sprint 1.5 — web production:** deploy Vercel https://lexflow-taupe.vercel.app, CORS đa origin.
  - **Sprint 2 — luồng nghiệp vụ:** upload → duyệt (maker-checker) → re-ingest tự động; trang /admin; graph-augmented retrieval (Neo4j 1-hop vào prompt); lịch sử chat; roadmap hạ tầng 1–9 hoàn tất (auth Supabase JWT, SSE streaming, Langfuse observability, bảng change_events + trang /alerts).
- **Ship:** Cloud Run rev 00004 → 00010; migrations 0001–0004.
- **Decision:** corpus canonical đặt trên Supabase Storage (đè file commit, fail-open khi lỗi); không dùng service-role key — mọi ghi DB qua JWT người dùng.
- **Next:** giai đoạn tính năng chờ KB mới.

## 2026-07-23 (T5)

**Giai đoạn:** dựng hạ tầng production.

- **Done:** chốt kiến trúc (Cloud Run + Supabase + LanceDB Cloud + Neo4j Aura + Gemini — chi tiết `docs/ARCHITECTURE.md`); tạo GCP project `lexflow-shb-2026`; deploy FastAPI đầu tiên lên Cloud Run (asia-southeast1); pipeline ingest chạy với corpus mẫu.
- **Decision:** loại Railway (hết trial), loại Qdrant (corpus nhỏ, LanceDB đủ); máy local yếu → mọi build/deploy đều trên cloud.

---

## Template mục mới (copy khi ghi tay)

```markdown
## YYYY-MM-DD (Thứ)

**Giai đoạn:** ...

- **Done:** ...
- **Ship:** commit ..., deploy ...
- **Decision:** ...
- **Next:** ...
```
