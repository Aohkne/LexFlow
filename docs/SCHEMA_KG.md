# Schema Đồ thị Tri thức — Pháp luật Ngân hàng & Fintech Việt Nam
### Bản đặc tả v0.4 — đồng bộ với Phần A v1.7

*Ngày: 27/07/2026 · Phạm vi: VBQPPL lĩnh vực ngân hàng, thanh toán, fintech, tài sản số · Nền tảng: Neo4j 5.x*

---

## Nhật ký thay đổi

### v0.1 → v0.2

| Hạng mục | v0.1 | v0.2 |
|---|---|---|
| Cấp phân rã | để ngỏ | `Điều` cho toàn corpus; `Khoản` cho nhóm lõi; bỏ `Điểm` |
| Tầng ngữ nghĩa | để ngỏ | **Có** `KhaiNiem` (P1); `ThucTheChiuDieuChinh` hạ xuống P2 |
| Nền tảng | để ngỏ | **Neo4j** (labeled property graph) |
| Temporal | 2 mức, để ngỏ | **Chọn lọc**: version-node cho nhóm nóng, date-property cho phần còn lại |
| `QUY_DINH_CHI_TIET` / `HUONG_DAN_AP_DUNG` | tách | **Gộp** thành `QUY_DINH_CHI_TIET_HUONG_DAN` + thuộc tính `loai` |
| `VuAn` / án lệ | để ngỏ | **Loại bỏ** khỏi schema |

### v0.2 → v0.3 — thay dữ liệu bịa bằng dữ liệu thật

v0.2 dùng cặp `18/2025/TT-NHNN ← 45/2025/TT-NHNN` làm ví dụ xuyên suốt. **Hai số hiệu đó không có thật** — chúng do tôi dựng ra ở giai đoạn chưa có dữ liệu và đã được báo lại. v0.3 thay bằng hai cụm đã đối chiếu Công báo:

- `40/2024/TT-NHNN ← 41/2025/TT-NHNN ← 22/2026/TT-NHNN` — trung gian thanh toán, **ba phiên bản**, có hiệu lực phân kỳ
- `17/2024/TT-NHNN ← 25/2025/TT-NHNN` — mở và sử dụng tài khoản thanh toán, hai phiên bản

Bản đặc tả này (file Markdown) trước v0.4 vẫn còn sót số hiệu bịa ở §1, §3, §4 và §5 dù script Cypher đã sạch từ v0.3. **v0.4 dọn nốt.**

### v0.3 → v0.4 — tám thay đổi từ Phần A v1.5–v1.7

Tất cả đều bắt nguồn từ nguyên văn **Phụ lục I ban hành kèm NĐ 187/2025/NĐ-CP** và **Điều 3 Luật 87/2025/QH15**. Bảy trong tám chạm tới khoá chính hoặc mô hình thời gian — tức là rẻ bây giờ, đắt sau khi nạp dữ liệu.

| # | Thay đổi | Nguồn quy phạm | Mức |
|---|---|---|---|
| 1 | Khoá `VanBan` tách **ba nhánh**: thân / kèm theo / phụ lục | Phụ lục I, Mục 1 Phần II điểm 1.b | **Chặn** |
| 2 | `so_dieu` tách thành `so_dieu_hien_thi` + `(so_dieu_goc, so_dieu_hau_to)` | Phụ lục I, Mục 1 Phần II điểm 5 | **Chặn** |
| 3 | Node `PhuLuc` và `VanBanKemTheo` | Phụ lục I, Mục 1 Phần III điểm 3 | **Chặn** |
| 4 | `Khoan.ten` — nullable, **không** bỏ trống mặc định | Phụ lục I, Mục 1 Phần III điểm 2.b | Cao |
| 5 | Khôi phục `Diem`, tạo theo nhu cầu ở tầng NÓNG | Phụ lục I, Mục 1 Phần III điểm 2.b | Cao |
| 6 | Cạnh `CHAM_DUT_AP_DUNG` + `nguon_hieu_luc_den` | Điều 3 Luật 87/2025 | Cao |
| 7 | `so_hieu_chuan_hoa` + cạnh `KE_THUA_CO_QUAN` | Phụ lục I, Mục 1 Phần II điểm 3 | Trung bình |
| 8 | `DAN_CHIEU` cho phép **nhiều đích** + `do_tin_cay` | Phụ lục I, Mục 2 Phần V điểm 6 | Trung bình |

---

## 0. Nguyên tắc thiết kế

1. **Mỗi loại quan hệ = một cạnh có hướng, có tên.** Không tạo cạnh nghịch (mirror). Thể chủ động / bị động (*sửa đổi* / *được sửa đổi*) do **chiều mũi tên** đảm nhiệm, không do tên cạnh.
2. **Quy ước chiều thống nhất — chủ thể tác động → đối tượng bị tác động**: văn bản *chủ động / mới hơn* trỏ tới văn bản *bị tác động / cũ hơn*.
   `(TT 41/2025 mới) -[:SUA_DOI_BO_SUNG]-> (TT 40/2024 cũ)`
3. **Quan hệ sửa đổi / bãi bỏ neo ở cấp Điều**, không chỉ cấp văn bản — vì phần lớn sửa đổi chỉ chạm vài điều khoản.
4. **Thời gian là thuộc tính hạng nhất** — có mặt trên node, trên cạnh, và (với nhóm nóng) trên node phiên bản riêng.
5. Giữa hai node có thể có **nhiều cạnh song song khác loại** (vừa `CAN_CU` vừa `SUA_DOI_BO_SUNG`) — nên loại quan hệ phải tách bằng tên, tuyệt đối không gộp.
6. **Temporal có chọn lọc.** Không phải văn bản nào cũng đáng dựng phiên bản. Chỉ nhóm có tần suất sửa đổi cao và giá trị demo cao mới được dựng `PhienBanDieu`. Cấp temporal của mỗi văn bản được ghi rõ bằng thuộc tính `muc_temporal`, để truy vấn biết trước phần nào của đồ thị hỗ trợ tra cứu điểm-thời-gian.
7. **Khoảng hiệu lực dùng quy ước nửa mở `[hieu_luc_tu, hieu_luc_den)`.** Ngày kết thúc của phiên bản `n` **bằng đúng** ngày bắt đầu của phiên bản `n+1` (không trừ một ngày). `NULL` nghĩa là còn mở. Quy ước này loại bỏ hoàn toàn lỗi lệch-một-ngày ở biên và làm điều kiện lọc chỉ còn một dạng duy nhất.

---

## 1. Các loại Node

### Tầng A — Cấu trúc văn bản

#### A1. `VanBan` — Văn bản QPPL *(node trung tâm)*

| Thuộc tính | Kiểu | Ví dụ / Ghi chú |
|---|---|---|
| `id` | string (PK) | `"40/2024/TT-NHNN"` |
| `ten_day_du` | string | tên đầy đủ |
| `loai_van_ban` | enum | `Luật / Nghị quyết QH / Pháp lệnh / Nghị định / Quyết định TTg / Thông tư / VBHN ...` |
| `so` | int | 40 |
| `nam` | int | 2024 |
| **`so_hieu_chuan_hoa`** | string | dạng đã chuẩn hoá để so khớp — xem §1.A1.b |
| `ngay_ban_hanh` | date | |
| `ngay_hieu_luc` | date | |
| `ngay_het_hieu_luc` | date? | `null` nếu còn hiệu lực |
| `tinh_trang_hieu_luc` | enum | `Còn hiệu lực / Hết hiệu lực toàn bộ / Hết hiệu lực một phần / Chưa có hiệu lực / Ngưng hiệu lực` |
| `nguoi_ky`, `chuc_danh_nguoi_ky` | string | |
| `nganh`, `pham_vi` | string / enum | |
| `so_cong_bao`, `nguon_url` | string? | |
| **`muc_temporal`** | enum | **`day_du`** (có `PhienBanDieu`) / **`co_ban`** (chỉ date-property) — xem §5 |
| **`co_khoan`** | bool | có phân rã tới cấp `Khoan` hay không |

> **Khóa:** ký hiệu `số/năm/loại-cơ quan` là duy nhất ở cấp trung ương. Corpus này chỉ gồm văn bản trung ương nên `id` đơn là đủ ở **cấp văn bản**. Nhưng ở cấp **Điều** thì không — xem A1.a ngay dưới.

##### A1.a. Khoá ba nhánh — thay đổi v0.4 #1 *(mức: chặn)*

Phụ lục I (Mục 1 Phần II điểm 1.b) cho phép một văn bản mang **văn bản khác kèm theo** (quyết định ban hành kèm quy chế) và **phụ lục** có đánh số Điều riêng. Hệ quả: trong cùng một số hiệu có thể tồn tại **nhiều "Điều 5" khác nhau** — một ở thân văn bản, một trong quy chế kèm theo, một trong phụ lục. Khoá cũ `{so_hieu}#dieu_{n}` **va chạm âm thầm**: MERGE sẽ gộp hai điều không liên quan thành một node, và lỗi này không báo gì cả.

Khoá `Dieu` từ v0.4 luôn mang **nhánh chứa** ở giữa:

```
{so_hieu}#than/dieu_{n}                    ← Điều trong thân văn bản
{so_hieu}#kemtheo_{slug}/dieu_{n}          ← Điều trong văn bản ban hành kèm theo
{so_hieu}#phuluc_{số La Mã}/dieu_{n}       ← Điều trong phụ lục có đánh số Điều
```

Nhánh `than` **được viết tường minh**, không để trống làm mặc định. Lý do: nếu `than` là chuỗi rỗng thì khoá cũ và khoá mới trông giống hệt nhau, và sẽ không có cách nào phân biệt dữ liệu nạp trước với dữ liệu nạp sau khi sửa schema.

##### A1.b. `so_hieu_chuan_hoa` — thay đổi v0.4 #7

Phụ lục I (Mục 1 Phần II điểm 3) quy định cách ghi số, ký hiệu văn bản. Ba biến thể xuất hiện thực tế trong corpus và phải quy về một dạng trước khi so khớp: số có **số 0 đứng đầu** (`07/2024/TT-NHNN` vs `7/2024/TT-NHNN`), năm ghi **hai chữ số**, và **khoảng trắng thừa** quanh dấu gạch chéo. Hàm chuẩn hoá: bỏ số 0 đứng đầu, ép năm về 4 chữ số, xoá mọi khoảng trắng, viết hoa phần ký hiệu cơ quan.

Kèm theo là cạnh **`KE_THUA_CO_QUAN`** giữa `CoQuanBanHanh`: bộ đếm số hiệu **reset giữa năm khi cơ quan tổ chức lại**, nên cùng một `(số, năm, ký hiệu)` có thể trỏ tới hai văn bản của hai pháp nhân khác nhau. Nếu corpus có mốc tổ chức lại, `id` phải kèm ký hiệu cơ quan *tại thời điểm ban hành*, và `KE_THUA_CO_QUAN` là thứ nối hai thời kỳ lại để truy vấn không bị đứt.

#### A2. `Dieu` — Điều luật *(định danh ổn định, KHÔNG chứa nội dung với nhóm nóng)*

Đây là thay đổi quan trọng nhất của v0.2. `Dieu` trở thành **định danh bất biến** của điều luật xuyên suốt lịch sử — tương ứng khái niệm *work* trong FRBR / *LegalResource* trong ELI. Nội dung cụ thể tại từng thời điểm nằm ở `PhienBanDieu` (*expression* / *LegalExpression*).

| Thuộc tính | Kiểu | Ghi chú |
|---|---|---|
| `id` | string (PK) | `"40/2024/TT-NHNN#than/dieu_5"` |
| `nhanh` | enum | `than / kemtheo / phuluc` — nhánh chứa, xem A1.a |
| **`so_dieu_hien_thi`** | string | `"5"`, `"4a"` — chuỗi đúng như in trong văn bản |
| **`so_dieu_goc`** | int | `4` — phần số, dùng để sắp xếp |
| **`so_dieu_hau_to`** | int | `0` nếu không có hậu tố; `1`=a, `2`=b, `3`=c, `4`=d, **`5`=đ**, `6`=e… |
| `tieu_de` | string | **bản hiện hành** — tiện cho hiển thị nhanh; bản lịch sử nằm ở phiên bản |
| `noi_dung` | text | **bản hiện hành** — với văn bản `muc_temporal = "co_ban"` đây là nguồn duy nhất |
| `tinh_trang_hieu_luc` | enum | trạng thái hiện hành ở cấp điều |

> Với văn bản `co_ban`, `Dieu.noi_dung` là toàn bộ dữ liệu. Với văn bản `day_du`, `Dieu.noi_dung` là **bản sao tiện lợi** của phiên bản mới nhất — nguồn chân lý là `PhienBanDieu`. Cần một truy vấn kiểm tra định kỳ để hai nơi không lệch nhau (§8.6).

##### A2.a. Vì sao `so` không còn là `int` — thay đổi v0.4 #2 *(mức: chặn)*

Phụ lục I (Mục 1 Phần II điểm 5) quy định điều bổ sung mang **số của điều liền trước cộng chữ cái**: `Điều 4a`, `Điều 4b`. Cơ chế sửa đổi VBQPPL Việt Nam dùng dạng này rất nhiều — TT 25/2025 bổ sung `Điều 15a` vào TT 17/2024 là ví dụ có thật trong corpus. Một trường `int` **không lưu được** `4a`; một trường `string` lưu được nhưng sắp xếp sai (`"10"` đứng trước `"4a"`, `"4b"` đứng trước `"4a"` là không xảy ra nhưng `"4a"` đứng trước `"4"` thì có).

Ba trường thay cho một: `so_dieu_hien_thi` để in ra, cặp `(so_dieu_goc, so_dieu_hau_to)` làm **khoá sắp xếp**. Thứ tự đúng là `ORDER BY so_dieu_goc, so_dieu_hau_to`.

> **Bẫy bảng chữ cái tiếng Việt — lần thứ nhất.** Hậu tố dùng bảng chữ cái tiếng Việt, trong đó **`đ` nằm giữa `d` và `e`**. Nếu ánh xạ hậu tố bằng `ord(ch) - ord('a')` của ASCII thì `Điều 4đ` sẽ rơi sai chỗ hoặc sinh mã trùng. Phải dùng bảng tra tường minh. Bẫy này lặp lại lần thứ hai ở `Diem` (A4.b) với cùng nguyên nhân và cùng cách chữa.

#### A3. `PhienBanDieu` — Phiên bản của một Điều theo thời gian *(node MỚI, trái tim của lớp temporal)*

| Thuộc tính | Kiểu | Ví dụ |
|---|---|---|
| `id` | string (PK) | `"40/2024/TT-NHNN#than/dieu_41@v2"` |
| `so_phien_ban` | int | 2 |
| `tieu_de` | string | tiêu đề **tại phiên bản này** (sửa đổi có thể đổi cả tiêu đề) |
| `noi_dung` | text? | toàn văn Điều tại phiên bản này; `null` nếu đây là phiên bản bãi bỏ |
| `hieu_luc_tu` | date | 2025-11-05 |
| `hieu_luc_den` | date? | `null` = còn mở; nếu có, **bằng đúng** `hieu_luc_tu` của phiên bản kế tiếp |
| `loai_thay_doi` | enum | `goc / sua_doi / bo_sung / thay_the_cum_tu / bai_bo` |
| `pham_vi_thay_doi` | string[] | `["khoan_3", "khoan_5"]` — khoản nào bị chạm; rỗng nếu sửa toàn điều |
| `nguon_hop_nhat` | string? | id VBHN dùng để đối chiếu, ví dụ `"30/VBHN-NHNN"` |
| `da_doi_chieu_vbhn` | bool | đã kiểm chứng với văn bản hợp nhất chính thức chưa |

**Bốn bất biến bắt buộc** (có truy vấn kiểm tra ở §8.6):

- Các phiên bản của cùng một `Dieu` tạo thành **một chuỗi liên tục, không chồng lấn, không hở**.
- Phiên bản đầu tiên có `so_phien_ban = 1`, `loai_thay_doi = "goc"`, và `hieu_luc_tu` **bằng** `ngay_hieu_luc` của văn bản gốc.
- Đúng **một** phiên bản có `hieu_luc_den IS NULL` (trừ khi điều đã bị bãi bỏ và chuỗi đóng hẳn).
- Bãi bỏ **không** làm cụt chuỗi mà tạo một phiên bản kết thúc với `noi_dung = null`, `loai_thay_doi = "bai_bo"`. Nhờ vậy truy vấn tại ngày sau khi bãi bỏ trả về câu trả lời có nghĩa ("điều này đã bị bãi bỏ bởi X từ ngày Y") thay vì trả về rỗng — vốn dễ bị hiểu nhầm là thiếu dữ liệu.

#### A4. `Chuong`, `Muc`, `Khoan`, `Diem` — cấu trúc phụ

`Chuong` / `Muc`: chỉ để giữ ngữ cảnh điều hướng, ít giá trị suy luận. `Khoan`: **chỉ dựng cho nhóm lõi** (`VanBan.co_khoan = true`), `id` = `"...#than/dieu_5#khoan_3"`. `TieuMuc` bỏ (hiếm gặp trong thông tư NHNN).

Thang bố cục đầy đủ theo Phụ lục I, Mục 1 Phần III — đây là **quy định thể thức, không phải quy ước biên tập**, nên mô hình phải theo:

| Cấp | Cách đánh số | Có tên gọi? | Trong schema |
|---|---|---|---|
| Phần / Chương | số La Mã | **Có** | `Chuong` |
| Mục / Tiểu mục | số Ả Rập | **Có** | `Muc` (bỏ `TieuMuc`) |
| **Điều** | số Ả Rập + dấu chấm | **Bắt buộc có** | `Dieu` |
| **Khoản** | số Ả Rập + dấu chấm | **CÓ THỂ có** | `Khoan` — xem A4.a |
| **Điểm** | chữ cái tiếng Việt + `)` | Không | `Diem` — xem A4.b |
| gạch đầu dòng | *không đánh số* | Không | **không mô hình hoá được** |

##### A4.a. `Khoan.ten` nullable — thay đổi v0.4 #4

Phụ lục I Mục 1 Phần III điểm 2.b nói khoản **có thể** có tên gọi. Bản đặc tả v0.2–v0.3 ghi sai là "không có tên". Hệ quả nếu để nguyên: parser sẽ **nuốt dòng tên khoản vào nội dung** hoặc coi nó là một khoản riêng không số. `Khoan.ten` là `string?` — `null` khi khoản không có tên, và `null` **khác** chuỗi rỗng: chuỗi rỗng nghĩa là "đã kiểm tra, có chỗ đặt tên nhưng để trống", `null` nghĩa là "khoản này không mang tên gọi".

##### A4.b. `Diem` được khôi phục — thay đổi v0.4 #5

v0.2 loại bỏ `Diem` để tiết kiệm. Nhưng cạnh `SUA_DOI_BO_SUNG` và `DAN_CHIEU` trong corpus fintech **thường xuyên trỏ tới cấp điểm** (`điểm c khoản 2 Điều 7`). Không có node `Diem`, những cạnh đó phải hạ độ chính xác lên cấp khoản, và đúng cái phần đắt giá nhất của đồ thị — độ mịn của quan hệ sửa đổi — bị mất.

Thoả hiệp: `Diem` **tạo theo nhu cầu, chỉ ở tầng NÓNG**. Node `Diem` chỉ ra đời khi có một cạnh thật sự cần trỏ vào nó. Không phân rã đại trà. `id` = `"...#than/dieu_7#khoan_2#diem_c"`.

> **Bẫy bảng chữ cái tiếng Việt — lần thứ hai.** Điểm đánh bằng chữ cái tiếng Việt: `a) b) c) d) đ) e) g) h)…` — có `đ`, **không có `f`**, và sau `e` là `g`. Sắp xếp bằng ASCII cho ra thứ tự sai. Dùng chung bảng tra với `so_dieu_hau_to`.

##### A4.c. `PhuLuc` và `VanBanKemTheo` — thay đổi v0.4 #3 *(mức: chặn)*

Hai node mới, cả hai đều được Phụ lục I Mục 1 Phần III điểm 3 thừa nhận là bộ phận của văn bản:

- **`PhuLuc`** — `so_la_ma`, `ten`, `co_danh_so_dieu` (bool). Nếu `co_danh_so_dieu = true` thì phụ lục chứa `Dieu` với nhánh khoá `phuluc_{số La Mã}`. Đây là kiểu lỗi **vắng mặt im lặng**: không mô hình hoá thì phần nội dung đó đơn giản là không có trong đồ thị, và không truy vấn nào báo thiếu.
- **`VanBanKemTheo`** — `slug`, `ten`, `loai` (`quy_che / quy_dinh / dieu_le / danh_muc`). Dạng "quyết định ban hành kèm theo quy chế" rất phổ biến ở cấp NHNN. Đây là kiểu lỗi **va chạm khoá im lặng** — nguy hiểm hơn vắng mặt, vì nó tạo ra dữ liệu sai chứ không phải dữ liệu thiếu.

Cạnh đi kèm: `CO_CHUA` từ `VanBan` xuống cả hai node này, rồi từ chúng xuống `Dieu`.

> **Không mô hình hoá được — ghi nhận thẳng.** Gạch đầu dòng dưới điểm **không có số hiệu**, nên không có cách nào tạo địa chỉ ổn định cho nó. Không văn bản nào dẫn chiếu tới một gạch đầu dòng cụ thể được, kể cả trên giấy. Nội dung gạch đầu dòng nằm trong `noi_dung` của điểm cha; đây là giới hạn của **hệ thống pháp luật**, không phải của schema.

### Tầng B — Tổ chức & tham chiếu

- **`CoQuanBanHanh`** — `ten`, `ten_viet_tat`, `cap`, `loai_quyen`.
- **`LinhVuc`** — `Thanh toán không dùng tiền mặt`, `Thẻ ngân hàng`, `Trung gian thanh toán`, `Phòng chống rửa tiền`, `Cấp tín dụng`, `Tài sản mã hóa`, `Sandbox Fintech`, `Bảo vệ dữ liệu cá nhân`, `An toàn hệ thống thông tin`.
- **`DeMuc`** *(P2, tùy chọn)* — đề mục Bộ pháp điển.

### Tầng C — Ngữ nghĩa pháp lý

- **`KhaiNiem`** *(P1 — đã chốt đưa vào)*: `thuat_ngu`, `dinh_nghia`, `nguon_dieu_khoan`, `chuan_hoa` (dạng đã chuẩn hóa để gộp biến thể chính tả). Trích từ điều "Giải thích từ ngữ". Đây là tầng khác biệt học thuật của đề tài.
- **`ThucTheChiuDieuChinh`** *(P2 — làm nếu còn thời gian)*: `Ngân hàng thương mại`, `Chi nhánh ngân hàng nước ngoài`, `Tổ chức cung ứng dịch vụ trung gian thanh toán`, `Doanh nghiệp tham gia cơ chế thử nghiệm`...
- **`VuAn` / án lệ — ĐÃ LOẠI BỎ.** Việt Nam theo hệ dân luật; số án lệ chính thức chỉ vài chục và gần như không có án lệ nào thuộc fintech / thanh toán. Câu hỏi fintech trả lời được trọn vẹn từ VBQPPL.

---

## 2. Các loại Quan hệ

### Nhóm 1 — Cấu trúc

| Cạnh | Từ → Đến | Ý nghĩa |
|---|---|---|
| `CO_CHUA` | VanBan → (VanBanKemTheo \| PhuLuc)? → Chuong → Muc → Dieu → Khoan → Diem | Phân cấp chứa đựng; hai node giữa là tuỳ chọn, xem A4.c |
| `BAN_HANH_BOI` | VanBan → CoQuanBanHanh | |
| `KE_THUA_CO_QUAN` | CoQuanBanHanh(mới) → CoQuanBanHanh(cũ) | Cơ quan kế thừa sau tổ chức lại — v0.4 #7, xem A1.b |
| `THUOC_LINH_VUC` | VanBan / Dieu → LinhVuc | |
| `DINH_NGHIA` | Dieu / Khoan → KhaiNiem | Điều khoản định nghĩa khái niệm |
| `SU_DUNG_KHAI_NIEM` | Dieu → KhaiNiem | Điều có dùng thuật ngữ (cho truy hồi ngữ nghĩa) |
| `DIEU_CHINH` | Dieu / VanBan → ThucTheChiuDieuChinh | *(P2)* |
| `PHAP_DIEN_VAO` | Dieu → DeMuc | *(P2)* |

### Nhóm 2 — Quan hệ giữa các văn bản *(13 loại sau khi gộp)*

Quy ước chiều: **văn bản chủ động / mới → văn bản bị tác động / cũ**. Cột "được…" trên giao diện vbpl chỉ là **đi ngược mũi tên**, không phải cạnh mới.

| Cạnh | Từ → Đến | Chiều thuận | Đọc ngược |
|---|---|---|---|
| `CAN_CU` | VanBan → VanBan | A căn cứ vào B để ban hành | B là căn cứ cho A |
| `QUY_DINH_CHI_TIET_HUONG_DAN` | VanBan → VanBan | A quy định chi tiết / hướng dẫn B | B được A chi tiết hóa |
| `SUA_DOI_BO_SUNG` | VanBan→VanBan **và** Dieu→Dieu | A sửa đổi, bổ sung B | B được A sửa đổi |
| `THAY_THE` | VanBan → VanBan | A thay thế B | B bị A thay thế |
| `DINH_CHINH` | VanBan → VanBan | A đính chính B | B được A đính chính |
| `BAI_BO` | VanBan/Dieu → VanBan/Dieu | A bãi bỏ B | B bị A bãi bỏ |
| `HOP_NHAT` | VBHN → VanBan | VBHN A hợp nhất B | B được hợp nhất vào A |
| `DAN_CHIEU` | Dieu/Khoan/Diem → Dieu/Khoan/Diem/VanBan | A dẫn chiếu tới B — **cho phép nhiều đích từ một vế nguồn** | B được A dẫn chiếu |
| `CHAM_DUT_AP_DUNG` | VanBan → VanBan | A ấn định thời điểm ngừng áp dụng B *(A không sửa, không bãi bỏ B)* | B ngừng được áp dụng theo A |
| `DINH_CHI_THI_HANH` | VanBan → VanBan | A đình chỉ thi hành B | B bị A đình chỉ |
| `TAM_NGUNG_HIEU_LUC` | VanBan → VanBan | A làm ngưng hiệu lực B | B bị A ngưng hiệu lực |
| `GIAI_THICH` | VanBan → VanBan | A giải thích B | B được A giải thích |
| `CONG_BO` | VanBan → VanBan | A công bố B | B được A công bố |

> **Về việc gộp:** `QUY_DINH_CHI_TIET` (luật ủy quyền tường minh, tạo quy phạm mới, điều luật gốc không thi hành được nếu thiếu) và `HUONG_DAN_AP_DUNG` (làm rõ cách áp dụng quy phạm vốn đã đầy đủ, không tạo quy phạm mới) khác nhau về lý thuyết nhưng ranh giới thực tế rất mờ, và chính vbpl.vn cũng dùng nhãn gộp. Gộp thành một cạnh với thuộc tính `loai: "chi_tiet" | "huong_dan" | "khong_ro"` giúp tiết kiệm đáng kể công gán nhãn mà không mất thông tin — ai cần tách vẫn lọc được theo thuộc tính.

#### 2.a. `CHAM_DUT_AP_DUNG` — thay đổi v0.4 #6

Điều 3 Luật 87/2025 phơi bày một hình thái quan hệ mà mười hai cạnh cũ không diễn tả được: **văn bản A ấn định thời điểm ngừng áp dụng văn bản B mà không sửa đổi cũng không bãi bỏ B**. Ở đó, một nghị quyết của HĐND cấp xã quy định thời điểm không áp dụng nghị quyết cấp huyện cũ trong địa giới của mình. B vẫn nguyên văn, vẫn tồn tại, chỉ là hết được áp dụng.

Hình thái này **không chỉ có ở cấp địa phương** — ở cấp thông tư nó xuất hiện dưới dạng điều khoản chuyển tiếp ấn định ngày một thông tư cũ ngừng áp dụng cho một nhóm đối tượng. Vì vậy cạnh này được giữ trong schema dù lớp không gian (§4.5) nằm ngoài phạm vi.

Kèm theo là thuộc tính **`nguon_hieu_luc_den`** trên `VanBan` và `PhienBanDieu`, ba giá trị:

| Giá trị | Nghĩa |
|---|---|
| `khang_dinh` | ngày kết thúc được nêu tường minh trong một văn bản có trong corpus |
| `suy_ra` | tính được từ quan hệ đã có (`THAY_THE`, phiên bản kế tiếp) |
| `mac_dinh` | rơi vào mốc trần chung, **không** có văn bản cụ thể nào nói |

Không có trường này thì một `hieu_luc_den` do suy đoán trông y hệt một `hieu_luc_den` đọc được từ văn bản, và toàn bộ phần đánh giá độ tin cậy của đồ thị mất căn cứ.

#### 2.b. Văn phạm viện dẫn — cơ sở khai thác `DAN_CHIEU`

Phụ lục I Mục 2 Phần V điểm 6 quy định **cách viết viện dẫn**, và quy định này chặt tới mức đủ dùng làm luật trích xuất: `Điều` viết hoa, `khoản` và `điểm` viết thường, thứ tự cố định **điểm → khoản → Điều → của → tên văn bản**.

```
(điểm <chữ cái>\s+)?(khoản <số>\s+)?Điều\s+<số>(<chữ>)?(\s+của\s+<tên văn bản>)?
```

Một vế nguồn có thể dẫn chiếu tới nhiều đích trong cùng một câu (`các điều 5, 7 và 9`), nên `DAN_CHIEU` **không** ràng buộc một-một. Mỗi cạnh mang `do_tin_cay` riêng vì phần đích không ghi tên văn bản (viện dẫn nội bộ) chắc chắn hơn hẳn phần phải phân giải tên văn bản thành số hiệu.

Nguồn thứ hai gần như miễn phí: **phần căn cứ ban hành** ở đầu mỗi văn bản — mỗi căn cứ một dòng, kết thúc bằng dấu chấm phẩy, chứa cả số hiệu lẫn tên đầy đủ. Đây vừa là mỏ cạnh `CAN_CU` vừa là bảng tra *tên văn bản → số hiệu* để phân giải các viện dẫn chỉ ghi tên.

> **Bẫy khi tách từ PDF:** Phụ lục I ấn định cỡ chữ 13–14 cho **mọi** cấp bố cục, phân biệt chỉ bằng đậm/nghiêng và thụt đầu dòng. Mọi giải thuật tách cấu trúc dựa vào cỡ chữ **chắc chắn thất bại** trên văn bản Việt Nam. Phải tách bằng mẫu đánh số ở đầu dòng.

### Nhóm 3 — Temporal *(MỚI)*

| Cạnh | Từ → Đến | Ý nghĩa |
|---|---|---|
| `CO_PHIEN_BAN` | Dieu → PhienBanDieu | Điều có các phiên bản |
| `KE_THUA` | PhienBanDieu(mới) → PhienBanDieu(cũ) | Phiên bản mới kế thừa phiên bản trước — **chiều mới→cũ, đúng nguyên tắc #2** |
| `TAO_PHIEN_BAN` | VanBan → PhienBanDieu | Văn bản sửa đổi nào đã sinh ra phiên bản này *(nguồn gốc / provenance)* |

Ba cạnh này là toàn bộ chi phí cấu trúc của tính năng tra cứu điểm-thời-gian. `KE_THUA` cho phép duyệt lịch sử tuần tự mà không cần sắp xếp theo ngày; `TAO_PHIEN_BAN` là thứ tạo ra câu trả lời có giải trình ("Điều 41 bản này có hiệu lực từ 05/11/2025 do khoản 3 Điều 1 TT 41/2025/TT-NHNN sửa đổi").

---

## 3. Thuộc tính trên cạnh

Quan trọng nhất với `SUA_DOI_BO_SUNG`, `BAI_BO`, `THAY_THE` — cần biết *cái gì sửa cái gì, từ khi nào*:

```cypher
(TT41_2025)-[:SUA_DOI_BO_SUNG {
    dieu_khoan_nguon: "khoản 3 Điều 1",   // vế thực hiện sửa đổi (trong TT 41/2025)
    dieu_khoan_dich:  "Điều 41",          // vế bị sửa (trong TT 40/2024)
    nhanh_dich:       "than",             // than | kemtheo_<slug> | phuluc_<La Mã>  → v0.4 #1
    loai_thao_tac:    "sua_doi",          // sua_doi | bo_sung | thay_the_cum_tu | bai_bo
    ngay_hieu_luc:    date("2025-11-05"), // CHÚ Ý: TT 41/2025 có hiệu lực phân kỳ — xem ghi chú dưới
    trich_dan_nguon:  "https://congbao.chinhphu.vn/van-ban/thong-tu-so-41-2025-tt-nhnn-46540/59662.htm",
    do_tin_cay:       "thu_cong"          // thu_cong | rule_based | llm  → phục vụ đánh giá chất lượng trích xuất
}]->(TT40_2024)
```

> **Vì sao `ngay_hieu_luc` nằm trên cạnh chứ không trên `VanBan`:** TT 41/2025 là ví dụ sống của **hiệu lực phân kỳ** — một số điều sửa đổi lùi tới 01/01/2026 trong khi phần còn lại có hiệu lực ngay. Nếu ngày hiệu lực chỉ nằm ở cấp văn bản thì mọi phiên bản sinh ra từ nó đều mang sai ngày. Cạnh là nơi duy nhất đủ mịn để giữ đúng.

Thuộc tính `do_tin_cay` không thừa: nó cho phép báo cáo riêng độ chính xác của phần trích xuất tự động so với phần gán tay, vốn là một phần bắt buộc của đánh giá thực nghiệm.

---

## 4. Lớp temporal chọn lọc *(phần cốt lõi của v0.2)*

### 4.1 Mô hình

```
    (TT40_2024:VanBan) ──CO_CHUA──▶ (D41:Dieu {id:"40/2024/TT-NHNN#than/dieu_41"})
                                         │
                                    CO_PHIEN_BAN
                            ┌────────────┼────────────┐
                            ▼            ▼            ▼
                   ┌─────────────┐┌─────────────┐┌─────────────┐
                   │  D41@v1     ││  D41@v2     ││  D41@v3     │
                   │ tu 2024-07-17│◀│tu 2025-11-05│◀│tu 2026-05-19│
                   │ den 2025-11-05││den 2026-05-19││ den  NULL  │
                   └─────────────┘└─────────────┘└─────────────┘
                          ▲       KE_THUA ▲   KE_THUA  ▲
                   TAO_PHIEN_BAN          │            │
                          │               │            │
                   (TT40_2024)      (TT41_2025)  (TT22_2026)
```

Chú ý biên: `v1.hieu_luc_den = v2.hieu_luc_tu = 2025-11-05`. Ngày 05/11/2025 thuộc về **v2**, đúng với thực tế pháp lý là văn bản sửa đổi có hiệu lực *kể từ* ngày đó.

Cụm này được chọn làm ví dụ xuyên suốt vì nó có **ba** phiên bản chứ không phải hai — chuỗi ba mắt là thứ duy nhất bộc lộ được lỗi ở mắt giữa, vốn là lỗi hay gặp nhất khi sinh phiên bản tự động.

### 4.2 Vị từ tra cứu điểm-thời-gian

Toàn bộ tính năng quy về **một** vị từ duy nhất, dùng lại ở mọi truy vấn:

```cypher
p.hieu_luc_tu <= $T AND (p.hieu_luc_den IS NULL OR $T < p.hieu_luc_den)
```

Sự đơn giản này chính là lý do chọn quy ước nửa mở. Nếu dùng khoảng đóng `[tu, den]` với `den = tu_kế_tiếp - 1`, mỗi lần nhập liệu đều phải trừ ngày thủ công và mọi lỗi lệch biên sẽ âm thầm cho ra câu trả lời sai đúng ở ngày quan trọng nhất — ngày văn bản có hiệu lực.

### 4.3 Quy trình sinh phiên bản

Từ mỗi cạnh `SUA_DOI_BO_SUNG` ở cấp `Dieu → Dieu`:

1. Đọc `loai_thao_tac` và `dieu_khoan_dich` để biết phạm vi tác động.
2. Lấy phiên bản đang mở của điều đích (`hieu_luc_den IS NULL`).
3. Áp thao tác lên `noi_dung` của phiên bản đó → văn bản mới.
4. Đóng phiên bản cũ: `hieu_luc_den = ngay_hieu_luc` của cạnh sửa đổi.
5. Tạo phiên bản mới với `hieu_luc_tu = ngay_hieu_luc` của cạnh, `hieu_luc_den = null`, nối `KE_THUA` về phiên bản cũ và `TAO_PHIEN_BAN` từ văn bản sửa đổi.
6. Đồng bộ `Dieu.noi_dung` / `Dieu.tieu_de` với phiên bản mới nhất.

Bước 3 là bước khó duy nhất. Điểm thuận lợi lớn: văn phong sửa đổi VBQPPL Việt Nam **cực kỳ khuôn mẫu** và được Nghị định 78/2025/NĐ-CP quy định thể thức, dạng `Sửa đổi, bổ sung khoản 3 Điều 5 như sau: "…"` với phần thay thế đặt trong ngoặc kép. Phần lớn xử lý được bằng luật (regex + quy tắc), LLM chỉ dọn phần đuôi bất quy tắc.

### 4.4 Đối chiếu với văn bản hợp nhất — nguồn ground truth miễn phí

NHNN công bố VBHN chính thức cho các cụm sửa đổi. Nghĩa là kết quả bước 3 **có sẵn đáp án để chấm**, không cần gán nhãn thủ công. Đây là lợi thế đánh giá hiếm có: đặt `da_doi_chieu_vbhn = true` cho mỗi phiên bản khớp VBHN, rồi báo cáo tỷ lệ khớp như một chỉ số chất lượng độc lập.

Thêm bối cảnh đáng khai thác trong phần mở đầu báo cáo: Pháp lệnh 01/2026/UBTVQH16 (hiệu lực 01/7/2026) đã nâng văn bản hợp nhất thành **căn cứ viện dẫn chính thức**, thay vì chỉ có giá trị tham khảo như trước. Việc mô hình hóa và sinh phiên bản hợp nhất do đó vừa mới trở thành vấn đề có ý nghĩa pháp lý.

### 4.5 Lớp không gian — ghi nhận nhưng KHÔNG làm trong 6 tuần

Điều 3 Luật 87/2025 cho thấy hiệu lực của văn bản cấp huyện là **hàm của (thời gian × địa giới)**, không phải hàm của thời gian:

```
hieu_luc_den(H, X) = min( ngày xã X quy định,
                          ngày cơ quan cấp trên quy định,
                          2027-03-01 )
```

Cùng một văn bản cấp huyện H có thể đã hết áp dụng ở xã X nhưng còn áp dụng ở xã Y. Mô hình đúng cần `(:VanBan)-[:CO_HIEU_LUC_TAI {tu, den}]->(:DiaGioi)`, trong đó `DiaGioi` là **ảnh chụp ranh giới có vòng đời riêng** — ranh giới huyện trước sắp xếp không còn pháp nhân tương ứng nào ở hiện tại, nên nó là thực thể có phiên bản thứ tư trong đề tài.

Mốc `2027-03-01` là mốc trần nửa mở, tương ứng "hết ngày 28/02/2027". Năm 2027 **không nhuận**, nên 28/02 đúng là ngày cuối tháng Hai.

**Quyết định phạm vi:** không dựng lớp này. Corpus fintech **toàn bộ là văn bản trung ương**, nơi địa giới không biến thiên — chi phí thì bằng cả một chiều mô hình mới, còn lợi ích trên corpus này bằng không. Cái được giữ lại là cạnh `CHAM_DUT_AP_DUNG` và trường `nguon_hieu_luc_den` (§2.a), vì hình thái "ngày chấm dứt nằm trong một văn bản thứ ba" có thật ở cấp thông tư.

> **Một điều Điều 3 nói mà `ngay_het_hieu_luc` không giữ được:** ngày 28/02/2027 mang **hai vai trò pháp lý khác nhau** — ở khoản 1 nó là ngày cuối cùng còn hiệu lực, ở khoản 2 nó là **hạn chót của một nghĩa vụ** đặt lên HĐND/UBND cấp xã. Gộp cả hai vào một trường ngày làm mất hẳn vế nghĩa vụ. Đây chính là chỗ đồ thị quy phạm nghĩa vụ (deontic / normative rule graph) ở Phần B có đất dùng — ghi nhận trong báo cáo, không cài đặt.

---

## 5. Phân tầng corpus — văn bản nào được đối xử ra sao

> **Trạng thái dữ liệu (cập nhật v0.4):** danh mục dưới đây đã được đối chiếu Công báo và ghi trong `corpus-seed-daxacminh.csv` với cột `muc_xac_minh` cho từng dòng. Các văn bản còn ở mức `chua_xac_minh` được đánh dấu rõ. Bản v0.2 từng dùng cặp `18/2025` ← `45/2025` — **hai số hiệu bịa** — nay đã bị loại khỏi mọi tệp.

### Nhóm NÓNG — `muc_temporal = "day_du"`, có `PhienBanDieu`, có `Khoan`, có `Diem` theo nhu cầu

Chọn theo hai tiêu chí: (a) đã bị sửa đổi ít nhất một lần trong khung thời gian nghiên cứu, (b) là trung tâm câu hỏi fintech thực tế.

| Văn bản | Lĩnh vực | Vì sao thuộc nhóm nóng | Nguồn |
|---|---|---|---|
| TT 40/2024/TT-NHNN | Trung gian thanh toán (ví điện tử) | **Gốc của chuỗi ba phiên bản** — văn bản mẫu của script Cypher | Công báo |
| TT 41/2025/TT-NHNN | Trung gian thanh toán | Sửa đổi lần 1 → sinh v2; **có hiệu lực phân kỳ** | Công báo |
| TT 22/2026/TT-NHNN | Trung gian thanh toán | Sửa đổi lần 2 → sinh v3; hiệu lực 19/5/2026, nằm giữa kỳ nghiên cứu | Công báo |
| TT 17/2024/TT-NHNN | Mở & sử dụng tài khoản thanh toán | Gốc của chuỗi hai phiên bản | Công báo |
| TT 25/2025/TT-NHNN | Mở & sử dụng tài khoản thanh toán | Sửa đổi → sinh v2; **bổ sung Điều 15a** → ca thử `so_dieu_hau_to` | Công báo |
| NĐ 52/2024/NĐ-CP | Thanh toán không dùng tiền mặt | HUB của toàn miền; `THAY_THE` → NĐ 101/2012 | thứ cấp |

Hai cụm này hội đủ **mọi hiện tượng** cần minh họa: thay thế toàn bộ, sửa đổi từng khoản, chuỗi ba mắt, điều bổ sung có hậu tố chữ cái, hiệu lực phân kỳ, và hai cạnh khác loại giữa cùng cặp node. Không cần thêm gì để chứng minh mô hình đúng.

> **Còn thiếu để chốt nhóm nóng:** toàn văn các điều bị sửa của TT 41/2025, TT 22/2026, TT 25/2025; và một VBHN của TT 40/2024 ban hành sau 19/5/2026 để làm ground truth (§4.4). Nếu không tìm được VBHN cho cụm 40/2024 thì cụm 17/2024 thay thế vai trò đó.

### Nhóm ẤM — `muc_temporal = "co_ban"`, có `Khoan`, không có phiên bản

Luật Các TCTD 32/2024/QH15 · Luật PCRT 14/2022/QH15 · NĐ 94/2025/NĐ-CP (cơ chế thử nghiệm có kiểm soát trong lĩnh vực ngân hàng). Đây là các văn bản nền hay được dẫn chiếu, cần phân rã sâu để trả lời câu hỏi, nhưng ổn định về thời gian.

### Nhóm NỀN — `muc_temporal = "co_ban"`, chỉ tới `Dieu`

Phần còn lại của corpus (~7 văn bản): các thông tư về mở và sử dụng tài khoản thanh toán, cung ứng dịch vụ thanh toán, hoạt động trung gian thanh toán, an toàn hệ thống thông tin, quyết định về xác thực sinh trắc học, và các văn bản về bảo vệ dữ liệu cá nhân có liên quan.

**Tổng quy mô mục tiêu:** 12–15 văn bản · ~600–900 `Dieu` · ~1.500 `Khoan` cho nhóm nóng + ấm · ~60–120 `PhienBanDieu` · ~150 `KhaiNiem`.

Con số `PhienBanDieu` đáng chú ý: chỉ khoảng 60–120 node cho toàn bộ tính năng. Chi phí thật của temporal chọn lọc **không nằm ở số node** mà nằm ở công tái dựng nội dung từng phiên bản.

---

## 6. Ràng buộc & chỉ mục

- `VanBan.id`, `Dieu.id`, `Khoan.id`, `Diem.id`, `PhienBanDieu.id`, `PhuLuc.id`, `VanBanKemTheo.id` — UNIQUE.
- `Dieu.nhanh` bắt buộc có giá trị (`than` / `kemtheo` / `phuluc`) — **không** cho `null`, vì `null` ở đây là dữ liệu cũ chưa di trú chứ không phải "thân văn bản".
- Mỗi `Dieu` phải có đủ bộ ba `so_dieu_hien_thi`, `so_dieu_goc`, `so_dieu_hau_to`; truy vấn kiểm tra: dựng lại `so_dieu_hien_thi` từ cặp số và so với giá trị đã lưu.
- `so_hieu_chuan_hoa` — có chỉ mục, **không** unique (hai cơ quan khác thời kỳ có thể trùng, xem A1.b).
- `KhaiNiem` — **không** unique theo `thuat_ngu` (cùng thuật ngữ có thể được định nghĩa khác nhau ở nhiều văn bản, ví dụ "ví điện tử"); unique theo cặp `(thuat_ngu, nguon_dieu_khoan)`.
- Mọi `VanBan` phải có ≥1 `BAN_HANH_BOI`.
- Mọi `Dieu` thuộc văn bản `muc_temporal = "day_du"` phải có ≥1 `PhienBanDieu`.
- Chỉ mục trên `VanBan.loai_van_ban`, `VanBan.ngay_hieu_luc`, `PhienBanDieu.hieu_luc_tu`, `PhienBanDieu.hieu_luc_den`, `KhaiNiem.chuan_hoa`.
- Chỉ mục toàn văn (full-text) trên `Dieu.noi_dung` và `PhienBanDieu.noi_dung` để kết hợp truy hồi từ khóa với duyệt đồ thị.

---

## 7. Kế hoạch 6 tuần

| Tuần | Việc | Sản phẩm kiểm chứng được |
|---|---|---|
| 1 | Chốt corpus, crawl vbpl.vn + congbao, tách `Dieu` bằng mẫu đánh số đầu dòng *(không dùng cỡ chữ — §2.b)* | Số Điều tách ra khớp với số Điều thật của từng văn bản; điều có hậu tố (`15a`) tách đúng |
| 2 | Nạp Neo4j: `VanBan`, `Dieu`, cấu trúc, 13 quan hệ liên văn bản | Lược đồ TT 40/2024 trong đồ thị khớp lược đồ vbpl.vn |
| 3 | **Lớp temporal**: `PhienBanDieu` cho nhóm nóng, sinh phiên bản | 4 bất biến §A3 đều pass |
| 4 | Đối chiếu VBHN, tầng `KhaiNiem`, hoàn thiện `Khoan` nhóm nóng+ấm | Tỷ lệ khớp VBHN có số cụ thể |
| 5 | Bộ đánh giá: 30 câu hỏi × 3 mốc thời gian; chạy baseline không temporal | Bảng so sánh accuracy có chênh lệch quy được về đúng biến temporal |
| 6 | Viết báo cáo, demo tra cứu điểm-thời-gian | |

Đường găng là tuần 3. Nếu bước sinh phiên bản chậm hơn dự kiến, phương án lùi: thu nhóm nóng xuống **chỉ cụm trung gian thanh toán** (TT 40/2024 + 41/2025 + 22/2026, hạ NĐ 52/2024 và cụm 17/2024 xuống nhóm ấm). Chuỗi ba mắt một mình vẫn đủ cho toàn bộ luận điểm.

---

## 8. Rủi ro & kiểm soát chất lượng

**Rủi ro dữ liệu.** Toàn văn bản gốc thì có sẵn, nhưng *toàn văn của một Điều tại một ngày bất kỳ* thì không nơi nào công bố — phải tái dựng. Đây là phần lao động thật, và cũng chính là đóng góp của đề tài.

**Rủi ro nguồn.** thuvienphapluat.vn có dữ liệu quan hệ điều khoản tốt nhưng nằm sau tài khoản trả phí kèm theo dõi hành vi, mỗi khoản là một lời gọi API riêng. Chỉ dùng để **đối chiếu thủ công điểm lẻ**. Crawl hàng loạt phải nhắm vào vbpl.vn và congbao.chinhphu.vn — miễn phí, chính thống.

**Rủi ro nhất quán.** Ba nhóm truy vấn kiểm tra phải chạy sau mỗi lần nạp: khoảng hiệu lực chồng lấn hoặc hở; phiên bản có `hieu_luc_tu` sớm hơn ngày hiệu lực của văn bản sinh ra nó; `Dieu.noi_dung` lệch với phiên bản mới nhất. Chi tiết trong file `truy-van-diem-thoi-gian.cypher`.

Đáng nói: chính các truy vấn này thường phát hiện bất nhất **trong dữ liệu nguồn chính thống** — điều còn ghi "còn hiệu lực" trong văn bản đã hết hiệu lực, hai văn bản cùng tuyên bố thay thế một văn bản. Thống kê được các lỗi này là một quan sát có thể báo cáo, và nó chỉ xuất hiện *nhờ* mô hình temporal.

---

## 9. Tệp đi kèm

- `init-neo4j-fintech-kg.cypher` — script khởi tạo: ràng buộc, chỉ mục, node/cạnh mẫu cụm **TT 40/2024 ← 41/2025 ← 22/2026** với ba phiên bản Điều 41.
- `truy-van-diem-thoi-gian.cypher` — thư viện truy vấn: tra cứu as-at-date, so sánh hai mốc, sinh văn bản hợp nhất, kiểm tra chất lượng temporal.
- `corpus-seed-daxacminh.csv` — danh mục hạt giống kèm cột `nguon_xac_minh` / `muc_xac_minh` / `con_phai_kiem` cho từng văn bản.
- `schema-kg-visual.html` — sơ đồ trực quan của bản đặc tả này.
- `cau-truc-phap-luat-viet-nam.html` — Phần A: cấu trúc pháp luật Việt Nam, nguồn của tám thay đổi v0.4.

---

## 10. Việc còn mở sau v0.4

| Việc | Ai làm được | Chặn gì |
|---|---|---|
| Đếm số văn bản hạt giống dùng dạng **"quyết định ban hành kèm theo quy chế/quy định"** | Bạn — nhanh hơn tôi crawl | Quyết định mức ưu tiên của `VanBanKemTheo`; nếu bằng 0 thì node vẫn giữ trong schema nhưng không nạp dữ liệu |
| Toàn văn các điều bị sửa của TT 41/2025, TT 22/2026, TT 25/2025 | Bạn (vbpl.vn chặn robots với tôi) | Tuần 3 — không có thì không sinh được phiên bản |
| Tìm VBHN của TT 40/2024 sau 19/5/2026 | Bạn | Tuần 4 — ground truth để chấm |
| Xác minh 32/2024/QH15, 46/2010/QH12, 14/2022/QH15 | Bạn | Nhóm ẤM/NỀN; không chặn tuần 1–3 |
| Xác nhận `thu_tuc_rut_gon` từ phần căn cứ ban hành | Bạn | Không chặn — chỉ làm giàu metadata |
