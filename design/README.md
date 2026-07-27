# Handoff: LexFlow / Hoa Tiêu Pháp Lý — 5 màn hình web

## Overview
Bộ thiết kế cho sản phẩm **Hoa Tiêu Pháp Lý (LexFlow)** — trợ lý tra cứu pháp luật cho khối Pháp chế & Tuân thủ ngân hàng. Câu trả lời luôn gắn trích dẫn tới đúng điều/khoản **đang hiệu lực**, có cảnh báo mâu thuẫn giữa các văn bản, tra cứu theo mốc thời gian, và kiểm tra tài liệu nội bộ so với văn bản pháp luật.

5 màn hình trong bundle:

| # | Màn hình | File thiết kế | Route đề xuất trong `web/` |
|---|---|---|---|
| 1 | Landing (marketing) | `designs/LexFlow Landing.dc.html` | `app/(marketing)/page.tsx` hoặc trang riêng |
| 2 | Đăng nhập / Đăng ký | `designs/LexFlow Auth.dc.html` | `app/login/page.tsx` |
| 3 | Tra cứu (chatbot hỏi đáp) | `designs/LexFlow Anthropic.dc.html` | `app/page.tsx` |
| 4 | Thư viện văn bản | `designs/LexFlow Thu Vien.dc.html` | `app/docs/page.tsx` + `app/docs/[docId]` |
| 5 | Kiểm tra tài liệu (tuân thủ) | `designs/LexFlow Kiem Tra.dc.html` | route mới, ví dụ `app/review/page.tsx` |

`designs/LexFlow Styles.dc.html` là bảng so sánh 5 hướng style ban đầu — **chỉ tham khảo**, hướng được chọn là `1a` (Anthropic: giấy ấm + clay + serif editorial). Không implement file này.

## About the Design Files
Các file trong `designs/` là **thiết kế tham chiếu viết bằng HTML** — prototype thể hiện bố cục, màu, chữ và hành vi mong muốn. **Không phải production code để copy trực tiếp.** Chúng dùng một runtime nội bộ (`support.js`, thẻ `<x-dc>`, `<sc-for>`, `<sc-if>`, `{{ hole }}`) không tồn tại trong codebase thật.

Nhiệm vụ: **tái tạo các thiết kế này trong codebase hiện có** — `LexFlow/web` (Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4, Supabase, cytoscape), theo pattern sẵn có của repo. Mở file HTML trực tiếp trong browser để xem và bấm thử trước khi code.

Cách đọc file thiết kế:
- Phần giữa `<x-dc>` … `</x-dc>` = markup + style (toàn bộ style là **inline**).
- Phần trong `<script type="text/x-dc">` = state, data mẫu, handler, và các hàm sinh style theo trạng thái (`pill()`, `seg()`, `chip()`, `facetBtn()` …). Chuyển các hàm này thành Tailwind class hoặc `clsx` variants.
- `<sc-for list as>` = `.map()`, `<sc-if value>` = conditional render.

## Fidelity
**High-fidelity (hifi).** Màu, typography, spacing, radius, hover state đều là giá trị cuối. Hãy tái tạo pixel-perfect bằng Tailwind + token của repo, không "diễn giải lại" bố cục.

⚠ **Quan trọng — token trong repo hiện đang lệch so với thiết kế.** `web/app/globals.css` đang dùng bảng màu cũ (`--background:#fbfaf7`, `--accent:#b85c3a`, `--border:#ddd8cb`). Thiết kế chốt dùng bảng màu ở mục **Design Tokens** dưới đây (`#F0EEE6`, `#CC785C`, `#E4DFD2`…). Bước đầu tiên nên là **cập nhật `globals.css` sang bộ token mới**, rồi build UI trên token đó — không hardcode hex trong component.

Font: thiết kế dùng **Newsreader** (serif, Google Fonts) cho tiêu đề/câu trả lời/trích dẫn, **system-ui** cho UI, và **ui-monospace** cho metadata. Repo hiện dùng `--font-geist-sans/mono`; cần thêm Newsreader qua `next/font/google` và giữ system-ui cho sans (hoặc giữ Geist Sans nếu team muốn — nhưng serif Newsreader là bắt buộc, nó là đặc trưng của style).

---

## Design Tokens

### Màu (light — dùng cho tất cả màn hình)
| Token | Hex | Dùng ở đâu |
|---|---|---|
| `--background` | `#F0EEE6` | nền trang, nền cột nội dung |
| `--panel` | `#FAF9F5` | card, composer, panel phải, header |
| `--sidebar` | `#F5F2EA` | nền sidebar trái |
| `--inset` | `#F0EBE0` | nút ghost, badge nhạt |
| `--inset-strong` | `#EAE4D6` | segment control track, nav item active, badge loại VB |
| `--border` | `#E4DFD2` | viền chuẩn |
| `--border-soft` | `#EDE8DC` | viền chia trong panel |
| `--border-hover` | `#D8C4A8` | viền khi hover card |
| `--foreground` | `#191919` | chữ chính |
| `--fg-body` | `#26241F` | thân câu trả lời |
| `--fg-strong` | `#33302A` | chữ đậm phụ, trích dẫn |
| `--dim` | `#6E6A5E` | chữ phụ |
| `--faint` | `#8A8577` | label, nút ghost |
| `--muted` | `#B0A895` | placeholder, mono metadata |
| `--accent` | `#CC785C` | clay — nút chính, logo, avatar bot |
| `--accent-hover` | `#B4633E` | hover nút chính, label uppercase |
| `--accent-dim` | `#8F4A30` | link/nhấn mạnh trên nền sáng |
| `--accent-wash` | `#F7EDE6` | nền cảnh báo / chip đang chọn |
| `--accent-wash-border` | `#E7C9B6` | viền cảnh báo |
| `--user-bubble` | `#EEE7DA` (viền `#E4DAC7`) | bong bóng câu hỏi người dùng |
| `--cite-bg` | `#EFE7DA` | nền số trích dẫn ¹ ² |
| `--avatar-bg` | `#E7DDCB` | avatar người dùng (chữ `#8F4A30`) |
| green (đang hiệu lực) | fg `#5B7A5B`, bg `#EAF0E7`, bd `#CFE0C6` | pill "Đang hiệu lực" |
| grey (hết hiệu lực) | fg `#9C9686`, bg `#F0EDE5`, bd `#E4DFD2` | pill "Hết hiệu lực" |
| red (vi phạm) | fg `#A8412F`, bg `#F7E6E1`, bd `#E6BFB2` | finding "Vi phạm" |
| amber (cảnh báo) | fg `#B4633E`, bg `#F7EDE6`, bd `#E7C9B6` | finding "Cảnh báo" |
| dark panel | bg `#2B211C`, card `#352922`, bd `#46362C` | panel phải màn Auth |
| dark CTA | bg `#26241F`, heading `#F3F0E7`, body `#A49A88` | khối CTA cuối Landing |
| selection | `#E7C9B6` | `::selection` |

Ghi chú: `#F0EEE6 / #FAF9F5 / #CC785C` là bộ chính; **không thêm màu mới**. Landing/Auth có một khối tối duy nhất mỗi trang.

### Typography
- Serif — `'Newsreader', Georgia, serif`, weight 400/500/600 + italic. Dùng cho: h1/h2, thân câu trả lời, trích dẫn văn bản (italic), tiêu đề văn bản trong list, số thống kê.
- Sans — `system-ui, -apple-system, "Segoe UI", sans-serif`. Toàn bộ UI chrome, nav, nút, label, form.
- Mono — `ui-monospace, "SF Mono", Menlo, monospace`. Số hiệu điều khoản, ngày, đếm, hint bàn phím, email.
- Thang cỡ chữ thực dùng: 9.5 / 10 / 10.5 / 11 / 11.5 / 12 / 12.5 / 13 / 13.5 / 14 / 14.5 / 15 / 15.5 / 16 / 17 / 17.5 / 21 / 22 / 25 / 27 / 30 / 32 / 34 / 36 / 40 / 60 px.
- Label uppercase: `font-size:9.5–10px; letter-spacing:.08–.12em; text-transform:uppercase; font-weight:600`, màu `#B4633E` (nhấn) hoặc `#8A8577`/`#B0A895` (trung tính).
- Heading lớn luôn kèm `letter-spacing:-.015em → -.025em`, `line-height:1.06–1.18`.
- Line-height thân văn: 1.5–1.68 (câu trả lời serif dùng 1.68).
- `-webkit-font-smoothing:antialiased` trên body.

### Spacing / hình khối
- Radius: `5px` badge loại VB · `6–7px` ô nhỏ/nút ghost · `8–9px` icon vuông, nút phụ · `10–11px` input, card nguồn · `12–14px` card lớn · `16px` composer · `18–20px` panel/section lớn · `999px` pill/chip · `50%` avatar.
- Gap chuẩn: 1, 6, 7, 8, 9, 10, 11, 12, 14, 16, 22, 26px. **Luôn dùng flex/grid + gap**, không margin lẻ giữa các sibling.
- Padding card: `11–17px` ngang 12–18px. Panel: `18–24px`.
- Shadow: card nổi `0 4px 20px rgba(40,34,24,.07)`; popover `0 18px 46px rgba(40,34,24,.16)`; preview landing `0 24px 60px rgba(40,34,24,.13)`; segment thumb `0 1px 2px rgba(40,34,24,.12)`.
- Scrollbar tuỳ biến: `width:10px`, thumb `#DED8C9`, `border-radius:99px`, `border:3px solid #F0EEE6`.
- Transition: `.12s` (nhỏ), `.15s` (chuẩn), `.18–.2s` (border card).

### Keyframes
```css
@keyframes fadeup { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:none} }
@keyframes srcflash {
  0%{box-shadow:0 0 0 3px rgba(204,120,92,0)}
  18%{box-shadow:0 0 0 3px rgba(204,120,92,.55)}
  100%{box-shadow:0 0 0 3px rgba(204,120,92,0)}
}
```

---

## Screens / Views

### 1. Landing — `designs/LexFlow Landing.dc.html`
**Mục đích:** giới thiệu sản phẩm, dẫn tới đăng ký/demo.
**Layout:** một cột, `max-width:1120px`, `padding:0 32px`. Nền `#F0EEE6`.
1. **Header** sticky, `background:rgba(240,238,230,.86)`, `backdrop-filter:blur(12px)`, `border-bottom:1px solid #E4DFD2`, padding `13px 32px`. Logo (ô 29px radius 8 `#CC785C`, glyph `⎈`) + tên + `/ LexFlow` mono. Nav phải: Tính năng / Cách hoạt động / Nguồn dữ liệu (13.5px, `#6E6A5E`, hover `#191919`) + "Đăng nhập" (ghost) + "Dùng thử miễn phí" (primary).
2. **Hero** (`padding-top:76px`, canh giữa): pill "Dành cho khối Pháp chế & Tuân thủ ngân hàng"; h1 serif **60px**/1.06, weight 500, `max-width:760px`, có đoạn italic `#B4633E`; sub 17px `#6E6A5E` max 600px; 2 CTA; dòng mono 11px `#B0A895`.
3. **Product preview**: khung browser giả (radius `18px 18px 0 0`), 3 dot `#E4DFD2` + URL mono `lexflow.vn/tra-cuu`; bên trong: bong bóng câu hỏi serif 15px + câu trả lời có superscript trích dẫn + 1 card nguồn.
4. **Problem** (nền `#FAF9F5`, viền trên/dưới): grid `1fr 1fr`, gap 56. Trái: eyebrow + h2 serif 34px + đoạn 15px. Phải: 3 card icon (`◇ ◷ ⚠`).
5. **Features**: h2 serif 40px canh giữa; grid `repeat(3,1fr)` gap 16; 6 card `#FAF9F5` radius 15, icon 34px trong ô `#F7EDE6` viền `#E7C9B6`; hover `border-color:#D8C4A8; translateY(-2px)`.
6. **How it works**: card lớn `#FAF9F5` radius 20 padding 44; grid 4 bước, badge số mono 26px `#CC785C`.
7. **Sources**: grid `1fr 1.1fr`; trái: eyebrow + h2 + 5 chip loại văn bản; phải: timeline 3 mốc (ngày mono width 58px, tên VB, pill trạng thái; mốc hết hiệu lực `opacity:.62`).
8. **Stats**: grid 4 cột, `gap:1px` trên nền `#E4DFD2` (tạo đường kẻ), số serif 36px: 42.000+ / 100% / < 3s / 1.200+.
9. **CTA tối**: `#26241F` radius 20 padding `56px 44px`, h2 serif 40px `#F3F0E7`, 2 nút.
10. **Footer** + dòng disclaimer 11px `#B0A895`.

**Nội dung:** lấy nguyên văn tiếng Việt từ file (`problems`, `features`, `steps`, `docTypes`, `timeline`, `stats` trong `renderVals()`).

### 2. Auth — `designs/LexFlow Auth.dc.html`
**Mục đích:** đăng nhập / đăng ký bằng email công việc.
**Layout:** `min-height:100vh`, grid `1.05fr .95fr`.
- **Trái** (`#F0EEE6`, padding `26px 32px 34px`): logo góc trên (link về landing); form canh giữa, `max-width:404px`.
  - h1 serif 34px + sub 14.5px, **đổi theo mode**: login = "Chào mừng trở lại" / register = "Tạo tài khoản LexFlow".
  - **Tab** segment: track `#E7E3D8` radius 11 padding 3; tab active `#FAF9F5` + shadow `0 1px 2px rgba(40,34,24,.12)`, inactive `#8A8577`.
  - Field: label 12.5px weight 500 `#33302A`, input `#FAF9F5` viền `#E4DFD2` radius 10 padding `11px 13px` 14px; focus: `border-color:#CC785C` + `box-shadow:0 0 0 3px rgba(204,120,92,.13)`.
  - Register thêm: grid 2 cột Họ tên + Đơn vị/Phòng ban; hint mật khẩu "Tối thiểu 10 ký tự, gồm chữ và số."; checkbox đồng ý điều khoản. Login thêm: link "Quên mật khẩu?" + checkbox "Ghi nhớ đăng nhập".
  - Toggle hiện/ẩn mật khẩu: nút 32px trong input (icon eye SVG 17px, stroke 1.6, có gạch chéo khi ẩn).
  - Nút submit primary full-width radius 11; divider "hoặc"; nút SSO Google (`#FAF9F5`, hover `#F7F5EE` + `border-color:#D8C4A8`); dòng chuyển mode; dòng mono "Dữ liệu lưu trữ tại Việt Nam · Đăng nhập được ghi log phục vụ kiểm toán".
- **Phải** (panel tối `#2B211C`, padding `48px 52px`, `max-width:440px` nội dung): pill "Mọi câu trả lời đều truy được nguồn"; h2 serif 32px `#F3F0E7`; mini answer card `#352922` viền `#46362C` (2 pill trust + câu trả lời serif + 1 nguồn); 3 perk có tick; testimonial serif italic + avatar "NM".

**Điều hướng hiện tại trong prototype:** nút submit là `<a>` sang màn Tra cứu (chỉ để demo flow) — trong app thật thay bằng Supabase auth (`app/login/page.tsx` đã có sẵn logic, giữ logic, đổi UI).

### 3. Tra cứu / Chatbot hỏi đáp — `designs/LexFlow Anthropic.dc.html` ⭐ màn chính
**Mục đích:** hỏi bằng ngôn ngữ tự nhiên, nhận câu trả lời có trích dẫn kiểm chứng được, giới hạn phạm vi văn bản khi cần.
**Layout:** `height:100vh; display:flex`.

**A. Sidebar trái** — `width:260px` (flex:none), `#F5F2EA`, `border-right:1px solid #E4DFD2`, cột dọc:
- Brand: ô 28px `#CC785C` + "Hoa Tiêu Pháp Lý" 14px w600 + "LexFlow" mono 10px.
- Nút **"✚ Tra cứu mới"** full-width `#CC785C` radius 10 padding `10px 13px`, hover `#B4633E`.
- Nav: Tra cứu (active: `#EAE4D6`, chữ `#191919`, w500) / Đồ thị tri thức / Cảnh báo (badge tròn `#CC785C` số 3). Icon glyph trong ô width 16 canh giữa: `⌘ ◰ ⚠`. Hover `#EFEADF`.
- **Gần đây**: label uppercase 10px + 4 hội thoại, item 12.5px 1 dòng ellipsis, item đầu active `#EAE4D6`.
- Footer account: avatar tròn 30px `#E7DDCB`/`#8F4A30` chữ "AT", tên + email mono, icon `⚙`.

**B. Thread (giữa, cuộn)** — `flex:1`, `overflow-y:auto`, `scroll-behavior:smooth`, id `lf-thread`; nội dung `max-width:760px` `margin:0 auto` padding `34px 26px 28px`.
- **Intro (khi chưa có lượt nào)**: icon 44px radius 12 `#CC785C`; h1 serif 27px "Hỏi về quy định — nhận câu trả lời truy được nguồn"; sub 14px max 480px có đoạn serif italic `#B4633E`.
- **Mỗi lượt hỏi–đáp** (`padding:22px 0`, `animation:fadeup .35s ease-out`; lượt thứ 2+ có `border-top:1px solid #E4DFD2`):
  1. **Chip phạm vi ghim vào câu hỏi** — canh phải, `margin-right:38px`: label mono 10px "Phạm vi" + pill 10.5px. Có giới hạn → `#F7EDE6`/`#E7C9B6`/`#8F4A30`; toàn bộ → `#F5F2EA`/`#E4DFD2`/`#8A8577`.
  2. **Bong bóng người dùng** — canh phải, serif 16px, `max-width:78%`, `#EEE7DA` viền `#E4DAC7`, radius `16px 16px 5px 16px`, padding `11px 16px`; avatar 28px bên phải.
  3. **Khối trả lời** — avatar bot 28px radius 8 `#CC785C` bên trái, gap 10.
     - **Trust bar**: pill xanh "2 nguồn đang hiệu lực" (có dot 6px) + pill clay "⚠ 1 mâu thuẫn" + mono "tra tại 24/07/2026".
     - **Cảnh báo mâu thuẫn** (accordion, mặc định mở): khối `#F7EDE6` viền `#E7C9B6` radius 13. Header là button: icon 28px `#CC785C` `⚠`, eyebrow "Mâu thuẫn · Nghiêm trọng", 1 dòng mô tả, nhãn mono phải "Thu gọn ▲ / Chi tiết ▼". Nội dung mở: 2 card trắng cạnh nhau (`TT 23/2019 · Điều 9` — 50 triệu, pill "Đã hết hiệu lực" / `TT 40/2024 · Điều 9` — 100 triệu, viền `#CFE0C6`, pill "✓ Đang áp dụng") phân cách bởi `↔`, + đoạn giải thích LexFlow chọn số nào.
     - **Câu trả lời**: serif **17.5px/1.68** `#26241F`; số trích dẫn là `<button>` superscript: mono 10px, padding `2px 6px`, radius 6, `#EFE7DA`/`#8F4A30` w600; hover → `#CC785C` chữ trắng.
     - **Action row**: "⧉ Sao chép kèm nguồn" (đổi thành "✓ Đã sao chép" 1.6s), "⌄ Ẩn nguồn / ⌃ Hiện 2 nguồn", hint "Nhấp số ¹ ² để kiểm chứng". Nút ghost: 11.5px `#8A8577` trên `#F0EBE0` radius 7 padding `6px 11px`.
     - **Danh sách nguồn** (toggle được, mặc định mở): mỗi card `#FAF9F5` viền `#E4DFD2` radius 13, `data-src={index}`; badge số mono 23px `#EFE7DA`; hàng meta: badge loại VB, số hiệu 13.5px w600, số điều mono `#B4633E`, pill "Đang hiệu lực", "từ 01/2024" mono canh phải; trích dẫn serif 14px italic; nút "Xem toàn văn điều khoản / Thu gọn" mở khối toàn văn (`#F0EEE6` radius 9, 12px) + link "Mở văn bản gốc ↗".
     - **Follow-up chip**: 12px, `#FAF9F5` viền `#E4DFD2` radius 999, text + " →"; hover `border-color:#CC785C; color:#8F4A30; background:#F7EDE6`. Click = gửi luôn câu hỏi đó.

**C. Composer (đáy, không cuộn)** — `flex:none`, nền `linear-gradient(to top,#F0EEE6 62%,rgba(240,238,230,0))`, padding `6px 26px 18px`; nội dung `max-width:760px`, `position:relative`.
- **Thanh phạm vi** (trong khung composer, trên textarea, `border-bottom:1px solid #EDE8DC`):
  - Nút **"◈ Phạm vi"** viền `1px dashed #D8CFBB`, nền `#F5F2EA`, 11.5px, kèm số mono (`tất cả` hoặc số lượng). Toggle popover.
  - Chip mỗi văn bản đã chọn: `#F7EDE6` viền `#E7C9B6` `#8F4A30`, radius 999, có nút ✕ tròn 15px `#EDDCCF`.
  - Khi chưa chọn: dòng nhắc 11.5px `#B0A895` "Đang hỏi trên toàn bộ văn bản còn hiệu lực".
- **Popover chọn văn bản** — `position:absolute; left:0; right:0; bottom:calc(100% + 10px); z-index:30`, `#FAF9F5` viền `#E4DFD2` radius 16, shadow `0 18px 46px rgba(40,34,24,.16)`, `animation:fadeup .16s ease-out`:
  - Header: "Chọn văn bản để hỏi" 13.5px w600 + phụ đề "Giới hạn câu trả lời trong các văn bản bạn chọn" + nút ✕ 24px.
  - Ô tìm kiếm (`#fff` viền `#E4DFD2` radius 10) — filter theo `code + title`.
  - **Preset chip** (chọn đơn): Toàn bộ đang hiệu lực (default) / Nhóm Thanh toán / Nhóm KYC – PCRT / Nhóm An toàn / Gồm cả văn bản hết hiệu lực. Chip active `#F7EDE6` viền `#CC785C` chữ `#8F4A30`.
  - **Danh sách checkbox** `max-height:262px` cuộn: mỗi hàng là button với ô check 18px radius 6 (`#CC785C` khi chọn, viền `#D8CFBB` khi chưa), badge loại VB, số hiệu, pill hiệu lực, tên văn bản 1 dòng ellipsis, "n điều" mono. Hàng đã chọn: nền `#F7EDE6` viền `#E7C9B6`. Rỗng → "Không tìm thấy văn bản phù hợp."
  - Footer `#F5F2EA`: tóm tắt ("n văn bản đã chọn" / "Chưa chọn — hỏi trên toàn bộ phạm vi") + "Bỏ chọn tất cả" + nút **Áp dụng** primary.
- **Khung soạn**: `#FAF9F5` viền `#E4DFD2` radius 16 padding `6px 6px 6px 8px`, shadow `0 4px 20px rgba(40,34,24,.07)`. Textarea 15.5px không viền, `resize:none`, `max-height:120px`, placeholder "Hỏi tiếp về quy định thanh toán…" (`#B0A895`).
- **Hàng dưới**: label "Hiệu lực tại" + `<input type="date">` (mặc định `2026-07-24`) — đây là **as-of date** áp cho câu trả lời; hint mono "Enter để gửi · Shift+Enter xuống dòng"; nút gửi 34px vuông radius 10 `#CC785C`, glyph `↑`.
- Disclaimer 10.5px canh giữa: "Thông tin mang tính tham khảo — đối chiếu bản gốc trước khi ra quyết định."

**Dữ liệu mẫu trong file:** `SOURCES` (2 nguồn: TT 40/2024 Điều 9; NĐ 52/2024 Điều 27 — có `quote` và `full`), `FOLLOWUPS` (2 câu), `LIB` (6 văn bản cho picker, mỗi cái có `type, code, title, live, articles, group`), `PRESETS` (5 preset).

### 4. Thư viện văn bản — `designs/LexFlow Thu Vien.dc.html`
**Mục đích:** duyệt/tìm toàn bộ văn bản đã lập chỉ mục, xem metadata, quan hệ và mục lục điều khoản.
**Layout:** 3 cột trong `height:100vh`, wrapper cuộn ngang với `min-width:1140px`:
- **Sidebar 260px** — giống màn Tra cứu, nhưng phần dưới là **facet** thay vì lịch sử. 3 nhóm facet, mỗi item là button full-width có đếm mono bên phải, active `#EAE4D6` w500:
  - Tình trạng: Tất cả văn bản / Đang hiệu lực / Hết hiệu lực
  - Loại văn bản: Luật / Nghị định / Thông tư / Quyết định
  - Lĩnh vực: Thanh toán / Định danh khách hàng / An toàn giao dịch
- **List (giữa, `flex:1`, `min-width:520px`)** padding `24px 30px 60px`, `max-width:900px`:
  - h1 serif 30px + sub 14px.
  - Hàng tìm kiếm: input có icon `⌕` (absolute left 13) + segment sort "Mới nhất | Số hiệu".
  - **Thanh as-of**: card `#FAF9F5` radius 12 — "Xem tình trạng hiệu lực tại" + input date (`2026-07-24`) + meta mono "cập nhật tới dd/mm/yyyy" + nút "Xóa bộ lọc" canh phải.
  - Dòng heading động: tên facet (serif 17px) + "n văn bản".
  - **Card văn bản** (button, `#FAF9F5` radius 14): badge loại + số hiệu 14px w600 + pill trạng thái + ngày hiệu lực mono canh phải; tên văn bản serif 15.5px; hàng cuối: cơ quan ban hành, "n điều", quan hệ có màu theo loại (`replace #5B7A5B`, `amend #B4633E`, `replaced #9C9686`, `none #B0A895`). Card đang chọn: viền `#CC785C`. Văn bản hết hiệu lực: `opacity:.72`. Hover: `border-color:#D8C4A8`.
- **Detail (phải, `width:392px`, `#FAF9F5`, `border-left`)** padding `20px 22px 40px`:
  - badge loại + pill trạng thái; số hiệu 17px w600; tên serif 15px.
  - **Bảng metadata**: các hàng `#F0EEE6` cách nhau 1px trên nền `#EDE8DC` (radius 11 overflow hidden): Số hiệu / Cơ quan ban hành / Ngày ban hành / Ngày hiệu lực / Tình trạng / Lĩnh vực — key 11.5px width 112px, value mono 11px.
  - 2 nút: **"Hỏi về văn bản này"** (primary — mở màn Tra cứu với văn bản này **đã nằm trong phạm vi**, nối trực tiếp với picker ở màn 3) + "Mở gốc ↗".
  - **Quan hệ văn bản**: card mỗi quan hệ (kind uppercase, code mono `#B4633E`, pill trạng thái, ghi chú); viền `#CFE0C6` nếu VB liên quan còn hiệu lực.
  - **Mục lục điều khoản**: khối viền, mỗi hàng "Điều n" mono width 52 `#B4633E` + tên điều; điều có `quote` hiện thêm trích dẫn serif italic thụt 62px.

**Dữ liệu mẫu:** `DOCS` — 6 văn bản đầy đủ `meta / relations / outline` (TT 40/2024, NĐ 52/2024, TT 17/2024, Luật PCRT 2022, TT 23/2019 hết hiệu lực, QĐ 2345). Đây là schema tối thiểu API cần trả cho trang này.

### 5. Kiểm tra tài liệu (tuân thủ) — `designs/LexFlow Kiem Tra.dc.html`
**Mục đích:** đối chiếu tài liệu nội bộ (PDF) với các văn bản pháp luật tại một mốc thời gian, xuất danh sách phát hiện.
**Layout:** 3 cột, wrapper cuộn ngang `min-width:1180px`:
- **Sidebar 260px** — như trên, nav item active là "Kiểm tra tài liệu"; nút chính "✚ Phiên kiểm tra mới"; danh sách "Phiên kiểm tra gần đây".
- **Config panel `width:352px`** (`#FAF9F5`, `border-right`), header cố định + thân cuộn + footer cố định:
  - Header: h1 serif 22px "Kiểm tra tuân thủ" + sub 12.5px.
  - **Bước 1 — Tài liệu nội bộ**: badge số mono 20px `#CC785C`; card có thumb "PDF" (30×36, chữ `#B4633E`), tên file 13px, meta mono "18 trang · 1,4 MB · tải lên 26/07"; 2 nút "Đổi tài liệu" / "Xem trước".
  - **Bước 2 — Văn bản đối chiếu**: pill "n đã chọn" canh phải; input tìm; 4 chip filter (Tất cả / Đang hiệu lực / Thanh toán / Định danh KH — chip active nền `#CC785C` chữ trắng); danh sách checkbox (`accent-color:#CC785C`) trong khối viền, mỗi hàng: badge loại, số hiệu, pill trạng thái, tên, `scope` mono ("Điều 5–14 · hạn mức, liên kết ví"). Hàng đã chọn nền `#F3F0E7`; VB hết hiệu lực `opacity:.6`. Ghi chú cuối: "Mặc định LexFlow đề xuất văn bản theo chủ đề của tài liệu nội bộ."
  - **Bước 3 — Thời điểm kiểm tra**: segment 3 chế độ (Hôm nay / Ngày cụ thể / Mốc sắp tới) + input date + hint đổi theo chế độ (3 câu trong file).
  - Footer: nút primary full-width **"Chạy kiểm tra n văn bản"** + meta mono "Ước tính ~40 giây · 18 trang".
- **Results (`flex:1`, `min-width:568px`)**, `max-width:820px` padding `24px 30px 60px`:
  - Header: h2 serif 25px tên tài liệu + pill "Cần xử lý"; dòng mono "Đối chiếu n văn bản · hiệu lực tại dd/mm/yyyy · chạy lúc 09:42 26/07"; 2 nút ghost "⧉ Xuất báo cáo" / "Chia sẻ".
  - **Score strip**: grid `1.25fr 1fr 1fr 1fr`, `gap:1px` trên `#E4DFD2`, radius 14. Ô đầu: "Mức tuân thủ" + số serif 32px `72` + `/100` + progress bar 5px (`#EAE4D6` track, `#CC785C` fill 72%). 3 ô còn lại: Vi phạm 1 (`#A8412F`) / Cảnh báo 1 (`#B4633E`) / Tuân thủ 1 (`#5B7A5B`), kèm ghi chú.
  - **Findings**: hàng tiêu đề "Phát hiện" + segment tab (Tất cả 3 / Vi phạm 1 / Cảnh báo 1 / Tuân thủ 1). Mỗi finding là card accordion `#FAF9F5` radius 14:
    - Header: icon 30px radius 9 theo tone (`✕` đỏ / `⚠` amber / `✓` xanh), pill verdict, vị trí mono ("Mục 3.2, trang 6"), tiêu đề 14.5px w600, tóm tắt 12.5px, nhãn "Chi tiết ▼ / Thu gọn ▲".
    - Mở ra (thụt trái 54px): grid 2 cột so sánh — **Tài liệu nội bộ** (`#F0EEE6`, vị trí mono, trích dẫn serif italic) vs **Văn bản pháp luật** (viền xanh nếu còn hiệu lực, pill trạng thái, `legalRef` mono `#B4633E`, trích dẫn serif italic); khối **"Đề xuất chỉnh sửa"** `#F7EDE6` viền `#E7C9B6`; 3 nút ghost: "Mở văn bản gốc ↗" / "Gán người xử lý" / "Bỏ qua có lý do".
  - Disclaimer cuối: "Kết quả mang tính hỗ trợ rà soát — vui lòng đối chiếu bản gốc trước khi ban hành tài liệu."
  - Responsive nhỏ: `@media (max-width:1180px)` → score strip về 2 cột.

**Dữ liệu mẫu:** `LEGAL` (5 văn bản có `scope`, `on` = chọn sẵn), `FINDINGS` (3 phát hiện đủ trường: verdict/kind/location/title/summary/internalQuote/legalRef/legalQuote/legalStatus/suggestion).

---

## Interactions & Behavior

### Màn Tra cứu (quan trọng nhất)
| Hành vi | Chi tiết |
|---|---|
| Gửi câu hỏi | Enter gửi, Shift+Enter xuống dòng; bỏ qua khi trống; xoá draft; append lượt mới; auto-scroll `scrollTo({top: scrollHeight, behavior:'smooth'})` trong `requestAnimationFrame` |
| Phạm vi ghim theo lượt | Khi gửi, **snapshot** phạm vi hiện tại vào lượt đó (`scope` text + `narrow` bool). Đổi phạm vi sau đó **không** thay đổi các lượt cũ |
| Nhãn phạm vi | 1 văn bản → hiện số hiệu; ≥2 → "n văn bản đã chọn"; không chọn → nhãn preset đang bật |
| Mở picker | Toggle; đóng bằng ✕ hoặc Áp dụng. *Nên bổ sung khi code thật:* Esc để đóng + click ra ngoài để đóng (prototype chưa có) |
| Chọn văn bản | Toggle theo `code`; preset là chọn đơn và chỉ lọc danh sách hiển thị (không tự tick) |
| Click số trích dẫn ¹² | Mở panel nguồn nếu đang đóng, set `active=index`, cuộn thread tới `el.offsetTop - 120` (smooth), chạy `srcflash` 1.4s và viền card đổi `#CC785C`; reset sau 1.5s |
| Sao chép | `navigator.clipboard.writeText` (bọc try/catch) với text đã chèn `[TT 40/2024/TT-NHNN, Điều 9]`; nhãn nút đổi 1.6s |
| Follow-up chip | Gửi ngay câu hỏi đó (kèm snapshot phạm vi) |
| Accordion mâu thuẫn / nguồn / toàn văn | Độc lập nhau; mâu thuẫn + nguồn mặc định **mở**, toàn văn mặc định **đóng** |
| Tra cứu mới | Reset draft + thread về lượt mẫu |

### Các màn khác
- **Auth**: tab + link đổi mode (login/register) làm đổi heading, sub, field, nhãn nút, prompt; toggle hiện/ẩn mật khẩu đổi `type` + icon + `aria-label`.
- **Thư viện**: facet (chọn đơn) → filter; search filter `code+title+issuer` (lowercase, không dấu-sensitive); sort "Mới nhất" theo `year` giảm dần, "Số hiệu" theo `localeCompare(vi)`; click card → chọn và cập nhật panel phải; "Xóa bộ lọc" reset search + facet (không reset date).
- **Kiểm tra**: checkbox nhiều lựa chọn (giữ index gốc khi list bị filter); chip filter + search; segment thời gian đổi label input date + hint; tab findings filter theo `kind`; accordion từng finding; nhãn nút chạy hiển thị số văn bản đang chọn.

### Trạng thái còn thiếu trong prototype (cần thiết kế/triển khai khi code)
Prototype **không** có: loading/streaming câu trả lời, empty state khi chưa có kết quả tìm kiếm ở Thư viện, lỗi mạng/lỗi auth, validation form, upload PDF thật, progress khi chạy kiểm tra, responsive mobile (thiết kế cho desktop ≥1180–1440px; 2 màn 3 cột hiện xử lý bằng cuộn ngang). Hãy dùng token và pattern sẵn có (pill, card, ghost button) để dựng các state này, hoặc hỏi lại designer.

## State Management
- **Tra cứu**: `scope: string[]` (mã văn bản), `pickerOpen: bool`, `query: string`, `preset: 'live'|'thanhtoan'|'kyc'|'antoan'|'all'`, `draft: string`, `turns: {question, scope, narrow}[]`, `conflictOpen`, `sourcesOpen`, `copied`, `active: number|null`, `open: Record<number,bool>` (toàn văn từng nguồn), as-of date.
- **Auth**: `mode: 'login'|'register'`, `showPw: bool`.
- **Thư viện**: `search`, `facet`, `sort`, `date`, `selected: number` (nên là `docId` trong app thật).
- **Kiểm tra**: `picked: bool[]`, `search`, `filter`, `timeMode`, `date`, `tab`, `open: Record<number,bool>`.

**Data fetching cần có:**
- `GET /documents?status&type&field&q&asOf&sort` → list Thư viện (schema = `DOCS`).
- `GET /documents/:id` → metadata + relations + outline (panel phải).
- `POST /ask { question, scope: string[], preset, asOf }` → `{ answer (markdown + citation markers), sources[], conflicts[], followups[] }`. **Phạm vi và as-of date phải được gửi lên và ghi lại theo từng lượt** để audit.
- `POST /reviews { fileId, docCodes[], asOf }` → `{ score, counts, findings[] }`.
Backend Python đã có sẵn (`app/api`, `app/reasoning`, `app/knowledge`) — kiểm tra contract thực tế ở đó trước khi tự định nghĩa.

## Assets
Không có ảnh/bitmap. Toàn bộ icon là **ký tự Unicode** dùng như glyph: `⎈` (logo), `✚ ⌘ ◰ ⚠ ▤ ⎗ ⚙ ⌕ ◈ ✕ ✓ ↑ ↔ ⧉ ◇ ◷ ◉ ¹ △ ⌄ ⌃ ▲ ▼ ↗ →`. Nếu team muốn icon set thật (lucide…), map 1–1 và giữ nguyên kích cỡ ô chứa. Font duy nhất cần tải: **Newsreader** (Google Fonts, weight 400/500/600 + italic). Không dùng emoji.

## Files
```
design_handoff_lexflow/
├── README.md                       ← tài liệu này
└── designs/
    ├── LexFlow Landing.dc.html     ← màn 1
    ├── LexFlow Auth.dc.html        ← màn 2
    ├── LexFlow Anthropic.dc.html   ← màn 3 (Tra cứu / chatbot) ⭐
    ├── LexFlow Thu Vien.dc.html    ← màn 4
    ├── LexFlow Kiem Tra.dc.html    ← màn 5
    ├── LexFlow Styles.dc.html      ← 5 hướng style (tham khảo, đã chọn 1a)
    └── support.js                  ← runtime để mở prototype trong browser (không port sang app)
```
Mở bất kỳ file `.dc.html` bằng browser (cần `support.js` cùng thư mục) để xem và tương tác trực tiếp.

## Thứ tự triển khai đề xuất
1. Cập nhật `web/app/globals.css` sang bộ token mới + thêm font Newsreader trong `app/layout.tsx`.
2. Dựng **AppShell** (sidebar 260px + nav + account footer) dùng chung cho màn 3, 4, 5.
3. Primitives dùng lại: `Pill` (live/expired/violation/warning/pass), `TypeBadge`, `GhostButton`, `PrimaryButton`, `SegmentedControl`, `Chip`, `Card`, `Accordion`, `MetaTable`, `SourceCard`, `DatePicker`.
4. Màn Tra cứu (gồm scope picker) → Thư viện → Kiểm tra → Auth → Landing.
