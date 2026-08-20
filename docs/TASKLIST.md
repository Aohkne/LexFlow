# LexFlow — Việc tồn đọng

> Danh sách việc **đã biết nhưng chưa làm**, để không phải phát hiện lại. Khác với
> `ROADMAP-SPRINT.md` (kế hoạch theo sprint) và `WORKLOG.md` (nhật ký đã làm).
>
> Quy ước: mỗi mục ghi **vì sao quan trọng** và **bước đầu tiên cụ thể** — đủ để người khác
> (hoặc chính mình ba tuần sau) bắt tay vào mà không phải điều tra lại. Mọi con số đều kèm
> ngày đo; số không có ngày là số chưa kiểm.
>
> Cập nhật gần nhất: 2026-08-18.

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

**Cập nhật 13/08 — POC GraphCompliance đã chạy thật** (nhánh `feat/ai-compliance`, spec/plan
ở `.superpowers/sdd/2026-08-11-graphcompliance-poc/`). Điều kiện "chưa mở" ở trên đã đổi:

- Nhãn người gán **đã có**: 95 comment luật sư trên 2 hợp đồng thật, chủ repo duyệt 12/08
  (`eval/compliance/gold.jsonl`, local-only) — 11 `phap_ly`, trong đó 4 dòng viện dẫn tường
  minh + trong corpus làm mẫu số recall chính.
- Schema **đã có ô tình thái** (6 nhãn, gán bằng regex tất định) **và ô ngưỡng** (`Nguong`,
  giao thức ca-lạ) — hướng (a) đã làm xong trong POC; pipeline Policy Graph in-memory →
  ER-triples (grounding nguyên văn) → hypernym (danh sách ứng viên đóng) → gate tất định →
  judge 2 vòng (Eq. 6 override) chạy được đầu-cuối, 852 test xanh.
- **Recall đo 13/08: đường mới 0/4, đường cũ cũng 0/4** (đường cũ `pass` cả 4 điều liên
  quan; 1 warning duy nhất khác nội dung comment). Nguyên nhân đo được, không phải đoán:
  **cả 4 comment viện dẫn Đ3 NĐ52-2024, Đ3 TT18-2024, Đ8 TT40-2024, Đ20 TT15-2024 — không
  điều nào nằm trong 12 Điều đã trích CU** (bộ CU trích 11/08, gold chốt 12/08). Tức số 0/4
  đo **độ phủ CU**, chưa đo được chất lượng gate/judge.
- Ca lạ chờ chốt schema (gom từ 2 lần chạy + Task 4): `nguong_bo_sot` — dấu hiệu
  'trở lên/ít nhất/tối thiểu/tối đa' không ghép được số (NĐ52 Đ22k2 ×4, TT18 Đ13k2);
  `tinh_thai_kho` — action không mang dấu hiệu tình thái nhưng khoản có ràng buộc cứng
  (TT18 Đ9k6·k7, TT40 Đ25k6); danh sách đầy đủ trong 2 báo cáo local + `task-4-report.md`.
- **Bước đầu tiên (mở lại):** trích CU đúng 4 điều gold viện dẫn ở trên rồi chạy lại 2 báo
  cáo — chi phí ~4 lượt LLM trích; khi đó recall mới bắt đầu nói về chất lượng phán định.

**Cập nhật 13/08 (tối) — đã trích 4 điều gold viện dẫn và chạy lại cả 2 báo cáo.** Hai điều
định nghĩa (Đ3 NĐ52, Đ3 TT18) đúng thiết kế phân vai `premise` nên **không sinh actor-CU**;
hai điều còn lại sinh **12 CU mới** (TT15-Đ20 k1-5, TT40-Đ8 k1-7) → `pred.jsonl` 61 bản ghi,
trong đó 2 lỗi cứng chống-bịa bị loại ⇒ **Policy Graph nạp 59 CU**. Hai lần chạy lại chết vì
lỗi mạng LanceDB Cloud trước khi xong — đã vá 2 tầng (`app/core/vectordb.py` retry_config
tường minh vì env `LANCE_CLIENT_*` không tới tầng Rust; `app/knowledge/retrieval.py`
`_vector_hits` retry 5/15/45s vì client không retry lỗi tầng kết nối) rồi cả hai chạy trọn.

**Recall đường CU sau khi vá độ phủ: ThuHo 0/1 · PAYFAC 0/3** — nhưng khác 0/4 hôm trước,
giờ **từng miss quy được về một nguyên nhân đo trực tiếp**, chia 3 nhóm:

1. **#30 (ThuHo Đ2, cite TT15-Đ20):** chunk Đ20-k3 xếp hạng 5/8 trong retrieval, gate đưa
   đủ k1/2/4/5 vào judge (`tuan_thu`/`khong_ap_dung`) — **CU duy nhất khớp nội dung comment
   là k3, chính là 1 trong 2 bản ghi lỗi cứng bị loại khỏi graph** (guard chống-bịa bắt LLM
   thêm chữ "có" khi trích). Sửa 1 bản ghi này là miss biến mất.
2. **#13, #35 (PAYFAC, cite Đ3 định nghĩa):** cấu trúc — điều định nghĩa → `premise`,
   không có actor-CU cho gate bắt. Muốn bắt phải cho judge dùng tầng premise/khainiem.
3. **#194 (PAYFAC Đ4, cite TT40-Đ8):** thân Điều 4 hợp đồng chỉ **243 ký tự** (nội dung
   thật nằm ở Phụ lục) → query quá loãng, top-8 retrieval không có chunk Đ8 → CU Đ8 không
   thành ứng viên (đo bằng probe `search_in_docs` 13/08). CU dạng "hợp đồng phải có nội
   dung X" là ràng buộc **mức toàn văn bản** — gate theo từng điều chỉ bắt được khi
   retrieval may mắn (ThuHo Đ2 bắt được đúng kiểu này: TT40-Đ8 k5/k7 ra `thieu_thong_tin`).

- ~~**Bước kế tiếp:** (a) sửa tay/trích lại bản ghi `15/2024/TT-NHNN#than/dieu_20#khoan_3`
  (và `40/2024...dieu_8#khoan_1`) đang lỗi cứng — rẻ nhất, gỡ ngay nhóm 1; (b) gate CU dạng
  "hợp đồng phải có tối thiểu..." ở mức toàn hợp đồng thay vì từng điều — gỡ nhóm 3;
  (c) nhóm 2 để lại cho quyết định schema (nối premise vào judge) — đắt, cần bàn.~~

**Cập nhật 16/08 — đã làm cả (a)(b)(c), recall đo lại: ThuHo 1/1 · PAYFAC 2/3** (commit
`7123b13` + `418894b`; hai lần chạy trọn trên corpus thật, checkpoint per-điều mới thêm vì
máy kill job nền 4 lần giữa chừng).

- **(a)** k3 trích lại sau khi thêm "trách nhiệm" trần vào từ điển tình thái (khuôn
  "Trách nhiệm của X:" là cách áp nghĩa vụ chuẩn — guard kết tội oan nhãn "Có trách nhiệm");
  Đ8-k1 sửa tay nhãn về dạng liệt kê như k2, kèm ghi chú trong bản ghi. Graph nạp **61 CU**.
- **(b)** `lap_cu_plan` → thêm `lap_plan_toan_van`: điều luật có actor-CU mà subject là
  "hợp đồng/thỏa thuận" (đo trên 61 CU: đúng TT40-Đ8 + TT18-Đ9) vào một lượt judge trên
  toàn văn, chọn tất định không qua retrieval. Recall ghi công verdict toàn-văn theo tiền
  tố văn bản.
- **(c)** Khái niệm khớp nguyên văn/hypernym trong điều hợp đồng đi cùng prompt judge
  (không thêm lượt LLM), verdict mang id khái niệm. Đã sửa docstring `KhaiNiem` ghi lại
  thay đổi triết lý: định nghĩa vào judge để so CÁCH DÙNG thuật ngữ, không phải nghĩa vụ.
- **Ba bug lộ ra khi chạy thật, đều đã vá + test:** LLM trả quote null làm vỡ `PhanQuyet`;
  gold #30 ghi `dieu_hop_dong` kiểu **int** (dòng duy nhất/95) nên không bao giờ khớp khoá
  chuỗi — recall nay `str()` hoá; **127/981 verdict là "LLM bỏ sót"** bị đổi lặng thành
  `thieu_thong_tin` (suýt ghi công rỗng cho #13/#35) — prompt nay BẮT BUỘC trả đủ mọi id,
  đo lại còn 50+5.
- **Đọc số cho đúng:** #30 và #194 bắt bằng verdict trúng đúng điều luật sư viện dẫn; #35
  bắt qua TT18-**Đ9** ở lượt toàn văn (gold chỉ ghi `van_ban` mức số hiệu, luật sư viện dẫn
  Đ3 — định nghĩa Đ3 judge chấm `tuan_thu` thật); #13 sót vì judge đánh giá thật định nghĩa
  NĐ52-Đ3 và kết luận `tuan_thu` — **bất đồng phán định**, không phải lỗ hổng độ phủ.
- ~~**Còn mở:** 50 verdict "LLM bỏ sót" còn lại ở ThuHo (điều có plan lớn) — cân nhắc chẻ
  prompt theo lô CU; và #13 cần người đọc lại comment gốc để phân xử judge vs luật sư.~~
  **Đã gỡ 16/08 (tối), commit `ae1648a` — 0 "bỏ sót" ở cả hai báo cáo, recall giữ 1/1 · 2/3.**
  Ba nguyên nhân đo được (probe raw từng lời gọi): (1) model thoái hoá Ở CUỐI — JSON hoàn
  chỉnh kèm đuôi rác lặp, `json.loads` vỡ vì Extra data → `chat_json` nay `raw_decode` lấy
  object đầu; (2) prompt 24 CU làm model chạy loạn 236k ký tự rồi đứt ở trần token —
  `phan_dinh` nay chẻ lô ≤8 mục/lời gọi; (3) ThuHo có HAI điều trùng "số 4" (heading gõ tay)
  — dict verdict khoá theo số bị ghi đè mất trắng điều trước, nay gộp thay vì gán.
  ~~**Còn mở duy nhất:** #13 — người đọc lại comment gốc để phân xử judge (`tuan_thu` có căn
  cứ) vs luật sư (đánh dấu pháp lý).~~ **Đã phân xử 17/08 (chủ repo):** luật sư đúng về cụm
  thuật ngữ (bản gốc hợp đồng ghi thiếu một từ trong tên dịch vụ) nhưng **dẫn sai khoản** —
  NĐ52 Đ3 **k18** mới là khoản định nghĩa cụm đó, không phải k15 (gold đã sửa `refs`, local).
  Soi cache PAYFAC: định nghĩa k18 **có** trong plan, và bản docx "Dự thảo 1-2" đang chạy
  **đã mang sửa đổi của luật sư** — `tuan_thu` của judge đúng với văn bản nó nhìn thấy. Miss
  #13 là **lệch phiên bản gold/input** (nhãn gán trên bản trước sửa), không phải lỗi judge
  hay lỗ hổng schema; giữ trong mẫu số recall (PAYFAC 2/3) kèm `ghi_chu` trong gold. Hướng
  schema "định nghĩa vào judge có verdict riêng" được chủ repo **duyệt giữ 17/08** (docstring
  `KhaiNiem` là chỗ ghi lý do); việc khớp thuật ngữ mờ để bắt ca lệch-một-từ tách sang **T28**.

### [ ] T27 · 2 ca tư vấn pháp chế thật — nguồn eval hỏi đáp, nhưng 3/4 văn bản viện dẫn ngoài corpus

`docs/compliance/tu_van_phap_ly.md` (local-only, cả thư mục gitignored — tài liệu nội bộ
ngân hàng, **không commit, không chép nội dung tư vấn vào file nào được commit**; ở đây chỉ
ghi số hiệu văn bản). Soi 16/08: 2 ca tư vấn của phòng pháp chế về nghiệp vụ Mobile Money,
mỗi ca gồm mô tả quy trình → câu hỏi → ý kiến kèm căn cứ điều khoản, tổng ~5 cặp hỏi–đáp.

- **Không dùng trực tiếp được cho pipeline compliance**: đầu vào của `python -m app.compliance`
  là hợp đồng có cấu trúc Điều/Khoản, còn đây là tình huống nghiệp vụ dạng tường thuật. Muốn
  dùng phải thêm dạng task mới (đánh giá tuân thủ mức quy trình) — chưa có, chưa mở.
- **Giá trị thật nằm ở nhánh hỏi đáp**: ~5 câu hỏi có đáp án do pháp chế ngân hàng soạn, trích
  dẫn tường minh tới điều/khoản — nhãn người ngoài dự án gán, đúng thứ benchmark tự sinh đang
  thiếu (máy tự chấm máy). Ứng viên cho bộ câu hỏi so sánh LexFlow vs SVB (Sprint 3).
- **Chốt chặn đo 16/08**: 4 văn bản được viện dẫn thì chỉ `40/2024/TT-NHNN` có trong corpus
  (và là văn bản duy nhất đã có CU — 92 bản ghi ontology liên quan). Ba văn bản vắng:
  `368/2025/NĐ-CP · 64/2024/TT-NHNN · 77/2025/TT-NHNN` — hệ hỏi đáp hiện **không thể** trả
  đúng các câu này dù prompt tốt đến đâu.
- Giá trị phụ cho compliance (sau này): lập luận CASE 2 về trách nhiệm ngân hàng mở TKĐBTT
  (Đ3.7, Đ27 NĐ 368) có cấu trúc y hệt ActorCU — nguồn seed CU tốt khi NĐ 368 vào corpus.
- **Bước đầu tiên:** đưa 3 văn bản trên vào danh sách ưu tiên của đợt nạp 840 (Sprint 3, dòng
  «Nạp đầy đủ văn bản»); sau khi ingest xong mới chuyển ~5 cặp hỏi–đáp thành file eval — nhớ
  ràng buộc **không commit dữ liệu dẫn xuất từ tài liệu nội bộ** (cùng lệ với gold.jsonl).

### [x] T28 · Khớp thuật ngữ mờ trong `khai_niem_lien_quan` — bắt ca hợp đồng viết lệch một từ

Sinh ra từ phân xử #13 (17/08). `khai_niem_lien_quan` (`app/compliance/gate.py:191`) hiện chỉ
chọn định nghĩa khi thuật ngữ **nằm nguyên văn** trong điều hợp đồng hoặc **trùng đúng** một
hypernym đã map. Lớp lỗi thật của #13 là hợp đồng viết tên dịch vụ **thiếu/lệch một từ** so
với thuật ngữ luật — khi đó đường nguyên văn chắc chắn trượt, còn đường hypernym chỉ trúng
nếu embedding may mắn map về đúng cụm. Tức chính ca mà cơ chế định-nghĩa-có-verdict sinh ra
để bắt lại là ca dễ bị gate lọc mất trước khi judge kịp nhìn.

- **Hướng làm (đã cân nhắc 17/08, chọn tất định + stdlib, không LLM/không embedding thêm):**
  1. chuẩn hoá hai phía (lower, gộp khoảng trắng) rồi khớp **tập-con token**: mọi token của
     n-gram trong điều là tập con token của thuật ngữ luật (hoặc ngược lại, chênh ≤1-2 token)
     — bắt trúng lớp "thiếu một từ" bằng phép so tập, không cần thư viện;
  2. lưới an toàn mức ký tự bằng `difflib.SequenceMatcher.ratio()` (stdlib) ngưỡng ~0.85
     trên cửa sổ trượt quanh vị trí khớp thô — Levenshtein thuần mức ký tự KHÔNG đủ cho
     tiếng Việt đa-từ (thuật ngữ 5-6 từ, lệch cả từ chứ không lệch ký tự), nên token trước,
     ký tự sau;
  3. giữ trần 8 + ưu tiên: nguyên văn > tập-con token > mờ; ghi vào `ly_do`/ghi chú đường
     nào khớp để judge và người đọc report biết đây là khớp mờ.
- **Bước đầu tiên:** viết test đỏ tái hiện #13 — điều hợp đồng chứa cụm thiếu một từ so với
  `thuat_ngu` k18, khẳng định `khai_niem_lien_quan` hiện tại trả rỗng; rồi thêm nhánh
  tập-con token cho test xanh. Sau đó chạy lại 2 báo cáo, xem plan có phình (định nghĩa rác
  khớp mờ) không — nếu phình thì siết ngưỡng trước khi nghĩ tiếp.
- Ràng buộc: chọn lọc phải **tất định** (gate không LLM) để cache theo khoá sha1 còn đúng.

**Làm xong 17/08 (cùng ngày mở), TDD đúng trình tự test-đỏ-trước.** Kết quả đo:

- Bản đầu (cho bỏ token bất kỳ 1-2 vị trí) làm plan **phình +27/+29** định nghĩa trên 2 hợp
  đồng — toàn khớp oan kiểu "Chủ [tài] khoản thanh toán"→"tài khoản thanh toán". Siết còn
  **chỉ bỏ đuôi, phần còn lại ≥4 token** → delta **+1 (ThuHo) / +3 (PAYFAC)**, trong đó có
  đúng ca nhắm tới: **k18 vào plan Điều 2 PAYFAC** — điều đó vẫn viết cụm thiếu "điện tử"
  (luật sư chỉ sửa ở điều định nghĩa). Judge nhìn thấy và chấm `tuan_thu` (coi mô tả dịch
  vụ khớp khái niệm, tên gọi thiếu từ không đáng phạt) — mục tiêu "gate không che mắt
  judge" đạt; độ khó tính về tên gọi là chuyện prompt judge, chưa mở.
- Khoá cache per-điều nay băm thêm `khainiem.jsonl` + `PHIEN_BAN_GATE` (gate.py) — T28 lộ
  ra khoá cũ chỉ băm pred nên đổi cách chọn định nghĩa thì cache vẫn hit nhầm.
- **Hai bug lộ ra khi chấm lại từ đầu (đều vá + test, 876 xanh):** (1) "LLM bỏ sót" là lỗi
  NGẪU NHIÊN theo lời gọi chứ chưa bị chặn hẳn — lượt 16/08 ra 0 là may, lượt 17/08 ra
  20/2655; judge nay có **vòng retry hỏi lại đúng các id sót** (lô nhỏ), sót lần hai mới
  chịu `thieu_thong_tin`. (2) Đ23 PAYFAC hỏng lặp lại có hệ thống: model quote văn bản luật
  có **xuống dòng thật trong chuỗi JSON** — strict JSON cấm control char, cả phiếu mất
  trắng dù JSON hoàn chỉnh, temp 0 nên retry lặp y hệt; `chat_json` nay parse
  `strict=False`. Sau hai vá: **0 "bỏ sót" ở cả hai báo cáo**.
- Recall chốt 17/08: **ThuHo 1/1 · PAYFAC 1/3** — #13 là lệch phiên bản gold/input (đã phân
  xử), #194 mất ghi công vì verdict biên lật giữa hai lần chạy → tách thành **T29**.

### [ ] T29 · Recall dao động giữa các lần chạy — verdict biên `thieu_thong_tin ↔ khong_ap_dung`

Đo 17/08 khi chấm lại toàn bộ (khoá cache đổi): lượt toàn-văn PAYFAC, CU TT40-Đ8-**k7**
(nội dung hợp đồng về ví điện tử) đổi từ `thieu_thong_tin` (16/08, có ghi công #194) sang
`khong_ap_dung` (17/08, mất ghi công) → recall PAYFAC nhảy 2/3 ↔ 1/3 dù prompt, CU, văn
bản y hệt và temperature 0. Hai nhãn đều là "không kết luận được áp dụng" nhưng quy tắc
recall chỉ đếm một — với hợp đồng không có nghiệp vụ ví thì `khong_ap_dung` thật ra đúng
hơn, tức ghi công cũ thuộc diện may mắn ở ranh giới.

- Bản chất: đây là dao động của **metric trên verdict biên**, không phải bug pipeline —
  self-consistency 2+1 ổn trong một lần chạy nhưng không ổn giữa các lần chạy (Gemini
  temp 0 vẫn trôi nhẹ).
- **Bước đầu tiên:** chạy riêng lượt toàn-văn PAYFAC ~5 lần (chỉ tốn vài lời gọi judge,
  không cần chấm cả hợp đồng), đo tần suất lật của k7. Lật thường xuyên → cân nhắc: luôn
  3 phiếu cho lượt toàn-văn, hoặc báo cáo recall dạng khoảng thay vì điểm; hiếm → ghi
  nhận biên và giữ nguyên.
- Lần lật thứ 3 (18/08, pilot T30): NĐ52-Đ26k2::vi_pham synthetic lật
  `vi_pham → khong_ap_dung` giữa hai lần chấm — nặng hơn cặp
  thieu_thong_tin↔khong_ap_dung vì mất hẳn một cảnh báo vi phạm. Bộ synthetic giờ là
  giàn đo sẵn cho task này (chấm lại N lần, đếm tần suất lật từng case).
- **Đo 19/08 (giàn synthetic, `eval/compliance/t29_lat.jsonl`): judge KHÔNG phải nguồn
  dao động.** 14 case, plan dựng MỘT lần/case rồi `phan_dinh` 5 lượt độc lập: **0/14
  case lật** — 70 lượt (mỗi lượt 2-3 phiếu bên trong) ra verdict y hệt, kể cả
  NĐ52-Đ26k2::vi_pham từng lật 18/08 (nay 5×vi_pham) và các ca biên ttt↔kad. Suy ra
  3 cú lật lịch sử nằm ở **tầng trước judge**: `trich_triples` (LLM) đổi entities →
  hypernym → thành phần/thứ tự plan đổi → judge nhìn ngữ cảnh khác. (Caveat: các cú
  lật lịch sử đo giữa các phiên bản code khác nhau nên còn nhiễu; nhưng chiều "judge
  ổn định khi plan cố định" là sạch — cùng code, cùng plan, cùng prompt.) Bằng chứng
  cùng chiều: Đ13k3::thieu_thong_tin lượt này 5×khong_ap_dung ổn định, trong khi lượt
  18/08 (plan từ lần trích khác) ra thieu_thong_tin — cùng case, khác plan, khác verdict.
- **Đo tiếp 19/08 — TÌM RA THỦ PHẠM, không phải "Gemini temp-0 trôi".** Đo variance
  từng mắt xích trên 3 case biên (5 lần/case): `trich_triples` 5/5 bộ entities Y HỆT,
  hypernym y hệt, embedding query bit-identical (2 lần gọi, diff = 0.0) — nhưng plan
  case NĐ52-Đ26k2::vi_pham vẫn có 1/5 lần MẤT 3 CU Điều 22. Cơ chế (kiểm chứng bằng
  diff hybrid vs vector-only): `_bat_fts` (retrieval.py:60) **nuốt mọi exception, trả
  `[]` fail-open** — khi LanceDB Cloud blip mạng thoáng qua (đo được 2 lần ngay trong
  phiên 19/08), RRF chỉ còn nhánh vector, top-8 đổi: mất (Đ35, Đ22k2), thêm (Đ20k4-5,
  Đ32) ⇒ plan ±3 CU ⇒ ngữ cảnh judge đổi ⇒ verdict biên lật. Fail-open "vì còn vector
  gánh" hoá ra KHÔNG trung tính với ranking.
- ~~Vá `_bat_fts`~~ — **ĐÃ VÁ 19/08**: rút vòng retry 5/15/45s thành helper
  `_thu_lai_loi_mang` dùng chung cả hai nhánh hybrid; `_bat_fts` giờ retry-rồi-raise
  với lỗi MẠNG (`HttpError`/`RetryError`), chỉ lỗi khác (index hỏng, thiếu
  with_position) mới còn fail-open trả rỗng + warn. TDD, 882 test xanh. Lưu ý hệ quả:
  đường Q&A (`hybrid_search`) giờ cũng chết thật khi LanceDB mất mạng kéo dài thay vì
  âm thầm chạy nửa hệ truy hồi — chấp nhận có chủ đích.
- **Ca biên thứ 4 (20/08, chấm lại 2 báo cáo thật):** gold #35 PAYFAC mất ghi công —
  lượt toàn-văn TT18-Đ9 k2+k3 đổi `thieu_thong_tin → khong_ap_dung` sau khi prompt
  judge đổi 19/08 (cache giữ 3 thế hệ: 2 lượt cũ đều ttt). Không phải flip cùng-code,
  nhưng cùng bài học: ca biên ttt↔kad dịch chuyển theo MỌI thay đổi prompt, metric
  recall đếm một bên ranh giới nên nhảy 1/3↔0/3. Recall 20/08: ThuHo 1/1 · PAYFAC 0/3
  (#13 lệch phiên bản như cũ, #194 kad như cũ, #35 mới). Chờ chủ repo phân xử #35
  như đã phân xử #194.
- **Bước tiếp theo:** (tuỳ chọn, khi rảnh máy) chạy giàn synthetic full-pipeline N lần
  xác nhận hết lật — blip mạng hiếm nên lượt xác nhận chủ yếu đo may rủi; cơ chế đã
  kiểm chứng trực tiếp bằng diff hybrid vs vector-only.

### [ ] T30 · Dữ liệu synthetic từ CU luật — pilot 15 case đạt 7/15, lộ 3 lớp lỗi

Pilot 18/08 (báo cáo đầy đủ: `eval/compliance/synthetic_pilot.md`): sinh điều khoản hợp
đồng từ 5 CU có ngưỡng/tình thái rõ (TT18-Đ13k3/k4, TT40-Đ25k5/Đ26k1, NĐ52-Đ26k2) × 3
biến thể `tuan_thu`/`vi_pham`/`thieu_thong_tin`, **nhãn biết trước theo cách sinh** (LLM
chỉ viết văn), model sinh (chat) ≠ model chấm (reasoning). Chấm bằng pipeline thật.

Kết quả 7/15 khớp end-to-end — theo biến thể: `vi_pham` **4/5** · `tuan_thu` 3/5 ·
`thieu_thong_tin` 1/5 (số cuối KHÔNG phải recall thật của lớp im-lặng: bắt im lặng là
việc của lượt toàn-văn, pilot chỉ chấm từng điều đơn lẻ). Ba lớp lỗi lộ ra:

1. **Gate xóa oan TT40-Đ26k1 qua cổng phủ-định** — trượt cả 3 biến thể, kể cả case
   vi_pham "hạn mức ví 150.000.000 đồng/tháng". Probe 18/08: KHÔNG phải subject nghèo —
   retrieval trúng Điều 26 top-1, CU vào ứng viên rồi bị meta-CU Đ26k2 xóa vì hypernym
   generic "giao dịch thanh toán" là substring văn xuôi điều kiện loại trừ. **ĐÃ SỬA**
   (gate v3): khớp phủ-định phân bậc — bằng nguyên cụm label mới xóa, substring văn
   xuôi thì fail-open + cờ. Chấm lại: gate ✓ cả 3, tuan_thu ✓, vi_pham ✓; case im-lặng
   thành ca biên T29 mới. **Điểm sau fix: 10/14.**
2. **Judge phán `vi_pham` cho điều khoản phủ-định đúng luật** (Đ25k5::tuan_thu — "sẽ
   KHÔNG nhận tiền mặt nạp ví…" vẫn bị coi là vi phạm, can_cu chỉ chép lại điều khoản).
   Ca false-positive lớp phủ-định đầu tiên đo được.
3. **Biên `thieu_thong_tin ↔ khong_ap_dung`** thêm 2 ca — cùng lớp T29.

Bài học khâu sinh: lượt đầu 4/5 case `vi_pham` sai nhãn (model viết điều khoản *chế tài
vi phạm* thay vì điều khoản trái luật) — phải siết prompt mới ra vi phạm thật ⇒ nhãn
synthetic bắt buộc qua người duyệt, đúng nguyên tắc đã chốt.

~~**Bước đầu tiên:** chủ repo duyệt 15 case~~ — **ĐÃ DUYỆT 18/08**: 12 giữ · 2 sửa
`thieu_thong_tin → khong_ap_dung` · 1 loại; NĐ52-Đ26k2::tuan_thu phân xử GIỮ `tuan_thu`
⇒ verdict `khong_ap_dung` của judge ca đó là lỗi hệ thống. **Điểm sau duyệt: 8/14** —
6 ca lệch đều là lỗi hệ thống xác nhận (4 gate miss, 1 judge FP phủ-định, 1 judge chấm
sai NĐ52-Đ26k2::tuan_thu). Bộ case đã commit (whitelist trong `.gitignore`, sinh từ
luật công khai).

Chấm lại 18/08 với từ vựng hypernym mới (premise raw_text + 46 alias corpus, xem
worklog): **9/14, gate hit 14/15** — điểm giảm 1 hoàn toàn do NĐ52-Đ26k2::vi_pham LẬT
vi_pham→khong_ap_dung giữa hai lần chạy (lần lật thứ 3 của lớp T29, lần này ở cặp
nặng vi_pham↔khong_ap_dung); từ vựng mới không làm hỏng gate (hit 11/15→14/15).

~~Sửa prompt judge cho ca FP phủ-định~~ — **ĐÃ SỬA 19/08**, mất 2 vòng: chỉ dẫn trừu
tượng ("cam kết KHÔNG làm điều cấm là tuân thủ") KHÔNG đủ — judge vẫn ra `vi_pham` với
can_cu "*Hợp đồng cam kết không thực hiện hành vi mà luật cấm*" (lý-do-tuân-thủ dán
nhãn-vi-phạm = đảo nhãn, không phải đọc sai phủ định). Phải thêm ví dụ cụ thể cặp
đôi (cấm trả lãi ví: "không được trả lãi"→tuan_thu / "trả lãi 0,5%/năm"→vi_pham) mới
hết. Chấm lại 3 case Đ25k5: cả 3 đúng, case `vi_pham` thật không hỏng. **Điểm: 10/14.**
Lưu ý: đổi `_SYSTEM` đổi khoá cache — cache 2 báo cáo hợp đồng thật vốn đã vô hiệu.

- **Bước tiếp theo:** đo tần suất lật bằng giàn synthetic (T29), rồi mới mở rộng bộ
  sinh (CU `chi_duoc`/`cho_phep`, case toàn-văn cho lớp thieu_thong_tin).

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
