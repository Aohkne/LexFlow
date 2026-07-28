# DESIGN-GAP — Đối chiếu design handoff ↔ hiện trạng sau khi triển khai

> Ngày: 27/07/2026 · Nguồn design: `design/` (5 màn, style 1a Anthropic — giấy ấm + clay + Newsreader).
> Trạng thái: **cả 5 màn đã triển khai** trên nền app hiện có (token mới trong `globals.css`, AppSidebar dùng chung, route group `(app)`).
> File này liệt kê những gì design cần mà hệ thống **còn thiếu**, và những gì hệ thống **có thêm** ngoài design (đã giữ lại), để bạn quyết định bước tiếp theo.

## 1. THIẾU — design yêu cầu nhưng backend/dữ liệu chưa có

### Chặn tính năng chính (nên ưu tiên)

| # | Hạng mục | Hiện trạng | Việc cần làm |
|---|---|---|---|
| 1 | **Backend Kiểm tra tuân thủ** (`POST /reviews`) — màn 5 | UI `/review` đã đủ (config 3 bước + score strip + findings accordion) nhưng phần kết quả là **dữ liệu minh họa**, có ghi chú ngay trên UI | Xây service: mỗi điều nội bộ → retrieval điều luật liên quan → so khớp → findings + compliance score. Trùng với đề xuất B.2 trong `docs/PHAN-TICH-IO-UI.md` — khoảng trống giá trị nhất |
| 2 | **Lưu phạm vi + as-of theo từng lượt chat** | `doc_ids` + `as_of` đã gửi lên backend và giới hạn retrieval đúng, nhưng **không lưu vào `chat_messages`** → mở lại phiên cũ, chip "Phạm vi" hiển thị mặc định | Thêm cột `scope jsonb` + `as_of date` vào `chat_messages` (migration) + ghi trong `save_chat_turn` — README design yêu cầu rõ để phục vụ audit |
| 3 | **Câu hỏi gợi ý tiếp theo (follow-up chips)** | Backend không sinh followups → không render | Thêm 1 lời gọi LLM phụ (hoặc gộp vào prompt chính, trả JSON) → SSE event `followups` |
| 4 | **Trường dữ liệu văn bản còn thiếu**: cơ quan ban hành, ngày ban hành, lĩnh vực (Thanh toán / KYC / An toàn) | FE đang **suy đoán** cơ quan từ loại văn bản; preset lĩnh vực thay bằng preset theo nguồn (Pháp luật/Nội bộ); facet "Lĩnh vực" ở Thư viện thay bằng "Nguồn" | Khi làm KB mới: thêm `issuer`, `issued_date`, `field` vào `DocumentMeta` (đều optional — không vỡ corpus cũ). Khớp với nghiên cứu cấu trúc luật của bạn (số hiệu tự mã hóa cơ quan ban hành) |
| 5 | **Danh sách phiên kiểm tra gần đây** (sidebar màn 5) | Placeholder "chưa có phiên nào" | Cần bảng `review_sessions` khi làm #1 |

### Nhỏ hơn / quyết định sau

| # | Hạng mục | Ghi chú |
|---|---|---|
| 6 | SSO Google (màn Auth) | Supabase chưa cấu hình OAuth provider — nút bị lược bỏ. Bật trong Supabase Dashboard nếu cần |
| 7 | Quên mật khẩu | Hiện chỉ hiện text "liên hệ quản trị". Supabase có sẵn reset-by-email nếu muốn làm |
| 8 | Password policy ≥10 ký tự chữ+số (design hint) | Supabase đang enforce ≥6. Chỉnh trong Auth settings + sửa `minLength` |
| 9 | Upload tài liệu ở màn Kiểm tra (bước 1) | Card hiện tĩnh (trỏ file demo SHB-QD-VINHANH-2026). Nối với luồng upload thật khi làm #1 |
| 10 | Nút "Xuất báo cáo", "Chia sẻ", "Gán người xử lý", "Bỏ qua có lý do" (findings) | Chưa render vì chưa có backend — thêm cùng #1 |
| 11 | "Xem toàn văn điều khoản" mở inline trong card nguồn | Thay bằng link **"Mở toàn văn điều khoản ↗"** sang trình xem `/docs/[id]#dieu-N` — mạnh hơn design (deep-link + highlight); nếu vẫn muốn expand inline thì cần API trả full text điều trong citation |
| 12 | Citation marker | Backend trả dạng ngoặc `[Văn bản — Điều X]`; FE parse → nút superscript ¹ ². Bracket không khớp được citation nào thì giữ nguyên chữ. Muốn 100% chuẩn cần backend trả marker có cấu trúc (vd `⟦1⟧`) |
| 13 | Responsive mobile | Design chỉ vẽ desktop ≥1180px (README tự ghi nhận). Đã làm: detail panel Thư viện ẩn dưới `xl`, panel tối Auth ẩn dưới `lg`, grid Landing co giãn. Chưa tối ưu: sidebar không có drawer mobile |
| 14 | Số liệu Stats trên Landing | Design ghi 42.000+ điều khoản / 1.200+ mâu thuẫn (số minh họa) — **đã thay bằng số thật**: 449+ chunks, 100% trích dẫn, benchmark 36/36 & 7/7. Tránh claim sai trước hội đồng |
| 15 | "Đặt lịch demo" (CTA Landing) | Trỏ về `/login` — không có hệ thống đặt lịch |

## 2. THỪA — app có nhưng design không đề cập (đã GIỮ LẠI)

| # | Tính năng | Xử lý trong redesign |
|---|---|---|
| 1 | **Chế độ Checklist luồng** (`mode=qa\|checklist`) | Giữ dạng segment nhỏ cạnh ô "Hiệu lực tại" trong composer. Nếu designer muốn bỏ thì xóa segment là xong |
| 2 | **Trang Quản trị `/admin`** (upload → duyệt JSON → ingest, maker-checker) | Giữ nguyên chức năng, thêm nav item "Quản trị văn bản" (chỉ admin thấy) — design không có màn này |
| 3 | **Trang Cảnh báo `/alerts`** (change events + đăng ký) | Design chỉ có badge số trên nav "Cảnh báo" (badge giờ đếm thật từ `change_events`); trang giữ nguyên style cũ đã áp token mới |
| 4 | **Đồ thị tri thức `/graph`** (Cytoscape) | Design có nav item nhưng không có màn thiết kế riêng — giữ nguyên |
| 5 | **Trình xem toàn văn `/docs/[docId]`** (tab Nội dung + Lược đồ, highlight điều bị sửa đổi, banner hết hiệu lực) | Design màn Thư viện chỉ có detail panel + mục lục. Viewer là tính năng vừa ship 27/07 — panel phải có nút "Toàn văn ↗" dẫn sang; citation chat cũng deep-link vào đây |
| 6 | **Lịch sử phiên chat** đọc từ Supabase | Design vẽ 4 hội thoại mẫu; app load thật (15 phiên gần nhất), click mở lại phiên qua `/?session=<id>` |

## 3. Khác biệt triển khai có chủ đích (deviation)

- **Sidebar hợp nhất**: design vẽ sidebar hơi khác nhau ở mỗi màn (Gần đây / Facet / Phiên kiểm tra). Triển khai bằng MỘT component `AppSidebar` + slot `extra` theo màn — đồng bộ nav/account, ít code trùng.
- **Nav đầy đủ hơn design**: thêm "Thư viện văn bản" và "Kiểm tra tài liệu" vào nav mọi màn (design màn 3 chỉ vẽ 3 mục).
- **"Tra cứu mới" / "Phiên kiểm tra mới"** là Link điều hướng (reset qua route) thay vì reset state tại chỗ.
- **Popover phạm vi**: đã bổ sung Esc + click-ra-ngoài để đóng (README design ghi chú "nên bổ sung khi code thật").
- **Route Landing**: đặt tại `/landing` (public, đã mở trong `proxy.ts`); `/` vẫn là màn Tra cứu sau đăng nhập. Nếu muốn `/` là landing cho khách vãng lai thì đổi logic redirect trong proxy.

## 4. Việc backend đã làm thêm trong đợt này (phục vụ design)

- `ChatRequest.doc_ids: list[str]` — giới hạn retrieval trong văn bản được chọn (`search_in_docs`), nối với scope picker. Có test (`tests/test_stream.py::test_doc_ids_gioi_han_pham_vi`).
- Badge Cảnh báo trên sidebar đếm số `change_events` thật.

## 4b. Lexi — mascot trợ thủ (bổ sung 28/07)

Handoff v2 tại `design/Lexi/` đã tích hợp: component `web/components/lexi.tsx` + `lexi.css` (hoạt ảnh nằm trong CSS, SVG public/ là bản tĩnh có chủ ý), favicon `app/icon.svg`.

Vị trí đã gắn (quy tắc: một Lexi động/màn): Tra cứu (empty state `searching` 66px trong khung 96px; avatar 30px cạnh câu trả lời — lượt mới nhất động `found`/`conflict`, lượt cũ tĩnh; ô lỗi `error` + nút Thử lại), `/review` (idle → searching giả lập ~1.4s → conflict/found cạnh tiêu đề kết quả), Landing hero (`idle` 72px) + avatar preview tĩnh, mini-card Auth (tĩnh 22px), Thư viện không có kết quả (`idle` 44px), trang 404 `not-found.tsx` (`error` 66px). **Không** dùng Lexi làm logo sidebar (chỉ định của designer — linh vật ≠ logo).

Cập nhật 28/07 chiều: designer bổ sung `greeting` (nhún + vẫy cánh — dùng ở hero Landing 80px; theo chỉ định "chỉ chào một lần" nên KHÔNG đặt trong màn Tra cứu hằng ngày) và `reading` (đọc sách, mắt rà dòng `steps(1)` — thay searching ở pha chạy /review, cho tác vụ hàng chục giây; không dùng dưới 40px). Backlog Lexi: hết.

## 5. Đề xuất thứ tự làm tiếp

1. **Backend Kiểm tra tuân thủ** (#1 — biến màn 5 thành thật; giá trị demo lớn nhất cho SHB)
2. **Migration lưu scope + as-of theo lượt** (#2 — câu chuyện audit, rẻ)
3. **Thêm `issuer/issued_date/field` vào schema** (#4 — gộp vào đợt KB mới đang chuẩn bị)
4. Follow-up chips (#3) và các mục nhỏ còn lại theo nhu cầu demo
