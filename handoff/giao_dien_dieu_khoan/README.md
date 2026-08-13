# Handoff: Toàn văn — đánh dấu điều khoản bị tác động → pop-up đối chiếu (phương án 2a)

## Overview
Màn xem **toàn văn** một văn bản quy phạm pháp luật trong LexFlow / Hoa Tiêu Pháp Lý, trong đó các **khoản/điểm bị tác động** bởi văn bản khác được đánh dấu ngay trong dòng chữ. Click vào khoản đánh dấu mở **modal đối chiếu** giữa *điều luật gốc* (văn bản đang đọc) và *điều luật tác động* (văn bản sửa đổi/bãi bỏ/bổ sung), kèm nội dung sau hợp nhất và metadata.

Thay thế/nâng cấp cho màn hiện tại `web/app/(app)/docs/[docId]/page.tsx`, vốn chỉ có vạch lề clay báo "có thay đổi" mà không cho biết thay đổi thành gì.

## About the Design Files
Các file trong gói này là **design reference viết bằng HTML** — prototype thể hiện diện mạo và hành vi mong muốn, **không phải production code để copy thẳng**. Nhiệm vụ là **dựng lại thiết kế này trong codebase đích** (ở đây: Next.js App Router + React + Tailwind v4 của `web/`), dùng đúng pattern, component và token đã có sẵn ở đó — không bê nguyên HTML.

Cụ thể với repo LexFlow: giữ `PageShell`/`AppSidebar`, giữ `lib/anchors.ts` (slug anchor Điều/Khoản/Điểm), giữ các biến màu trong `web/app/globals.css`. Chỉ thay phần thân trình xem văn bản.

## Fidelity
**High-fidelity.** Màu, typography, spacing, bo góc, shadow, và trạng thái tương tác đều là giá trị cuối. Dựng lại pixel-perfect bằng thư viện sẵn có của codebase.

## Screens / Views

### 1. Toàn văn (nền)
**Purpose:** Đọc liên tục toàn bộ văn bản như bản in; nhận ra ngay khoản nào đã bị tác động mà không phải rời trang.

**Layout** — cột dọc, nền `#FAF9F5`:
- **Header** (flex row, `flex: none`, padding `13px 30px`, `border-bottom: 1px solid #E4DFD2`, gap `11px`):
  - Chip loại văn bản: `background #EAE4D6`, `color #26241F`, `font-size 11px / 600`, `padding 3px 8px`, `radius 5px` — nội dung "Thông tư"
  - Số hiệu: mono `12.5px`, `color #8F4A30` — "40/2024/TT-NHNN"
  - Tiêu đề: Newsreader `17px / 500`, `color #191919`
  - `flex: 1` spacer
  - Chip đếm: pill `radius 999px`, `border 1px solid #E7C9B6`, `background #F7EDE6`, `color #8F4A30`, `font-size 11.5px`, `padding 4px 11px`, có chấm `6×6px` `#CC785C` phía trước — "4 khoản bị tác động"
  - Nút lọc: `border 1px solid #E4DFD2`, `background #F0EEE6`, `radius 9px`, `font-size 11.5px`, `color #6E6A5E`, `padding 5px 11px` — "Chỉ điều bị tác động"
- **Vùng cuộn** (`flex: 1`, `overflow-y: auto`): cột chữ `max-width: 800px`, căn giữa, `padding 36px 30px 90px`

**Mỗi Điều** (`<section>`, `margin-top: 34px`):
- Tiêu đề Điều: Newsreader `17.5px / 600`, `line-height 1.35`, `color #191919` — "Điều 26. Hạn mức giao dịch qua ví điện tử"

**Mỗi Khoản/Điểm** (wrapper `position: relative`, `margin-left: -46px`, `padding-left: 46px`, `padding-right: 8px`, `radius 8px`; khoản có tác động thêm `cursor: pointer`):
- **Đoạn văn**: `font-family 'Newsreader', Georgia, serif`, `font-size 16px`, `line-height 1.75`, `text-align: justify`, `color #26241F`, `margin 10px 0 0`, `text-indent 28px`. Cấp Điểm (a, b, c) thêm `padding-left: 28px`.
- **Huy hiệu số ở lề** (chỉ khoản bị tác động): `position absolute; left 14px; top 16px`, `20×20px`, `radius 6px`, chữ mono `10.5px / 600` màu trắng, nền = màu theo loại tác động. Nội dung là số thứ tự thay đổi trong văn bản (1…4).
- **Highlight nội dòng** (`<span>` bọc text, chỉ khoản bị tác động): `background` = màu nền loại, `box-shadow: 0 0 0 3px <cùng màu nền>` (tạo padding quang học), `border-radius 2px`, `border-bottom: 1.5px solid <màu loại>`. Loại *Bãi bỏ* thêm `color: #7A7266`.
- **Dòng gợi ý** dưới đoạn: `display block`, `margin-top 6px`, `font-size 11px`, `color` = màu loại; cấp Điểm thêm `padding-left: 28px`. Nội dung: `"{Loại} · {Số hiệu VB tác động} · Điều X · từ {dd/mm/yyyy} — bấm để đối chiếu"`.

**Bảng màu theo loại tác động**

| Loại | key | Màu nhấn (viền/huy hiệu/chữ) | Nền highlight |
|---|---|---|---|
| Bị sửa đổi | `sua` | `#B4633E` | `#F7E7DA` |
| Bị bãi bỏ | `bai_bo` | `#A8412F` | `#F5E2DC` |
| Được bổ sung | `bo_sung` | `#5B7A5B` | `#E7EFE4` |

### 2. Modal đối chiếu
**Purpose:** Trả lời "thay đổi thành gì, do văn bản nào, từ khi nào" mà không rời khỏi mạch đọc.

**Overlay:** `position absolute; inset 0`, `background rgba(32,27,20,.42)`, `backdrop-filter: blur(2px)`, `display grid; place-items center`, animation `fadeup .16s ease-out` (`from { opacity:0; translateY(8px) }`). Click overlay → đóng. Click bên trong dialog → `stopPropagation`.

**Dialog:** `width 1000px`, `max-height 760px`, cột dọc, `border 1px solid #E4DFD2`, `radius 16px`, `background #FAF9F5`, `box-shadow 0 30px 70px rgba(30,24,16,.34)`, `overflow hidden`.

**a) Thanh tiêu đề** (`flex: none`, `background #F5F2EA`, `border-bottom 1px solid #E4DFD2`, `padding 15px 22px`, gap `11px`):
- Pill loại tác động: `border 1px solid <màu loại>`, `radius 999px`, `color <màu loại>`, `10.5px / 600`, `letter-spacing .04em`, `padding 3px 10px`
- Địa chỉ: mono `13.5px`, `color #26241F` — "Điều 26 · Khoản 1"
- spacer `flex: 1`
- Ngày hiệu lực: mono `11.5px`, `color #8A8577` — "hiệu lực từ 01/07/2025"
- Nút đóng: `28×28px`, `border 1px solid #E4DFD2`, `radius 8px`, `background #F0EEE6`, `color #6E6A5E`, glyph `✕` `14px`

**b) Thân cuộn** (`flex: 1`, `overflow-y: auto`):

*Hai cột đối chiếu* — `display grid; grid-template-columns 1fr 1fr; gap 1px; background #E4DFD2` (gap làm đường kẻ dọc):
- **Cột trái — "ĐIỀU LUẬT GỐC"**: nền `#FAF9F5`, `padding 18px 22px`. Nhãn eyebrow `9.5px / 600`, `letter-spacing .1em`, `uppercase`, `color #8A8577`; cạnh nó là số hiệu văn bản đang đọc mono `10.5px` `#9C9686`. Dòng tên Điều: Newsreader `13px italic`, `#8A8577`. Nguyên văn khoản: Newsreader `14.5px`, `line-height 1.72`, `justify`, `color #26241F`, `margin-top 12px`. Nếu loại = *bãi bỏ*: `color #9C9686` + `text-decoration: line-through` với `text-decoration-color #D3C6B6`.
- **Cột phải — "ĐIỀU LUẬT TÁC ĐỘNG"**: nền `#F7EDE6`, cùng padding. Eyebrow `color #B4633E`; số hiệu mono `#8F4A30`; tên Điều của văn bản tác động Newsreader `13px italic` `#8F4A30`. Nguyên văn điều khoản tác động: cùng kiểu chữ cột trái, `color #26241F`.

*Nội dung sau hợp nhất* — `border-top 1px solid #E4DFD2`, `padding 18px 22px 22px`. Eyebrow `9.5px / 600 uppercase`, `color #5B7A5B`, kèm đường kẻ `flex:1; height 1px; background #E4DFD2`. Đoạn văn: `border-left 2px solid #5B7A5B`, `padding-left 14px`, Newsreader `15px`, `line-height 1.72`, `justify`, `color #26241F`.

*Dải metadata* — `grid-template-columns repeat(4, 1fr)`, `gap 1px`, `background #E4DFD2`, mỗi ô nền `#F5F2EA`, `padding 11px 16px`. Nhãn `10px` `#8A8577`; giá trị mono `11.5px` `#26241F`. Bốn ô: **Loại tác động**, **Văn bản tác động**, **Hiệu lực từ**, **Địa chỉ neo** (id dạng `26.1`).

**c) Chân** (`flex: none`, `background #F5F2EA`, `border-top 1px solid #E4DFD2`, `padding 13px 22px`, gap `9px`):
- "↑ Thay đổi trước" và "Thay đổi tiếp ↓": `border 1px solid #E4DFD2`, `radius 9px`, `background #F0EEE6`, `12px`, `color #26241F`, `padding 7px 12px`
- Vị trí: mono `11px` `#8A8577` — "2 / 4"
- spacer
- "Hỏi Lexi": cùng kiểu nút phụ
- "Mở toàn văn {số hiệu} ↗": nút chính, `background #CC785C`, `color #fff`, `radius 9px`, `12px / 500`, `padding 7px 14px`

## Interactions & Behavior
- **Click khoản có tác động** (bất kỳ đâu trong wrapper, kể cả huy hiệu và dòng gợi ý) → `setState({ modal: <anchorId> })`. Khoản không có tác động: no-op, không đổi con trỏ.
- **Đóng modal**: click overlay, hoặc nút `✕`. *Cần bổ sung khi implement:* phím `Esc`, focus trap, `aria-modal="true"`, trả focus về khoản vừa click, khoá scroll nền.
- **Duyệt tuần tự**: "Thay đổi trước/tiếp" nhảy vòng tròn (`(i ± 1 + n) % n`) qua **danh sách phẳng các khoản bị tác động theo thứ tự văn bản**, không đóng modal. Khi implement nên đồng thời scroll đoạn tương ứng ở nền vào tầm nhìn (**không dùng `scrollIntoView`** — tính toán `scrollTop` thủ công).
- **Nút lọc "Chỉ điều bị tác động"** ở header: ẩn các Điều không có khoản đánh dấu (trong prototype nút này ở màn 2a là tĩnh; logic đã có ở phương án 1b của file design).
- **Hover** (chưa vẽ trong prototype, khuyến nghị): wrapper khoản có tác động `background rgba(204,120,92,.05)`; nút phụ `background #EAE4D6`; nút chính `background #B4633E`.
- **Transition**: overlay `fadeup .16s ease-out`. Không animation nào khác.
- **Responsive**: dưới ~1100px, hai cột đối chiếu xếp dọc (gốc trên, tác động dưới, giữ nền màu khác nhau); dải metadata thành `repeat(2, 1fr)`; dialog `width: calc(100vw - 32px)`.

## State Management
```
modal: string | null      // anchor id của khoản đang mở đối chiếu, vd "26.1"
only:  boolean            // lọc chỉ hiện điều bị tác động
```
Dẫn xuất: `MARKED` = danh sách phẳng các khoản có `mark`, theo thứ tự văn bản → dùng cho số huy hiệu, chỉ số "2 / 4", và điều hướng trước/tiếp.

**Data fetching** — mỗi khoản cần:
```
{ id, cap: 'khoan'|'diem', t,          // địa chỉ neo, cấp, nguyên văn gốc
  mark?: 'sua'|'bai_bo'|'bo_sung',     // loại tác động (nếu có)
  moi?, from?, by? }                   // nội dung sau hợp nhất, ngày hiệu lực, nguồn
```
và, cho cột phải của modal, nguyên văn điều khoản của **văn bản tác động**:
```
{ code, art, text }   // "TT 18/2024/TT-NHNN", "Điều 9. Sửa đổi hạn mức…", nguyên văn
```
Trong repo, `mark`/`by`/`from` map sang quan hệ `tac_dong` đã có trong `web/lib/anchors.ts`; `code/art/text` cần API trả nguyên văn điều khoản nguồn — hiện chưa có, **là việc backend phải bổ sung**.

## Design Tokens
**Màu nền/bề mặt** — `#F0EEE6` (giấy nền), `#FAF9F5` (bề mặt nổi/trang), `#F5F2EA` (thanh phụ, header/footer modal), `#EAE4D6` (chip, nút phụ nhấn), `#E4DFD2` (đường kẻ, viền).
**Chữ** — `#191919` (tiêu đề), `#26241F` (thân), `#6E6A5E` (phụ), `#8A8577` (mờ), `#9C9686` / `#B0A895` (rất mờ), `#D3C6B6` (màu gạch ngang).
**Clay/nhấn** — `#CC785C` (chính), `#B4633E` (sửa đổi), `#8F4A30` (link/mono nhấn), `#A8412F` (bãi bỏ), `#5B7A5B` (bổ sung/hợp lệ). Nền nhạt: `#F7EDE6`, `#F7E7DA`, `#F5E2DC`, `#E7EFE4`, `#E7C9B6` (viền pill).
Tất cả đã có trong `web/app/globals.css` (bảng "Hoa Tiêu Pháp Lý" style 1a) — dùng biến ở đó, không hardcode.

**Typography**
- Thân văn bản luật: `'Newsreader', Georgia, serif` — 16px/1.75 justify, text-indent 28px
- Tiêu đề Điều: Newsreader 17.5px/600; tiêu đề văn bản 17px/500; trích trong modal 14.5–15px/1.72
- UI: `system-ui, -apple-system, 'Segoe UI', sans-serif` — 11px / 11.5px / 12px / 12.5px / 13px
- Eyebrow: 9.5–10px, 600, `letter-spacing .1em`, uppercase
- Mono (số hiệu, ngày, id): `ui-monospace, Menlo, monospace` — 10.5 / 11 / 11.5 / 12.5 / 13.5px

**Spacing** — 2, 3, 4, 6, 8, 9, 11, 12, 14, 16, 18, 22, 26, 28, 30, 34, 36, 46, 90 px
**Radius** — 2 (highlight), 5–6 (chip, huy hiệu), 8–9 (nút, wrapper), 12, 16 (dialog), 999 (pill)
**Shadow** — dialog `0 30px 70px rgba(30,24,16,.34)`; card `0 4px 20px rgba(40,34,24,.07)`
**Cột chữ** — 800px (vùng đọc), 620–680px (các phương án khác), 1000px (dialog)

## Assets
Không có ảnh/icon file. Icon dùng ký tự: `✕ ↑ ↓ ↗ ⎈ ✚ ⌘ ▤ ⎗ ◰ ⚠ ✓`. Khi implement nên thay bằng icon set sẵn có của codebase (lucide-react).
Font **Newsreader** nạp từ Google Fonts (weights 400/500/600 + italic 400/500); trong Next.js dùng `next/font/google` thay vì `<link>`.

Nội dung mẫu là nguyên văn Điều 25–27 Thông tư 40/2024/TT-NHNN, lấy từ `data/fixtures/TT40-2024-dieu{25,26,27}.txt` của repo. Các văn bản tác động (TT 17/2024, TT 18/2024) và nguyên văn điều khoản của chúng là **dữ liệu minh hoạ do thiết kế dựng ra** để thể hiện bố cục — không phải quy định pháp luật có thật, phải thay bằng dữ liệu thật trước khi ship.

## Files
- `Toan Van.dc.html` — file thiết kế. Phương án bàn giao là **2a** (`<section id="t2">`, khối `id="2a"`), ở đầu file. Logic tương ứng trong class `Component`: hằng `SRC`, `MARKED`, biến `groupsE` và nhóm giá trị `m*` (`modalOpen`, `mAddr`, `mCu`, `mSrcText`, `mMoi`, `mMeta`, `prevMark`, `nextMark`…).
- `support.js` — runtime để mở file thiết kế trực tiếp trong trình duyệt. Không liên quan tới sản phẩm.
- Turn 1 trong cùng file (`<section id="t1">`, các khối `1a`–`1d`) là 4 hướng bố cục đã khảo sát: `1a` hiện trạng, `1b` chế độ Đọc/Rà soát + panel phải, `1c` hai cột gốc↔hợp nhất theo mốc thời gian, `1d` bản in + ghi chú lề. Giữ lại làm tham chiếu cho các bước sau (as-of timeline, bộ lọc, minimap) — **không nằm trong phạm vi bàn giao lần này**.

### Trong repo LexFlow
- `web/app/(app)/docs/[docId]/page.tsx` — màn cần thay
- `web/lib/anchors.ts` — slug anchor Điều/Khoản/Điểm, gom nhóm quan hệ `tac_dong`
- `web/app/globals.css` — bảng màu, biến token
- `web/components/page-shell.tsx`, `web/components/app-sidebar.tsx` — khung trang, giữ nguyên
