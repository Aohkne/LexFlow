# Phân tích Input/Output & Thành phần giao diện — LexFlow (Hoa Tiêu Pháp Lý)

> Phạm vi: hai chức năng lõi — **(A) Chatbot hỏi-đáp luật** và **(B) Kiểm định tuân thủ tài liệu nội bộ ↔ luật hiện hành**.
> Mỗi chức năng phân tích theo 4 lớp: *Input → Xử lý → Output → Thành phần giao diện*, kèm cột **Hiện trạng trong code** vs **Đề xuất bổ sung**.
> Nguồn đối chiếu: `app/core/schemas.py`, `app/api/chat.py`, `app/reasoning/answer.py`, `app/reasoning/conflict.py`, `app/knowledge/retrieval.py`, `app/ingestion/versioning.py`, `web/app/page.tsx`, `web/lib/api.ts`, `docs/SPEC.html`, `docs/ARCHITECTURE.md`. Cập nhật: 2026-07-24.

---

## A. Chatbot hỏi-đáp luật (`mode = qa | checklist`)

### A.1 — Input

| Trường | Kiểu | Nguồn / ràng buộc | Ghi chú |
|---|---|---|---|
| `query` | string | Người dùng nhập (textarea) | Câu hỏi tự nhiên **hoặc** mô tả một luồng nghiệp vụ (khi `mode=checklist`) |
| `mode` | `"qa"` \| `"checklist"` | Toggle UI, mặc định `qa` | `qa` = hỏi–đáp; `checklist` = liệt kê toàn bộ quy định áp dụng cho một luồng |
| `as_of` | ISO date \| null | Date picker "Tại thời điểm" | `null` ⇒ hôm nay. Quyết định điều khoản nào *đang hiệu lực* |
| `top_k` | int (mặc định 6) | Hằng trong FE (chưa expose UI) | Số chunk truy hồi tối đa |
| `session_id` | string \| null | Trả về từ lần chat trước | `null` ⇒ tạo phiên mới; có giá trị ⇒ nối tiếp phiên đã lưu |
| `Authorization` | Bearer JWT | Supabase session (header) | Định danh + role (`admin`/`staff`); dev mode = no-op |

**Đầu vào ngầm (không phải từ người dùng):** vector embedding của `query` (Gemini `gemini-embedding-001`), corpus đã index trong LanceDB, ngày hệ thống `today_iso()`.

### A.2 — Xử lý (tóm tắt luồng)

`hybrid_search` (vector + BM25 → RRF) → **lọc hiệu lực** `is_effective(valid_from, valid_to, superseded, as_of)` → dựng prompt (`_QA_SYSTEM` hoặc `_CHECKLIST_SYSTEM`) → `chat_stream` (Gemini) → song song `detect_conflicts` trên các chunk đã lấy. Toàn bộ được `@observe` trace bằng Langfuse.

### A.3 — Output (SSE streaming: `meta → delta* → conflicts → done`)

| Sự kiện SSE | Payload | Ý nghĩa UX |
|---|---|---|
| `meta` | `{ citations: Citation[] }` | Gửi **trước** để hiện nguồn ngay khi bắt đầu |
| `delta` | `{ text: string }` | Từng mẩu câu trả lời, hiện dần |
| `conflicts` | `{ conflicts: ConflictAlert[] }` | Gửi sau (cần 1 lời gọi LLM riêng) |
| `done` | `{ session_id: string \| null }` | Kết thúc; trả id phiên đã lưu |
| `error` | `{ detail: string }` | Lỗi giữa chừng |

**`Citation`** = `{ doc_id, doc_title, doc_type, article, valid_from, valid_to, snippet(≤280 ký tự) }`
**`ConflictAlert`** = `{ doc_a, doc_b, article_a, article_b, explanation, severity: info|warning|critical }`
**`answer`** (ghép từ `delta`) = văn bản tiếng Việt, có trích dẫn inline dạng `[Thông tư 40/2024 — Điều 12 Khoản 1]`; nếu không đủ căn cứ trả câu "Chưa tìm thấy quy định đang hiệu lực phù hợp…".

### A.4 — Thành phần giao diện

**Hiện có (`web/app/page.tsx`):**

- **Khối điều khiển:** toggle `Hỏi–đáp / Checklist luồng`; date picker *Tại thời điểm*; textarea (gửi bằng ⌘/Ctrl+Enter); nút **Tra cứu** (trạng thái loading "Đang tra cứu…").
- **Chips câu hỏi mẫu** (bấm là hỏi luôn).
- **Error banner** (viền đỏ).
- **Khối cảnh báo mâu thuẫn:** border-trái đổi màu theo `severity` (info=xanh dương / warning=cam / critical=đỏ), nhãn *Thông tin / Cảnh báo / Nghiêm trọng*, dòng `doc_a (article_a) ↔ doc_b (article_b)`.
- **Khối Trả lời:** stream dần, `whitespace-pre-wrap`.
- **Danh sách Nguồn trích dẫn:** mỗi thẻ có badge `doc_type`, `doc_title`, `article` (mono), dải "hiệu lực từ … đến …", `snippet`.

**Đề xuất bổ sung (còn thiếu):**

- **Sidebar lịch sử phiên** — `session_id` đã lưu vào Supabase (`chat_sessions`/`chat_messages`) nhưng UI chưa có danh sách/nạp lại/xóa phiên.
- **Click trích dẫn → mở PDF gốc** (Supabase Storage) và highlight đúng điều/khoản; hiện `snippet` là ngõ cụt.
- **Neo trích dẫn ↔ đoạn trong câu trả lời** (hover `[TT40 — Điều 12]` sáng thẻ nguồn tương ứng).
- **Nút phản hồi** 👍/👎 + lý do → nạp ngược vào eval/benchmark.
- **Hiển thị `as_of` trong kết quả** ("Kết quả tính đến 2026-07-24") + cảnh báo khi tra quá khứ.
- **Trạng thái "không tìm thấy" riêng** (khác câu trả lời thường), gợi ý mở rộng phạm vi.
- **Chế độ dev (Regulation-to-Spec):** SPEC.html nêu nhưng chưa có ở FE — output nên là *yêu cầu kỹ thuật cụ thể* thay vì văn xuôi.
- **Điều khiển `top_k` / hủy request đang stream / retry.**

---

## B. Kiểm định tuân thủ: tài liệu nội bộ ↔ luật hiện hành

> **Quan sát quan trọng:** trong code hiện tại, đây **chưa phải một chức năng độc lập**. Nó tồn tại dưới dạng `detect_conflicts()` chạy *ngầm bên trong luồng chat*, chỉ so khớp các chunk tình cờ cùng lọt vào `top_k` của một câu hỏi. Chưa có màn hình "chọn một tài liệu nội bộ → quét toàn bộ luật liên quan → xuất báo cáo tuân thủ". Phần dưới tách rõ **hiện trạng** và **thiết kế đích đề xuất**.

### B.1 — Hiện trạng (Conflict Detector nhúng trong chat)

**Input:** `chunks: list[dict]` — kết quả `hybrid_search` (lẫn `source=internal` và `source=external`). Điều kiện chạy: phải có **≥ 2 `doc_id` khác nhau**, nếu không trả `[]`.
**Xử lý:** liệt kê chunk kèm `nguồn=internal|external` → `chat_json` với `_SYSTEM` ("chỉ báo mâu thuẫn thực sự, không suy diễn") → JSON `{conflicts:[{id_a,id_b,explanation,severity}]}` → ánh xạ về `ConflictAlert`.
**Output:** `list[ConflictAlert]` (hiển thị ở khối cảnh báo mục A.4).
**Giới hạn:** (1) chỉ so trong phạm vi vài chunk của 1 câu hỏi, không quét toàn văn bản nội bộ; (2) ưu tiên internal↔external chỉ bằng *lời nhắc prompt*, không ép ràng buộc; (3) không có điểm tuân thủ, không đề xuất sửa, không xuất báo cáo, không lưu vết finding.

### B.2 — Thiết kế đích đề xuất (chức năng "Kiểm định tuân thủ" đúng nghĩa)

**Input:**

| Trường | Kiểu | Nguồn | Ghi chú |
|---|---|---|---|
| `internal_doc_id` **hoặc** file upload | string / file (PDF, docx) | Chọn từ tài liệu nội bộ đã ingest, hoặc tải lên → parse → chunk tạm | Đối tượng cần kiểm định |
| `scope` | enum/filter | UI | Phạm vi luật đối chiếu: *toàn bộ external đang hiệu lực* / lọc theo `doc_type` / theo chủ đề (vd. thanh toán) |
| `as_of` | ISO date | Date picker | Kiểm định "tại thời điểm" nào |
| `min_severity` | enum | UI | Ngưỡng báo (info/warning/critical) |
| `use_graph` | bool | UI | Có mở rộng qua knowledge graph (dẫn chiếu/hướng dẫn) không |

**Xử lý (đề xuất):** với **từng điều khoản nội bộ** → truy hồi điều luật liên quan (hybrid + graph) → so khớp có cấu trúc theo *loại xung đột* (hạn mức số, điều kiện, cho phép/cấm, thời hiệu) → tổng hợp finding + tính điểm.

**Output — Báo cáo kiểm định:**

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `findings[]` | list | Mỗi mục: `{ internal_article, external_article, conflict_type, severity, explanation, suggested_fix }` |
| `coverage[]` | list | Trạng thái mỗi điều nội bộ: *tuân thủ / mâu thuẫn / thiếu quy định đối chiếu / cần rà tay* |
| `compliance_score` | số/tỷ lệ | Điểm tuân thủ tổng thể + phân rã theo severity |
| `as_of`, `scope`, `checked_at`, `by_user` | metadata | Phục vụ audit/giải trình |
| `export` | PDF/xlsx | Báo cáo tải về cho pháp chế/thanh tra |

**Thành phần giao diện (đề xuất):**

- **Bộ chọn tài liệu nội bộ** (dropdown/tìm kiếm) **hoặc vùng kéo-thả upload**.
- **Thanh bộ lọc phạm vi + `as_of` + ngưỡng severity.**
- **Thẻ tóm tắt:** tổng số điều, số mâu thuẫn theo từng mức, `compliance_score` (vòng tròn/thanh tiến độ).
- **Bảng findings:** badge severity, hai cột *Điều khoản nội bộ ↔ Điều luật đối chiếu*, `explanation`, cột *đề xuất sửa*, nút "tạo cảnh báo/subscription".
- **Xem đối chiếu side-by-side / diff** giữa điều nội bộ và điều luật.
- **Nút xuất báo cáo PDF** + nút "gửi cho pháp chế".
- **Trạng thái tiến trình** khi quét văn bản dài (progress + hủy).

---

## C. Brainstorm — những khía cạnh nên phân tích thêm (phần bạn có thể còn thiếu)

Ngoài I/O + UI của hai chức năng trên, để bản đặc tả đủ dùng cho thiết kế và cho vòng thi, nên phân tích thêm các nhóm sau:

**1. Trạng thái biên & lỗi (empty / error states).** Retrieval rỗng, LLM lỗi/timeout, JSON conflict sai định dạng, Neo4j tắt (đồ thị "tạm nghỉ"), Supabase pause sau ~1 tuần idle, câu hỏi ngoài phạm vi corpus. Mỗi trạng thái cần I/O và UI riêng.

**2. UX streaming.** Hủy request đang chạy, hiển thị partial answer khi mất kết nối, timeout, chống double-submit, cuộn theo dòng đang stream.

**3. Truy vết nguồn (provenance).** Click citation → mở đúng trang PDF gốc trong Supabase Storage + highlight; đảm bảo mọi con số/hạn mức trong `answer` đều dẫn được về `article`.

**4. Phân quyền theo role.** `admin` vs `staff` thay đổi gì ở I/O và UI (ai được ingest/duyệt văn bản, ai chỉ tra cứu); ẩn/hiện màn hình admin & alerts.

**5. Lịch sử hội thoại & giải trình.** Sidebar phiên, nạp lại `session_id`, xóa; và **màn hình audit log** (ai hỏi gì, trả lời dựa văn bản nào) phục vụ thanh tra NHNN — dữ liệu đã có ở `audit_log` nhưng chưa có UI.

**6. Versioning UX.** Chọn `as_of`; hiển thị rõ khi một văn bản *đã hết hiệu lực* / *bị thay thế một phần (partial supersession)*; so sánh hai phiên bản của cùng một điều; timeline hiệu lực.

**7. Knowledge graph tương tác (painpoint 2).** I/O của `/graph` (`GraphNode`/`GraphEdge`), click node → xem văn bản, lọc theo `rel_type` (THAY_THE/SUA_DOI/HUONG_DAN/DAN_CHIEU), tô màu theo tình trạng hiệu lực, layout khi corpus lớn.

**8. Cảnh báo thay đổi quy định (painpoint 4).** Trang `/alerts` + `alert_subscriptions`: form đăng ký, chọn kênh (email/Slack — hiện chưa gửi thật), map "luồng nghiệp vụ đang vận hành ↔ văn bản" để biết luồng nào bị ảnh hưởng; I/O của `change_events`.

**9. Admin / ingest & kiểm duyệt đầu vào (painpoint 3).** Form nhập metadata (`doc_id, title, doc_type, source, valid_from/to`), validation trùng/thay thế văn bản đang có, preview trước khi index, workflow duyệt (`legal_documents`), xử lý file scan/ảnh (cần OCR).

**10. Độ tin cậy & an toàn nội dung.** Hiển thị mức tin cậy / cảnh báo "không đủ căn cứ"; chống hallucination (chỉ trả lời từ chunk cung cấp); **chống prompt injection** từ nội dung tài liệu; xử lý khi hai nguồn mâu thuẫn thì *không tự chọn liều*.

**11. Chuẩn hóa dữ liệu pháp lý.** Cách hiển thị/so khớp hạn mức (số tiền, đơn vị, "triệu/tháng"), ngày tháng, tham chiếu chéo Điều–Khoản–Điểm; chuẩn tên văn bản.

**12. Đo lường & eval gắn vào UI.** Nút feedback trên câu trả lời → feed vào `eval/questions.jsonl` + benchmark (painpoint 5); log độ chính xác trích dẫn / tỷ lệ tránh văn bản hết hiệu lực / tỷ lệ phát hiện mâu thuẫn.

**13. Hiệu năng, chi phí, tải.** Thời gian phản hồi mục tiêu, giới hạn `top_k`, chi phí token Gemini mỗi truy vấn (nhất là conflict cần gọi LLM riêng), scale-to-zero Cloud Run (cold start).

**14. Bảo mật & quyền riêng tư.** Tài liệu nội bộ nhạy cảm: RLS Supabase, không rò rỉ chunk giữa các user/tổ chức, audit chống giả mạo (nâng service-role key khi cần).

**15. Phi chức năng UI.** Responsive/mobile, accessibility (bàn phím, tương phản), i18n (thuật ngữ pháp lý), dark mode, in báo cáo.

---

### Ưu tiên đề xuất
Nếu chọn 3 việc tác động lớn nhất cho vòng thi: (1) **tách "Kiểm định tuân thủ" thành chức năng riêng** với báo cáo + điểm tuân thủ (mục B.2) — đây là điểm bạn hỏi và đang là khoảng trống lớn nhất; (2) **click trích dẫn → PDF gốc + màn hình audit** (niềm tin của ngân hàng); (3) **feedback UI nối vào benchmark** (chứng minh giá trị kiến trúc, painpoint 5).
