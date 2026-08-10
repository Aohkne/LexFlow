# LexFlow — Việc tồn đọng

> Danh sách việc **đã biết nhưng chưa làm**, để không phải phát hiện lại. Khác với
> `ROADMAP-SPRINT.md` (kế hoạch theo sprint) và `WORKLOG.md` (nhật ký đã làm).
>
> Quy ước: mỗi mục ghi **vì sao quan trọng** và **bước đầu tiên cụ thể** — đủ để người khác
> (hoặc chính mình ba tuần sau) bắt tay vào mà không phải điều tra lại. Mọi con số đều kèm
> ngày đo; số không có ngày là số chưa kiểm.
>
> Cập nhật gần nhất: 2026-08-10.

---

## Chặn — cần người quyết trước khi làm

### [ ] T1 · Re-ingest LanceDB để bản vá chunking tới production

Commit `8dd53f0` (09/08) sửa nhánh chẻ dự phòng, nhưng **LanceDB Cloud vẫn giữ 3 chunk cũ**
của `TT66-2025 Điều 6` — bản cắt giữa chữ "ngân" thành `ngâ` + `n`.

- Vì sao quan trọng: điều này nằm trên đường nóng của lớp phủ (cạnh
  `66/2025/TT-NHNN#than/dieu_6 → 34/2024/TT-NHNN#than/dieu_9#khoan_2#diem_đ`), nên chữ kéo
  vào prompt hiện mở đầu bằng nửa câu.
- Giá phải trả: `write_lancedb` **embed lại toàn bộ 661 chunk** rồi
  `create_table(mode="overwrite")` — không có đường cập nhật 3 hàng riêng lẻ. Tức là tốn
  embedding cho cả bảng và ghi đè bảng đang phục vụ.
- Bước đầu: gộp luôn với **T2** trong cùng một lượt, rồi
  `uv run python -m app.ingestion data/corpus.real.json`.
- **Chờ duyệt** (ghi lên cloud).

---

## Chất lượng dữ liệu

### [ ] T2 · Trùng id chunk ở TT23-2019 — 5 id / 7 hàng

Đo 09/08 trên `data/corpus.real.json`:

```
TT23-2019::Điều 1 Khoản 2    x3   ← ba chunk KHÁC NHAU, cùng một id
TT23-2019::Điều 1 Khoản 6    x3
TT23-2019::Điều 1 Khoản 1    x2
TT23-2019::Điều 1 Khoản 3-4  x2
TT23-2019::Điều 1 Khoản 5    x2
```

- Nguyên nhân: TT23-2019 là văn bản **sửa đổi**, cả Điều 1 (55.902 ký tự → 27 mảnh) chép lại
  nguyên văn nhiều điều của TT39-2014, nên số khoản **khởi động lại nhiều lần** trong cùng
  một điều. Kèm 6 nhãn vô nghĩa kiểu `Khoản 18-1`, `Khoản 11-7` (số đầu > số cuối).
- Vì sao quan trọng: `_rrf()` gom kết quả vào `dict` khoá bằng `row["id"]` — hai chunk trùng
  id cùng lọt vào pool thì **một cái bị nuốt**, và trích dẫn trỏ tới một địa chỉ có ba nội
  dung khác nhau. Hiện chưa gây hại thấy được vì TT23-2019 đã hết hiệu lực
  (`valid_to = 2024-07-17`) nên bị lọc ra; sẽ nổ ngay khi có văn bản sửa đổi **còn hiệu lực**
  cấu trúc tương tự.
- Bước đầu: trong `pipeline._split_khoan`, nhãn đã tồn tại trong cùng doc thì thêm hậu tố thứ
  tự (`Điều 1 Khoản 2 (2)`); giữ nguyên ngưỡng và luật chẻ. Test ghim đúng ca TT23-2019.

### [x] T3 · Gemini có cắt đuôi chunk dài không — ĐÃ ĐO 09/08

**Có cắt, ở ~7.156 ký tự (±32)** — nhưng chỉ **1/661 chunk** vượt ngưỡng đó.

Đo bằng `scripts/do_gioi_han_embed.py` (gắn câu mốc vào cuối chuỗi rồi so vector: mốc không
làm đổi vector ⇒ nó không tới được model). Đo trên chuỗi **thật sự được embed** —
`"{doc_title} — {article}: {text}"`, không phải mình `text`.

```
model              gemini-embedding-001 · 768 chiều
ngưỡng đo được     ~7156 ký tự
chuỗi > _MAX_CHUNK  98/661     (đếm cả tiền tố tiêu đề)
chunk MẤT ĐUÔI      1/661
   TT23-2019::Điều 1 Khoản 6   9746 ký tự — mất 2590
```

- Kết luận: `_MAX_CHUNK = 2000` là lựa chọn về **độ chính xác retrieval**, không phải ràng
  buộc của API — còn cách trần thật hơn ba lần. 97 chunk vượt ngưỡng chẻ vẫn vào vector trọn vẹn.
- Chunk duy nhất mất đuôi thuộc TT23-2019, văn bản **đã hết hiệu lực** (`valid_to = 2024-07-17`)
  nên bị lọc khỏi mọi đường truy hồi mặc định ⇒ tác hại hôm nay bằng 0. Cũng chính là văn bản
  của **T2** — sửa T2 (chẻ Điều 1 dài 55.902 ký tự) thì mục này tan theo.
- Đo lại khi đổi model embedding hoặc khi nạp văn bản mới có khoản dài bất thường.

### [ ] T16 · Hai đơn vị mất/lệch nút vì nguồn không gắn `prov-*`

Đã **soi DOM xác nhận 09/08**, không phải suy từ JSON đã parse. Cả hai đoạn nằm trong
`<p class="flex flex-col gap-[10px] p-2 rounded-md">` — class layout của Tailwind, không phải
class ngữ nghĩa; các khoản anh em ngay cạnh thì vẫn `<p class="prov-clause">`. Chữ **không
mất** (vẫn đủ trong `noi_dung`), chỉ mất nhãn ngữ nghĩa. Tầng cào chép trung thực, parser đi
đúng markup nguồn gắn — lỗi là của nguồn.

**a) TT15-2024 Điều 15 — nút treo nhầm cha.** Nguồn đẩy cả hai đoạn `b)` xuống sau `c)` của
khoản 2, nên cả hai bám vào khoản 2 (`[a, c, b, b]`) còn khoản 1 mất điểm b (`[a, c]`). Điều 14
khoản 2 cùng kiểu (`[a, b, a, b, c]`). **Tổng số Điểm vẫn đúng** nên `check_tree_coverage`
(đếm tổng) mù hoàn toàn; `check_unit_sequence` (commit `bdba00b`) nay bắt được — chạy trên 14
văn bản ra 3 cảnh báo, đều thuộc văn bản này, 13 văn bản còn lại sạch.

**b) TT40-2024 Điều 25 — mất nút khoản 1.** Nguồn viết `1.Việc nạp tiền` thiếu dấu cách nên
không được gắn `prov-clause`; khoản 1 không thành nút và các điểm a–đ của nó mồ côi treo thẳng
dưới Điều. Đã có `canh_bao` "thiếu dấu cách sau số khoản" bắt đúng ca này.

- Vì sao quan trọng: đây là 2 trong 104 đơn vị bị đánh dấu **không tra ra nguyên văn** trong
  bảng đối chiếu của trình xem (86 tra ra, 16 còn lại là `bo_sung` nên vốn chưa tồn tại trong
  bản gốc — đo 09/08). Modal đang nói thẳng "không tìm thấy nguyên văn" chứ không để trống.
- **KHÔNG sửa bằng cách đoán.** Đoán đoạn `b)` nào thuộc khoản nào là đoán hộ nguồn, mà chính
  nguồn đang tự mâu thuẫn — ở TT15 hai đoạn `b)` còn nằm sai thứ tự ngay trong luồng chữ.
  Suy nút từ tiền tố cũng chính là chuẩn hoá ngầm mà dự án cấm.
- Bước đầu: đây là việc **báo cho nguồn / chờ nguồn sửa**, không phải việc của parser. Trong
  lúc chờ, hai cảnh báo trên đã đủ để không ai phát hiện lại. Chỉ mở lại nếu số ca tăng — lúc
  đó mới đáng cân nhắc một lớp vá có kiểm chứng hai chiều.

### [ ] T4 · 8 văn bản ngoài chưa có bảng thuộc tính

`ND101-2012 · TT17-2024 · TT18-2024 · TT20-2016 · TT23-2014 · TT23-2019 · TT39-2014 · TT46-2014`

- Tình trạng 09/08: **14/26** văn bản có `co_quan_ban_hanh`; 4 văn bản nội bộ SHB không có
  nguồn vbpl nên không tính là thiếu.
- Chặn: `vbpl search` không tìm ra URL của 8 văn bản này qua sitemap — **phải lấy URL tay**.
- Sau khi có URL: cào → `enrich_corpus_from_vbpl.py --tu-thu-muc` → deploy lại (xem T5).
- Phần thưởng kèm: ND101-2012 (16 đơn vị bị tác động) và TT39-2014 (4) chiếm **toàn bộ 20
  badge cấp khoản đang không bind được**.

### [ ] T5 · Canonical chưa từng tồn tại trên Supabase Storage

Bucket `legal-docs` rỗng, bảng `legal_documents` rỗng — nghĩa là **chưa văn bản nào đi qua
workflow `/admin` duyệt**. `app/core/corpus.py` fallback về file đóng gói trong image, nên
production đang phục vụ `data/corpus.real.json` của lần build gần nhất.

- Hệ quả thực dụng: **mọi thay đổi corpus đều phải deploy lại image**, `sync_corpus_storage.py`
  không giải quyết được.
- Bước đầu: chạy thử luồng `/admin` duyệt một văn bản để đường đó có ít nhất một lần chạy
  thật trước kỳ đánh giá — hiện nó chưa từng được kiểm trên production.

---

## Độ phủ tri thức

### [ ] T6 · 39/177 cạnh lớp phủ trỏ tới văn bản ngoài corpus

Đo lại 10/08 trên `data/overlay/lop_phu.json`. Router trả `None` cho chúng — **đúng thiết kế**,
nhưng đó là trần độ phủ hiện tại. Muốn nâng thì phải **mở corpus**, không phải sửa router.

Mẫu số đổi 178 → 177 vì bỏ một cạnh giả (xem T16-b), không phải mất độ phủ: cạnh đó trỏ vào
TT40-2024 — văn bản **có** trong corpus — nên tử số 39 giữ nguyên. Chín văn bản ngoài corpus:
`10/2010/NĐ-CP · 135/2015/NĐ-CP · 19/2016/TT-NHNN · 22/2015/TT-NHNN · 36/2012/TT-NHNN ·
39/2014/NĐ-CP · 41/2024/TT-NHNN · 57/2016/NĐ-CP · 89/2016/NĐ-CP`.

### [ ] T7 · Chỉ 8/35 quan hệ có anchors mức Điều

27 quan hệ còn lại chỉ nối văn bản ↔ văn bản, không chỉ được vào điều khoản cụ thể.

### [ ] T8 · BM25 không hiểu từ ghép tiếng Việt, và không phủ tiêu đề

- Index dựng bằng tokenizer mặc định (`create_fts_index("text")`, không truyền cấu hình) —
  cắt theo khoảng trắng/ranh giới từ Unicode, **không tách từ ghép, không stemming**.
  "ví điện tử" vào index thành ba token rời.
- Bất đối xứng: text đem **embed** là `"{doc_title} — {article}: {text}"` (có tiêu đề làm ngữ
  cảnh), text đem **index BM25** chỉ là `text` trần. Hỏi "Thông tư 40 quy định gì" thì nhánh
  vector bắt được tên văn bản, nhánh BM25 không.
- Chưa đo tác động — cần một bộ câu hỏi có số hiệu/thuật ngữ ghép để biết mất bao nhiêu.

---

## Nợ kỹ thuật (parked từ review P4, 06/08)

### [ ] T11 · Ghi rõ dựng lại artefact lớp phủ cần `data/raw/vbpl/raw/`

Thư mục đó **gitignored** (22 file, 3.7 MB). Người clone repo sạch không dựng lại được
`data/overlay/lop_phu.json` và sẽ không hiểu vì sao.

Vấp đúng ca này 10/08 khi sinh lại artefact từ worktree `feat/software`: `raw/` chỉ tồn tại ở
checkout `main`. Cách giải rẻ nhất là **junction** thay vì copy, giữ một nguồn duy nhất:
`New-Item -ItemType Junction -Path data\raw\vbpl\raw -Target <checkout-main>\data\raw\vbpl\raw`.
Tác dụng phụ đáng ghi: **52 test đang bị skip nhờ đó chạy thật** (guard theo sự tồn tại của
`raw/`), và đều xanh.

Soi lại 09/08: vấn đề lớn hơn mục này. **`docs/ARCHITECTURE.md` không hề nhắc tới lớp phủ** —
cả một tầng kiến trúc đã lên sản phẩm mà tài liệu kiến trúc không biết. T11 chỉ là một triệu
chứng; nên gộp vào cùng lượt viết lại ARCHITECTURE (xem T12).

### [ ] T15 · Ba chỗ còn suy `doc_id` theo quy ước — đang có dây bẫy canh

`hien_hanh.nut_don_vi` (thuộc tính node Neo4j), `dinh_tuyen._cite` và `dinh_tuyen._tach_khoa`
(câu trích + khoá sắp xếp) vẫn gọi `doc_id_theo_corpus` thay vì hỏi bảng của artefact — xem
T10 đã đóng. Nằm sâu trong hàm sắp xếp nên luồn tham số vào là refactor rộng cho một lỗi
tác hại **bằng 0 hôm nay**.

- Đang được canh bởi `tests/test_lop_phu_anh_xa.py::test_quy_uoc_va_artefact_khong_duoc_lech`:
  mọi văn bản có mặt trong lớp phủ phải có `doc_id` mà quy ước tái tạo được.
- **Chỉ làm khi ca đó đỏ.** Đỏ nghĩa là đã có văn bản đặt tên lệch quy ước lọt vào lớp phủ
  (nhóm nội bộ SHB là ứng viên đầu tiên) — lúc đó mới đáng trả giá refactor.

---

## Tài liệu lệch với thực tế

### [ ] T12 · `docs/CORPUS.md` lỗi thời

Ghi 15 văn bản / 449 chunk / 13 quan hệ. Thực tế đo 09/08: **26 văn bản / 661 chunk /
35 quan hệ**, 425 điều. Ai đọc tài liệu để hiểu hệ thống sẽ hiểu sai quy mô.

### [ ] T13 · Mục 07/08 trong `docs/WORKLOG.md` còn câu đã sai

Mục đó ghi "Chưa tới production" và "Next: chạy sync canonical bằng tài khoản admin" — cả hai
nay đều sai: bucket rỗng nên canonical chưa từng tồn tại, và việc đã xong bằng đường **deploy
lại** (rev `lexflow-api-00019-52n`, 08/08). Bản sửa từng bị từ chối 08/08, **chờ chủ repo
quyết** viết lại thế nào.

---

## Việc của chủ repo (không giao cho AI)

### [ ] T14 · Bộ câu hỏi eval cấp khoản (backlog #19)

Chủ repo tự chuẩn bị — đã nói rõ 07/08: "về bộ câu hỏi thì tôi sẽ chuẩn bị riêng".

---

## Đã đóng

- **09/08 · T9** — Lớp phủ hỏng lặng lẽ. `/health` nay có khối `overlay` (`nap`, `so_canh`,
  `sinh_luc`) và `status` xuống `degraded` khi lớp phủ bật mà artefact không nạp được; log một
  dòng lúc khởi động. HTTP vẫn 200 ở mọi ca — không có gì đọc endpoint này bằng máy, đổi thành
  mã lỗi là biến cảnh báo thành sự cố triển khai. Nghiệm thu trên server thật, không chỉ test:
  lần chạy đầu lộ ra dòng log **không hề tồn tại** (uvicorn chỉ cấu hình `uvicorn.*`), phải đặt
  mức thẳng trên namespace `app`. Commit `85c9467`.
- **09/08 · T10** — `doc_id` suy theo quy ước thay vì hỏi bảng của artefact; 4/26 văn bản lệch,
  và 9 văn bản ngoài corpus bị **bịa** ra mã trông như thật (`ND135-2015`…) khiến web dựng link
  tới trang trống. `tach_khoa` nay tra bảng, không có thì trả `None`. Không đổi một ký tự nào
  trong response hôm nay (mọi `nguon` đều có trong bảng). Ba chỗ còn lại → **T15** + dây bẫy.
  Commit `27abe0d`.
- **09/08 · T3** — Đo được ngưỡng cắt embedding ~7.156 ký tự, chỉ 1/661 chunk vượt. Chi tiết ở
  mục T3 phía trên. Commit `83ac6dd`.
- **09/08** — Nhánh chẻ dự phòng cắt giữa từ. `TT66-2025 Điều 6` bị cắt ngay giữa chữ "ngân"
  (`ngâ` + `n`); vá bằng lưới ranh giới dòng/câu + thang bậc điểm → tiểu mục → gạch đầu dòng.
  651/654 chunk id giữ nguyên từng byte. Commit `8dd53f0`, 7 test mới, CI xanh. **Dữ liệu
  trên LanceDB vẫn là bản cũ — xem T1.**
