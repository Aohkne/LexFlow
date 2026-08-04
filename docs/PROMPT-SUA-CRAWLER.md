Bộ crawl vbpl.vn của mình sinh ra hai artefact cho mỗi văn bản: bản ghi thô `<slug>.json` và
bản đã chuyển khuôn `<slug>.corpus.json`. Mình đã đối chiếu output với corpus đang có và tìm ra
bốn khuyết tật. Cần bạn sửa, theo thứ tự ưu tiên dưới đây.

**Bối cảnh để bạn hiểu vì sao nghiêm trọng.** Hệ thống downstream trích các đơn vị tuân thủ ở
**cấp Khoản**, khoá node là `{số hiệu}#than/dieu_{n}#khoan_{m}#diem_{x}`, và có một bất biến về
xuất xứ ở mức ký tự (`văn_bản[start:end] == node.text`). Nghĩa là **số thứ tự khoản/điểm không
phải chuyện trình bày — nó là KHOÁ**. Mất nó là mất cả tầng dưới Điều.

**Văn bản dùng để đối chiếu** là TT 15/2024/TT-NHNN — văn bản duy nhất có mặt ở cả corpus lẫn
bản crawl, nên là chỗ duy nhất so được. Mọi con số dưới đây đo trên nó.

---

## Khuyết tật 1 (NGHIÊM TRỌNG) — `articles[].text` mất sạch đánh số và tiêu đề điều

### Bằng chứng

Chạy bộ tách khoản/điểm lên `articles[].text` của bản crawl:

| nguồn | điều | khoản | điểm |
|---|---|---|---|
| corpus đang có | 22 | 98 | 57 |
| `articles[].text` của bản crawl | 23 | **0** | **0** |

Nhìn cụ thể `Điều 2`:

```text
# corpus (đúng)
Đối tượng áp dụng
1. Tổ chức cung ứng dịch vụ thanh toán bao gồm:
a) Ngân hàng Nhà nước Việt Nam (sau đây gọi là Ngân hàng Nhà nước);
b) Ngân hàng thương mại, ngân hàng chính sách, ngân hàng hợp tác xã, ...

# articles[].text của bản crawl — mất "Đối tượng áp dụng", mất "1.", mất "a)" "b)"
Tổ chức cung ứng dịch vụ thanh toán bao gồm:
Ngân hàng Nhà nước Việt Nam (sau đây gọi là Ngân hàng Nhà nước);
Ngân hàng thương mại, ngân hàng chính sách, ngân hàng hợp tác xã, ...
```

### Vì sao nguy hiểm hơn là "thiếu chính xác"

Nó **hỏng im lặng**. Bộ tách chỉ trả về 0 khoản, mà một điều 0 khoản trông y hệt một điều thật
sự không chẻ khoản — corpus của mình có 25/267 điều đúng là như vậy. Không exception, không cảnh
báo. Nạp vào là mất dữ liệu mà không ai biết.

### Nguyên nhân

`articles[]` đang được sinh bằng cách **làm phẳng cây `provisions`**, và bước làm phẳng chỉ lấy
trường `text` của từng nút, bỏ mất `so` (số thứ tự) lẫn `tieu_de`.

### Cách sửa — sinh `articles[]` từ `noi_dung`, ĐỪNG dựng lại từ cây

`noi_dung` trong `<slug>.json` giữ nguyên đánh số và tiêu đề điều:

```text
Điều 2. Đối tượng áp dụng
1. Tổ chức cung ứng dịch vụ thanh toán bao gồm:
a) Ngân hàng Nhà nước Việt Nam (sau đây gọi là Ngân hàng Nhà nước);
```

Tách theo mẫu `^Điều\s+(\d+)\s*\.\s*(.+)$`, giữ nguyên phần còn lại từng ký tự.

**Đừng** sửa bằng cách nhét lại `so` vào lúc làm phẳng cây — xem khuyết tật 2, cây tự nó đã
thiếu nút nên không cứu được bằng đường đó.

---

## Khuyết tật 2 (VỪA) — cây `provisions` thiếu nút

### Bằng chứng

So số khoản trong cây với số khoản đếm từ `noi_dung`:

| điều | khoản trong cây | khoản thật | thiếu |
|---|---|---|---|
| Điều 3 | 9 | 10 | khoản 10 |
| Điều 6 | 6 | 7 | khoản 5 |
| Điều 7 | 1 | 2 | khoản 2 |
| Điều 12 | 1 | 2 | khoản 2 |
| Điều 19 | 5 | 10 | 5 khoản |
| **tổng** | **88** | **97** | **9** |

Ở `Điều 7`, khoản `1.` và điểm `a) Lập, gửi chứng từ` không có trong cây, và **con của chúng bị
nâng thẳng lên** làm con trực tiếp của Điều — tức cấu trúc bị làm phẳng sai một cấp, chứ không
chỉ thiếu.

### Cần bạn làm

Tìm nguyên nhân ở bước dựng cây từ HTML (nhiều khả năng ở chỗ danh sách lồng nhau, hoặc khoản có
đoạn dẫn dài rồi mới tới điểm). **Kèm một test** so tổng khoản/điểm trong cây với số đếm từ
`noi_dung`, cảnh báo khi lệch — loại lỗi này không tự lộ ra.

### Nhưng ưu tiên thấp hơn khuyết tật 1, vì sau khi sửa 1 thì cây chỉ còn dùng cho

- **Chương/Mục** — chỗ này cây **đang đúng và đủ** (23/23 điều ánh xạ được về Chương). Đây là dữ
  liệu quý: tách `noi_dung` theo Điều thì mất dòng Chương, không có nguồn nào khác bù được.
- `bi_tac_dong` — điều khoản bị tác động, cũng đang dùng được.

---

## Khuyết tật 3 (VỪA) — văn bản không có toàn văn vẫn được ghi như thể có

### Bằng chứng

`29/VBHN-NHNN` (`.../van-ban-hop-nhat-so-29-vbhn-nhnn-...--186078`) ra `articles: []`,
`provisions: []`, `cay_dieu_khoan: []`. vbpl **không đăng toàn văn** cho văn bản này (nhiều khả
năng nằm trong tệp đính kèm).

Chỗ đáng lo hơn: `noi_dung` của nó **không rỗng** mà có 334 ký tự — và nội dung đó là **bảng
thuộc tính**, không phải thân văn bản:

```text
Văn bản hợp nhất số 29/VBHN-NHNN Quy định về hoạt động cung ứng dịch vụ trung gian thanh toán
Số hiệu
29/VBHN-NHNN
Loại văn bản
Văn bản hợp nhất
...
```

Tức bộ đọc đã **lùi về tab thuộc tính** khi không lấy được thân văn bản, mà không nói ra. Một
phép kiểm kiểu `if len(noi_dung) > 100` sẽ cho qua.

### Cần bạn làm

1. Thêm trường tường minh `co_toan_van: bool` vào cả hai artefact. Điều kiện: `noi_dung` phải
   chứa ít nhất một dòng khớp `^Điều\s+\d+\s*\.` — **đừng** dựa vào độ dài.
2. `co_toan_van: false` thì ghi lý do vào `canh_bao`, và **đừng** đặt bảng thuộc tính vào
   `noi_dung` — để rỗng còn trung thực hơn.
3. Cố lấy link tệp đính kèm vào `source_files` (hiện luôn `[]`). Không có thì ghi `canh_bao` nói
   rõ là không có, để phía sau biết phải tìm nguồn khác.

---

## Khuyết tật 4 (VỪA) — panel "điều khoản bị tác động" của vbpl bị nuốt vào thân điều

Đây là khuyết tật mình phát hiện muộn nhất và nó **làm sai cả con số nghiệm thu**, nên đọc kỹ.

### Bằng chứng

vbpl chèn vào trang hai thứ không thuộc văn bản: **dòng nhãn** đánh dấu điều khoản bị tác động,
và ở một số điều là **cả bản sao của các khoản đó**. Cả hai lọt vào `noi_dung`.

`Điều 19` là ca rõ nhất — khoản 1,2,3,8,9 xuất hiện **hai lần**:

```text
 0  Trách nhiệm của tổ chức cung ứng dịch vụ thanh toán
 1  1. Thông báo và hướng dẫn khách hàng sử dụng dịch vụ thanh toán ...
 2  2. Thực hiện giao dịch thanh toán kịp thời, an toàn, chính xác ...
 ...
10  10. Thực hiện các trách nhiệm khác theo quy định tại Thông tư này ...
11  Điều khoản được sửa đổi, bổ sung        <-- nhãn, không thuộc văn bản
12  1. Thông báo và hướng dẫn khách hàng ...  <-- LẶP LẠI dòng 1, y hệt từng ký tự
13  Điều khoản được bổ sung
14  Điều khoản được sửa đổi, bổ sung
15  2. Thực hiện giao dịch thanh toán ...     <-- LẶP LẠI dòng 2
```

Mình đã kiểm: **các bản lặp giống hệt nhau từng ký tự**, không phải "bản cũ vs bản mới". Là lặp
thuần tuý.

Nhưng ở `Điều 3` thì nhãn lại là **dấu đứng ngay trước khoản bị sửa**, và khoản đó **chỉ xuất
hiện một lần**:

```text
10  9. Giao dịch thanh toán qua Mã phản hồi nhanh (QR Code) ...
11  Điều khoản được sửa đổi, bổ sung        <-- nhãn
12  10. Giấy tờ tùy thân bao gồm thẻ căn cước công dân ...   <-- KHÔNG lặp, là nội dung thật
```

⇒ **Không được cắt bỏ mọi thứ từ dòng nhãn trở đi.** Mình đã thử và nó ăn mất nội dung thật.

### Hệ quả lên con số

| phiên bản `noi_dung` | điều | khoản | điểm |
|---|---|---|---|
| nguyên như đang có | 23 | 102 | 57 |
| bỏ dòng nhãn + khử khoản lặp y hệt | 23 | **97** | 57 |

Tức **102 là số bị thổi phồng**, không phải số thật.

### Cần bạn làm

1. **Bỏ các dòng nhãn khỏi `noi_dung`.** Mẫu: dòng đứng riêng khớp `^Điều khoản (được|bị)\s`.
   **Đừng** lọc theo tiền tố `"Điều khoản"` trần — `"Điều khoản thi hành"` là **tiêu đề điều có
   thật**, xuất hiện ở 3 văn bản trong lô này.
2. **Khử khoản lặp**: trong cùng một Điều, dòng khoản `^\d+\.` trùng **y hệt** một dòng đã xuất
   hiện trước đó thì bỏ. Chỉ khi giống hệt — khác một ký tự thì giữ cả hai và ghi `canh_bao`,
   vì lúc đó rất có thể là bản cũ vs bản mới và **không được chọn hộ**.
3. **Giữ lại thông tin đã lọc**, đừng vứt: nhãn cho biết điều khoản nào bị tác động, đó chính là
   thứ `bi_tac_dong` trong cây đang mang. Nếu `bi_tac_dong` chưa có mục tương ứng thì thêm vào.

Số dòng nhãn nằm trong thân điều, để bạn biết quy mô: `40/2024/TT-NHNN` 46 dòng,
`15/2024/TT-NHNN` 28 dòng, `41/2025/TT-NHNN` 3 dòng.

---

## Ba việc nhỏ kèm theo

**a. `doc_id` lệch quy ước corpus.** Bộ crawl sinh `15-2024-TT-NHNN`, corpus dùng `TT15-2024`.
Nạp thẳng vào là **hai node cho một văn bản**. Quy ước corpus, đo từ 11 văn bản ngoại đang có:
`<loại viết ASCII><số>-<năm>` — `101/2012/NĐ-CP` → `ND101-2012`, `15/2024/TT-NHNN` →
`TT15-2024`. Ký hiệu không có năm thì lấy cơ quan làm phần phân biệt: `29/VBHN-NHNN` →
`VBHN29-NHNN`.

**b. Hai artefact đụng nhau khi quét thư mục.** `<slug>.corpus.json` khớp cả glob `*.json`, nên
mọi vòng lặp đọc "bản ghi thô" sẽ nuốt luôn bản đã chuyển khuôn (và cả `crawl-report.json`). Đề
nghị tách thư mục `raw/` và `corpus/`, hoặc đổi đuôi thành `.corpus` không kèm `.json`.

**c. Ba khuyết tật của NGUỒN — báo ra, đừng tự sửa im lặng.**

- Lược đồ `80/2016/NĐ-CP` ghi `"Thông tư số 21/2017/TT- NHNN …"` — **thừa một dấu cách** sau
  gạch nối làm số hiệu bị cắt rời.
- Lược đồ `52/2024/NĐ-CP` có `51/2025/TT-BTС` với `С` là **Cyrillic** (U+0421), không phải `C`
  Latin.
- `Điều 14` của TT15/2024 viết `3.Dịch vụ thu hộ và dịch vụ chi hộ` — **thiếu dấu cách** sau dấu
  chấm, làm bộ tách khoản của mình bỏ sót đúng khoản đó.

Phía mình đã xử lý cả ba. Chỉ cần bạn **giữ nguyên như nguồn** và ghi vào `canh_bao` nếu phát
hiện được — chuẩn hoá im lặng ở tầng crawl thì phía sau không còn cách nào biết nguồn đã sai.

---

## Ràng buộc

- **Không đổi nội dung chữ trong `noi_dung`**, ngoài việc bỏ nhãn và khoản lặp ở khuyết tật 4.
  Bất biến `char_span` ở downstream neo vào nó từng ký tự.
- Mỗi khuyết tật kèm ít nhất một test dùng **file thật đã crawl**, không dùng dữ liệu bịa.
- Sau khi sửa, chạy lại trên TT15/2024 và báo cáo: phải ra **23 điều / 97 khoản / 57 điểm**, và
  `chapter` điền đủ **23/23**.
- Con số kiểm chéo cho các văn bản khác trong lô (sau khi làm sạch): `52/2024/NĐ-CP` 38 điều /
  153 khoản / 102 điểm · `40/2024/TT-NHNN` 54 / 193 / **216** *(sửa: bản trước tôi ghi 218 —
  sai, vì phép khử trùng lúc đo chỉ xử lý dòng khoản mà bỏ sót dòng điểm; Điều 37 khoản 1 có
  điểm `đ` và `i` lặp)* · `41/2025/TT-NHNN` 27 / 46 / 13 ·
  `66/2025/TT-NHNN` 16 / 20 / 25 · `22/2026/TT-NHNN` 6 / 12 / 19 · `16/2019/NĐ-CP` 7 / 14 / 1 ·
  `80/2016/NĐ-CP` 3 / 14 / 7. Nếu số của bạn khác, **đừng chỉnh cho khớp** — báo lại để mình
  cùng xem, vì có thể mình sai.

## Một điều KHÔNG cần sửa

Cấp **tiết** (`(i)`, `(ii)`) không có trong cây, và điều đó **đúng như mong muốn** — đừng thêm.
Phía mình mô hình hoá tiết như một *span* bên trong văn bản của Điểm chứ không cấp id riêng (đo
được: chỉ 4/586 viện dẫn đi tới cấp này, và cả 4 đều thuộc văn bản đã hết hiệu lực). Chỉ cần
`noi_dung` giữ nguyên chuỗi `(i)`, `(ii)` là đủ — riêng TT15/2024 có 38 chỗ như vậy.

## Một điều nên biết: corpus của mình đang SAI ở chỗ bản crawl đúng

Nói ra để bạn không tưởng corpus là chuẩn mực. Corpus cũ của mình **không có `Điều 19`**, và
`Điều 18` của nó có **15 khoản** — vì bộ tách cũ bỏ sót dòng `Điều 19.` và dán toàn bộ nội dung
Điều 19 vào đuôi Điều 18 (5 khoản thật của Điều 18 + 10 khoản của Điều 19 = 15). `noi_dung` của
bạn tách đúng thành 5 và 10.

Corpus cũ còn một lỗi nữa mà `noi_dung` không mắc: mỗi liên kết viện dẫn bị tách thành một dòng
riêng, làm một câu vỡ vụn —

```text
2. Quỹ tín dụng nhân dân ... không qua tài khoản thanh toán ...
Điều 10
,
Điều 11
và
khoản 2 Điều 12 Thông tư này
.
```

`noi_dung` giữ nguyên một dòng liền. Đúng, và đừng đổi.
