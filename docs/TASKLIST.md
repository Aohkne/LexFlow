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

*(Hiện không có mục nào chặn.)*

---

## Chất lượng dữ liệu

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
  nên bị lọc khỏi mọi đường truy hồi mặc định ⇒ tác hại hôm nay bằng 0.
- **Sửa 10/08:** bản ghi trước đó đoán "sửa T2 thì mục này tan theo" — **sai**. T2 chỉ đổi
  NHÃN, không chẻ nhỏ thêm; đo lại sau T2 thì chunk quá cỡ vẫn còn, chỉ mang tên mới
  `TT23-2019::Điều 1 Khoản 6 (2)` (9.750 ký tự, mất ~2.594). Muốn hết thì phải chẻ **bên
  trong một khoản** — nhánh gộp hiện chỉ ngắt *giữa* các khoản — và việc đó đổi nhãn chunk nên
  kéo theo một lượt re-ingest nữa.
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

### [x] T8 · BM25 chấm điểm túi-từ, không chấm cụm — ĐÃ SỬA 10/08

Đo trên 14 cụm **có thật** trong corpus, precision@10 của riêng nhánh BM25. Thước đo này
**tự nghiệm** ("top-10 có thật sự chứa cụm đã hỏi không") nên không cần đáp án vàng, không
phải chờ T14:

```
chỉ mục cũ  + MatchQuery        8.4/10
chỉ mục mới + MatchQuery        9.0/10   an toàn 2→10
chỉ mục mới + Match + Phrase    9.9/10   giấy phép hoạt động 3→9 · quy định nội bộ 4→10
```

- Hai nguyên nhân tách bạch. (1) Chỉ mục dựng bằng **mặc định tiếng Anh**: stemmer Snowball +
  stop-word tiếng Anh, mà `ascii_folding` bỏ dấu **trước** khi lọc nên từ Việt thường rơi
  đúng vào danh sách đó. (2) **Không có vị trí token** ⇒ không truy vấn cụm nào khả thi.
- `PhraseQuery` đứng cạnh `MatchQuery` ở mức `SHOULD`: cộng dồn điểm cho chunk chứa nguyên
  cụm, còn câu hỏi dài dạng tự nhiên không khớp mệnh đề cụm và không mất gì (2 câu thử: 6/6
  hit y như cũ).
- Dựng lại chỉ mục **không embedding lại chunk nào** — chỉ đụng cột `text`.
- Nhánh BM25 nay **ghi log khi tắt** thay vì nuốt lặng.
- **Còn lại của mục này:** bất đối xứng chưa xử — text đem *embed* là
  `"{doc_title} — {article}: {text}"` còn text đem *index BM25* chỉ là `text` trần, nên hỏi
  "Thông tư 40 quy định gì" thì vector bắt được tên văn bản, BM25 không. Chưa đo tác động.

### [ ] T19 · Không có cách nghiệm thu truy hồi trên production mà không cần đăng nhập

Lộ ra khi deploy T8 (10/08): `/health` nói được lớp phủ có nạp không, nhưng **không có gì**
nói được nhánh truy hồi đang hành xử ra sao. Mọi endpoint chạm retrieval đều sau `get_current_user`,
nên sau mỗi deploy chỉ xác minh được "revision đã đổi", không xác minh được "truy hồi vẫn đúng".

- Vì sao quan trọng: đây đúng là khoảng mù mà T9 sinh ra để bịt, chỉ khác tầng. Một thay đổi
  làm hỏng nhánh BM25 trên production sẽ không bị bắt bởi bất kỳ phép kiểm tự động nào.
- Hai hướng: (a) thêm vào `/health` một phép **tự kiểm** rẻ — chạy một truy vấn cố định rồi
  báo số hit của từng nhánh (vector / BM25), không trả nội dung nên không lộ dữ liệu;
  (b) script nghiệm thu sau deploy dùng token thật, chạy tay.
- (a) đáng làm hơn: nó biến "truy hồi còn sống không" thành thứ đọc được bằng một lượt `curl`,
  giống hệt cách T9 làm với lớp phủ.

### [ ] T18 · `create_fts_index` đã deprecated từ lancedb 0.25

Cảnh báo khi dựng lại chỉ mục 10/08: *"use `create_index()` with `config=FTS()` instead"*.
Chữ ký `RemoteTable.create_index` **không có tham số cột** rõ ràng cho FTS, nên chưa đổi —
đoán mò ở đây là làm hỏng đường ingest. Cần đọc tài liệu rồi mới chuyển.

- Cùng họ deprecated: `db.list_tables()` cũng bị đánh dấu cũ, nhưng đường thay thế
  `table_names()` là đường **duy nhất chạy được** trên LanceDB Cloud của dự án —
  `list_tables()` ném `HttpError 400` thật (*"PgCatalog::open_database() requires a table
  name to resolve the storage path"*), đo 10/08 trong fix round 1 của Task 4. `ingest_one_doc`
  đã dùng `table_names()`, và `tests/test_ingest_mot_van_ban.py::_FakeDB.list_tables` ghim
  chuyện này bằng `AssertionError`. Lần chuyển `create_fts_index` sau **đừng** tiện tay đổi
  luôn `table_names()` → `list_tables()` vì thấy cùng là deprecated — hai cái không cùng số
  phận trên deployment này.

---

## Chất lượng phán định tuân thủ

> Số đo và cách đo ở `docs/EVAL-COMPLIANCE.md`. Ở đây chỉ là hàng đợi việc.

### [ ] T23 · Cặp `SHB Mục 4.2 ↔ TT40 Điều 25` chưa bao giờ bắt được

Cặp vàng duy nhất bị bỏ sót, bỏ ở **cả hai** ca chạm tới nó — đây là toàn bộ khoảng cách giữa
recall 0,800 và 1,000 ở tầng cặp (đo 10/08, `results/precision-cap-20260810-094112.json`).

- Nội dung: nội bộ cho **nạp tiền mặt tại quầy** vào ví, `TT40-2024 Điều 25` chỉ cho nạp từ
  tài khoản/thẻ liên kết.
- Bằng chứng đã có: log cho thấy bộ phát hiện **có** xử lý `Mục 4.2`, nhưng ghép nó với
  `TT40-2024::Điều 37 Khoản 1(i)(vi)` và `Điều 25 Khoản 1(a)` — hai địa chỉ **không quy được
  về chunk nào trong tập lấy về**. Tức chunk chứa khoản 1 Điều 25 không được truy hồi.
- ⇒ Nghi là **lỗ hổng truy hồi, không phải phán định**. **Xác nhận trước, đừng sửa trước:**
  chỉ cần in tập chunk của câu đó và xem `TT40-2024 Điều 25` được chẻ thành những chunk nào,
  chunk nào lọt vào top-k.

### [ ] T24 · `SHB-QD-TK-2022 Mục 2.3` ra `warning` thay vì `violation`

eKYC từ đủ **14** tuổi trong khi `TT17-2024 Điều 11` đòi đủ **15** — một con số chọi một con
số, đáng lẽ là `violation` dứt khoát. Ổn định qua cả hai lượt đo 10/08 nên **không phải nhiễu**.

- Đây là điểm trừ duy nhất của `review.py` trong lượt chấm đầu tiên (đúng 6/7, sai 0).
- Chưa truy nguyên nhân. Hai hướng đáng nhìn trước: căn cứ mà `_judge` chọn có đúng là
  Điều 11 không, và luật ranh giới số 1 trong `_SYSTEM` (“nội bộ đặt con số KHÁC điều luật →
  violation”) có bị luật số 2 (“im lặng về một nghĩa vụ → warning”) lấn át không.

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

### [ ] T20 · Dọn node rỗng khớp bằng `so_hieu`, mà văn bản duyệt qua `/admin` không có

`don_node_rong_da_co_toan_van()` (`app/knowledge/graph.py`) tìm node rỗng cần thay bằng
`WHERE that.so_hieu = rong.doc_id`. Nhưng `CorpusDocument.so_hieu` là **optional**, nên với
văn bản không có số hiệu thì `_merge_doc` ghi `n.so_hieu = null` (Neo4j xoá luôn property) và
câu khớp trên không bao giờ đúng: hàm dọn chạy, tốn một round-trip, trả `[]`, và **đồ thị nằm
lại với hai node cho một văn bản** — node rỗng giữ hết cạnh đi vào cũ, `related_docs()` lọc
`co_toan_van=false` ra nên các quan hệ ấy biến mất khỏi truy hồi, `thieu_toan_van()` vẫn kê
văn bản vừa duyệt vào danh sách cần crawl. Không lỗi, không cảnh báo.

**Đọc mã 10/08 thì ca này còn rộng hơn mô tả ban đầu:** không phải "chỉ hỏng khi không rút
được số hiệu". `app/ingestion/extract.py:165 extract_document()` dựng `CorpusDocument(...)`
mà **không truyền `so_hieu` vào**, dù `extract_metadata` ngay bên trên đã tính
`meta["so_hieu"] = so_hieu_trong(text)` kèm hẳn một đoạn chú thích giải thích vì sao trường
này là cây cầu. Tức **mọi** văn bản đi qua `/admin` (upload → extract → duyệt) đều có
`so_hieu = None`, kể cả khi số hiệu nằm nguyên văn ở dòng đầu và parser đọc ra được.

- Vì sao quan trọng: đây là đường duyệt trên production (T5), và lớp phủ + `related_docs`
  đọc đúng cái node bị bỏ lại. Hôm nay tác hại còn nhỏ vì bucket mới có ít văn bản, nhưng nó
  lớn dần theo mỗi lượt duyệt.
- **Bước đầu tiên — ĐÃ LÀM 10/08.** `extract_document` nay truyền `so_hieu=meta["so_hieu"]`
  vào `CorpusDocument`, kèm ca `test_extract_document_dien_so_hieu_vao_van_ban` chạy qua
  parser thật (chỉ giả lập lời gọi Gemini). Nghiệm thu là ca đó ĐỎ trước khi sửa với đúng
  `assert None == '52/2024/NĐ-CP'`. Việc này đóng phần lớn ca: mọi văn bản có số hiệu đọc
  được nay điền đúng.
- **Còn mở:** PDF scan/layout hỏng không rút được số hiệu thì `so_hieu` vẫn `None`, và hàm dọn
  vẫn không khớp. Lúc ấy mới phải quyết **đổi khoá khớp** của hàm dọn (khớp thêm theo `doc_id`,
  hoặc để admin nhập số hiệu trong ô JSON trước khi duyệt) — quyết định thiết kế, không phải
  việc sửa kèm. Chưa có số đo tần suất ca này; lượt nghiệm thu T5 là dịp đầu tiên để đếm.

### [ ] T21 · `download_storage` nuốt 400/404 cho mọi caller

`app/core/appdb.py` trả `None` khi Storage đáp 400 **hoặc** 404, không đọc thân lỗi. Hai hệ quả
đo được 10/08:

- `download_original` (`app/api/documents.py`) biến một lỗi RLS hoặc lỗi truyền tải thành
  "chưa có file gốc" 404 cho người dùng — sai nguyên nhân, và không cách nào phân biệt.
- `load_canonical(strict=True)` — hàng rào dựng cho `approve_document` để nó không ghi đè
  canonical bằng bản đóng gói — **không chặn được nhánh 400/404**, vì `download_storage` đã
  nuốt trước khi `strict` nhìn thấy. Hàng rào đó hiện an toàn vì quyền ĐỌC bucket yếu hơn
  quyền GHI (`0001_init.sql:139-142` so với `0004_doc_workflow.sql:7-10`), nên read bị RLS
  chặn thì upload sau đó chắc chắn cũng chặn. Nhưng đó là lập luận, không phải rào.

- Vì sao quan trọng: phần còn lại là 400/404 **thoáng qua trên một object CÓ THẬT** — lúc đó
  `approve` merge một văn bản vào corpus 26 bản đóng gói rồi ghi đè `corpus.json`, xoá mọi
  văn bản đã duyệt trước đó. Im lặng.
- **Bước đầu tiên:** dùng lại `scripts/sync_corpus_storage._ma_loi_storage` (đã có sẵn, đang
  không được tái sử dụng) trong `download_storage`: chỉ trả `None` khi thân lỗi nói `NoSuchKey`
  hoặc `statusCode 404`, còn lại thì ném. Đóng cả hai ca trên bằng một chỗ.

### [ ] T22 · Bốn mẩu nợ nhỏ còn lại của nhánh ingest-một-văn-bản

Đều lộ ra trong review nhánh T5 (10/08), đều đã cân nhắc và cố ý để lại — ghi ở đây để không
phải phát hiện lại.

- **Lưới test chặn Supabase là "tắt" chứ không phải "bẫy".** `tests/conftest.py` xoá
  `settings.supabase_url` nên `appdb.enabled()` trả `False` và mọi thứ thành no-op im lặng —
  khác hẳn hai seam kia (LanceDB, Neo4j) vốn **ném lỗi có thông điệp**. Test nào tự đặt lại
  `supabase_url` rồi quên vá `appdb` thì không có gì canh.
- **`don_node_rong_da_co_toan_van` dùng `SET m += properties(e)`** khi dời cạnh khỏi node rỗng.
  Trước đây hàm này chỉ chạy sau một lượt nạp toàn bộ nên không có gì tươi để đè; nay nó chạy
  ngay sau khi `push_one_doc` vừa dựng lại cạnh từ corpus hiện tại, nên `note`/`anchors` cũ có
  thể ghi đè bản vừa ghi.
- **`canh_vao` gộp toàn bộ cạnh đi vào của corpus**, không phải phần chênh. Mỗi lượt duyệt
  MERGE lại tất cả, một round-trip mỗi cạnh (`_merge_canh` chưa gộp lô như `push_overlay`).
  35 cạnh hôm nay nên không đau; nó lớn tuyến tính theo corpus, trên đúng đường đã từng rớt
  kết nối Aura giữa chừng.
- **`DocumentMeta.so_hieu` khai hai lần** (`app/core/schemas.py:115` và `:118`, cùng kiểu cùng
  mặc định). Pydantic v2 lấy khai báo sau, nên vô hại — nhưng đoạn chú thích giải thích ở trên
  đang gắn vào dòng đã chết.

- Vì sao quan trọng: không mục nào hỏng hôm nay; ba mục đầu là thứ sẽ hỏng khi corpus lớn lên
  hoặc khi có người viết test tiếp theo.
- **Bước đầu tiên:** mục cuối là một dòng xoá — làm luôn khi nào chạm `schemas.py`. Ba mục còn
  lại chỉ mở khi có triệu chứng thật.

### [ ] T26 · `dong_goi` dựng lớp phủ từ corpus KHÔNG phải corpus đang phục vụ

Từ khi T5 đưa canonical lên Supabase Storage, production đọc `legal-docs/corpus.json`, còn
`data/corpus.real.json` trong image tụt xuống làm bản dự phòng — và nó là **ảnh chụp của lần
build cuối**, không nhận được văn bản nào duyệt qua `/admin` sau đó.

`app/ontology/dong_goi.py:203` đọc đúng file đóng gói ấy (`Path("data/corpus.real.json")`).
Nghĩa là artefact lớp phủ đang được dựng từ một corpus **không phải** corpus đang phục vụ, và
khoảng cách lớn dần theo mỗi lượt duyệt.

- Vì sao quan trọng: cạnh `TAC_DONG` là thứ sinh ra huy hiệu "điều bị tác động" và modal đối
  chiếu. Dựng nó từ một corpus cũ nghĩa là văn bản duyệt sau lần build cuối **không tồn tại**
  với tầng lớp phủ, và không có gì báo.
- Hôm nay chưa đau vì mới có ít lượt duyệt. Nó lớn tuyến tính theo số lượt.
- **Bước đầu tiên:** cho `dong_goi` nhận đường dẫn corpus qua tham số (mặc định giữ nguyên
  `data/corpus.real.json`), rồi thêm một lối tải canonical từ Storage về file tạm trước khi
  dựng. Có `scripts/sync_corpus_storage.py` làm mẫu cho phần tải.

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

### [ ] T25 · 5/12 mục nội bộ chưa có nhãn verdict

`eval/tuan_thu_vang.jsonl` mới phủ **7/12** mục của 4 văn bản SHB: 5 mục có mâu thuẫn cài sẵn
+ 2 mục đối chứng thuần chính sách phí. Năm mục chưa có nhãn:

`SHB-QD-VI-2023::Mục 5.1` · `SHB-QD-TK-2022::Mục 2.5` · `SHB-QD-TK-2022::Mục 6.1` ·
`SHB-QD-THE-2023::Mục 7.3` · `SHB-CS-PHI-2024` (đã phủ cả 2 mục)

- Vì sao không giao cho AI: nhãn vàng do chính hệ thống-cùng-tác-giả sinh ra thì **phép đo mất
  giá trị** — tự gán rồi tự chấm là tự chấm bài của mình. Chủ repo đã chọn phương án này
  10/08, cố ý nhận mẫu nhỏ hơn để nhãn sạch.
- Cần gì: với mỗi mục, một verdict `violation` / `warning` / `pass` kèm một câu lý do và điều
  luật làm căn cứ. Có nhãn thì mẫu số của `ty_le_dung` tăng từ 7 lên 12 mà không phải sửa dòng
  mã nào — `eval/do_tuan_thu.py` tự đọc thêm.

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
- **10/08 · T8** — BM25 chấm điểm cụm: 8.4 → **9.9/10** precision@10. Chi tiết ở mục T8 phía
  trên. Chỉ mục trên LanceDB Cloud đã dựng lại (không embedding lại chunk nào). Deploy rev
  `lexflow-api-00022-242`, 100% traffic.
  **Giới hạn của phép nghiệm thu:** mọi endpoint chạm truy hồi đều đòi đăng nhập, nên không
  gọi được từ ngoài để chứng minh phần cộng điểm cụm đang chạy trên chính process đang phục
  vụ. Đã chứng minh: bản vá đo trên **đúng chỉ mục production đọc**, và revision build từ mã
  hiện tại. Chưa chứng minh: một lượt truy vấn thật qua production. Xem **T19**.
- **10/08 · T17** — Deploy để mã khớp dữ liệu vừa nạp: rev `lexflow-api-00021-jvs`, 100%
  traffic. Nghiệm thu đúng thứ cần chứng minh chứ không chỉ `/health` (nó không phân biệt được
  revision cũ với mới): tra thẳng 10 nhãn có hậu tố trên **bảng LanceDB đang phục vụ** —
  **10/10 giải được** bằng mã mới, **0/10** bằng regex cũ. Cả 10 rơi về khoá cấp điều
  `23/2019/TT-NHNN#than/dieu_1`, đúng thiết kế.
- **10/08 · T1 + T2** — Re-ingest mang cả hai bản vá chunking sang dữ liệu đang phục vụ.
  LanceDB: **661 hàng / 661 id phân biệt** (trước: 654 id, 7 hàng đụng nhau). Neo4j về đúng số
  cũ: 26 Document · 293 DonVi · 255 THUOC · 178 TAC_DONG · 35 cạnh văn bản. Nghiệm thu trên
  chính dữ liệu đang phục vụ: `TT66-2025 Điều 6` hết cắt giữa từ; bốn chunk từng đụng id lộ ra
  là **bốn điều khoản khác hẳn nhau** (thông tin khách hàng · hạn mức BTĐT · quyền và trách
  nhiệm ngân hàng hợp tác) — va chạm cũ đúng là có hại; hybrid search trả 4 hit bình thường
  nên chỉ mục FTS sống sót qua lượt ghi đè. Commit `3219fba`.
  **Hai chuyện phát sinh, đều đã xử:** `ingest_docs` không gọi lại `push_overlay` sau
  `push_corpus` (mất 255 cạnh `THUOC` trong im lặng) — nay nối vào đường ingest kèm test;
  `push_overlay` chạy ~764 round-trip lẻ nên Aura rớt giữa chừng ở 221/255 — nay gộp lô bằng
  `UNWIND`, commit `f3ccf2f`.
- **09/08 · T3** — Đo được ngưỡng cắt embedding ~7.156 ký tự, chỉ 1/661 chunk vượt. Chi tiết ở
  mục T3 phía trên (kèm một đính chính 10/08). Commit `83ac6dd`.
- **09/08** — Nhánh chẻ dự phòng cắt giữa từ. `TT66-2025 Điều 6` bị cắt ngay giữa chữ "ngân"
  (`ngâ` + `n`); vá bằng lưới ranh giới dòng/câu + thang bậc điểm → tiểu mục → gạch đầu dòng.
  651/654 chunk id giữ nguyên từng byte. Commit `8dd53f0`, 7 test mới, CI xanh. **Dữ liệu
  trên LanceDB vẫn là bản cũ — xem T1.**
