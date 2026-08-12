# LexFlow — Việc tồn đọng

> Danh sách việc **đã biết nhưng chưa làm**, để không phải phát hiện lại. Khác với
> `ROADMAP-SPRINT.md` (kế hoạch theo sprint) và `WORKLOG.md` (nhật ký đã làm).
>
> Quy ước: mỗi mục ghi **vì sao quan trọng** và **bước đầu tiên cụ thể** — đủ để người khác
> (hoặc chính mình ba tuần sau) bắt tay vào mà không phải điều tra lại. Mọi con số đều kèm
> ngày đo; số không có ngày là số chưa kiểm.
>
> Cập nhật gần nhất: 2026-08-09.

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

### [ ] T6 · 39/178 cạnh lớp phủ trỏ tới văn bản ngoài corpus

Đo 09/08 trên `data/overlay/lop_phu.json`. Router trả `None` cho chúng — **đúng thiết kế**,
nhưng đó là trần độ phủ hiện tại. Muốn nâng thì phải **mở corpus**, không phải sửa router.

### [ ] T7 · Chỉ 8/35 quan hệ có anchors mức Điều

27 quan hệ còn lại chỉ nối văn bản ↔ văn bản, không chỉ được vào điều khoản cụ thể.

### [ ] T8 · BM25 không hiểu từ ghép tiếng Việt, và không phủ tiêu đề

- Index dựng bằng tokenizer mặc định (`create_fts_index("text")`, không truyền cấu hình) —
  cắt theo khoảng trắng/ranh giới từ Unicode, **không tách từ ghép, không stemming**.
  "ví điện tử" vào index thành ba token rời.
- Bất đối xứng: text đem **embed** là `"{doc_title} — {article}: {text}"` (có tiêu đề làm ngữ
  cảnh), text đem **index BM25** chỉ là `text` trần. Hỏi "Thông tư 40 quy định gì" thì nhánh
  vector bắt được tên văn bản, nhánh BM25 không.
- ~~Chưa đo tác động.~~ **Đã đo 11/08, đo lại đầy đủ 12/08** trên 68 câu có nhãn cấp điều: BM25 ở
  **mức điều** đạt R@1 = 0.02 và **R@20 = 0.22** — gần như vô dụng, trong khi chính nó ở mức văn
  bản đạt R@20 0.84.
  Tức nó tìm được đúng văn bản nhưng không phân biệt nổi điều nào trong đó. Vì `hybrid_search` hợp
  nhất nhánh này qua RRF, nó kéo các điều **sai** của **đúng văn bản** lên top và làm LexFlow xếp
  hạng mức điều thua cả dense thuần từ R@1 tới R@10. Xem `docs/EVAL-IR.md` §6.
- **Đã giảm thiệt hại 11/08, chưa sửa nguyên nhân:** trọng số nhánh thưa hạ 1.0 → 0.1 (§7), lấy
  lại phần lớn thứ hạng — mức điều LexFlow từ thua Naive RAG ở mọi k ≤ 10 thành hơn ở mọi k. Nhưng index vẫn hỏng như mô tả trên — T8 xong mới biết nhánh thưa **đáng**
  bao nhiêu, và mới có căn cứ nâng trọng số trở lại. Bước đầu vẫn là dựng lại FTS index có tách từ
  ghép và phủ `doc_title`, rồi chạy `eval/quet_trong_so.py` lần nữa: nếu trọng số tối ưu nhích lên
  khỏi 0.1 thì index mới có giá trị, còn giữ nguyên 0.1 thì nhánh thưa không cứu được.

### [ ] T21 · Trọng số nhánh thưa có thể lệch giữa luật đã chết và luật hiện hành

- Sweep trên `eval/bo_sbv.jsonl` (29 câu, luật ĐANG hiệu lực, người ngoài soạn) cho tối ưu
  0.25 chứ không phải 0.1 — mà 0.1 được chỉnh trên ba bộ đều thiên về luật
  đã chết. Chưa đổi: 29 câu với |R| = 1 thì một câu = 3,4 điểm R@1.
- Bước đầu: cào 8 văn bản ở T20 để bộ này lên 72/100 câu, quét lại. Còn lệch thì mới đổi.

### [ ] T20 · Corpus phủ 4/37 văn bản mà bộ eval TVPL hỏi tới

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

---

## Khoảng cách với bài báo SBV-LawGraph (mở 10/08)

> Đối chiếu `docs/paper/ACIIDS2026a.pdf` với code hiện có. Tầng **đo lường** đã làm xong
> (`eval/metrics.py`, `docs/EVAL-IR.md`); bốn mục dưới đây là phần **retrieval/generation** của
> bài báo mà LexFlow chưa có. Cả bốn đều cố ý hoãn: chưa có thước đo thì không chứng minh được
> thay đổi nào là cải thiện. Làm chúng **sau** khi bộ câu hỏi gán nhãn đầy đủ về tới nơi.

### [ ] T16 · Cross-encoder rerank sau RRF

Bài báo (§4.3) xếp lại top-k bằng ViRanker + `bge-reranker-v2-m3`; `docs/RAG-DESIGN.md:116` chốt
"không reranker cross-encoder ở quy mô này" — quyết định lấy từ hồi corpus 15 văn bản.

- ~~Bước đầu: đo cột `lexflow` ở R@1 vs R@5.~~ **Đã đo 11/08** (`bo_tvpl_dung_thoi`, 71 câu có
  nhãn cấp điều) và kết quả nói nên làm: ở **mức điều**, LexFlow R@1 = 0.15 → R@20 = 0.90, tức
  đúng điều gần như luôn nằm trong top-20 nhưng **không** nằm ở đầu. Tệ hơn, dense thuần xếp hạng
  tốt hơn LexFlow từ R@1 tới R@10 (0.26/0.44/0.71/0.80 so với 0.15/0.28/0.57/0.78). "Đúng văn bản,
  sai thứ tự điều" đúng là dạng lỗi cross-encoder sửa. Xem `docs/EVAL-IR.md` §6.
- Bước tiếp: rerank top-20 của cột `lexflow` ở **mức điều**, đo lại đúng bảng đó. **Mốc phải vượt
  là R@1 mức điều 0.38** (đo 12/08, sau khi hạ trọng số) — không phải 0.26 của Naive RAG, mốc đó
  đã bị vượt bằng một hằng số. Không đạt thì reranker không đáng một lượt gọi API.
- Chủ repo đã chốt dùng **cloud/API** (Gemini hoặc rerank API), không tải model HF về máy yếu.
- ~~Cân nhắc rẻ hơn trước khi làm T16: hạ trọng số nhánh thưa trong `_rrf`.~~ **Đã làm 11/08, đo
  lại đầy đủ 12/08** — `TRONG_SO_THUA` 1.0 → 0.1, R@1 mức điều **0.15 → 0.38**, mức văn bản
  0.51 → 0.60, và trên 36 câu 0.72 → 0.78; gate stale-avoidance vẫn 36/36 (`docs/EVAL-IR.md` §7).
  Phần "đúng văn bản, sai thứ tự điều" vì thế đã ăn hết phần dễ; T16 giờ là phần khó còn lại.

### [ ] T17 · Ngưỡng điểm τ + fallback "không đủ căn cứ"

Bài báo lọc `Score(d) ≥ τ` (cosine 0.9) TRƯỚC generation, rỗng thì trả "Unknown Answer".
`answer.py` chỉ trả `_NOT_FOUND` khi retrieval **rỗng hoàn toàn** — tức là một chunk lạc đề vẫn
đủ để hệ nói tiếp.

- Bước đầu: cho `_rrf` trả kèm điểm (`_rrf_score`) mà **không** đổi thứ tự xếp hạng, rồi sweep τ
  trên bộ eval để xem ngưỡng nào cắt được câu lạc đề mà không cắt nhầm câu đúng.

### [ ] T18 · Nhận diện viện dẫn trong CÂU HỎI → anchor đồ thị

Bài báo (§4.3, SBV-RR) chạy NER trên câu hỏi để bắt "Thông tư 23/2025/TT-NHNN" làm điểm neo cho
Cypher. LexFlow **đã có parser viện dẫn đầy đủ** (`app/ontology/citation.py:121`,
`parse_citations` + `to_node_ids`) nhưng chỉ dùng lúc ingest (`classify.py`, `tac_dong.py`,
`extractor.py`) — đường hỏi đáp không gọi nó lần nào.

- Hệ quả: hỏi thẳng "Điều 12 Thông tư 40/2024 quy định gì" vẫn phải đi qua tìm kiếm ngữ nghĩa,
  trong khi câu trả lời là một phép tra khoá.
- Bước đầu: trong `answer._prepare`, gọi `parse_citations(req.query)`; có viện dẫn tường minh thì
  lấy chunk theo `lay_chunk_theo_tien_to` trước, hybrid search chỉ để bổ sung. Đúng nhánh
  "GRAPH LOOKUP trực tiếp" mà `docs/RAG-DESIGN.md:37` đã thiết kế mà chưa cài.

### [ ] T19 · Hậu kiểm câu trả lời: `HasCitations` / `EvidenceMismatch`

Bài báo (Algorithm 2, dòng 20–21) kiểm SAU khi sinh: không có trích dẫn, hoặc trích dẫn không khớp
bằng chứng ⇒ từ chối trả lời. LexFlow chỉ **dặn** trong system prompt (`answer.py:16`), không verify.

- Bước đầu: `HasCitations` là phép rẻ nhất — regex `\[.+—.+\]` trên câu trả lời, không khớp thì
  đánh dấu. Đo tỷ lệ rớt trên bộ eval trước, rồi mới quyết có chặn hay chỉ cảnh báo.

---

## Nợ kỹ thuật (parked từ review P4, 06/08)

### [ ] T11 · Ghi rõ dựng lại artefact lớp phủ cần `data/raw/vbpl/raw/`

Thư mục đó **gitignored** (22 file, 3.7 MB). Người clone repo sạch không dựng lại được
`data/overlay/lop_phu.json` và sẽ không hiểu vì sao.

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

**10/08**: bộ curate từ thuvienphapluat.vn đã về (`data/evaluate/`, 251 câu, có nhãn cấp điều),
chuyển sang định dạng eval bằng `eval/chuyen_tvpl.py` → 76 câu dùng được, xem `docs/EVAL-IR.md` §6.
Còn thiếu để đóng T14: câu hỏi cấp **khoản** (bộ TVPL chỉ tới cấp điều), và câu có **nhiều hơn
một** căn cứ — 73/76 câu hiện chỉ dẫn một văn bản, nên `|R| = 1` và recall vẫn chưa phân biệt được
các cột. Mở corpus (T20) không sửa được chỗ này; nó là tính chất của cách TVPL viết bài.

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
