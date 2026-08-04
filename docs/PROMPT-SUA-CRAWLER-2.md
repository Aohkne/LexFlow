Lô crawl vừa rồi **dữ liệu đúng** — mình đã kiểm độc lập, không lấy báo cáo làm bằng:

- `noi_dung[char_start:char_end] == articles[].text` — **8/8 văn bản, 100% số điều**. Đây đúng
  là bất biến xuất xứ mà hệ thống mình dựa vào, và giờ nguồn tự bảo đảm nó.
- Số điều/khoản/điểm khớp bảng nghiệm thu **7/8**. Ca lệch duy nhất là `40/2024/TT-NHNN`:
  216 điểm chứ không phải 218 — và **con số 218 là của mình sai**, vì lúc đo mình khử trùng
  dòng khoản `^\d+\.` mà quên dòng điểm `a)`. Bên bạn làm đủ hơn. Không phải sửa gì.
- `doc_id` đã theo quy ước corpus (`ND80-2016`, `VBHN29-NHNN`). Đúng rồi.

Chỉ còn **hai câu cảnh báo mô tả sai bản chất**, và một trong hai **nói ngược**. Dữ liệu không
phải sửa, chỉ sửa cách diễn giải.

---

## Vấn đề: khối trích dẫn trong văn bản sửa đổi

Một văn bản sửa đổi luôn **chép nguyên văn nội dung mới** vào giữa hai dấu ngoặc kép. Nội dung
được chép mang **đánh số của văn bản BỊ sửa**, không phải của văn bản đang đọc.

`80/2016/NĐ-CP` Điều 1 là ca rõ nhất:

```text
1. Sửa đổi, bổ sung khoản 4, 5, 6, 7, 8 Điều 4 như sau:      ← khoản 1 CỦA ND80
"4. Tổ chức cung ứng dịch vụ trung gian thanh toán là: ...
 5. Chủ tài khoản thanh toán ...                              ← khoản 5 của ND101, ĐƯỢC CHÉP
 6. Phương tiện thanh toán không dùng tiền mặt ...             ← khoản 6 của ND101
 7. Phương tiện thanh toán không hợp pháp ...
 8. Dịch vụ ví điện tử là ..."
2. Bổ sung khoản 6 Điều 6 như sau: ...                        ← khoản 2 CỦA ND80
...
5. Sửa đổi điểm b khoản 2 Điều 12 như sau:                    ← khoản 5 CỦA ND80
6. Bãi bỏ điểm c khoản 2 Điều 12.
7. Sửa đổi khoản 3 Điều 14 như sau:
8. Sửa đổi, bổ sung điểm a, b, đ, e, g, h khoản 2 Điều 15 như sau:
```

Nên số 5, 6, 7, 8 xuất hiện hai lần — nhưng là **hai văn bản khác nhau**, không phải hai phiên
bản của một khoản.

**Việc tách khối trích dẫn là của phía mình, không phải của bạn.** Dấu ngoặc kép là của chính
đạo luật; bỏ nó đi là sửa văn bản gốc và làm mất nghĩa của một văn bản sửa đổi. Bạn giữ nguyên
như đang làm là đúng. Chỉ cần sửa hai chỗ **diễn giải** dưới đây.

---

## Sửa 1 — cảnh báo "cần người đọc quyết bản nào đang hiệu lực"

### Hiện tại

```json
"Điều 1: khoản 5 xuất hiện 2 lần với nội dung KHÁC nhau — giữ cả hai,
 cần người đọc quyết bản nào là bản đang hiệu lực"
```

### Vì sao sai

Không có gì để quyết. Một cái là khoản của ND80, một cái là nội dung của ND101 được chép vào.
Cảnh báo này tạo ra **việc rà soát giả** — người đọc mở ra, mất mười phút, rồi phát hiện không
có câu hỏi nào cả. Vài lần như thế là người ta ngừng đọc cảnh báo, và lúc đó cảnh báo thật cũng
chết theo.

Lưu ý: luật gốc **rất hiếm khi** có hai bản của cùng một khoản đặt cạnh nhau. Ca đó đáng cảnh
báo thật — nhưng phải là ca **cả hai đều nằm ngoài ngoặc kép**.

### Cần làm

Trước khi so trùng, đánh dấu ký tự nào đang nằm trong ngoặc kép. Chỉ so trùng giữa các dòng
**cùng ở ngoài ngoặc**.

- Số trùng mà một trong hai ở trong ngoặc ⇒ **không cảnh báo** (chuyện bình thường của văn bản
  sửa đổi).
- Số trùng mà **cả hai đều ngoài ngoặc** ⇒ vẫn cảnh báo như cũ, giữ nguyên câu chữ.

Ký tự cần xử lý, đo trên chính lô này: `"` (đảo trạng thái), `“` (mở), `”` (đóng). Mình đã kiểm
**ngoặc cân 100%** ở cả 9 văn bản — `"` luôn chẵn, số `“` bằng số `”` — nên máy trạng thái đơn
giản là đủ, không cần phân tích cú pháp gì thêm.

---

## Sửa 2 — `check_tree_coverage` đang nói NGƯỢC

### Hiện tại

```json
"cây điều khoản thiếu 4 Khoản so với toàn văn (10/14)"
```

### Vì sao ngược

Cây có **10 khoản, và 10 mới là số đúng**. Con số 14 là toàn văn đếm cả 4 dòng nằm trong ngoặc
kép. **Cây không thiếu — toàn văn thừa.**

Đây là chỗ đáng chú ý: với `15/2024/TT-NHNN` thì cây thiếu nút thật (khuyết tật 2 mình đã báo
lượt trước), còn ở văn bản sửa đổi thì cây lại **đúng hơn** toàn văn — vì cây đọc theo cấu trúc
HTML nên biết khối trích dẫn là con của khoản, còn đếm phẳng thì không biết.

### Cần làm

Phép đếm đối chiếu chỉ đếm dòng **ngoài ngoặc kép**. Sau khi sửa, đo trên lô hiện tại phải ra
(cột "ngoài" là con số đúng để đối chiếu với cây):

| văn bản | dòng mở đầu bằng số, **ngoài** ngoặc | **trong** ngoặc |
|---|---|---|
| `16/2019/NĐ-CP` | 14 | 0 |
| `52/2024/NĐ-CP` | 153 | 0 |
| `80/2016/NĐ-CP` | **10** | **4** |
| `22/2026/TT-NHNN` | **2** | **10** |
| `15/2024/TT-NHNN` | 97 | 0 |
| `40/2024/TT-NHNN` | 209 | 0 |
| `41/2025/TT-NHNN` | **34** | **12** |
| `66/2025/TT-NHNN` | **14** | **5** |

*(Cột "ngoài" đếm bằng regex thô `^\d+\.\s` nên **không** bằng số khoản trong bảng nghiệm thu —
bộ tách của mình còn luật khác. Dùng cột này để so với cây, đừng dùng làm số khoản.)*

Sau khi sửa, số điều mà cây khớp toàn văn phải là: ND16 4/4 · ND52 35/35 · ND80 1/1 ·
TT22 1/1 · TT41 13/13 · TT66 4/4 · TT15 21/22 · TT40 46/50.

**Bảy văn bản khớp trọn.** Năm điều còn lệch (TT15 Điều 12; TT40 Điều 19, 26, 37, 42) **không**
liên quan tới ngoặc kép — đó là khuyết tật 2 (cây thiếu nút) mình đã báo, cứ để nguyên cảnh báo
cho những ca đó.

---

## Một việc tuỳ chọn, chỉ làm nếu rẻ

Nếu bạn đã tính vị trí các khối trích dẫn để làm hai việc trên, thì xuất luôn ra cũng tiện:

```json
"trich_dan": [{"char_start": 1234, "char_end": 3456}]
```

Không có cũng không sao — phía mình tự suy lại được, và mình sẽ làm thế. Đừng vì cái này mà
động vào `noi_dung`.

---

## Ràng buộc

- **Không đổi một ký tự nào trong `noi_dung` và `articles[].text`.** Hai sửa ở trên chỉ đụng
  phần *đếm* và phần *sinh cảnh báo*. `char_span` hiện đúng 100%, đừng làm nó lệch.
- Mỗi sửa kèm ít nhất một test dùng **file thật đã crawl** — `80/2016/NĐ-CP` cho ca trong-ngoặc,
  `52/2024/NĐ-CP` cho ca không có ngoặc nào (phải không đổi kết quả).
- Chạy lại cả lô và báo cáo bảng trên. Nếu số của bạn khác, **đừng chỉnh cho khớp** — báo lại,
  vì có thể mình sai (lượt trước mình đã sai một lần đúng kiểu đó).
