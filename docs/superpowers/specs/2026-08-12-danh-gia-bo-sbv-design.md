# Thiết kế: chạy đánh giá trên bộ test SBV-LawGraph

*Brainstorm 12/08/2026, đã duyệt. Ba câu chốt với chủ repo: bộ này dùng để **đối sánh bài báo +
kiểm chứng độc lập + đo trên luật đang hiệu lực** (Correctness hoãn) · **không chạy 71 câu ngoài
corpus**, cột 100 câu suy bằng hệ số · nếu sweep hold-out cho tối ưu khác 0.1 thì **ghi nhận,
không đổi**.*

## Bài toán

`data/evaluate/svb_graph/sbv_testset_tvpl.json` — 100 câu hỏi-đáp, mỗi dòng 5 khoá
(`question_id · question · url · relevant_articles · reference_answer`), nhãn dạng
`"12/2022/tt-nhnn_3"` = số hiệu + số điều. Đây là bộ test của **chính bài báo SBV-LawGraph**
(`docs/paper/ACIIDS2026a.pdf`).

Nó khác ba bộ đang có ở ba điểm, và cả ba đều là lý do nên đo:

1. **Luật đang hiệu lực.** Bốn văn bản corpus phủ được — TT17-2024, TT18-2024, TT40-2024,
   NĐ52-2024 — đều còn hiệu lực. Mọi số IR từ trước tới nay đo trên câu hỏi về luật **đã chết**
   từ 2024-07, tức ca biên nơi lớp lọc hiệu lực toả sáng, không phải ca thường ngày của sản phẩm.
2. **Dữ liệu ngoài.** `TRONG_SO_THUA = 0.1` được chỉnh trên ba bộ tự dựng, đều thiên về luật đã
   chết và câu hỏi diễn đạt tự nhiên. Bộ này là **hold-out** thật để kiểm hằng số đó có overfit không.
3. **Nhãn cấp điều trên 100% câu.** Bộ TVPL cũ chỉ đạt 68/76 sau chuyển đổi.

**Phủ corpus, đo chứ không ước lượng:** 29/100 câu dùng được. 27 văn bản được dẫn, corpus có 4.
0 câu có cửa sổ hiệu lực rỗng, 0 nhãn trỏ vào điều mà corpus không có. 71 câu còn lại là
**negative sạch cả 71** — không câu nào dẫn lẫn một văn bản corpus có.

## Quyết định 1: không chạy 71 câu — cột "100 câu" là phép nhân

71 câu kia dẫn văn bản ngoài corpus nên không kết quả nào khớp được: `recall = precision = rr = 0`
ở **mọi** cột, chắc chắn. `metrics.tong_hop` là macro-average, nên thêm 71 số 0 vào trung bình của
29 câu:

- `recall`, `precision`, `mrr` — chia 100 thay vì 29 ⇒ nhân `29/100`
- `f2 = 5PR/(4P+R)` — nhân cả `P` và `R` với `c` cho `5c²PR / c(4P+R) = c · 5PR/(4P+R)` ⇒ cũng
  nhân `c`. `f2_macro` là macro-average nên hiển nhiên.

Tức **mọi ô của mọi cột trong bảng 100 câu = ô tương ứng của bảng 29 câu × 0.29**. Chạy 71 câu tốn
~70 phút và 71 lượt gọi API để thu về đúng con số nhân tay ra được, và vì mọi cột co cùng tỷ lệ,
nó **không phân biệt được cột nào với cột nào**.

Cột đối sánh bài báo vì thế viết bằng một câu chứ không phải một bảng: *trên đúng 100 câu của bài
báo, mọi số phải nhân 0.29 vì corpus thiếu 71/100 văn bản được hỏi — con số đó nói về **corpus**,
không nói về truy hồi.*

Thứ duy nhất chạy 71 câu mới cho là **hệ trả gì khi không có căn cứ** (abstention, T17) và mức độ
bịa khi thiếu căn cứ (Correctness). T17 chưa làm nên hệ luôn trả kết quả — số sẽ là 0/71 từ chối,
biết trước. Correctness đã hoãn. Nên 71 câu chỉ **sinh ra file**, không chạy.

## Quyết định 2: `chuyen_sbv.py` là file riêng, dùng lại tra cứu corpus của `chuyen_tvpl.py`

Định dạng vào khác, định dạng ra khác ⇒ bộ chuyển đổi riêng. Nhưng `chuan_so_hieu`, `tra_cuu`,
`cua_so`, `XA` là tra cứu corpus dùng chung — import từ `eval/chuyen_tvpl.py`, không chép lại.
Chép lại thì hai bản quy tắc chuẩn hoá số hiệu sẽ trôi khỏi nhau, và lệch chuẩn hoá là kiểu lỗi
làm phủ tụt về 0 trong khi bảng vẫn trông bình thường (đã gặp 11/08).

### Tách nhãn

`rsplit("_", 1)` — **từ phải**, vì hậu tố là số điều. `"08/2023/tt-nhnn_21"` phải ra `21`, không
phải `2`. Nhãn không tách được thì **ném lỗi**, không im lặng bỏ: nhãn hỏng là lỗi định dạng, khác
hẳn câu ngoài phạm vi, và trộn hai thứ đó vào một nhánh "bỏ qua" là cách mất dữ liệu êm nhất.

### Chỗ đang đúng nhờ may, phải ghim bằng test

Nhãn SBV **viết thường hoàn toàn** (`tt-nhnn`), mà `chuan_so_hieu` khớp regex
`^\d+/\d{4}/[A-ZĐ]+…` trên chuỗi **thô**. Với chuỗi thường regex **không khớp**, hàm rơi vào nhánh
dự phòng `s.upper()` và ra đúng — nhưng chỉ vì định dạng SBV không có đuôi slug, mà đuôi slug mới
là thứ regex sinh ra để cắt. Nó đúng do trùng hợp, nên phải có test giữ: một lần sửa regex sau này
sẽ làm phủ tụt về 0 mà không ai thấy.

### `as_of` tính, không hard-code

Dùng `cua_so` như bộ TVPL. Hiện cả bốn văn bản còn hiệu lực nên kết quả luôn là hôm nay, nhưng khi
một trong bốn bị thay thế thì `as_of` tự lùi về ngày cuối cửa sổ (`den − 1`, vì `valid_to` là mốc
mở) thay vì lặng lẽ sai.

### Kiểm mới mà `chuyen_tvpl.py` không có

Loại câu có nhãn trỏ vào **điều không tồn tại** trong corpus. Nhãn `Điều 99` của một văn bản chỉ
có 54 điều làm recall câu đó vĩnh viễn 0, và ta sẽ đọc thành "hệ dở". Hiện đo được 0 câu như vậy —
nhưng đó là 0 **đã kiểm**, khác 0 **giả định**, và nó sẽ bắt lỗi khi corpus được cào thêm.

## Hai file ra

| File | Nội dung | Ai dùng |
|---|---|---|
| `eval/bo_sbv.jsonl` | 29 câu: `query · as_of · relevant_docs · relevant_articles · expected_doc · question_id · cua_so · group` | `run_benchmark.py`, `quet_trong_so.py` |
| `eval/bo_sbv_khong_can_cu.jsonl` | 71 câu: `query · question_id · van_ban_thieu` — **không** nhãn vàng | T17 (chưa chạy) |

**Không** sinh `must_not_doc`: bộ này không có mặt lỗi thời nào để đo, nên `stale_avoidance` sẽ
bằng 1.0 và **rỗng nghĩa** — ghi rõ cạnh bảng, như đã làm với `bo_tvpl_dung_thoi`.

**Không** đưa `reference_answer` vào file eval — giữ file nhãn sạch; khi làm Correctness thì join
lại theo `question_id`.

File 71 câu **không chạy được** bằng `run_benchmark` (mọi mức IR bỏ qua nó vì nhãn rỗng —
`run_benchmark.py::_tong_hop_ir`). Docstring phải nói thẳng, không thì sẽ có người chạy rồi tưởng
hệ điểm 0.

## Bộ negative: 71 bây giờ, 157 ghi vào T17

Bộ TVPL (`data/evaluate/eval_filtered_clean.jsonl`) có **157 câu** cùng tính chất (đo 12/08: 76 đủ
trong corpus · 157 negative sạch · 2 một phần · 16 không dẫn văn bản). Tức nguồn negative thật của
dự án là 228 câu.

Đợt này chỉ sinh 71 câu, vì nó là sản phẩm phụ gần như miễn phí của bộ chuyển đổi đang viết. 157
câu kia phải sửa `chuyen_tvpl.py` — một script đang chạy đúng — để thêm file ra thứ ba, mà T17
chưa bắt đầu. Ghi con số 157 và cách lấy vào T17.

**Hai bộ khác loại, T17 đừng trộn rồi báo một tỷ lệ:** 71 câu SBV hỏi về luật **hiện hành** corpus
thiếu; 157 câu TVPL hỏi về luật **đã chết trước 2024** corpus thiếu. Bộ SBV khó hơn — chủ đề của
nó (Open API, eKYC, cho thuê tài chính) đủ gần thanh toán để truy hồi trả về văn bản trông rất hợp lý.

## Kiểm thử — `tests/test_chuyen_sbv.py`

- Tách từ phải: `"…tt-nhnn_21"` → `21`, không phải `2`.
- Nhãn viết thường khớp được `so_hieu` trong corpus (ghim nhánh dự phòng của `chuan_so_hieu`).
- Nhãn không tách được ⇒ **ném**, không bỏ qua.
- Câu dẫn văn bản ngoài corpus ⇒ vào file 71, không vào file 29.
- Nhãn trỏ vào điều không tồn tại ⇒ loại, đếm đúng lý do.
- Nhiều điều cùng một văn bản ⇒ `relevant_articles` đủ, `relevant_docs` một phần tử.
- `as_of` = hôm nay khi mọi văn bản còn hiệu lực; = `den − 1` khi cửa sổ đóng.
- Không sinh `must_not_doc`.
- Bất biến: **29 + 71 = 100**, không câu nào vào cả hai file, không câu nào biến mất.

## Chạy & báo cáo

1. `uv run python eval/chuyen_sbv.py`
2. **Sweep hold-out trước** — `uv run python eval/quet_trong_so.py --bo eval/bo_sbv.jsonl`. Vài
   phút, không tốn lượt benchmark nào. Đây là phần trả lời "0.1 có overfit không". Luật đã chốt:
   **ghi nhận, không đổi** — 29 câu với `|R| = 1` thì một câu = 3,4 điểm R@1, quá mỏng để dịch một
   hằng số sản phẩm. Nếu lệch thì mở mục TASKLIST, quyết lại sau khi cào thêm (72/100 câu).
3. `uv run python -u eval/run_benchmark.py --bo eval/bo_sbv.jsonl` — ~35 phút, chạy tách phiên
   bằng `Start-Process` (chạy trực tiếp trong terminal bị kill khi đổi phiên, đã mất hai lượt
   ngày 11/08 vì việc này).
4. `docs/EVAL-IR.md` §11: bảng 29 câu · chứng minh hệ số 0.29 · cảnh báo mẫu số nhỏ ·
   `stale_avoidance` rỗng nghĩa · kết quả sweep hold-out.
5. README một dòng · `docs/TASKLIST.md` (T17 nhận bộ negative + con số 157; T20 thêm 8 văn bản đưa
   phủ 29 → 72/100) · `docs/WORKLOG.md`.

## Kiểm chứng

1. `uv run ruff check .` sạch · `uv run pytest -q` xanh.
2. Đối chiếu tay một câu đã biết đáp án (q4 → `TT40-2024::Điều 18`): in top-20, tính `R@1` bằng
   tay, so với số script in ra. Metric sai lặng lẽ là kiểu lỗi khó thấy nhất ở tầng này.
3. Gate hồi quy không đổi: `eval/questions.jsonl` vẫn `stale_avoidance` 36/36.

## Rủi ro đã biết

- **Mẫu 29 câu, và `|R|` gần như luôn bằng 1** (đo 12/08: mức điều 26 câu một điều · 2 câu hai
  điều · 1 câu ba điều; mức văn bản **29/29 câu đúng một văn bản**). Ở mức văn bản `R@k` vì thế
  suy biến thành "đúng văn bản có nằm trong top-k không" và **không phân biệt được gì hơn
  `citation_accuracy` đã có**; số đáng đọc của bộ này nằm ở **mức điều**. `R@20` sẽ bão hoà. Đây
  là bộ kiểm chứng và đối sánh, **không** phải bộ để rút kết luận tiêu đề.
- **Index có thể cũ** (T1: LanceDB Cloud còn chunk cũ của `TT66-2025 Điều 6`) — ghi ngày đo cạnh bảng.
- **`HttpError` thoáng qua từ LanceDB Cloud** đã làm rơi 7/152 câu ngày 12/08. Với 29 câu, mỗi câu
  rơi là 3,4 điểm — nếu lượt chạy rơi quá 2 câu thì chạy lại thay vì báo số trên mẫu số vá víu.
