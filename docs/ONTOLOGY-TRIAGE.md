# Hàng đợi duyệt — các đơn vị bị gắn cờ

> Sinh bằng `uv run python eval/ontology/triage.py --md <file>`.
> Xếp theo **hậu quả nếu bỏ qua**, không theo tần suất. T5 được đếm nhưng
> không vào hàng đợi — xem `eval/ontology/triage.py` để biết vì sao.

28/49 bản ghi có cờ · 95 cờ tổng cộng

| mức | loại cờ | số cờ | số bản ghi ở mức này |
|---|---|---|---|
| T1 · máy đã tự quyết thay người | máy tự gộp span của mô hình | 1 | 5 |
|  | máy tự hạ lỗi cứng xuống cảnh báo | 1 |  |
|  | máy tự lùi về span đơn vị | 3 |  |
| T2 · phép logic chưa xác định | chưa xác định 'và' hay 'hoặc' | 1 | 2 |
|  | tiết đã có guard — xác nhận loại trừ nhau | 2 |  |
| T3 · nghi bịa tình thái | nghi bịa: THÊM dấu hiệu tình thái | 9 | 2 |
| T4 · neo sai phạm vi | cổng thời gian thiếu mốc ngày | 1 | 0 |
|  | quote thu hẹp sai chỗ | 1 |  |
|  | span không bao hết các tiết | 1 |  |
|  | điểm không tồn tại trong khoản | 19 |  |
| T5 · ít giá trị đọc | nhãn tóm lược: MẤT dấu hiệu | 25 | 11 |
|  | quote lệch marker/dấu câu | 18 |  |
| T? · chưa phân loại | chưa phân loại | 13 | 1 |

---

## Hàng đợi (T0–T4)

### [T6 · khuyết tật hệ thống — sửa prompt, không đọc luật] · 13 bản ghi · 19 cờ

Mọi `source_diem` mô hình khai đều không tồn tại ⇒ **Khoản không chẻ Điểm nào**. Mô hình đang dùng `source_diem` như *số thứ tự* cho các ý trong một đoạn liền, không phải như *địa chỉ*. Một khuyết tật của prompt — **không cần đọc luật bản nào**:

- `18/2024/TT-NHNN#than/dieu_13#khoan_4` — mô hình khai ['a', 'b'], Khoản không có Điểm
- `52/2024/NĐ-CP#than/dieu_26#khoan_2` — mô hình khai ['a', 'b'], Khoản không có Điểm
- `52/2024/NĐ-CP#than/dieu_23#khoan_1` — mô hình khai ['a', 'b'], Khoản không có Điểm
- `18/2024/TT-NHNN#than/dieu_9#khoan_1` — mô hình khai ['a', 'b'], Khoản không có Điểm
- `18/2024/TT-NHNN#than/dieu_9#khoan_9` — mô hình khai ['a'], Khoản không có Điểm
- `18/2024/TT-NHNN#than/dieu_13#khoan_1` — mô hình khai ['a'], Khoản không có Điểm
- `18/2024/TT-NHNN#than/dieu_13#khoan_2` — mô hình khai ['a'], Khoản không có Điểm
- `18/2024/TT-NHNN#than/dieu_9#khoan_4` — mô hình khai ['a'], Khoản không có Điểm
- `18/2024/TT-NHNN#than/dieu_9#khoan_5` — mô hình khai ['a'], Khoản không có Điểm
- `18/2024/TT-NHNN#than/dieu_9#khoan_6` — mô hình khai ['a'], Khoản không có Điểm
- `18/2024/TT-NHNN#than/dieu_9#khoan_7` — mô hình khai ['a'], Khoản không có Điểm
- `18/2024/TT-NHNN#than/dieu_9#khoan_8` — mô hình khai ['a'], Khoản không có Điểm
- `52/2024/NĐ-CP#than/dieu_22#khoan_3` — mô hình khai ['a', 'b', 'c'], Khoản không có Điểm

### [T1 · máy đã tự quyết thay người] `17/2024/TT-NHNN#than/dieu_16#khoan_2`  ·  actor_cu

- **máy tự hạ lỗi cứng xuống cảnh báo** — `điều kiện c.constraint_label`
  > hạ mức 'bịa ràng buộc nhóm nghia_vu': cụm này CÓ trong các đơn vị đã chọn, chỉ nằm ngoài đoạn mà 'quote' thu hẹp vào
  - chữ của luật: *Lưu trữ, bảo quản đầy đủ, chi tiết đối với các tài liệu, thông tin, dữ liệu nhận biết khách hàng trong quá trình mở, sử dụng tài khoản thanh toán bằng phương tiện điện tử*
- **tiết đã có guard — xác nhận loại trừ nhau** — `điều kiện b`
  > tiet_semicolon_guard_da_phu: 2 tiết đều có điều kiện áp dụng riêng ('cá nhân' | 'tổ chức'). Xác nhận: các guard này có loại trừ nhau không? Nếu có thì 'và'/'hoặc' không còn ảnh hưởng — giữ connector 'unknown' là an toàn.
  - chữ của luật: *Xác nhận việc khách hàng chấp thuận với các nội dung tại thỏa thuận mở và sử dụng tài khoản thanh toán*
- **nghi bịa: THÊM dấu hiệu tình thái** — `điều kiện c.constraint_label`
  > [cảnh báo] thêm dấu hiệu cho_phep: được
  - chữ của luật: *Lưu trữ, bảo quản đầy đủ, chi tiết đối với các tài liệu, thông tin, dữ liệu nhận biết khách hàng trong quá trình mở, sử dụng tài khoản thanh toán bằng phương tiện điện tử*
- **nghi bịa: THÊM dấu hiệu tình thái** — `điều kiện c.constraint_label`
  > [cảnh báo] thêm dấu hiệu nghia_vu: phải
  - chữ của luật: *Lưu trữ, bảo quản đầy đủ, chi tiết đối với các tài liệu, thông tin, dữ liệu nhận biết khách hàng trong quá trình mở, sử dụng tài khoản thanh toán bằng phương tiện điện tử*
- **nghi bịa: THÊM dấu hiệu tình thái** — `điều kiện d.constraint_label`
  > [cảnh báo] thêm dấu hiệu dieu_kien: khi
  - chữ của luật: *Ngân hàng, chi nhánh ngân hàng nước ngoài phải thường xuyên kiểm tra, đánh giá mức độ an toàn, bảo mật của biện pháp, hình thức, công nghệ và thực hiện tạm dừng cung cấp dịch vụ để nâng cấp, chỉnh sửa, hoàn thiện trong trường hợp có dấu hiệu mất an toàn*
- **span không bao hết các tiết** — `điều kiện b`
  > span không bao hết các tiết của điểm b
  - chữ của luật: *Xác nhận việc khách hàng chấp thuận với các nội dung tại thỏa thuận mở và sử dụng tài khoản thanh toán*
- **quote thu hẹp sai chỗ** — `điều kiện c.constraint_label`
  > ⇒ 'quote' thu hẹp sai chỗ: `text` của trường này KHÔNG chứa đoạn mà nhãn đang mô tả — cần người duyệt xác nhận phạm vi
  - chữ của luật: *Lưu trữ, bảo quản đầy đủ, chi tiết đối với các tài liệu, thông tin, dữ liệu nhận biết khách hàng trong quá trình mở, sử dụng tài khoản thanh toán bằng phương tiện điện tử*
- _(ẩn 3 cờ mức T5)_

### [T1 · máy đã tự quyết thay người] `52/2024/NĐ-CP#than/dieu_26#khoan_1`  ·  actor_cu

- **máy tự lùi về span đơn vị** — `action`
  > quote không nằm trong đơn vị đã chọn, lùi về span đơn vị | mất 'a )'; mất 'b )'; mất 'c )'; mất 'd )'; …
  - chữ của luật: *a) Tổ chức cung ứng dịch vụ trung gian thanh toán gửi 01 bộ hồ sơ đề nghị sửa đổi, bổ sung Giấy phép gồm: đơn đề nghị sửa đổi, bổ sung Giấy phép hoạt động cung ứng dịch vụ trung gian thanh toán theo Mẫu số 12 ban hành kèm theo Nghị định này; bản sao Giấy phép hoạt động cung ứng d*
- **nghi bịa: THÊM dấu hiệu tình thái** — `subject`
  > [cảnh báo] thêm dấu hiệu dieu_kien: khi
  - chữ của luật: *Trường hợp thay đổi một trong các nội dung quy định trong Giấy phép hoạt động cung ứng dịch vụ trung gian thanh toán sau: tên tổ chức, địa điểm đặt trụ sở chính, ngừng cung cấp một hoặc một số dịch vụ trung gian thanh toán đã được cấp phép, kết nối thêm hệ thống thanh toán quốc t*
- **nghi bịa: THÊM dấu hiệu tình thái** — `điều kiện a#2.constraint_label`
  > [cảnh báo] thêm dấu hiệu dieu_kien: khi
  - chữ của luật: *Trường hợp đề nghị kết nối thêm hệ thống thanh toán quốc tế, tổ chức cung ứng dịch vụ chuyển mạch tài chính quốc tế bổ sung thêm các tài liệu quy định tại điểm i khoản 2 Điều 24 Nghị định này;*
- **nghi bịa: THÊM dấu hiệu tình thái** — `điều kiện b#2.constraint_label`
  > [cảnh báo] thêm dấu hiệu dieu_kien: khi
  - chữ của luật: *Trường hợp từ chối sửa đổi, bổ sung Giấy phép, Ngân hàng Nhà nước có văn bản trả lời tổ chức trong đó nêu rõ lý do*
- _(ẩn 5 cờ mức T5)_

### [T1 · máy đã tự quyết thay người] `18/2024/TT-NHNN#than/dieu_13#khoan_4`  ·  actor_cu

- **máy tự lùi về span đơn vị** — `action`
  > quote không nằm trong đơn vị đã chọn, lùi về span đơn vị | mất '4 . đối với thẻ trả trước , tcpht'; '( bao gồm giao dịch rút tiền mặt , giao dịch chuyển khoản , giao dịch thanh toán tiền hàng hóa , dịch vụ )' → '. . .'
  - chữ của luật: *4. Đối với thẻ trả trước, TCPHT quy định cụ thể hạn mức số dư, hạn mức nạp thêm tiền vào thẻ và hạn mức giao dịch; đảm bảo số dư tại mọi thời điểm trên một thẻ trả trước vô danh không được quá 05 (năm) triệu đồng Việt Nam; tổng hạn mức giao dịch (bao gồm giao dịch rút tiền mặt, g*
- **điểm không tồn tại trong khoản** — `điều kiện a`
  > điểm không tồn tại trong khoản này
  - chữ của luật: *số dư tại mọi thời điểm trên một thẻ trả trước vô danh không được quá 05 (năm) triệu đồng Việt Nam*
- **điểm không tồn tại trong khoản** — `điều kiện b`
  > điểm không tồn tại trong khoản này
  - chữ của luật: *tổng hạn mức giao dịch (bao gồm giao dịch rút tiền mặt, giao dịch chuyển khoản, giao dịch thanh toán tiền hàng hóa, dịch vụ) trên một thẻ trả trước định danh không được quá 100 (một trăm) triệu đồng Việt Nam trong 01 tháng*

### [T1 · máy đã tự quyết thay người] `52/2024/NĐ-CP#than/dieu_37#khoan_2`  ·  meta_cu

- **máy tự lùi về span đơn vị** — `menh_de`
  > quote không nằm trong đơn vị đã chọn, lùi về span đơn vị | mất '2 .'
  - chữ của luật: *2. Nghị định này thay thế cho Nghị định số 101/2012/NĐ-CP ngày 22 tháng 11 năm 2012 của Chính phủ về thanh toán không dùng tiền mặt; Nghị định số 80/2016/NĐ-CP ngày 01 tháng 7 năm 2016 của Chính phủ sửa đổi, bổ sung một số điều của Nghị định số 101/2012/NĐ-CP ngày 22 tháng 11 năm*
- **cổng thời gian thiếu mốc ngày** — `—`
  > cổng thời gian nhưng chưa tách được mốc ngày ở dạng cấu trúc — mốc (nếu có) chỉ còn là chữ tự do trong `menh_de`

### [T1 · máy đã tự quyết thay người] `40/2024/TT-NHNN#than/dieu_26#khoan_2`  ·  meta_cu

- **máy tự gộp span của mô hình** — `—`
  > cổng không có bên bị ràng buộc — mô hình vẫn khai 'subject', đã gộp đơn vị [1] vào `menh_de` để không mất nửa mệnh đề

### [T2 · phép logic chưa xác định] `17/2024/TT-NHNN#than/dieu_16#khoan_1`  ·  actor_cu

- **tiết đã có guard — xác nhận loại trừ nhau** — `điều kiện a`
  > tiet_semicolon_guard_da_phu: 2 tiết đều có điều kiện áp dụng riêng ('cá nhân' | 'tổ chức'). Xác nhận: các guard này có loại trừ nhau không? Nếu có thì 'và'/'hoặc' không còn ảnh hưởng — giữ connector 'unknown' là an toàn.
  - chữ của luật: *a) Thu thập các tài liệu, thông tin, dữ liệu để xác minh thông tin nhận biết khách hàng theo quy định tại khoản 2, 3 Điều 12 Thông tư này và: (i) Thông tin sinh trắc học của chủ tài khoản đối với khách hàng là cá nhân; (ii) Thông tin sinh trắc học của người đại diện hợp pháp đối *
- _(ẩn 5 cờ mức T5)_

### [T2 · phép logic chưa xác định] `18/2024/TT-NHNN#than/dieu_9#khoan_3`  ·  actor_cu

- **chưa xác định 'và' hay 'hoặc'** — `điều kiện c`
  > tiet_semicolon_mo_ho: có 2 tiết nhưng chỉ ngăn bằng ';' — không xác định được là 'và' hay 'hoặc', cần người đọc chốt
  - chữ của luật: *c) Trường hợp các tài liệu, thông tin, dữ liệu nêu tại điểm a, điểm b khoản này bằng tiếng nước ngoài, TCPHT được thỏa thuận với khách hàng về việc dịch hoặc không dịch ra tiếng Việt nhưng phải đảm bảo các nguyên tắc sau: (i) TCPHT phải kiểm tra, kiểm soát và chịu trách nhiệm xác*
- _(ẩn 1 cờ mức T5)_

### [T3 · nghi bịa tình thái] `52/2024/NĐ-CP#than/dieu_22#khoan_2`  ·  actor_cu

- **nghi bịa: THÊM dấu hiệu tình thái** — `điều kiện b#2.object_label`
  > [cảnh báo] thêm dấu hiệu cho_phep: được
  - chữ của luật: *300 tỷ đồng đối với dịch vụ chuyển mạch tài chính, dịch vụ chuyển mạch tài chính quốc tế, dịch vụ bù trừ điện tử*
- **nghi bịa: THÊM dấu hiệu tình thái** — `điều kiện b#2.constraint_label`
  > [cảnh báo] thêm dấu hiệu dinh_luong: tối thiểu
  - chữ của luật: *300 tỷ đồng đối với dịch vụ chuyển mạch tài chính, dịch vụ chuyển mạch tài chính quốc tế, dịch vụ bù trừ điện tử*
- _(ẩn 12 cờ mức T5)_

### [T3 · nghi bịa tình thái] `40/2024/TT-NHNN#than/dieu_25#khoan_5`  ·  actor_cu

- **nghi bịa: THÊM dấu hiệu tình thái** — `action`
  > [cảnh báo] thêm dấu hiệu cam: không được
  - chữ của luật: *không được nhận tiền mặt từ khách hàng để nạp tiền vào ví điện tử; không được phép cấp tín dụng cho khách hàng sử dụng ví điện tử, trả lãi trên số dư ví điện tử*
