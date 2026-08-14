# Thiết kế: nhập 23 văn bản bộ SBV vào corpus phục vụ (29 → tối đa 100 câu)

*Brainstorm 14/08/2026. Mục tiêu: bộ test SBV-LawGraph chạy được nhiều hơn 29/100 câu bằng cách
nạp 23 văn bản nó dẫn mà corpus chưa có. Chạm **corpus phục vụ** (production) nên đi spec→plan.*

## Bài toán

Bộ SBV (`data/evaluate/svb_graph/sbv_testset_tvpl.json`, 100 câu) hiện chỉ chạy 29 câu — 71 câu còn
lại dẫn 23 văn bản corpus chưa có (`eval/bo_sbv_khong_can_cu.jsonl`, tập `van_ban_thieu`). **70/71
câu chỉ thiếu đúng 1 văn bản** nên mỗi văn bản mở khoá độc lập. 23 văn bản đã **cào sẵn** về staging
`data/raw/vbpl/corpus/*.json` (dạng `CorpusDocument`). Việc còn lại **không phải cào, không phải
embed** (ingest tăng dần chỉ embed 23 văn bản mới — đo ở `ingest_one_doc` docstring; 661 chunk cũ
không đụng) mà là **gộp + curate + nhập** vào `data/corpus.real.json`, rồi chạy lại `chuyen_sbv.py`.

Ba dữ kiện đo 14/08 khiến task này không trivial:

1. **doc_id đụng corpus: 0.** 23 doc_id staging (`ND94-2025`, `TT64-2024`…) đều đúng quy ước và không
   trùng 26 văn bản đang có — thêm sạch, không đụng chunk/quan hệ hiện tại.
2. **Hiệu lực phải curate.** Trong 20 file khớp được: 8 "còn hiệu lực", 9 "hết hiệu lực một phần",
   **3 "hết hiệu lực toàn bộ"** — `TT32-2024` (valid_to 2026-02-15), `TT37-2024` (2025-10-15),
   `TT45-2024` (2025-08-14). Nếu nạp mà không giữ `valid_to`, lớp lọc hiệu lực sẽ coi văn bản đã chết
   là còn sống — hỏng đúng điểm mạnh của sản phẩm.
3. **3 file lệch chuẩn hoá số hiệu**, không khớp bằng so sánh chuỗi thẳng: `94/2025/NĐ-CP`,
   `26/2025/NĐ-CP` (NĐ vs ND), `21/2017/TT-NHNN`. Đúng bẫy đã ghi ở memory "grep văn bản pháp lý".

Ngoài ra **article schema staging khác corpus**: staging có `chapter/section/char_start/char_end`,
corpus có `valid_from/valid_to` cấp điều. Gộp phải chuyển đổi, không bê nguyên.

## Quyết định 1: gộp bằng script nhỏ, người duyệt DIFF trước khi nhập

Không có script gộp văn bản MỚI vào corpus (`enrich_corpus_from_vbpl.py` chỉ THÊM thuộc tính cho văn
bản ĐÃ có). Viết `scripts/gop_corpus_tu_staging.py`: đọc N file staging, lấy **subset field corpus**
(`doc_id, title, doc_type, source, valid_from, valid_to, so_hieu, articles`), chuyển article schema
(giữ `article/text/superseded`, bỏ `chapter/section/char_*`, KHÔNG bịa `valid_from/valid_to` cấp
điều), rồi APPEND vào `documents` của `corpus.real.json`. Không đụng `relationships`.

Vì sao script chứ không tay: 23 văn bản × ~28 điều = ~575 điều, chép tay là nguồn lỗi. Nhưng **script
chỉ dựng bản nháp** — maker-checker duyệt `git diff data/corpus.real.json` trước khi nhập, đúng câu
chuyện cho ngân hàng. Script phải **idempotent** (chạy lại không nhân đôi) và **từ chối doc_id đã có**
(guard trùng).

## Quyết định 2: `valid_to` lấy từ staging, KHÔNG tự suy; 9 văn bản "một phần" nạp ở mức doc

`valid_to` cho 3 văn bản "hết hiệu lực toàn bộ" đã có sẵn trong staging (`tinh_trang_hieu_luc` +
`valid_to`) — script chép thẳng, không tính tay. 9 văn bản "hết hiệu lực một phần": staging để
`valid_to` trống (đúng — chỉ vài điều/khoản chết, không phải cả văn bản). Nạp ở **mức doc là còn
hiệu lực**, KHÔNG curate `valid_to` cấp điều trong đợt này — đó là việc lớn riêng (như lớp phủ
dưới-văn-bản), và với bộ SBV thì `chuyen_sbv.py` tự tính `cua_so` theo doc-level, đủ để câu chạy.
Ghi rõ giới hạn này cạnh bảng kết quả, không giả vờ đã curate cấp điều.

**Trigger curate cấp điều (eval-driven, per-doc):** chỉ curate `valid_to` cấp điều cho một văn bản
cụ thể khi có **một câu trả sai truy được về "phục vụ một điều/khoản đã bãi bỏ như đang hiệu lực"**
(kiểu nghi vấn qid=5). Đo trước → câu nào sai vì điều chết mới curate điều đó, không quét cả 9 văn
bản. Phần lớn điều bị bãi bỏ không có câu hỏi chạm tới nên curate trước = việc thừa (YAGNI); và lớp
phủ dưới-văn-bản (`chu_thich_ket_qua`/`lop_phu`) đã chú thích động một phần hiệu lực cấp điều lúc
retrieval, không nhất thiết phải bơm hết vào `valid_to` tĩnh.

## Quyết định 3: 3 văn bản lệch chuẩn hoá — sửa map, không sửa tên tay

Gộp map staging→target theo `chuan_so_hieu` (đã có ở `eval/chuyen_tvpl.py`) chứ không so chuỗi thẳng,
để `94/2025/NĐ-CP` khớp bất kể NĐ/ND. KHÔNG sửa tay `so_hieu` trong file staging (sửa tay là nguồn
lệch mới). `21/2017` phải kiểm vì sao lệch (tên file/so_hieu) — dump ra xem, đừng đoán.

## Quyết định 4: Neo4j — nạp node mồ côi trước, edge curate theo bằng chứng

Thứ tự: **nạp node → đo → curate edge nếu số liệu cần**, không curate edge mù trước.

23 văn bản mới lên Neo4j thành node mồ côi (không cạnh). `graph_augmented_search` làm 1-hop: node
không cạnh thì không kéo thêm neighbor, nhưng vẫn nằm trong retrieval nền (LanceDB) nên câu hỏi về
chúng vẫn trả lời được ngay. Graph augmentation chỉ **cộng thêm**, không bớt → node mồ côi không hại
kết quả hiện có.

**Bằng chứng hoãn edge gần như miễn phí cho bộ SBV:** §11 `EVAL-IR.md` cho thấy `LexFlow hybrid` ==
`+graph` == `+router` trên bộ SBV (doc 0.90, điều 0.69 — giống hệt). Graph đã không nhích số SBV nào,
nên hoãn edge mất 0 điểm đo được trên chính bộ này. Curate quan hệ THAY_THE/SUA_DOI chỉ đáng khi một
câu (sản phẩm hoặc eval) sai vì thiếu quan hệ bắc cầu — lúc đó mở task riêng, per-doc.

## Rủi ро phải biết trước

- **Chạm mọi câu trả lời sản phẩm, không chỉ eval.** Thêm 23 văn bản đổi thứ retrieval trả về cho
  MỌI truy vấn. Phải chạy lại toàn bộ eval hiện có (36 câu, 76 TVPL, 29 SBV) và khẳng định không tụt
  — regression gate, không chỉ đo câu mới.
- **`stale_avoidance` có thể đổi**: 3 văn bản hết hiệu lực toàn bộ vào corpus có thể trở thành
  `must_not_doc` mới cho vài câu — kiểm.
- **Gần như nhân đôi corpus** (26→49, 661→~1236 chunk): R@20 vốn bão hoà nay có thêm ứng viên, một
  số chỉ số mức văn bản có thể động. Đo lại cả ba bộ cũ, không chỉ SBV.
- **Nhân đôi corpus = nhân đôi bề mặt lỗi trích dẫn**: web dựng link theo doc_id; kiểm 23 doc_id mới
  đều tra được ở bảng khoá (`tach_khoa`, ca T10/T15).

## Nghiệm thu

1. `scripts/gop_corpus_tu_staging.py` chạy → `git diff` cho đúng 23 văn bản mới, 0 văn bản cũ đổi.
2. `uv run pytest -q` + `uv run ruff check .` xanh (gồm test mới cho script gộp).
3. `uv run python -m app.ingestion data/corpus.real.json` — log cho thấy **chỉ 23 văn bản embed**,
   26 cũ "không đổi — bỏ qua embedding".
4. `uv run python eval/chuyen_sbv.py` — `bo_sbv.jsonl` tăng từ 29 lên (kỳ vọng ~100 nếu đủ 23; ghi
   số thật, không giả định).
5. Chạy lại benchmark + judge cả bốn bộ; khẳng định 36/76/29 cũ KHÔNG tụt, SBV mới có số.
6. 3 văn bản hết hiệu lực toàn bộ: kiểm `valid_to` vào corpus đúng, và câu hỏi về chúng lọc hiệu lực
   đúng (không trả lời như đang sống tại as_of sau ngày chết).
