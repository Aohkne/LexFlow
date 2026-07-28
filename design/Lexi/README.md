# Handoff: Lexi — linh vật trợ thủ AI của LexFlow

## Overview

Lexi là linh vật đại diện cho trợ thủ AI trong sản phẩm **Hoa Tiêu Pháp Lý (LexFlow)** — trợ lý tra cứu pháp luật cho khối Pháp chế & Tuân thủ ngân hàng. Hình tượng là **một con cú**: biểu tượng quen thuộc của trí tuệ và sự phán đoán, và khối tròn của nó vẫn đọc được khi thu nhỏ thành avatar 16px.

Lexi có **7 trạng thái** khớp với các pha của luồng hỏi đáp, mỗi trạng thái một màu và một chuyển động riêng, cộng thêm **1 bản tĩnh** cho favicon/avatar nhỏ:

| Trạng thái | Khi nào | Màu thân | Chuyển động |
|---|---|---|---|
| `idle` | chưa hỏi gì, màn rỗng | clay `#CC785C` | nghiêng đầu qua lại, chớp mắt kép mỗi 4.4s |
| `greeting` | onboarding, sau khi đăng nhập, lần đầu vào app | clay `#CC785C` | nhún nhẹ 1.9s + vẫy cánh 0.62s, mắt nheo cười |
| `searching` | đang gọi API trả lời (tra cứu nhanh) | clay `#CC785C` | mắt đảo tìm quanh trang (ngang + dọc), 4.2s |
| `reading` | đang đọc/đối chiếu văn bản dài — màn Kiểm tra tài liệu | clay `#CC785C` | sách nâng ngang mỏ; mắt rà 3 dòng (`steps`), 5.4s |
| `found` | trả lời xong, nguồn còn hiệu lực | sage `#5B7A5B` | gật nhẹ liên tục + dấu tích bật ra một lần |
| `conflict` | phát hiện mâu thuẫn giữa các văn bản | clay đậm `#B4633E` | lắc đầu + chấm than bật ra một lần |
| `error` | lỗi hệ thống: API thất bại, hết phiên, không tra được | xám `#9C9686` | đầu rũ xuống + dấu ✕ đỏ bật ra một lần |
| `static` | favicon, chip ≤20px, OG image, email | clay `#CC785C` | không có (tĩnh) |

## About the Design Files

Các file trong bundle này là **thiết kế tham chiếu**, không phải production code phải copy nguyên trạng — **trừ thư mục `assets/`, đó là asset thật, dùng được ngay**.

- `assets/lexi.css` — **asset sản xuất**, chứa toàn bộ hoạt ảnh. Copy vào `web/components/`.
- `assets/*.svg` — **asset sản xuất**, bản tĩnh. Copy vào `web/public/lexi/`.
- `reference/Lexi.tsx` — component có chuyển động (SVG inline + class từ `lexi.css`). Đọc, rồi viết lại theo pattern của repo (đường dẫn, naming, lint rule). Kèm helper suy ra trạng thái từ luồng hỏi đáp.
- `reference/LexFlow Anthropic v2.dc.html` — prototype màn Tra cứu **đã ghép Lexi vào**, để xem đặt ở đâu, cỡ bao nhiêu. Mở bằng browser. Đây là HTML prototype, không phải code để copy.
- `reference/Lexi 3D.html` + `three-d-stage.js` — bản 3D của Lexi (three.js), dùng làm nguồn tham chiếu hình khối và để xuất OBJ/GLB nếu cần dựng ảnh render. Không cần đưa vào web app.
- `reference/Lexi mascot explorations.dc.html` + `support.js` — canvas thiết kế gốc: 4 hướng hình linh vật đã cân nhắc (con dấu / kim hoa tiêu / thẻ đánh dấu / dấu trích dẫn), lý do chọn con cú, và 5 trạng thái đặt cạnh nhau. Mở bằng browser, dùng để hiểu ý định thiết kế — không phải code để copy.
- `preview.html` — **mở file này trước tiên** để nghiệm thu: hàng trên phải chuyển động, hàng dưới tĩnh.
- `README-greeting-reading.md` — ghi chú chi tiết cho hai trạng thái mới nhất (`greeting`, `reading`): toạ độ hình, nhịp, và ba lỗi dễ mắc khi dựng lại.

Nhiệm vụ: đưa `lexi.css` + component Lexi vào `web/` (Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4) và gắn vào luồng hỏi đáp ở màn Tra cứu. Backend Python đã có sẵn (`app/api`, `app/reasoning`) — Lexi chỉ đọc trạng thái của request, không gọi API nào.

## Fidelity

**High-fidelity (hifi).** Hình dạng, màu, nhịp hoạt ảnh đều là giá trị cuối. Hình và hoạt ảnh đều là asset thật nên không cần dựng lại — chỉ cần nhúng đúng cách và gắn đúng trạng thái.

## ⚠ Đọc phần này trước — hoạt ảnh nằm ở đâu

Đây chính là điểm đã làm Claude Code báo "file không có hiệu ứng".

**Hoạt ảnh KHÔNG nằm trong file `.svg`. Nó nằm trong `assets/lexi.css`.**

Lý do: mọi cách nhúng hoạt ảnh vào bên trong một file `.svg` đều dễ bị mất trên đường đi —
`<style>` + `@keyframes` bị SVGR lược bỏ theo cấu hình mặc định; `next/image` có thể bỏ qua
hoặc rasterise SVG; và một số pipeline sanitise cả thẻ SMIL (`<animateTransform>`).
Đặt hoạt ảnh trong một file `.css` thật thì không công cụ nào chạm tới nó.

Vì vậy bundle này chia làm hai phần rõ ràng:

| Thành phần | Có chuyển động? | Dùng cho |
|---|---|---|
| `assets/*.svg` (8 file) | **Không** — tĩnh, có chủ ý | favicon, OG image, email, slide, chip ≤20px |
| `reference/Lexi.tsx` + `assets/lexi.css` | **Có** | mọi chỗ trong web app |

**Ba quy tắc bắt buộc:**
1. Muốn có chuyển động trên web → dùng **component SVG inline** (`Lexi.tsx`) và `import './lexi.css'`. Đừng mong `<img src="lexi-idle.svg">` tự nhúc nhích — nó tĩnh, và đó là thiết kế.
2. **Không dùng `next/image`** cho các file SVG này. Dùng `<img>` thường nếu chỉ cần ảnh tĩnh.
3. Nếu import SVG qua SVGR, không cần lo mất hoạt ảnh nữa — trong file không còn hoạt ảnh để mất.

Mở `preview.html` để thấy đúng sự phân chia này: hàng trên (inline + CSS) chuyển động, hàng dưới (`<img>`) tĩnh.

## Cách nhúng

### A. Có chuyển động — component inline (dùng trong app)

```bash
cp reference/Lexi.tsx web/components/Lexi.tsx
cp assets/lexi.css  web/components/lexi.css
```

```tsx
import { Lexi } from '@/components/Lexi';   // Lexi.tsx đã tự import './lexi.css'

<Lexi state="searching" size={30} />
```

Đổi trạng thái = đổi prop `state`. Đổi màu = sửa hằng `C` trong component.

### B. Tĩnh — file trong `/public`

```bash
mkdir -p web/public/lexi && cp assets/*.svg web/public/lexi/
```

```tsx
<img src="/lexi/lexi-avatar.svg" alt="" aria-hidden width={20} height={20} />
```

Dùng cho favicon, chip nhỏ, ảnh chia sẻ — chỗ không cần chuyển động.

### Gắn vào luồng hỏi đáp

```tsx
import { Lexi, lexiState } from '@/components/Lexi';

<Lexi state={lexiState({ isLoading, reading, hasError, hasConflict, hasAnswer })} size={30} />
```

Thứ tự ưu tiên trong `lexiState()`: đang tải → `reading` nếu là tác vụ dài, ngược lại `searching` → `error` (request thất bại) → `conflict` (có mâu thuẫn) → `found` (đã có câu trả lời) → `idle`. `greeting` truyền tay, không qua hàm này.

## Screens / Views — Lexi đặt ở đâu

Xem trực quan trong `reference/LexFlow Anthropic v2.dc.html` (màn Tra cứu).

### 1. Avatar cạnh câu trả lời — màn Tra cứu

- **Vị trí**: đầu khối trả lời, bên trái, `flex: none`, `margin-top: 1px`, `gap: 10px` với phần nội dung.
- **Cỡ**: 30×30 px.
- **Trạng thái**: `searching` khi đang stream/chờ API, đổi sang `found` hoặc `conflict` khi có kết quả.
- **Đi kèm**: ngay sau avatar là hàng meta — tên **"Lexi"** (11.5px, weight 600, `#33302A`) rồi tới các pill tin cậy ("2 nguồn đang hiệu lực", "⚠ 1 mâu thuẫn") và mono "tra tại dd/mm/yyyy".

### 2. Trạng thái rỗng — màn Tra cứu

- **Vị trí**: giữa cột thread, `text-align: center`, trên tiêu đề h1.
- **Khung**: ô 96×96, `border-radius: 26px`, nền `#F7EDE6`, viền `1px solid #E7C9B6`, `display: inline-grid; place-items: center`.
- **Lexi**: `<Lexi state="searching" size={66} />` (mắt đảo tìm — tạo cảm giác "đang chờ bạn hỏi").
- **Dưới đó**: h1 serif 27px "Hỏi về quy định — nhận câu trả lời truy được nguồn".

### 3. Chip / dòng trạng thái

- **Cỡ**: 16–20px, dùng `state="static"` hoặc `lexi-avatar.svg` — dưới 24px chuyển động chỉ gây nhiễu.
- Ví dụ: chip "Lexi đang theo dõi 4 văn bản" — pill `#FAF9F5`, viền `#E4DFD2`, radius 999, padding `5px 12px 5px 7px`, gap 7px.

### 4. Favicon

```bash
cp assets/lexi-avatar.svg web/public/icon.svg
```
Next.js App Router tự nhận `app/icon.svg`. Cần `.ico` cho trình duyệt cũ thì convert từ file này.

### 5. Không dùng Lexi ở đâu


- **Logo sidebar**: giữ nguyên mark `⎈` hiện tại. Linh vật và logo nên tách vai — linh vật đại diện AI, logo đại diện sản phẩm.
- Không đặt Lexi cạnh cảnh báo mâu thuẫn để **thay** cho cảnh báo. Biểu cảm là phụ trợ, thông tin pháp lý vẫn phải là chữ.

### 6. Trạng thái chào hỏi

- **Dùng khi**: màn chào sau đăng nhập, bước đầu onboarding, hoặc lần đầu người dùng mở màn Tra cứu. **Chỉ một lần** — không chào lại mỗi lần vào app, khối Pháp chế dùng công cụ này hằng ngày.
- **Cỡ**: 72–96px (đây là lúc duy nhất Lexi được to).
- **Đi kèm**: một câu giới thiệu ngắn + nút bắt đầu. Ví dụ "Tôi là Lexi. Hỏi tôi bất kỳ điều gì về quy định — mọi câu trả lời đều kèm điều khoản gốc."
- **Lưu ý kỹ thuật**: cánh nâng **lên** cạnh đầu (`cy=72`, nghiêng 14°) và quay quanh gốc vai (`transform-origin: 50% 100%`) nên đọc ra là vẫy tay, không phải cánh xệ. Phép nghiêng tĩnh đặt trên `<ellipse>`, animation trên `<g>` bọc ngoài — không ghi đè nhau. Cánh vẽ trước `<Head>` để không che mặt. Nhịp vẫy 0.62s lệch với nhịp nhún 1.9s nên động tác không máy móc. **Biên độ vẫy giữ nhỏ (−8°…+16°)**: viewBox chỉ rộng 120, vung mạnh hơn là đầu cánh bị cắt ở mép phải.

### 7. Trạng thái đọc sách

- **Dùng khi**: tác vụ dài có thật — màn **Kiểm tra tài liệu** đang đối chiếu tài liệu nội bộ với các văn bản, hoặc đang lập chỉ mục văn bản mới. Phân biệt với `searching`: `searching` cho tra cứu vài giây, `reading` cho tác vụ hàng chục giây.
- **Cỡ**: 48–72px, đặt trong khối tiến trình cùng thanh progress và dòng "Đang đối chiếu n văn bản…".
- **Chi tiết hình**: sách mở nâng lên **ngang mỏ** (y 88–113), che phần dưới mặt — đọc ra ngay là đang cầm sách đọc. Mắt hạ xuống `cy=63`. Sách vẫn nhỏ ở cỡ bé, đừng dùng `reading` dưới 40px.
- **Nhịp**: chỉ mắt động — rà 3 dòng bằng `steps(1, end)` (nhảy dòng dứt khoát, không trôi) rồi quay về dòng đầu. Sách đứng yên: thử hiệu ứng lật trang rồi bỏ, ở cỡ nhỏ nó chỉ nhoè thành một vệt nhấp nháy.

### 8. Trạng thái lỗi

- **Dùng khi**: gọi `POST /ask` thất bại, mất mạng, hết phiên đăng nhập, backend trả 5xx — **không** dùng cho mâu thuẫn pháp lý (đó là `conflict`).
- **Phân biệt bằng màu**: `error` xám kiệt `#9C9686` + badge đỏ `#A8412F`; `conflict` clay đậm + badge cam. Người dùng nhìn màu là biết đây là lỗi hệ thống, không phải phát hiện pháp lý.
- **Kèm chữ, luôn luôn**: Lexi rũ đầu chỉ là tín hiệu. Bên cạnh phải có thông báo cụ thể + nút "Thử lại". Không bao giờ để linh vật thay cho thông báo lỗi.
- **Cỡ**: 40–66px trong khối lỗi giữa thread; 30px nếu lỗi hiển thị inline cạnh câu hỏi.

## Interactions & Behavior

| Việc | Chi tiết |
|---|---|
| Chuyển trạng thái | Đổi prop `state`. Không cần transition — mỗi trạng thái là một hoạt ảnh độc lập. |
| `found` / `conflict` phát lại | Badge dùng `animation-fill-mode: both`, chạy **một lần**. Muốn chạy lại cho câu trả lời mới thì remount bằng `key`: `<Lexi key={answerId} state="found" />`. |
| `idle` / `greeting` / `searching` / `reading` | Lặp vô hạn. |
| Số lượng | Chỉ **một** Lexi động trên màn hình một lúc. Nhiều con cùng nhúc nhích là nhiễu thị giác. |
| Ngưỡng cỡ | Dưới 24px: dùng bản tĩnh `avatar`. |
| `prefers-reduced-motion` | Đã xử lý sẵn trong `lexi.css`: khi user tắt hiệu ứng thì mọi animation bị vô hiệu và badge vẫn hiện đầy đủ. Không cần code thêm. |
| Accessibility | Mặc định `decorative` = true → `aria-hidden`, vì cạnh Lexi thường đã có chữ ("Lexi", "Đang đối chiếu…"). Truyền `decorative={false}` khi Lexi đứng một mình và mang nghĩa; lúc đó component tự gắn `role="img"` + `aria-label` tiếng Việt. |

## State Management

Không có state riêng. Lexi là **thuần hàm của state sẵn có** ở màn Tra cứu:

```ts
type LexiState =
  | 'idle' | 'greeting' | 'searching' | 'reading'
  | 'found' | 'conflict' | 'error' | 'static';

// lexiState() suy ra từ:
isLoading    // đang gọi POST /ask
reading      // tác vụ dài (POST /reviews) thay vì tra cứu nhanh → 'reading'
hasError     // request thất bại / hết phiên / backend trả lỗi
hasConflict  // response.conflicts.length > 0
hasAnswer    // đã có response.answer

// 'greeting' KHÔNG suy ra từ request — sản phẩm chủ động chọn:
//   lần đầu onboarding, ngay sau khi đăng nhập, màn chào mừng.
```

Không thêm state mới, không lưu localStorage.

## Design Tokens

Toàn bộ màu Lexi đều đã có trong bảng màu LexFlow — không màu nào là mới:

| Vai trò | Hex | Dùng ở đâu trong Lexi |
|---|---|---|
| clay | `#CC785C` | thân `idle` / `searching` / `avatar`, viền badge cảnh báo |
| clay đậm | `#B4633E` | thân `conflict`, vành mắt, chân mày `idle`/`searching` |
| clay tối | `#8F4A30` | chân mày cau của `conflict` |
| xám kiệt | `#9C9686` | thân `error` |
| xám nhạt | `#F0EDE5` | đĩa mặt `error` |
| xám chữ | `#6E6A5E` | chân mày `error` |
| xám mỏ | `#D8CFBB` | mỏ `error` |
| đỏ | `#A8412F` | dấu ✕ và viền badge `error` |
| wash đỏ | `#F7E6E1` | nền badge `error` |
| sage | `#5B7A5B` | thân `found`, dấu tích |
| kem | `#FAF9F5` | đĩa mặt, điểm sáng trong mắt |
| mực | `#26241F` | con mắt, nét mắt nheo cười |
| mỏ | `#E0C39F` | mỏ |
| wash xanh | `#EAF0E7` | nền badge dấu tích |
| wash cam | `#F7EDE6` | nền badge cảnh báo, khung trạng thái rỗng |
| viền wash cam | `#E7C9B6` | viền khung trạng thái rỗng |

**Kích thước**: 16 / 20 / 30 / 40 / 66 px (viewBox luôn `0 0 120 120`).
**Radius khung chứa**: 26px cho ô 96px ở trạng thái rỗng.
**Nhịp hoạt ảnh** (định nghĩa trong `assets/lexi.css`): sway 3.4s · blink 4.4s · search 4.2s · read 5.4s · hop 1.9s · wave 0.62s · nod 1.6s · shake 2.6s · droop 2.8s · pop 0.5s (`cubic-bezier(.3,1.4,.5,1)`, delay 0.3s).
**Easing**: `ease-in-out` cho mọi vòng lặp, trừ `lexiRead` dùng `steps(1, end)` để mắt nhảy dòng dứt khoát thay vì trôi mượt.

## Assets

| File | Nội dung | Ghi chú |
|---|---|---|
| `assets/lexi-idle.svg` | Lexi sẵn sàng | tĩnh, viewBox 120×120 |
| `assets/lexi-greeting.svg` | Lexi chào hỏi, cánh nâng | tĩnh |
| `assets/lexi-searching.svg` | Lexi đang tra (mắt lệch trái trên) | tĩnh |
| `assets/lexi-reading.svg` | Lexi đọc sách mở | tĩnh |
| `assets/lexi-found.svg` | Lexi có nguồn + dấu tích | tĩnh, badge hiện sẵn |
| `assets/lexi-conflict.svg` | Lexi có mâu thuẫn + cảnh báo | tĩnh, badge hiện sẵn |
| `assets/lexi-error.svg` | Lexi gặp lỗi + dấu ✕ | tĩnh, badge hiện sẵn |
| `assets/lexi-avatar.svg` | Bản tròn, dùng làm favicon | tĩnh |
| `assets/lexi.css` | **Toàn bộ hoạt ảnh** | đi kèm `Lexi.tsx` |

Không có bitmap, không font riêng, không icon set ngoài. Toàn bộ là path/circle/ellipse/rect thuần, hoạt ảnh bằng CSS transform (không dùng filter, không dùng JS).

Cần PNG (ảnh chia sẻ mạng xã hội, slide)? SVG là đủ cho web — nói kích thước cần thì designer xuất thêm.

## Files

```
design_handoff_lexi_mascot/
├── README.md                              ← tài liệu này
├── README-greeting-reading.md              ← ghi chú riêng 2 trạng thái mới nhất
├── preview.html                           ← MỞ TRƯỚC: nghiệm thu hoạt ảnh
├── assets/                                ← ASSET SẢN XUẤT
│   ├── lexi.css                           ← hoạt ảnh (→ web/components/lexi.css)
│   ├── lexi-idle.svg                      ← 8 SVG TĨNH (→ web/public/lexi/)
│   ├── lexi-greeting.svg
│   ├── lexi-searching.svg
│   ├── lexi-reading.svg
│   ├── lexi-found.svg
│   ├── lexi-conflict.svg
│   ├── lexi-error.svg
│   └── lexi-avatar.svg
└── reference/                             ← tham chiếu, không copy nguyên trạng
    ├── Lexi.tsx                           ← component có chuyển động + helper lexiState()
    ├── LexFlow Anthropic v2.dc.html       ← màn Tra cứu đã ghép Lexi
    ├── Lexi mascot explorations.dc.html   ← canvas 4 hướng hình + 5 trạng thái
    ├── Lexi 3D.html                       ← bản 3D (three.js), xuất OBJ/GLB
    ├── three-d-stage.js                   ← runtime cho file 3D
    └── support.js                         ← runtime cho 2 file .dc.html
```

## Thứ tự triển khai

1. Mở `preview.html`: hàng trên phải chuyển động, hàng dưới tĩnh. Nếu hàng trên không chạy thì `lexi.css` chưa được load.
2. `cp assets/lexi.css web/components/` và `cp reference/Lexi.tsx web/components/` — sửa theo naming/lint của repo.
3. `cp assets/*.svg web/public/lexi/` và `cp assets/lexi-avatar.svg web/app/icon.svg`.
4. Gắn vào màn Tra cứu: `<Lexi size={30} />` cạnh câu trả lời + `<Lexi size={66} />` ở trạng thái rỗng.
5. Nối `hasError` vào nhánh catch của request `POST /ask`, kèm thông báo lỗi + nút "Thử lại".
6. Kiểm tra lại sau khi `next build` (không chỉ ở dev): CSS global/module có được load đúng không.

## Nếu cần dựng lại hình từ đầu

Toàn bộ hình Lexi là hình học thuần trên viewBox `0 0 120 120`, không có path phức tạp:

- **túm tai**: 2 tam giác `M40 44 L44 22 L54 40 Z` và bản đối xứng
- **đầu**: `circle cx=60 cy=66 r=42`
- **đĩa mặt**: 2 `ellipse rx=20 ry=22` tại `cx=44` và `cx=76`, `cy=60`
- **mắt**: vành `circle r=12.5` stroke 3 + con mắt `circle r=9` + điểm sáng `circle r=2.8` lệch `(-3.5,-3.5)`
- **mỏ**: `M60 71 L68 82 L60 89 L52 82 Z` (hình thoi)
- **chân mày**: `rect w=27 h=4.6 rx=2.3` — xoay ±15° (bình thường), ±19° và hạ xuống (cau giận), hoặc thay bằng cung `q13 -6 26 3` (cong lên, thân thiện)
- **badge trạng thái**: `circle r=17` stroke 2.5 ở góc phải trên (`cx≈96 cy≈29`), bên trong là dấu tích / chấm than / dấu ✕
- **mắt cười**: thay 2 mắt bằng cung `M34 63 q10 -13 20 0`
- **mắt lỗi**: thay 2 mắt bằng gạch ngang `M35 60 h18` stroke 4.4
