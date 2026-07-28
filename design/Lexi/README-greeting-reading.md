# Bổ sung: hai trạng thái `greeting` và `reading`

Ghi chú riêng cho hai trạng thái vừa thêm. Toàn bộ ngữ cảnh (bảng 7 trạng thái, token màu, cách nhúng, quy tắc "hoạt ảnh nằm trong `lexi.css` chứ không trong `.svg`") xem `README.md`.

## Cần lấy những gì

| File | Thay đổi |
|---|---|
| `assets/lexi.css` | thêm `.lexi-hop`, `.lexi-wave`, `.lexi-read` + 3 keyframes `lexiHop` / `lexiWave` / `lexiRead` |
| `reference/Lexi.tsx` | thêm 2 nhánh `state === 'greeting'` và `state === 'reading'`, 2 helper `<WavingWing>` và `<Book>`, `lexiState()` nhận cờ `reading` |
| `assets/lexi-greeting.svg` | bản tĩnh |
| `assets/lexi-reading.svg` | bản tĩnh |

## `greeting` — chào hỏi

```tsx
<Lexi state="greeting" size={88} />
```

**Hình**: đầu clay `#CC785C`, mắt nheo cười (cung `M34 63 q10 -13 20 0`), chân mày cong lên `#B4633E`, thêm một cánh `ellipse cx=97 cy=74 rx=8.5 ry=17` màu `#B4633E` nghiêng tĩnh 8°.

**Chuyển động**: hai lớp độc lập.
- `.lexi-hop` trên nhóm đầu — nhún 1.9s, `transform-origin: 50% 100%`, đỉnh `translateY(-3.2px)` ở 38%.
- `.lexi-wave` trên nhóm cánh — vẫy 0.62s, `transform-origin: 50% 100%` (gốc vai), `rotate(-8deg)` → `rotate(16deg)`.

**Ba điều dễ làm sai:**
1. Cánh phải vẽ **trước** `<Head>` trong DOM, nếu không nó che mặt.
2. Phép nghiêng tĩnh 8° phải nằm trên `<ellipse>`, **không** trên `<g class="lexi-wave">` — CSS animation ghi đè `transform` của chính phần tử đó.
3. **Không tăng biên độ vẫy.** viewBox chỉ rộng 120; quá ~16° là đầu cánh bị cắt ở mép phải. Muốn vẫy mạnh hơn thì phải nới viewBox của **tất cả** trạng thái để 8 file cùng cỡ.

**Dùng ở đâu**: màn chào sau đăng nhập, bước đầu onboarding, cỡ 72–96px. **Chỉ một lần** — khối Pháp chế dùng công cụ này hằng ngày, chào lại mỗi lần mở app là phiền. Đi kèm một câu giới thiệu + nút bắt đầu.

`greeting` **không** nằm trong `lexiState()`: nó do sản phẩm chủ động chọn, không suy ra từ request.

## `reading` — đọc sách

```tsx
<Lexi state="reading" size={64} />
```

**Hình**: đầu clay, đĩa mặt `cy=60`, mắt hạ xuống `cy=63` (đang nhìn vào trang), chân mày phẳng `y=40`, mỏ `M60 72 L68 83 L60 90 L52 83 Z`. Sách mở **nâng ngang mỏ** (y 88–113), che phần dưới mặt:

- bìa (vẽ trước): 2 path `#E0C39F` — `M60 90 Q40 84 20 90 L25 111 Q43 106 60 113 Z` và bản đối xứng
- hai trang: `#FAF9F5` viền `#D8CFBB` 2px — `M60 88 Q41 82 22 88 L26 108 Q43 103 60 110 Z` và bản đối xứng
- dòng chữ: `M30 93 h18 M31 98 h14` và `M72 93 h18 M75 98 h14`, stroke `#D8CFBB` 1.8px
- gáy: `M60 88 V110`

**Chuyển động**: chỉ mắt. `.lexi-read` trên nhóm 2 mắt — 5.4s, `steps(1, end)`, rà 3 dòng: `translate(-3px,1px)` → `(3px,1px)` → `(-3px,2.2px)` → `(3px,2.2px)` → `(-3px,3.4px)` → `(3px,3.4px)` → về dòng đầu.

`steps(1, end)` là cố ý: mắt phải **nhảy dòng dứt khoát** như người đọc thật, không trôi mượt.

**Đã thử rồi bỏ**: hiệu ứng lật trang. Ở cỡ 40–64px nó chỉ nhoè thành một vệt nhấp nháy và làm trang phải trông trắng trơn. Đừng thêm lại.

**Dùng ở đâu**: tác vụ dài có thật — màn **Kiểm tra tài liệu** đang đối chiếu tài liệu nội bộ với các văn bản, hoặc đang lập chỉ mục. Cỡ 48–72px, đặt cạnh thanh progress và dòng "Đang đối chiếu n văn bản…".

**Phân biệt với `searching`**: `searching` cho tra cứu vài giây (chỉ có mắt đảo, không có sách); `reading` cho tác vụ hàng chục giây. **Không dùng `reading` dưới 40px** — quyển sách sẽ biến mất.

Trong `lexiState()`:

```tsx
lexiState({ isLoading: true, reading: true })   // → 'reading'
lexiState({ isLoading: true })                  // → 'searching'
```

## Nghiệm thu

Mở `preview.html`. Hàng 1 (SVG inline + `lexi.css`) có 7 thẻ, thẻ **Chào hỏi** đầu tiên và **Đọc sách** thứ tư — cả hai phải chuyển động. Hàng 2 là 8 file `.svg` qua `<img>`, tĩnh là đúng.
