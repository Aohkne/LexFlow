# LexFlow — Việc tồn đọng

> Danh sách việc **đã biết nhưng chưa làm**, để không phải phát hiện lại. Khác với
> `ROADMAP-SPRINT.md` (kế hoạch theo sprint) và `WORKLOG.md` (nhật ký đã làm).
>
> Quy ước: mỗi mục ghi **vì sao quan trọng** và **bước đầu tiên cụ thể** — đủ để người khác
> (hoặc chính mình ba tuần sau) bắt tay vào mà không phải điều tra lại. Mọi con số đều kèm
> ngày đo; số không có ngày là số chưa kiểm.
>
> Cập nhật gần nhất: 2026-08-15.

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

  **Cập nhật 13/08:** cả hai đường ghi giờ dò bảng bằng `db.open_table(...)` trong `try`, bắt
  `ValueError` có lọc thông điệp `"not found"` — không còn lời gọi `table_names()` hay
  `list_tables()` nào trên đường ingest. Cách này tránh luôn cả HttpError 400 lẫn phân trang của
  `list_tables()`. Đo 13/08: cả LanceDB nhúng lẫn LanceDB Cloud đều ném
  `ValueError("Table 'x' was not found")`, cùng khung `lancedb/db.py:1722`. Bộ lọc thông điệp là
  thứ CHỊU LỰC — `ValueError` là built-in dùng cho vô số lý do, bắt trần nó biến một trục trặc
  mạng thoáng qua thành "bảng chưa có" rồi dựng đè bảng đang phục vụ.

### [ ] T26 · Tầng chuẩn tắc (CU / meta-CU / premise) có thật nhưng không nối vào đâu cả

Soi 10/08 để trả lời câu "knowledge base có thành phần nào trích premise / Compliance Unit
không". **Có** — `app/ontology/` là một bộ trích đầy đủ theo GraphCompliance, ánh xạ sang
tên node đã thiết kế ở KG v0.5 §10.2. `app/ontology/schema.py` định nghĩa `ActorCU:310`
(⟨S⟩ bắt buộc · ⟨A⟩ · `logic` · `conditions[]`), `MetaCU:333` (`gates[]` · `dieu_kien_cong`
· `menh_de`), `PremiseRecord:242`, `KhaiNiem:267`, `Gate:179`, `DieuKienCong:213`,
`ConditionItem:154`, `GuardApDung:114`, `Grounding:89`. Kèm `classify.py` (phân 3 vai, tất
định, không gọi LLM), `modality.py` (từ điển tình thái), `segmenter.py`, `extractor.py`.

**Nhưng nó không nằm trong KB, theo cả ba nghĩa** — ghi ra đây để người sau khỏi grep lại:

- **Không ở LanceDB.** Hàng chunk có đúng 10 cột + `vector` (`app/ingestion/pipeline.py:204-217`),
  không cột nào mang CU.
- **Không ở Neo4j.** Chỉ hai nhãn `:Document` và `:DonVi` (`app/knowledge/graph.py:86,90`).
  `NghiaVu`/`ChuThe`/`NgoaiLe` đã thiết kế rồi **hoãn có chủ đích** (KG v0.5 §10.2).
- **Không ở đường phục vụ.** Không file nào trong `app/api/` hay `app/reasoning/` import
  `extractor`/`classify`/`roles`/`schema`/`modality`/`segmenter`. `review.py:136` và
  `conflict.py:80` đều nối `text` thô rồi ném thẳng cho LLM, một nhịp. Phần duy nhất của
  `app/ontology/` chạm production là chuỗi lớp phủ (`tac_dong`/`hien_hanh`/`dinh_tuyen`/
  `dong_goi`) — tầng **thời hiệu**, không phải tầng chuẩn tắc.

Đường chạy hiện tại là CLI ngoại tuyến `python -m app.ontology` → `eval/ontology/*.jsonl`.

**Độ phủ đo 10/08:** `pred.jsonl` **49 CU** (40 actor + 9 meta) trên **12 Điều / 4 văn bản**;
`premise.jsonl` 45 (dinh_nghia 36 · vai_tro 7 · pham_vi 2) và `khainiem.jsonl` 36, cả hai chỉ
2 văn bản. Một trong bốn văn bản — `52/2024/NĐ-CP` — **không có trong corpus**, nên so với
corpus (26 văn bản / 425 Điều / 661 chunk) tầng chuẩn tắc phủ **8/425 Điều ≈ 1,9 %**.
`docs/ONTOLOGY-FOR-MENTOR.md:220` ghi thẳng chỗ yếu nhất: **0/94 nhãn người gán**.

**Lỗ hổng schema — ghi kèm vì nó quyết định THỨ TỰ làm.** `ActorCU` không có ô tình thái
(`must`/`must_not`/`may`): `modality.py` có từ điển deontic đủ nhưng chỉ dùng làm hàng rào
chống bịa và làm căn cứ phân vai. Và **không có ô ngưỡng/số ở bất cứ đâu** —
`MODALITY["dinh_luong"]` chỉ là danh sách từ khoá, `Delta.added_numbers` là guard
hallucination. Trong khi **cả 5 cặp vàng ở `eval/mau_thuan_vang.jsonl` đều là số chọi số**
(200↔100 triệu · 20↔5 triệu · 14↔15 tuổi) và **T24** đang hỏng đúng ở một cặp số. ⇒ Mở rộng
độ phủ CU trước khi có ô số thì không cải thiện được phán định: **schema trước, độ phủ sau**.

- **Bước đầu tiên: chưa mở.** Ba hướng đã cân nhắc 10/08, chủ repo hoãn cả ba — (a) thêm ô
  ngưỡng + tình thái vào `ActorCU`; (b) mở rộng độ phủ lên 425 Điều (tốn LLM, phải ước trước);
  (c) nối CU vào `review.py`/`conflict.py` (chỉ 8/425 Điều có CU nên phải chạy song song hai
  đường một thời gian).
- Mở lại khi có **nhãn người gán** — câu hỏi #1 gửi mentor ở `ONTOLOGY-FOR-MENTOR.md:230`.
  Không có nhãn thì mọi cải tiến ở tầng này vẫn là máy tự chấm máy.

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
- Ghi chú: `TT40-2024 Điều 25` **đã có CU trích sẵn** (6 bản ghi trong `eval/ontology/pred.jsonl`),
  nhưng đường phán định không đọc tới — xem **T26**.

### [ ] T24 · `SHB-QD-TK-2022 Mục 2.3` ra `warning` thay vì `violation`

eKYC từ đủ **14** tuổi trong khi `TT17-2024 Điều 11` đòi đủ **15** — một con số chọi một con
số, đáng lẽ là `violation` dứt khoát. Ổn định qua cả hai lượt đo 10/08 nên **không phải nhiễu**.

- Đây là điểm trừ duy nhất của `review.py` trong lượt chấm đầu tiên (đúng 6/7, sai 0).
- Chưa truy nguyên nhân. Hai hướng đáng nhìn trước: căn cứ mà `_judge` chọn có đúng là
  Điều 11 không, và luật ranh giới số 1 trong `_SYSTEM` (“nội bộ đặt con số KHÁC điều luật →
  violation”) có bị luật số 2 (“im lặng về một nghĩa vụ → warning”) lấn át không.
- Ghi chú: `TT17-2024 Điều 11` **đã có CU trích sẵn** (2 bản ghi, `logic="any"`, ba Điểm là ba
  loại cá nhân), nhưng con số 15 tuổi nằm trong `conditions[].text` chứ **không có ô ngưỡng**
  nào để so trực tiếp — xem **T26**.

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

### [ ] T27 · `dong_goi` dựng lớp phủ từ corpus KHÔNG phải corpus đang phục vụ

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

### [ ] T28 · Deploy vẫn là thao tác tay từ một thư mục, không phải từ `main`

`gcloud run deploy --source .` dựng **thư mục làm việc**, không dựng một git ref. Hai track mỗi
bên một worktree ⇒ ai deploy sau đè mất bên kia, **không lỗi, không cảnh báo**. `ci.yml` chỉ
chạy test, không có bước deploy nào.

Đã bịt hai lớp rẻ nhất 11/08: quy ước "chỉ deploy từ `main`" (`COMMIT-CONVENTION.md`) và trường
`commit` trong `/health` (đọc `GIT_SHA`). Cả hai đều **phát hiện** chứ không **ngăn**.

- Vì sao quan trọng: hôm 11/08 production đã có lúc chạy mã của `feat/software` trước khi PR
  #20 merge. Lần đó vô hại vì nhánh không tụt sau `main` commit nào — nhưng đó là may, không
  phải cơ chế. Triệu chứng nếu xảy ra thật rất dễ đọc nhầm: upload `.json` ở `/admin` trả
  `422 Extract thất bại: ...`, trông y hệt một file crawl hỏng.
- **Bước đầu tiên:** dựng Workload Identity Federation cho repo, rồi thêm job deploy vào
  `ci.yml` chạy khi `push` vào `main` (`google-github-actions/auth` + `deploy-cloudrun`), truyền
  `GIT_SHA=${{ github.sha }}`. Xong thì gỡ quyền deploy tay.
- Không làm trước kỳ đánh giá 04/09 trừ khi có thêm một lần đè nhau nữa — dựng WIF là việc
  riêng, và hai lớp phát hiện ở trên đủ để không mất hàng giờ chẩn đoán sai.

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

### [ ] T5 · Nghiệm thu luồng `/admin` trên production — chỉ còn một lượt bấm

Hạ ưu tiên 11/08 theo quyết định của chủ repo: **mã đã xong, chỉ còn phần phải có tay người và
một tài khoản admin thật.**

Đã xong (11/08): `is_admin()` đọc `app_metadata.role` (migration `0007`) nên đường duyệt qua
được RLS · `ingest_one_doc`/`push_one_doc` nạp một văn bản thay vì ghi đè bảng đang phục vụ ·
nhận thẳng file `.json` đã crawl · khoá Storage lấy từ `doc_id` nên tên file tiếng Việt không
còn làm hỏng upload · lỗi máy chủ nay đọc được trên giao diện.

Chưa xong: **chưa văn bản nào thật sự đi hết đường đó trên production.** Bucket `legal-docs` và
bảng `legal_documents` vẫn rỗng, nên `app/core/corpus.py` còn fallback về `data/corpus.real.json`
đóng gói trong image — tức mọi thay đổi corpus vẫn phải deploy lại.

- Vì sao không giao cho AI: cần một tài khoản admin thật trên production và một lượt bấm ở
  `/admin`; đây cũng chính là chỗ mà 10/08 một lượt chạy test đã lỡ đẩy văn bản bịa `TT99-2026`
  vào LanceDB và Neo4j thật.
- Cần gì: upload một file trong `data/raw/vbpl/corpus/`, bấm Approve, rồi kiểm **bốn** thứ —
  (1) văn bản mới có chunk trong LanceDB; (2) **số chunk của một văn bản khác KHÔNG đổi**;
  (3) Neo4j thêm đúng một `Document`; (4) **`THUOC` vẫn đúng 254**. Hai mục in đậm mới là phép
  kiểm thật: chúng phân biệt "nạp một văn bản" với "ghi đè cả bảng".

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

## feat/ai — dải T100+ (nối lại 13/08 sau khi hoà với `main`)

> 11 mục dưới đây tồn tại trên `feat/ai` ngay trước khi hoà (`git show d1f5f93:docs/TASKLIST.md`)
> và bị số hiệu của `main` đè khi Task 1 của kế hoạch hoà nhánh lấy nguyên bản `main` cho file
> này — 12 số trùng nghĩa khác nhau giữa hai bên (đợt đầu 13/08 đếm ra 9, review cùng ngày bắt
> thêm 3: `T17`/`T19`/`T20`). Thân mục chép nguyên văn, chỉ đổi số ở tiêu đề — luật dải xem
> `docs/COMMIT-CONVENTION.md` § Push rules. Một mục thứ mười hai (`ascii_folding`, số cũ `T24`)
> không nối lại vì đã có nội dung đúng hơn thay thế: khối chú thích `_FTS_OPTS` ở
> `app/ingestion/pipeline.py:238-249` (`T8` phía trên nêu nguyên nhân, code là nơi đã tháo mìn) —
> xem `docs/WORKLOG.md` mục 13/08.

### [ ] T100 · Cân nhắc `create_scalar_index("doc_id")`

`where("doc_id IN (...)")` giờ nằm trên đường ingest (mỗi lượt) chứ không chỉ đường tra lớp phủ.

- Đo 13/08: 0.61s cho một doc, 5.29s quét toàn bảng 661 hàng — **chưa cần**.
- Bước đầu: khi bảng vượt ~5.000 chunk hoặc lượt quét vượt 15s thì chạy
  `tbl.create_scalar_index("doc_id")` rồi đo lại. Ghi số vào đây, đừng làm sớm.
- Khi làm T100, nhớ rằng `_cho_index` **lọc theo `index_type == "FTS"`** đúng để index thứ hai không
  bị chờ và không bị cảnh báo nhầm. Có test ghim (`test_index_khong_phai_fts_thi_khong_cho_khong_canh_bao`)
  — nếu nó đỏ sau khi thêm index mới thì đó là dấu hiệu, không phải phiền toái.
- Cùng lúc, xác nhận LanceDB Cloud **không** giới hạn số hàng một truy vấn trả về: `_doc_can_nap`
  quét bằng `.limit(tbl.count_rows())`, nên nếu có trần phía server thì lượt quét bị cắt **im lặng**.
  Hướng cắt là an toàn (bỏ sót mồ côi, lượt sau tự lành) nhưng không có gì báo.
- Và: `write_lancedb` xoá văn bản dư bằng một vị từ `id IN (…)` liệt kê **mọi chunk** của mọi văn
  bản dư — ở quy mô corpus lớn là một chuỗi SQL rất dài. Với ca "dư" thì `doc_id IN (…)` đúng
  tương đương và ngắn hơn hai bậc. Chưa cần đổi, ghi lại để khỏi phải nghĩ lại.

### [ ] T101 · `count_rows()` sau `merge_insert` trên bảng từ xa có tươi không?

`write_lancedb` trả `n_tong = tbl.count_rows()` ngay sau `merge_insert` + `delete` — tiền đề này
giờ chỉ đúng cho đường CLI (`python -m app.ingestion`). `/documents/{id}/approve` gọi
`ingest_one_doc`, không phải `write_lancedb` (hoà nhánh 13/08); số ghi vào audit log ở đó là
`n_chunks` (`app/api/documents.py:341`), số của riêng `ingest_one_doc`, không phải
`n_chunks_bang`.

- Vì sao quan trọng: nếu LanceDB Cloud phục vụ `count_rows` từ manifest có cache thì con số CLI
  báo ra (`[ingest] Đã ghi ... bảng có N chunk`) trễ một nhịp. **Không sai dữ liệu** — chỉ sai
  con số in/ghi ra, mà đó là thứ người ta dùng để đối chiếu về sau. Gate ở Task 1
  (`scripts/do_merge_insert_remote.py`) không phủ `count_rows`.
- Bước đầu: thêm vào `scripts/do_merge_insert_remote.py` một phép đo `count_rows()` ngay trước và
  ngay sau `merge_insert` trên bảng nháp, so với số hàng đọc bằng `search().to_list()`.

### [ ] T102 · Vân tay chunk lệch khi ghi bằng `merge_insert`

Phép đo 13/08 (`scripts/soi_doc_can_nap.py`) so bảng thật với `build_chunks` được 0 ô lệch trên
661 hàng × 10 cột. Nhưng bảng đó được ghi bằng đường **cũ** (`create_table(mode="overwrite")`).
Chưa có gì chứng minh một hàng ghi bằng `merge_insert` đọc lại ra **y hệt từng ô** khi đem so vân
tay.

- Vì sao quan trọng: nếu `merge_insert` làm đổi dù chỉ một ô khi đọc lại (ép kiểu, chuẩn hoá chuỗi,
  `None` thành `""`), thì mọi văn bản từng được ghi bằng đường mới sẽ **lệch vân tay vĩnh viễn**
  ⇒ được nạp lại ở **mọi** lượt ingest sau đó, im lặng, với đầy đủ chi phí embedding. Đường
  `overwrite` cũ miễn nhiễm với lỗi này vì nó không bao giờ so gì cả. Đây đúng là loại hỏng mà
  tính năng vừa xây dựng lên để tránh, quay lại từ cửa sau.
- Bước đầu: mở rộng `scripts/do_merge_insert_remote.py` (script đo, chạy trên **bảng nháp** rồi drop
  — không đụng bảng phục vụ): ghi vài hàng bằng `merge_insert`, đọc lại bằng
  `search().select(<cột ≠ vector>)`, so từng ô và in ra cột nào lệch kèm **kiểu Python hai bên**.

### [ ] T103 · `StarletteDeprecationWarning` từ `fastapi/testclient` lúc import

`uv run pytest -q` in `1 warning`: `StarletteDeprecationWarning` phát từ `fastapi/testclient.py`.

- Vì sao quan trọng: nó **không phải** nhiễu của test mà là tín hiệu từ phụ thuộc. Thêm một mục
  `filterwarnings` để output "sạch" sẽ mua sự sạch sẽ bằng cách che đúng việc nâng cấp sẽ phải làm
  — người review đợt này khuyến nghị rõ **đừng** làm thế.
- Bước đầu: xác định phiên bản `fastapi`/`starlette`/`httpx` đang dùng và cảnh báo đòi hỏi gì, rồi
  quyết định nâng cấp hay ghim. Không thêm `filterwarnings`.

### [ ] T104 · Trọng số nhánh thưa có thể lệch giữa luật đã chết và luật hiện hành

- Đo 12/08: sweep trên `eval/bo_sbv.jsonl` (29 câu, luật ĐANG hiệu lực, người ngoài soạn) cho
  tối ưu 0.25 ở **R@1/MRR@2** mức điều (0.76/0.86 so với 0.69/0.83 của 0.1 hiện tại) — nhưng
  **thua** 0.1 ở R@5 mức điều (0.94 vs 0.98) và **hoà** ở R@2/P@2/F2@2; từ R@5 các cột đã bão hoà
  trên mẫu 26 văn bản này nên chỉ R@1/MRR@2 đáng đọc (`docs/EVAL-IR.md` §11). 0.1 được chỉnh trên
  ba bộ đều thiên về luật đã chết. Chưa đổi: 29 câu với |R| = 1 thì một câu = 3,4 điểm R@1.
- Bước đầu: **trước khi cào thêm**, xác định `question_id` nào đổi hạng giữa w=0.1 và w=0.25 ở
  R@1 mức điều, và kiểm xem có trùng một trong ba cặp câu hỏi trùng lặp đã biết không (`question_id`
  6/30, 7/31, 61/63 — cả ba đều TT17-2024, chiếm 14/29 câu, xem `docs/EVAL-IR.md` §11). Gap R@1 là
  2 câu/29; nếu hai câu đổi hạng đó rơi vào cùng một cặp trùng thì cả phát hiện T104 chỉ đứng trên
  một câu hỏi phân biệt duy nhất. Gần như miễn phí ở lượt sweep kế tiếp. Còn lệch thật (không phải
  trùng lặp) thì mới cào 7 văn bản trong phạm vi liệt kê ở `research/crawl_list_sbv.txt` để bộ này
  lên 56/100 câu rồi quét lại.

### [ ] T105 · `HttpError` thoáng qua từ LanceDB Cloud làm rớt câu khi benchmark

Không phải bug logic — SDK LanceDB Cloud thỉnh thoảng hết hạn retry (`HttpError` /
`RetryError`) giữa lượt gọi, và mỗi câu rớt bị try/except bắt đúng thiết kế nên không làm bảng
sai, chỉ làm mẫu số nhỏ lại.

- Vì sao quan trọng: trên 29 câu, mỗi câu rớt là **3,4 điểm R@1**. Đo 12/08: lượt chạy đầu của
  `bo_sbv.jsonl` rớt **7/29 câu** (phải bỏ lượt, chạy lại toàn bộ mất thêm ~20 phút); cùng ngày,
  hai lượt `bo_tvpl_*.jsonl` cộng lại rớt **7/152 câu**. Không phải sự cố một lần.
- Bước đầu: đo tần suất lỗi qua vài lượt chạy nữa trước khi sửa code. Nếu ổn định quanh vài phần
  trăm mỗi lượt gọi, nới retry/backoff quanh lời gọi LanceDB Cloud trong `retrieval.py` là đủ;
  nếu tăng dần theo thời gian thì báo hạ tầng (đổi region, kiểm quota) trước khi vá code.

### [x] T106 · `so_hieu` dính dấu cách thừa từ nguồn làm `chuan_so_hieu` cắt cụt — ĐÃ SỬA 12/08

Phát hiện và sửa cùng ngày. Trước khi sửa:

```
corpus  '21/2017/TT- NHNN'   -> chuan_so_hieu -> '21/2017/TT'      khớp? False
sau khi sửa                  -> chuan_so_hieu -> '21/2017/TT-NHNN' khớp? True
```

**Cách sửa:** xoá sạch khoảng trắng **trước** khi khớp regex, và dùng bản đã xoá ở **cả hai**
nhánh — nhánh dự phòng (chuỗi viết thường, tức nhãn bộ SBV) ban đầu vẫn trả chuỗi gốc, tức lỗi
im lặng quay lại đúng chỗ vừa vá. Ba test ghim ở `tests/test_chuyen_tvpl.py`: `'21/2017/TT-
NHNN'`, `'81 /2025/TT- NHNN'` (dấu cách trước dấu `/`), và ca nhánh dự phòng `'21/2017/tt-
nhnn'`. Ca đuôi slug cũ không đổi hành vi — chuỗi không có dấu cách thì phép xoá là đồng nhất.

- Vì sao quan trọng: vbpl.vn để lọt dấu cách vào `so_hieu` (`TT- NHNN`), mà regex `_SO_HIEU`
  trong `eval/chuyen_tvpl.py` dừng ở dấu cách nên cắt còn `21/2017/TT`. Không ném lỗi, không
  cảnh báo — văn bản chỉ **lặng lẽ không khớp** nhãn eval, và 2 câu của nó không bao giờ mở
  khoá. Cùng lỗi này sẽ ăn bất kỳ văn bản nào cào về sau có dấu cách thừa; bộ cào **đã** cảnh
  báo đúng hiện tượng đó ở `ND26-2025` (`'Thông tư số 81 /2025/TT- NHNN'`), tức nguồn hay lỗi
  kiểu này chứ không phải ca cá biệt.
- Còn lại: 23 văn bản đã cào **chưa vào** `data/corpus.real.json`. Cào chỉ sinh
  `data/raw/vbpl/corpus/*.json`; muốn bộ SBV lên 56/100 câu thì phải gộp vào corpus rồi
  re-ingest LanceDB + Neo4j — T1 vẫn chặn (ghi lên cloud, cần duyệt), nhưng từ 13/08 lượt ghi đó
  chỉ còn tốn embedding của đúng 23 văn bản mới thay vì cả 661 chunk (ingest tăng dần). Thêm
  bằng chứng 13/08: `scripts/soi_doc_can_nap.py` đo `dư` rỗng (bảng không có văn bản nào ngoài
  corpus) và `cần nạp` rỗng (corpus không có văn bản nào lệch bảng) — 23 văn bản đó nằm ngoài cả
  hai tập, đúng vị trí "chưa vào corpus" chứ không phải một lỗi khác.
- **Bốn cảnh báo còn lại của lượt cào 12/08 đã truy tới cùng — không mục nào cần sửa code**, ghi
  lại để khỏi điều tra lại. Cả bốn đều **không ảnh hưởng corpus hay truy hồi**, vì `articles`
  dựng từ toàn văn chứ không từ cây điều khoản:
  - `TT45-2024` cây rỗng hoàn toàn (0 nút ở mọi cấp). Chủ repo đối chiếu vbpl.vn: **nguồn không
    có dữ liệu cây** cho văn bản này. Corpus vẫn đủ 46 điều. Giới hạn nguồn, đừng sửa parser —
    cùng loại với ca VBHN không có toàn văn.
  - `TT32-2024` Điều 36 có hai khoản 4 nội dung khác nhau. Chủ repo xác nhận **lỗi có thật trong
    văn bản gốc**. Bộ cào giữ cả hai là đúng; ai dùng Điều 36 phải tự quyết bản nào đang áp dụng.
  - `TT12-2022` cây 51 / toàn văn 52 — thiếu đúng **Điều 8 "Trang điện tử"**. Đã soi markup: thẻ
    `<p>` của Điều 8 **không có `id`, không có class nào**, trong khi Điều 9 mang `class="prov-
    article"` và Điều 7/10 nằm trong khối có `id`. Mà `_JS_PROVISION_NODES` (`app/ingestion/
    vbpl.py:359`) lọc theo `[class*="prov-"], [type]`, nên nút ấy không tồn tại để bắt. Hai quan
    sát cùng đúng: chữ **có** hiện trên vbpl (nên đếm bằng mắt ra 52), nút cấu trúc thì **không
    có**. Corpus vẫn đủ 52 điều; chỉ đồ thị KG thiếu nút Điều 8.
  - `TT39-2016` nguồn viết `4.Phí cam kết…` (thiếu dấu cách sau số khoản) ở Điều 14, và
    `Điều 1.Phạm vi…`. Bộ tách khoản tìm `số + '.' + dấu cách` nên không nhận ra ranh giới đó.
    **Hệ quả thực tế ở đây bằng 0**: Điều 14 đủ ngắn nên không bị chẻ, cả bốn khoản nằm chung
    một chunk `Điều 14` và chữ không mất. Rủi ro chỉ xuất hiện nếu gặp điều **dài** có cùng lỗi
    — lúc đó ranh giới khoản bị bỏ qua và hai khoản dính làm một.

### [ ] T107 · Nhận diện viện dẫn trong CÂU HỎI → anchor đồ thị

Bài báo (§4.3, SBV-RR) chạy NER trên câu hỏi để bắt "Thông tư 23/2025/TT-NHNN" làm điểm neo cho
Cypher. LexFlow **đã có parser viện dẫn đầy đủ** (`app/ontology/citation.py:121`,
`parse_citations` + `to_node_ids`) nhưng chỉ dùng lúc ingest (`classify.py`, `tac_dong.py`,
`extractor.py`) — đường hỏi đáp không gọi nó lần nào.

- Hệ quả: hỏi thẳng "Điều 12 Thông tư 40/2024 quy định gì" vẫn phải đi qua tìm kiếm ngữ nghĩa,
  trong khi câu trả lời là một phép tra khoá.
- Bước đầu: trong `answer._prepare`, gọi `parse_citations(req.query)`; có viện dẫn tường minh thì
  lấy chunk theo `lay_chunk_theo_tien_to` trước, hybrid search chỉ để bổ sung. Đúng nhánh
  "GRAPH LOOKUP trực tiếp" mà `docs/RAG-DESIGN.md:37` đã thiết kế mà chưa cài.

### [ ] T108 · Ngưỡng điểm τ + fallback "không đủ căn cứ"

Bài báo lọc `Score(d) ≥ τ` (cosine 0.9) TRƯỚC generation, rỗng thì trả "Unknown Answer".
`answer.py` chỉ trả `_NOT_FOUND` khi retrieval **rỗng hoàn toàn** — tức là một chunk lạc đề vẫn
đủ để hệ nói tiếp.

- Bước đầu: cho `_rrf` trả kèm điểm (`_rrf_score`) mà **không** đổi thứ tự xếp hạng, rồi sweep τ
  trên bộ eval để xem ngưỡng nào cắt được câu lạc đề mà không cắt nhầm câu đúng.
- **Đã có bộ negative** (12/08): `eval/bo_sbv_khong_can_cu.jsonl` — 71 câu hỏi về luật hiện hành
  mà corpus không có, câu trả lời đúng là "không đủ căn cứ". Lấy thêm được **157 câu** cùng loại
  từ bộ TVPL (`data/evaluate/eval_filtered_clean.jsonl`) bằng cách thêm một file ra thứ ba vào
  `eval/chuyen_tvpl.py` — chưa làm vì T108 chưa bắt đầu.
- **Hai bộ khác LOẠI, đừng trộn rồi báo một tỷ lệ:** 71 câu SBV hỏi về luật **hiện hành** corpus
  thiếu; 157 câu TVPL hỏi về luật **đã chết trước 2024** corpus thiếu. Bộ SBV khó hơn — chủ đề
  của nó (Open API, thư tín dụng, cho thuê tài chính) đủ gần thanh toán để truy hồi trả về văn
  bản trông rất hợp lý.

### [ ] T109 · Hậu kiểm câu trả lời: `HasCitations` / `EvidenceMismatch`

Bài báo (Algorithm 2, dòng 20–21) kiểm SAU khi sinh: không có trích dẫn, hoặc trích dẫn không khớp
bằng chứng ⇒ từ chối trả lời. LexFlow chỉ **dặn** trong system prompt (`answer.py:16`), không verify.

- Bước đầu: `HasCitations` là phép rẻ nhất — regex `\[.+—.+\]` trên câu trả lời, không khớp thì
  đánh dấu. Đo tỷ lệ rớt trên bộ eval trước, rồi mới quyết có chặn hay chỉ cảnh báo.
- **Chẩn đoán 16/08 — lỗi chủ đạo là THIẾU tính đầy đủ, không phải trích-dẫn-sai.** Phân loại 19 câu
  judge "thiếu" (§12) trên bộ SBV: **18/19 chỉ có 1 điều vàng** (không thể do tail retrieval), **cả
  19/19 `trich_dan_khop=True`** (retrieval + trích dẫn đúng văn bản ở mọi câu). Đọc `ly_do`: mẫu đồng
  nhất "nêu đúng cốt lõi, cited đúng, TUY NHIÊN bỏ sót [mục/điều kiện phụ]" — vd qid 60 sót "để gửi
  tiền", qid 47 sót ý TP.HCM, qid 84 sót thời hạn 07 ngày. Tức **trích xuất thiếu từ chính điều đã lấy
  đúng** → thuần generation.
- **Hệ quả: mở rộng T109 sang chiều COMPLETENESS.** HasCitations/EvidenceMismatch chỉ bắt trích-dẫn-sai,
  không bắt được kiểu lỗi này. Cần thêm phép hậu kiểm "đã liệt kê đủ các mục/điều kiện trong điều đã
  dẫn chưa?" (vd so số gạch đầu dòng của câu trả lời với số khoản/điểm của điều được trích), hoặc chỉnh
  prompt sinh để liệt-kê-đủ. Đây là hướng chạm đúng ~20/21 câu chưa hoàn hảo (18 thiếu + 2 sai).
- **Phase 1 XONG (16/08) — sửa prompt, thắng.** `_QA_SYSTEM` (`answer.py`): bỏ "ngắn gọn", ép liệt-kê-đủ
  + rào chống phủ-định (thiếu căn cứ → nói "chưa nêu", không nói "không tồn tại"). Đo `judge.py` bộ SBV:
  **dung 79→86, sai 2→1, ngữ nghĩa 0.885→0.925**, khớp-trích-dẫn 0.990 y nguyên. Chi tiết + caveat nhiễu
  1-phiếu: `EVAL-IR.md` §12 "Phase 1". (Tiện thể sửa bug checkpoint judge.py: `--sinh-lai` xoá verdict
  cache muộn ở pha chấm → kill giữa pha sinh để lại verdict cũ; nay xoá cả hai trước pha sinh.)
- **Phase 2 XONG (16/08) — hậu kiểm warn-only.** `app/reasoning/postcheck.py::hau_kiem` chạy sau
  `chat()`, trả cờ lên `ChatResponse.canh_bao` (+ event SSE `canh_bao`), KHÔNG chặn cứng: `thiếu_trích_dẫn`
  (HasCitations) và `trích_dẫn_ngoài_căn_cứ:<...>` (EvidenceMismatch — khớp theo số hiệu+Điều với chunk
  đã retrieve; chỉ báo khi trích dẫn có số hiệu rõ → tránh báo giả). Test `tests/test_postcheck.py` +
  cập nhật `tests/test_stream.py`.
- **Completeness HOÃN** (chủ ý): Phase 1 (prompt) đã chạm gốc lỗi trích-xuất-thiếu; heuristic đếm
  khoản/điểm nguồn vs mục answer rất nhiễu với điều không đánh số → thêm cờ nhiễu lợi bất cập hại. Mở
  lại nếu số liệu FE/eval cho thấy cần. **Còn lại của T109:** quyết CHẶN hay chỉ CẢNH BÁO — cần đo tỷ
  lệ rớt của 2 cờ trên traffic/eval thật trước (nay đã có cờ để đếm).

### [ ] T110 · Corpus phủ 4/37 văn bản mà bộ eval TVPL hỏi tới

Đo 10/08 trên `data/evaluate/eval_filtered_clean.jsonl` (251 câu): chỉ **76 câu** dẫn toàn văn
bản có trong corpus, 159 câu dẫn văn bản ngoài, 16 câu không dẫn gì. Đây là trần độ phủ thật của
corpus khi gặp câu hỏi do người ngoài soạn — số 76 kia không phải "bộ eval nhỏ", mà là corpus hẹp.

Nạp thêm văn bản mở khoá được bao nhiêu (tính tham lam, `scratchpad/phu.py` dựng lại được):

| thêm | +câu | cộng dồn |
|---|---|---|
| `09/2020/TT-NHNN` — an toàn bảo mật giao dịch ngân hàng điện tử | +51 | 127 (51%) |
| `34/2012/TT-NHNN` | +21 | 148 (59%) |
| `37/2016/TT-NHNN` | +18 | 166 (66%) |
| `88/2019/NĐ-CP` — xử phạt VPHC lĩnh vực tiền tệ | +11 | 177 (71%) |

Bước đầu: crawl `09/2020/TT-NHNN` từ vbpl.vn (một văn bản, +51 câu — lãi nhất theo xa), kiểm
hiệu lực và quan hệ thay thế của nó, rồi chạy lại `eval/chuyen_tvpl.py`. Ba văn bản còn lại làm
sau nếu bảng đo cho thấy mẫu 76 câu chưa đủ phân biệt.

- **Bộ SBV cũng cần cào thêm** (đo 12/08): corpus phủ 4/27 văn bản bộ này hỏi tới ⇒ 29/100 câu
  dùng được. Cào 7 văn bản trong phạm vi sản phẩm (thanh toán · tài khoản · thẻ · ngoại hối ·
  PCRT · an toàn giao dịch) đưa `bo_sbv.jsonl` từ 29 → **56/100** câu, thứ tự lợi nhất:
  `94/2025/NĐ-CP` (→37) · `64/2024/TT-NHNN` (→43) · `58/2024/TT-NHNN` (→48) ·
  `50/2024/TT-NHNN` (→51) · `12/2022/TT-NHNN` (→53) · `60/2024/TT-NHNN` (→55) ·
  `08/2023/TT-NHNN` (→56). 16 văn bản còn lại (cho thuê tài chính, bảo lãnh, thư tín dụng, kiểm
  toán độc lập, thống kê tiền tệ, …) đưa tiếp 56 → 100/100, nhưng đó là **mở rộng sản phẩm**,
  không phải bổ sung dữ liệu — cùng phán đoán đã ghi ở trên cho bộ TVPL. Danh sách đầy đủ, đúng
  định dạng `scripts/crawl_vbpl_batch.py`: `research/crawl_list_sbv.txt` (tên văn bản trong đó
  **suy từ câu hỏi và slug URL**, chưa đọc văn bản gốc — kiểm lại khi tra URL). `21/2017/TT-NHNN`
  trùng với `research/crawl_list_eval.txt` — cào một lần dùng cho cả hai bộ.

### [ ] T111 · Văn bản 0 điều duyệt đầu tiên trên môi trường mới thì bảng LanceDB không được dựng

`ingest_one_doc` trên nhánh "chưa có bảng" chỉ gọi `_tao_bang_moi` khi `rows` không rỗng
(`n = _tao_bang_moi(db, rows)[0] if rows else 0`) — nếu văn bản ĐẦU TIÊN được duyệt qua
`/approve` trên một môi trường chưa từng có bảng `chunks` lại có 0 điều (admin xoá hết Điều
trong ô JSON rồi bấm duyệt), node vẫn lên Neo4j nhưng bảng LanceDB không bao giờ được dựng. Đúng
hành vi cũ (`elif rows:` của bản trước khi hoà nhánh 13/08), không phải lỗi mới — ghi lại vì
`CLAUDE.md` bắt việc-đã-biết-chưa-làm phải sống ở đây.

- Vì sao quan trọng: mọi lượt duyệt SAU đó — kể cả văn bản có điều thật — cũng rơi vào cùng
  nhánh "chưa có bảng" cho tới khi có một văn bản khác 0 điều đi qua, nghĩa là hybrid search
  hoàn toàn không hoạt động (không bảng, không lỗi) trong khoảng đó mà API vẫn trả
  `200 approved`. Rủi ro thấp trên corpus thật hôm nay (luôn có văn bản khác 0 điều nạp trước
  qua CLI), nhưng môi trường mới tinh (CI, demo, tenant mới) mà văn bản đầu duyệt qua UI lại
  rỗng là ca chưa ai kiểm.
- Bước đầu: thêm test ở `tests/test_ingest_mot_van_ban.py` — bảng chưa tồn tại + văn bản 0 điều
  → gọi `ingest_one_doc`, khẳng định bảng LanceDB VẪN được dựng (rỗng, có index FTS).
- Cách sửa hiển nhiên **đã bị bác bằng phép đo** (14/08): `create_table(data=[])` ném
  `ValueError: Cannot create table from empty list without a schema`, nên gọi thẳng
  `_tao_bang_moi(db, [])` không chạy. Bản sửa phải truyền `schema` tường minh — dựng schema từ
  đâu (hằng số viết tay, hay `pa.schema` suy từ `build_chunks` một văn bản giả) là câu hỏi mở
  và là thứ phải chốt trước khi viết code.

### [~] T112 · LLM-judge chất lượng câu trả lời (Correctness) — hạng mục 2 Sprint 3

`eval/judge.py` (mới, 14/08) chấm CHẤT LƯỢNG câu trả lời trên bộ SBV (`eval/bo_sbv.jsonl`, 29 câu):
join `reference_answer` do tác giả bài báo viết theo `question_id`, sinh câu trả lời qua đường sản
phẩm `answer.build_answer`, chấm 3 tiêu chí Correctness §5.3 — tương đương ngữ nghĩa (LLM,
temperature=0), có trích dẫn + trích dẫn khớp corpus (thuần Python). Kết quả vào
`eval/results/judge-sbv-*.json`. Test thuần ở `tests/test_judge.py`.

- Đã xong 14/08: (a) độ ổn định đo hai đợt — **0/29 verdict đổi (100%)**, nên 1 phiếu đủ, không
  cần self-consistency 2+1; (b) bug **`chat_json` mặc định reasoning treo > 2 phút/câu** trên nội
  dung pháp lý → sửa `cham_ngu_nghia` dùng `reasoning=False` (12s/câu); (c) số + phân tích 6 câu
  hụt ghi vào `docs/EVAL-IR.md` §12. Kết quả: điểm ngữ nghĩa TB 0.862, "dung" 23/29, trích dẫn
  khớp 29/29.
- Còn dở: (1) chưa có **cột baseline** (Naive RAG) để so — cần khi dựng one-pager (hạng mục 5),
  lúc đó tách phần sinh câu trả lời để dùng chunk naive; (2) hai câu "sai" (qid 55, 5) nên đào
  article-level để biết hụt ở retrieval khoản hay sinh câu trả lời; (3) mẫu 29 câu nhỏ + 3 câu
  trùng, KHÔNG so trực tiếp Correctness 2-annotator của bài báo.

### [ ] T113 · Mở rộng corpus để chạy hết bộ SBV 100 câu (29 → 100)

Bộ SBV hiện chỉ chạy 29/100 câu vì corpus thiếu **23 văn bản** được dẫn (tập `van_ban_thieu`
của `eval/bo_sbv_khong_can_cu.jsonl`). Không phải hệ trả sai — thiếu nguồn. **70/71 câu chỉ thiếu
đúng 1 văn bản** nên cào tăng dần được, mở khoá độc lập: top 6 văn bản mở ~37 câu, top 11 mở ~52,
cả 23 mở 71 (đuôi dài, mỗi văn bản +1). Toàn TT + NĐ-CP, không VBHN.

- Đã xong 14/08: `research/crawl_list_sbv.txt` đủ 23 URL (chủ repo tra 12/08), và **cào xong về
  staging `data/raw/vbpl/corpus/`** (`0 cào mới, 23 bỏ qua, 0 hỏng`). Việc cào KHÔNG còn là nút thắt.
- Nút thắt còn lại: **nhập** — enrich vào `data/corpus.real.json` + duyệt maker-checker. Nhập tăng
  dần (T104) đã sẵn; chỉ thiếu thời gian duyệt. Chạm corpus phục vụ nên qua spec→plan.
- Sau khi nhập: `uv run python eval/chuyen_sbv.py` (split tự cập nhật) → `run_benchmark.py`
  `--bo eval/bo_sbv.jsonl` + `judge.py`. Đây chạm corpus phục vụ (production) nên đi qua
  spec→plan như quy ước, không nhập ad-hoc.
- Không nhắm quy mô bài báo (840 văn bản): sai phạm vi sản phẩm (lát cắt thanh toán), xem
  `docs/EVAL-IR.md` §8.

### [ ] T114 · Top-k / reranker đường trả lời — điều chi phối rơi ngoài top-6

Judge SBV (§12 `docs/EVAL-IR.md`) lộ một ca hụt mức điều: qid=5 nhãn vàng `TT40-2024::Điều 23`
**không nằm top_k=6** mà `answer.build_answer` dùng, nhưng ở top_k=20 xếp **hạng 4**. Điều chi phối
truy hồi được và xếp hạng tốt, chỉ rơi ngoài cửa sổ top-6 ⇒ câu trả lời dựng thiếu điều đó. Đường
sản phẩm hiện `top_k=6` mặc định (`ChatRequest.top_k`).

- Quan sát kèm theo: **top-6 và top-20 ra thứ tự khác nhau** (không phải prefix ổn định) — RRF fuse
  theo pool nông/sâu cho ranking khác. Cần hiểu vì sao trước khi chỉnh, không chỉ nống k lên.
- Hai hướng, chưa chốt: (a) tăng `top_k` đường trả lời (rẻ, nhưng nhồi context nhiều hơn, có thể
  kéo nhiễu); (b) thêm **cross-encoder rerank** sau retrieval (đúng thứ bài báo có mà LexFlow thiếu,
  xem §10) — đắt hơn, cần model. Đo lại F2@k mức điều + judge Correctness sau mỗi hướng.
- Bước đầu: chạy `eval/judge.py` với đường trả lời `top_k` cao hơn (vd 10/12) trên 29 câu SBV, xem
  điểm ngữ nghĩa TB 0.862 có nhích không và có kéo nhiễu làm tụt câu khác không. Thuần đo, chưa đổi
  mặc định sản phẩm.
- **Đã dựng tầng đo rerank (16/08):** `eval/thu_rerank.py` (rerank top-20 hybrid, so R@1/R@2/R@5/MRR@2
  mức điều, checkpoint 2 tầng, provider đổi qua `.env`) + `eval/modal_reranker.py` (host ViRanker/bge
  trên Modal, endpoint cùng shape Jina). Kết quả + phân tích ở `docs/EVAL-IR.md` §13.
  - **3 provider đo xong (16/08), Δ R@1/MRR@2 mức điều:** Cohere `rerank-v3.5` **+5.8/+4.1pt** (thắng rõ,
    đuôi gần như không mất) > Jina reranker-v2 +3.3/+1.5pt ≈ ViRanker (Modal) +2.2/+1.5pt (cả hai tụt R@5
    ~−2.7pt). ViRanker tuned tiếng Việt **lại thua Cohere** (có thể do max_length=512 cắt điều dài).
  - **Kết luận:** (1) nếu làm rerank → **Cohere API, KHÔNG self-host** (ViRanker yếu hơn + thêm vận hành);
    (2) gain giới hạn (+5.8pt R@1 đổi −1.5pt R@5), chỉ đáng khi câu trả lời dựa top-1..2; (3) 2 câu judge
    sai (§12) là lỗi **sinh** không phải retrieval → rerank không chạm, xếp sau việc generation. Giữ `[ ]`.
  - Bàn đo giữ lại: `eval/thu_rerank.py` (đổi provider qua `.env`) + `eval/modal_reranker.py`. Chi tiết
    số + phân tích: `docs/EVAL-IR.md` §13.
  - **Chẩn đoán 16/08 củng cố "chưa đưa lên sản phẩm":** rerank chỉ hại R@5 ở câu nhiều-căn-cứ, mà bộ SBV
    chỉ 8/100 câu có ≥2 điều vàng, và trong 19 câu judge "thiếu" chỉ **1** thuộc nhóm đó (xem T109). Giải
    pháp rerank-fusion (giữ R@5) cứu ≤1/19 câu hiện lỗi → gần vô ích trên dữ liệu này. Ưu tiên T109
    (completeness) trước; rerank để dành khi bộ câu nhiều-căn-cứ trở nên quan trọng.

### [ ] T115 · TT45-2024 thiếu `provisions` (cây điều khoản parse rỗng ở nguồn)

Nạp 23 văn bản SBV (14/08): TT45-2024 vào corpus với `provisions = []`. `canh_bao` bản crawl ghi rõ
"lệch Điều giữa cây điều khoản và toàn văn: **cây 0, toàn văn 46**" — DOM cây điều khoản trên vbpl.vn
parse ra 0 node dù toàn văn có 46 điều. `provisions` dựng từ `build_provision_tree` (`vbpl.py:625`)
đọc node DOM, KHÔNG suy được từ text `articles`, nên không dựng lại tại chỗ được.

- **Không ảnh hưởng eval/retrieval:** `pipeline.py` (ingest→chunk) chỉ dùng `articles` (46 điều TT45
  đều có). `provisions` chỉ nuôi ontology (`app/ontology/parser.py`). Hoãn theo nguyên tắc eval-driven.
- Bước sửa (khi ontology cần TT45): re-crawl riêng TT45, soi DOM xem vì sao `prov_nodes` rỗng
  (`canh_bao`: nguồn bỏ markup một dòng khiến cây thiếu, hoặc render khối sửa đổi 2 lần) — đúng ca
  memory `khong-voi-do-loi-cho-nguon`, soi DOM kiểm chứng đừng đoán. Xong thì `enrich_corpus_from_vbpl.py`
  nạp `provisions` mới như 22 văn bản kia.

### [ ] T116 · Incremental ingest lớn trên Cloud để FTS mù với hàng mới; `num_indexed_rows` không đáng tin

Nạp 23 văn bản SBV (14/08): bảng 661→1496 chunk, nhưng `text_idx` `num_indexed_rows` **kẹt 661/1496
suốt 5+ phút** — `_cho_index` trên nhánh Cloud (`pipeline.py:523`) CHỈ `wait_for_index`, KHÔNG
`create_fts_index(replace=True)` (cố ý, tránh reindex toàn bảng mỗi lượt — comment `:501`), dựa vào
Cloud tự index nền. Nền không đuổi kịp trong cửa sổ đó ⇒ 835 hàng mới nằm ngoài FTS, nhánh BM25 mù.

- Phải trigger tay `create_fts_index("text", replace=True, **_FTS_OPTS)` mới phủ. **Sau replace,
  `num_indexed_rows` báo 0** (rồi giữ 0) DÙ FTS query thật đã trả về văn bản mới (test:
  `search("giao diện lập trình ứng dụng mở", query_type="fts")` → TT64-2024, ND94-2025). Tức
  `num_indexed_rows` là **metric không đáng tin trên Cloud sau replace** — cảnh báo "phủ X/Y hàng"
  của `_cho_index` (`:535`) dựa vào nó nên có thể báo oan hoặc bỏ sót.
- Chưa rõ: rebuild có THỰC SỰ cần không, hay hàng mới vốn tìm được qua flat-scan (chưa test FTS
  trên hàng mới TRƯỚC khi replace). Cần đo: sau một incremental lớn, FTS query hàng mới trả về
  không, độc lập với `num_indexed_rows`.
- Hướng: (a) `_cho_index` Cloud kiểm phủ bằng **FTS query thăm dò** thay vì `num_indexed_rows`;
  (b) nếu chưa phủ thì `create_fts_index(replace=True)` (chấp nhận reindex sau ingest lớn) hoặc
  ghi rõ vận hành phải chạy tay. `ingest_one_doc` (/approve) còn không gọi `_cho_index` nên rủi ро
  tương tự ở quy mô nhỏ.

### [ ] T117 · Ingest bộ VLQA (VLSP 2025 DRiLL) để chứng minh retrieval ở scale + có điểm leaderboard

Bộ SBV 49 văn bản quá nhỏ để phân biệt các cột (R@20 bão hoà ~0.99, EVAL-IR §11). VLQA
(`data/raw/VLQA/`, VLSP 2025 DRiLL — thử thách **truy hồi**, đoán `relevant_laws`) cho corpus lớn
thật + tập test công khai để so leaderboard. **Đo 15/08:**

```
legal_corpus.json   2.157 văn bản · 59.636 điều · 82,28M ký tự
token embed         ~25,7M (đo mẫu 40 điều: 3,21 ký tự/token)
train.json          2.190 câu CÓ nhãn (đo/tinh chỉnh local)
public/private test 312 / 627 câu (nhãn rỗng — nộp)
```

- **Chi phí tiền: ~$4** — embed corpus 25,7M token × $0.15/1M (gemini-embedding-001, giá tra
  15/08) = $3.85; query 939 câu test ~$0.01. Retrieval-only, không cần sinh câu trả lời cho DRiLL.
- **Infra KHÔNG phải nút thắt** (đính chính khảo sát đầu): Neo4j node là **cấp văn bản** (1/văn
  bản), không phải cấp điều → 2.157 node, cách xa mọi ngưỡng free; `DonVi` = 0 vì đến từ
  `push_overlay` banking, VLQA không có. **Nên bỏ hẳn Neo4j cho bộ này** (graph không thêm gì đo
  được, EVAL-IR §5/§11). LanceDB ~60k chunk ≈ 184 MB vector — canh rebuild FTS ở scale này (T116).
- **Việc kỹ thuật chính = adapter schema**: VLQA dùng `id/aid` số nguyên, LexFlow dùng `doc_id`
  chuỗi + nhãn "Điều N". Phải (a) chuyển `{id, law_id, content:[{aid, content_Article}]}` →
  `CorpusDocument`, **giữ `aid` trong chunk id** để nộp lại được; (b) map kết quả retrieval → danh
  sách `aid`. Corpus VLQA không kèm relationships.
- **Cảnh báo giá trị**: VLQA là luật TỔNG QUÁT (hôn nhân, phạm nhân, chứng khoán…), không banking →
  chứng minh **lõi retrieval** (hybrid RRF), KHÔNG chạm lớp compliance/hiệu lực/conflict. Tách
  **nhánh corpus riêng**, đừng trộn vào corpus banking sản phẩm.
- **Bước đầu**: viết spec→plan (chạm ingest/schema/infra — task ảnh hưởng lớn), rồi adapter
  `legal_corpus.json` → CorpusDocument giữ `aid`, ingest LanceDB (skip Neo4j), đo IR trên
  `train.json` 2.190 câu bằng `eval/metrics.py` trước khi nộp `public_test.json`.
- **Xác minh aid (16/08):** aid là **id điều TOÀN CỤC** 0..59.635 (duy nhất, liên tục across corpus) —
  một mình aid định danh điều; `relevant_laws` = tập aid cần đoán. 1 doc có `content` rỗng (bỏ qua).
  `content_Article` không có "Điều N" → dùng `article=str(aid)`, recover aid = số đầu nhãn (`_split_khoan`
  giữ tiền tố). Khớp metric = exact aid.
- **Tách LanceDB:** bảng RIÊNG `chunks_vlqa` (không phải cột cờ) — cô lập vector + FTS, `chunks` sản phẩm
  không đụng. Cách hiện thực: thêm param `table` (mặc định `LANCEDB_TABLE`) vào `_open_table`+`hybrid_search`;
  ingest tái dùng `build_chunks`+`_embed_rows` ghi bảng khác. Product byte-identical (934 test + gate 36/36).
- **STAGE A XONG (16/08) — máy móc chứng minh.** `eval/vlqa_adapter.py`+`vlqa_ingest.py`+`vlqa_eval.py`
  (+ test). Ingest slice 60 doc → 2.170 chunk; IR trên 58 câu train: R@1 0.674 · R@5 0.885 · R@20 0.932 ·
  MRR 0.851 (LẠC QUAN vì slice nhỏ ít distractor — không phải số thật). aid round-trip đúng.
- **STAGE B XONG (17/08) — $4, số thật + file nộp.** Ingest full 2.156 doc → **77.776 chunk** vào
  `chunks_vlqa` (resumable, 1 lần chạy). IR thật trên 2.188 câu train: **R@1 0.473 · R@5 0.769 · R@10
  0.840 · R@20 0.888 · MRR 0.678** — thấp hơn hẳn slice-60 (0.674/0.885/0.851) như dự đoán vì đủ
  distractor. Đây là lõi hybrid RRF thuần trên luật tổng quát (không hiệu lực/graph/overlay).
  - **Tối ưu topk theo Macro-F2** (metric của DRiLL = Recall/Precision/Macro-F2): sweep k=1..20 trên
    cache train → **k=2 tối đa F2 (0.533)**, hơn hẳn k=10 (0.335) — đa số câu 1–3 gold nên nộp nhiều
    giết precision. File nộp dùng top-2.
  - **File nộp:** `public_test` 312 câu + `private_test` 627 câu, **mirror y hệt input** (giữ question/
    answer, chỉ điền relevant_laws) vì DRiLL không công bố schema nộp — thừa trường thì grader bỏ qua.
    0 câu rỗng. Ở `eval/results/vlqa_*.json` (gitignored — nhúng câu hỏi test).
  - **Robust:** retry+skip lỗi Cloud thoáng qua per-câu; checkpoint per-câu (relaunch qua mỗi kill).
  - **Rerank (17/08, `vlqa_eval.py --rerank`):** đo trên 300 câu train, so @cutoff nộp k=2. **ViRanker
    (Modal) HẠI** (F2@2 0.557→0.516, tụt mọi metric); **Cohere `rerank-v3.5` GIÚP** (R@2 +2.2pt, **F2@2
    0.557→0.575**, mất đuôi R@20 −1.0). Khớp SBV (Cohere >> ViRanker). Vì nộp k=2, cải thiện F2@2 ăn thẳng
    điểm → **áp Cohere rerank cho file nộp** (public+private). Gain khiêm tốn nhưng dương.
  - **VARIABLE-K XONG (18/08) — leaderboard xác nhận.** Rerank Cohere đo trên 300 câu ĐẦU không transfer
    sang full private (private rerank+k2 = 0.5355 ≈ hybrid thuần 0.533) — cái +4pt là overfit subset dễ.
    Đòn thật là **cutoff theo độ tin cậy điểm rerank** (`--var-k`): biên top1-top2 ≥0.05 → nộp 1; top2≈top3
    ≤0.05 (đa gold) → nộp 3; else 2. Ngưỡng chốt bằng **2-fold CV trên 68 câu train** (gain out-of-sample
    +0.048, cả 2 fold cùng ngưỡng). biên điểm RRF thì VÔ DỤNG (theo rank, không phân biệt) — phải điểm
    rerank. **Leaderboard THẬT:** private F2 **0.5355→0.581** (P 0.361→0.447, R 0.609→0.628); public F2
    **0.5472** (P 0.425, R 0.590). Code ở `_var_k`/`_aids_scored`/`thu_rerank.rerank_scored`, commit `c693053`.
  - **Còn lại:** xác nhận schema với organizer (`minhnt@jaist.ac.jp`); nâng recall → **T118** (đòn tiếp).
    10 câu public cuối bị fallback hybrid (cạn budget Cohere trial) — nâng lên rerank khi account reset, marginal.

### [ ] T118 · VLQA — nâng trần recall (R@20 = 0.89, 11% gold ngoài top-20)

Sau var-k (T117), cutoff đã vắt kiệt; F2 giờ bị chặn bởi **recall**. Đo 18/08 trên 2.188 câu train:
R@1 0.473 · R@2 0.619 · R@5 0.769 · **R@20 0.888** · MRR 0.678. Oracle "chọn k đúng mỗi câu" trần
0.708 nhưng chỉ đạt được nếu gold nằm TRONG pool — 11% gold không hề lọt top-20 nên cutoff không cứu
được. Mọi kỹ thuật dưới chỉ đáng làm nếu **kéo gold bị miss vào pool** hoặc **đẩy gold lên top-2**.

- **Bước 0 — chẩn đoán 11% miss TRƯỚC (rẻ, quyết định tất cả).** Chưa biết gold bị miss ở nhánh nào.
  In, với mỗi câu train mà gold ngoài top-20: gold đó có trong top-100 vector-only không? top-100
  FTS-only không? → biết miss do embedding (cả hai trượt) hay do chunking/tokenizer (một nhánh trượt).
  Không đo cái này thì 1/3/5 dưới là đoán mò.

- **[x] Kỹ thuật 1 — tokenizer FTS tiếng Việt: ĐÃ THỬ 18/08, KHÔNG đáng (negative).** Rebuild FTS
  `chunks_vlqa` với `ascii_folding=False` (giữ dấu) — **BM25-only tăng rõ** (R@20 0.673→0.740, +6.7pt;
  mọi k +4-7pt trên 300 câu train). NHƯNG **hybrid gần như không đổi** (F2@2 0.553→0.554, +0.001), và
  tăng trọng số BM25 (`TRONG_SO_THUA` 0.1→0.25+) lại **hại** (F2@2 xuống 0.534→0.483). Vì nhánh **vector
  áp đảo** — gold BM25 mới bắt được thì vector đã có (khớp Phase 0: FTS chỉ cứu 25% miss, phần lớn trùng
  vector). Kết luận: tokenizer chỉ giúp BM25 cô lập, vô nghĩa khi hybrid vector-dominated. Index `chunks_vlqa`
  để lại ở `ascii_folding=False` (trung tính +0.001; re-ingest sau về `_FTS_OPTS` fold=True). Caches
  `cache-vlqa-train-branches/fts-nofold`.
- **[x] Kỹ thuật 1b — word-segment BM25 (pyvi): ĐÃ THỬ 18/08, dương NHỎ + phát hiện sản phẩm.** Tokenizer
  `simple` cắt tiếng Việt cấp ÂM TIẾT ("ngân hàng"→["ngân","hàng"]) — sai cho tiếng Việt. Segment bằng
  `pyvi` (nối "ngân_hàng") + bỏ dấu câu + `base_tokenizer='whitespace'` (simple TÁCH trên `_`, whitespace
  không) + `ascii_folding=False`. Bảng FTS LOCAL `chunks_vlqa_seg` (77k, ~5 phút). **BM25-only tăng mạnh:
  R@2 0.361→0.470 (+10.9pt), R@20 0.673→0.755 (+8.2pt)** — hơn hẳn ascii_folding. **Hybrid: F2@2
  0.553→0.562 (+0.009)** ở w=0.1 (tăng weight vẫn hại) — THẬT nhưng nhỏ vì vector áp đảo. Word-seg là đòn
  BM25 mạnh nhất nhưng lợi hybrid vẫn khiêm tốn cho VLQA. Scripts `kt1b_build/measure` (cần `pyvi` — chưa
  thêm vào deps chính vì chỉ script thí nghiệm dùng; cài lại khi hiện thực word-seg cho sản phẩm).
  - **[x] KT1b-sản phẩm — word-seg trên BM25 banking (bo_sbv, 100 câu article-level): ĐÃ ĐO 20/08,
    KHÔNG đáng đổi production (âm ở config thật).** Dựng bảng LOCAL từ `corpus.real` (1.496 chunk), hai
    biến FTS: âm-tiết `_FTS_OPTS` (production) vs word-seg pyvi. **BM25-only word-seg thắng RẤT mạnh —
    hơn hẳn VLQA: R@2 0.542→0.700 (+15.8pt), R@5 +9.0pt, R@20 0.945→0.993, F2@2 0.462→0.597 (+13.5pt),
    precision tăng mọi k.** NHƯNG hybrid (gemini vec + BM25) **lặp lại y hệt VLQA**: ở trọng số production
    **w=0.1 word-seg TRUNG TÍNH-tới-hơi âm** (F2@1 −0.010, F2@2 −0.013, còn lại ~0). Nâng weight mới thấy
    word-seg dương (w=1.0: F2@2 +0.033) nhưng **nâng weight tự nó hạ đỉnh**: ô F2@2 tốt nhất toàn bảng là
    **w=0.1 âm-tiết = 0.757** (= production hiện tại), word-seg không ô nào vượt. Lý do: **vector gemini quá
    mạnh trên sản phẩm** (vector-only R@1 0.755, R@2 0.865, F2@2 0.735) — gold mà word-seg-BM25 mới bắt
    được thì vector đã có. Kết luận: **giữ nguyên `_FTS_OPTS` + w=0.1**; word-seg không cứu được hybrid IR
    ngôn-ngữ-tự-nhiên. Scripts `prod_ws.py`, `prod_ws_hybrid.py` (scratchpad).
    - **[x] Ca exact-match / `search_in_docs` (within-doc, đo 20/08): CŨNG âm, có trần cứng.** Mô phỏng
      nhánh compliance — giới hạn ứng viên trong đúng văn bản gold rồi xếp hạng ĐIỀU (chỗ note
      `retrieval.py:78` nói BM25 âm-tiết yếu nhất). BM25-only within-doc: word-seg dương k≥2 (R@2 +0.060)
      nhưng vẫn thua xa vec-only (F2@2 0.67 vs 0.77). **Hybrid w=0.1 within-doc: word-seg = âm-tiết CHÍNH
      XÁC 0.000 mọi k** — BM25 (tokenizer bất kỳ) không đóng góp vào top. **Trần tuyệt đối:** vector chỉ
      trượt **6/100** câu (within-doc top-2), word-seg-BM25 cứu được **3** (3 câu còn lại cả hai nhánh
      cùng trượt) → tối đa word-seg thêm **+3/100 R@2**, và chỉ khi BM25 thắng mọi tie (ở w=0.1 = 0 thực
      tế). Scripts `prod_ws_indoc.py`, `prod_ws_ceiling.py`. **Kết luận đóng đinh: giữ `_FTS_OPTS` +
      w=0.1; T8 KHÔNG làm word-seg — vector gemini quá mạnh, thị phần BM25 chỉ 6 câu, nửa không lấy được.
      Đòn recall thật phải nhắm nhánh VECTOR (chunking/embedding), không phải BM25.**

- **[x] Kỹ thuật 2 — deep-pool rerank (20→100): ĐÃ THỬ 18/08, KHÔNG giúp (âm).** Retrieve hybrid top-100,
  rerank 100 (Cohere), so var-k pool-20/50/100 trên 200 câu train. **F2@2: pool-20 = 0.568, pool-100 =
  0.564** (hơi TỆ hơn). Deep-pool đưa 51% miss vào pool (Phase 0) nhưng rerank **không kéo chúng lên
  top-2** (hybrid xếp thấp vì tín hiệu yếu), thêm distractor lại hại nhẹ. `_POOL=20` là đúng. Script
  `kt2.py`, cache `cache-vlqa-train-pool100rr`.

- **[x] Bước 0 mở rộng — chẩn đoán cấu trúc miss theo ĐÒN BẨY (21/08, 2.188 câu train, hybrid top-20).**
  Phân rã lỗi để biết transform/reranker/embedder mỗi cái ăn được bao nhiêu (scripts `vlqa_miss.py`,
  `vlqa_pool100.py`, scratchpad):
  - **54.6%** đã đúng (mọi gold ≤ cutoff 2).
  - **28.2% RANKING** — gold TRONG top-20 nhưng dưới cutoff (20.3% gold-đầu rank>2; 7.9% đa-gold đuôi
    rớt) → địa hạt **reranker/var-k**, mảng lớn nhất. (Số này trên hybrid THUẦN nên là *dư địa* reranker,
    Cohere+var-k đã ăn một phần.)
  - **17.2% FIRST-STAGE** — gold rớt hẳn top-20, rerank KHÔNG bao giờ cứu (số cứng): **12.2% partial-multi**
    (đa-gold thiếu sub-đích → đích **subquery/multi-query độc quyền**) + **5.0% full-miss** (đích embedder/expand).
  - **Pool-100 (mẫu 200 câu, 30 miss):** ~**40% đích rớt top-20 lại trong top-100** (nới pool là đủ) nhưng
    ~**53% vắng cả top-100** (embedder thật sự không thấy). Đây là **lời giải cho KT2 âm**: nới pool CÓ kéo
    gold vào pool nhưng Cohere rerank không nhấc nổi lên top-2 → F2 phẳng. Trần thật = **sức reranker**, không
    phải độ sâu pool.
  - **Xếp hạng đòn (đã có số):** (1) **reranker mạnh hơn** ăn 28% ranking + mở khóa deep-pool; (2)
    **multi-query fusion** ăn 12.2% partial-multi mà reranker không với tới; (3) subquery ≈ multi-query nhưng
    đắt/dễ vỡ; (4) HyDE/expand — chỉ 5% full-miss, hơn nửa vắng cả top-100 → **bỏ**.
- **[x] Kỹ thuật 2b — reranker VN-tuned: `AITeamVN/Vietnamese_Reranker` THẮNG Cohere (21/08, dương rõ).**
  Đổi từ bge-v2-m3 trần sang **AITeamVN/Vietnamese_Reranker** (= chính bge-reranker-v2-m3 + 1.1M triplet
  tiếng Việt) sau khi search HF: không có reranker train-thẳng-legal-VN nào; các reranker VN mạnh đều là
  fine-tune bge-m3/bge-reranker-v2-m3 general. Host Modal (`modal_reranker.py`, chuyển sang path
  `AutoModelForSequenceClassification` + `tiktoken`/`sentencepiece` vì ST mới gọi `AutoProcessor` fail trên
  repo này). **Head-to-head trên ĐÚNG 300 câu train, cutoff F2@2, cùng hybrid baseline 0.569:**
  AITeamVN **F2@2 0.592** (R@1 0.543, R@2 0.687, MRR 0.747) > Cohere `rerank-v3.5` **0.566** (0.523/0.657/0.726)
  > hybrid 0.569. **AITeamVN thắng Cohere MỌI metric (F2@2 +2.6pt); +2.3pt vs hybrid. Cohere flat (~0 vs
  hybrid)** — khớp Bước 0 (reranker mạnh hơn ăn phần ranking 28% mà Cohere không nhấc nổi). Bài học: reranker
  VN *có* thắng, nhưng phải đúng model (ViRanker VN-general thua ở T114; AITeamVN thắng). Cache provider-aware
  `cache-vlqa-train-rerank-<provider>.jsonl` (sửa `do_train` để Cohere↔Modal khỏi đè nhau).
  - **[ ] Chưa xong để đưa vào nộp:** var-k tune cho thang điểm AITeamVN (logit ~[-11, 8], khe lớn) — ngưỡng
    `_VK_BIEN1/_VK_HOA3=0.05` là cho Cohere 0-1, phải tune lại (2-fold CV như T117) hoặc chuẩn hoá điểm trước.
    Sau đó dựng lại file nộp public/private bằng AITeamVN + đo leaderboard so 0.581. `.env` đang để Cohere
    (đường nộp hiện tại) tới khi tune xong.
- **[x] Kỹ thuật 5a — embedding `paraphrase-vietnamese-law` (model bài báo SBV): ĐÃ THỬ 18/08, THUA XA.**
  Deploy lên Modal (`eval/modal_embedder.py`, 768-dim, max 300 token), embed 77k chunk → bảng LanceDB
  **LOCAL** `chunks_vlqa_para` (né cloud throttle; ~$0 GPU), đo vector-only R@k trên 300 câu vs gemini.
  **Thua thảm mọi k:** R@1 0.159 vs 0.520 (-36pt), R@20 0.468 vs 0.891 (-42pt), R@100 0.675 vs 0.942
  (-27pt). Lý do: model tuned **câu↔câu paraphrase** (Spearman 0.86 trên cặp câu hỏi), KHÔNG phải
  câu↔đoạn retrieval; + cắt 300 token điều dài. `gemini-embedding-001` là retrieval embedding mạnh, khó
  thay. `modal_embedder.py` giữ lại (đổi `EMBED_MODEL_ID` để thử model khác). Scripts `kt5_embed/measure`.
- **Kỹ thuật 5b (chưa thử) — bge-m3:** retrieval embedding thật (bất đối xứng, 8k token, đa ngữ mạnh) —
  ứng viên KT5 duy nhất còn lại có cơ thắng gemini. Deploy: đổi `EMBED_MODEL_ID=BAAI/bge-m3` (1024-dim,
  bảng mới), re-embed, đo. Nhưng gemini vốn mạnh → kỳ vọng marginal; cân nhắc làm KT2 trước.
- **Kỹ thuật 3-4 (chưa lên kế hoạch):** (3) HyDE — Gemini sinh câu trả lời giả định rồi embed cái đó;
  query expansion thuật ngữ pháp lý. (4) Sub-query decomposition — tách câu phức, retrieve từng sub,
  hợp nhất; nhắm 25% câu đa gold.

- **KHÔNG phải đòn:** FAISS chỉ là backend ANN — đã có LanceDB IvfPq (verify), đổi ra cùng kết quả.
  Sweep trọng số hybrid (`TRONG_SO_THUA`) rẻ nhưng gain nhỏ, để kèm lượt khác.

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
