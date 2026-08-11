# EVAL-IR — Đo truy hồi theo bộ metric của bài báo SBV-LawGraph

> Tầng đo dựng ngày 2026-08-10, theo §5.2–5.3 của `docs/paper/ACIIDS2026a.pdf`
> (*SBV-LawGraph: A Hybrid RAG Approach Integrating Knowledge Graph for the State Bank of Vietnam
> Legal Documents*, ACIIDS 2026). Tài liệu này nói **cách đo**; số đo nằm ở
> `eval/results/<timestamp>.json` và bảng tóm tắt ở §5 dưới đây.

## 1. Vì sao cần tầng đo này

Trước 10/08, benchmark chỉ có `citation_accuracy` (có/không trúng `expected_doc`) và
`stale_avoidance`. Hai số đó nói được "hệ có trả đúng văn bản không" nhưng **không** nói được
trúng ở hạng mấy, bỏ sót bao nhiêu khi câu hỏi cần nhiều căn cứ, hay một thay đổi retrieval
(reranker, ngưỡng điểm) có đáng làm hay không. Bài báo báo cáo R@k / P@k / MRR@k / F2@k — muốn
đặt LexFlow cạnh nó thì phải đo cùng thước.

**Phạm vi đợt này là đo lường, không đổi retrieval.** Đường trả lời sản phẩm (`answer.py`) không
đổi một dòng nào; các cột baseline chỉ được gọi từ `eval/`.

## 2. Công thức (§5.3 của bài báo)

```
Recall@k    = |R̂k ∩ R| / |R|
Precision@k = |R̂k ∩ R| / k
MRR@k       = (1/|Q|) · Σ 1/rank_i        # rank_i = hạng kết quả đúng ĐẦU TIÊN, 0 nếu ngoài top-k
F2@k        = 5·P·R / (4·P + R)           # nghiêng về recall
```

Cài ở `eval/metrics.py`, thuần hàm, ghim bằng `tests/test_eval_metrics.py`.

Ba chỗ bài báo không nói rõ, chốt như sau:

- **Tử số recall vs precision.** Khi nhãn vàng ở cấp Điều còn chunk ở cấp Khoản, "giao của hai
  tập" không còn 1-1. Recall đếm **nhãn vàng được phủ** (mẫu số `|R|`); precision đếm **vị trí
  trong top-k có liên quan** (mẫu số `k`). Khớp chính xác thì hai cách trùng nhau, đúng định
  nghĩa gốc; khớp tiền tố thì đây là cách duy nhất không cho ra tỷ lệ > 1.
- **F2 tính từ đâu.** Báo cáo **cả hai**: `f2` tính từ hai trung bình (đọc đúng nghĩa đen công
  thức áp lên hàng của Table 3 — dùng khi so với bài báo) và `f2_macro` là trung bình F2 từng câu
  (đúng hơn khi các câu có `|R|` chênh nhau).
- **Câu không trúng gì** vẫn nằm trong mẫu số, đóng góp 0. Loại chúng ra là làm bảng đẹp lên bằng
  cách bỏ bớt câu khó.

## 3. Hai mức đo

| Mức | Khoá xếp hạng | Nhãn vàng |
|---|---|---|
| **văn bản** | `doc_id` | `relevant_docs` |
| **điều** | `"{doc_id}::Điều N"` (`metrics.khoa_dieu`) | `relevant_articles` |

Ở mức điều, các mảnh của cùng một điều (`"Điều 12 Khoản 1-3"`, `"Điều 12 Khoản 4-6"`,
`"Điều 12 (phần 2)"` — do `pipeline._split_khoan` chẻ) được gom về **một** hạng. Không gom thì
`P@k` tụt chỉ vì văn bản dài, tức là đo phép chẻ chứ không đo chất lượng truy hồi.

Khớp nhãn là **tiền tố hai chiều** với ranh giới dấu cách (`retrieval.khop_tien_to`, dùng chung
với đường truy hồi thật, không chép lại): `"Điều 3"` khớp `"Điều 3 Khoản 1-6"` nhưng **không**
khớp `"Điều 30"`. Hai chiều vì nhãn vàng có thể mịn hơn hoặc thô hơn nhãn chunk, và cả hai đều đúng.

## 4. Định dạng nhãn vàng

Định nghĩa đầy đủ ở docstring `eval/bo_cau_hoi.py`. Điểm quan trọng nhất:

> `relevant_docs` là **văn bản đủ để trả lời câu hỏi**, không phải "mọi văn bản có nhắc tới chủ đề".

Gán rộng tay làm recall trông thấp đi một cách giả tạo và precision trông cao lên. Đây là chỗ
quyết định con số có nghĩa hay không — quan trọng hơn mọi lựa chọn kỹ thuật trong tài liệu này.

Tương thích ngược: câu chỉ có `expected_doc` (36 câu hiện có) thì `relevant_docs` suy ra một phần
tử; không có `relevant_articles` thì mức "điều" bị bỏ qua với mẫu số bằng 0, không phải bằng 0 điểm.

Bộ câu hỏi mới cắm vào bằng `--bo` (lặp lại được, mỗi bộ một bảng riêng):

```bash
uv run python -u eval/run_benchmark.py --bo eval/bo_ngan_hang.jsonl
```

Bộ dựng sẵn từ dữ liệu thuvienphapluat.vn: xem §6.

## 5. Các cột so sánh

Ba cột đầu tái lập §5.2 của bài báo, ba cột sau là LexFlow:

| Cột | Nội dung | Lọc hiệu lực |
|---|---|---|
| BM25 | LanceDB FTS thuần (`retrieval.bm25_search`) | không |
| Naive RAG | dense thuần, cosine (`retrieval.baseline_vector_search`) | không |
| Advanced RAG | hợp điểm có trọng số **75% BM25 + 25% dense**, min-max từng nhánh (`retrieval.advanced_rag_search`) | không |
| LexFlow hybrid | vector + BM25 → **RRF k=60** | có (`as_of`) |
| LexFlow +graph | + mở rộng 1-hop qua Neo4j | có |
| LexFlow +router | + lớp phủ dưới-văn-bản | có |

Ba cột baseline **không** lọc hiệu lực — đúng như bài báo, ở đó không có khái niệm `as_of`. Đây
cũng là lý do so sánh giữa hai nhóm cột không thuần tuý là "ai truy hồi giỏi hơn": nhóm LexFlow
tự nguyện bỏ đi các điều đã hết hiệu lực, và bộ câu hỏi có `must_not_doc` chính là để tính điểm
cho việc bỏ đi đó.

### Kết quả — `eval/questions.jsonl`, 36 câu, đo 2026-08-10

`eval/results/20260810-145813.json`. Index: LanceDB Cloud **chưa** re-ingest (T1 còn mở), tức số
dưới đây là số của bản index cũ. Gate hồi quy xanh: `n_errors 0/36`, `stale_avoidance` 36/36 ở
mọi cột LexFlow (baseline 21/36).

| Model | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0.42 | 0.53 | 0.78 | 0.94 | 0.94 | 0.47 | 0.26 | 0.44 |
| Naive RAG | 0.56 | 0.83 | 1.00 | 1.00 | 1.00 | 0.69 | 0.42 | 0.69 |
| Advanced RAG | 0.47 | 0.56 | 0.86 | 0.94 | 0.94 | 0.51 | 0.28 | 0.46 |
| **LexFlow hybrid** | **0.72** | **0.97** | 1.00 | 1.00 | 1.00 | **0.85** | **0.49** | **0.81** |
| LexFlow +graph | 0.72 | 0.97 | 1.00 | 1.00 | 1.00 | 0.85 | 0.49 | 0.81 |
| LexFlow +router | 0.72 | 0.97 | 1.00 | 1.00 | 1.00 | 0.85 | 0.49 | 0.81 |

Mức điều: 36 câu này không có `relevant_articles` nào ⇒ bỏ qua, mẫu số 0.

**Đây là mô tả, không phải kết luận.** Mỗi câu chỉ có **một** `relevant_doc`, nên `recall@k` gần
như trùng `citation_accuracy` cũ, `P@k` tụt theo `1/k` một cách máy móc, và `R@5` bão hoà 1.00 vì
top-20 trên corpus 26 văn bản chỉ ra 4–5 `doc_id` khác nhau. Ba điều đáng ghi lại:

- **Advanced RAG (75% BM25 + 25% dense) thua Naive RAG** ở đây (F2@2 0.46 vs 0.69). Trọng số đó
  được bài báo chỉnh cho corpus 840 văn bản của họ; với 26 văn bản nhánh BM25 yếu nên đè 75% lên
  nó là hại. Bằng chứng siêu tham số của bài báo không chuyển sang corpus khác được — lý do
  T-sweep trong `docs/TASKLIST.md` đáng làm.
- **`+graph` và `+router` giống hệt `hybrid`.** Đồ thị và lớp phủ chưa đóng góp gì **đo được** ở
  mức văn bản (router chỉ đổi kết quả 1/36 câu). Muốn thấy chúng phải đo ở mức điều — mà bộ này
  không có nhãn mức đó.
- Tầng đo đã được đối chiếu tay: in top-20 thật của 3 câu, tính `recall/precision/RR` bằng tay ở
  cả 5 mốc k, khớp tuyệt đối với `eval/metrics.py`. Và `citation_accuracy` baseline cũ (36/36 ở
  `top_k=6`) nhất quán với `R@5 = 1.00` của cột Naive RAG — cùng một hàm retrieval, hai cách đo
  không mâu thuẫn.

## 6. Bộ câu hỏi TVPL — đo theo thời điểm

`data/evaluate/eval_filtered_clean.jsonl`: 251 câu hỏi-đáp luật ngân hàng lấy từ
thuvienphapluat.vn, mỗi câu có `question`, `answer`, `long_answer` và `reference_parsed` đã tách
sẵn số hiệu văn bản + số điều. `eval/chuyen_tvpl.py` chuyển nó sang định dạng ở §4.

**Bộ gốc không có trường ngày** — 251 dòng đúng 9 khoá, không khoá nào là thời điểm bài viết.
Nhưng không cần ngày đăng bài, vì mốc chặt hơn suy được từ chính corpus: **giao các khoảng hiệu
lực** của mọi văn bản mà câu đó dẫn. Đó đúng bằng khoảng thời gian nhãn vàng của TVPL còn đúng.
Trên 251 câu, giao này **không rỗng ở câu nào** — bộ dữ liệu nhất quán về thời gian, mỗi bài viết
theo đúng một thời điểm.

| Bộ | `as_of` | Nhãn vàng | Trả lời câu hỏi gì |
|---|---|---|---|
| `eval/bo_tvpl_dung_thoi.jsonl` | ngày cuối cửa sổ (2024-06-30 / 2024-07-16) | `relevant_docs` + `relevant_articles` của TVPL | truy hồi đúng luật **tại thời điểm đó** không |
| `eval/bo_tvpl_hien_nay.jsonl` | hôm nay | `relevant_docs` = văn bản kế thừa; `must_not_doc` = văn bản cũ | có **bỏ luật đã chết** và chuyển sang luật thay thế không |

76/251 câu vào được cả hai bộ. 159 câu bị loại vì dẫn văn bản ngoài corpus, 16 câu không dẫn văn
bản nào. Corpus phủ đúng 4/37 văn bản được tham chiếu: TT23-2014, ND101-2012, TT39-2014,
TT46-2014 — **cả bốn đều đã hết hiệu lực từ 2024-07**, nên tại hôm nay **0/76 câu** còn nhãn vàng
gốc đúng. Đó là lý do phải tách hai bộ: chạy bộ TVPL nguyên trạng với `as_of` = hôm nay sẽ cho
cột LexFlow recall ≈ 0 và các cột baseline điểm cao, rồi kết luận ngược hoàn toàn.

Bộ thứ hai là chỗ LexFlow tách khỏi mọi baseline của bài báo: BM25 / Naive RAG / Advanced RAG
**không có khái niệm `as_of`**, nên theo cấu trúc chúng trả cùng một kết quả ở cả hai bộ.

**Nhãn của `bo_tvpl_hien_nay.jsonl` là suy diễn, không phải nhãn người.** Nó lấy từ cạnh
`THAY_THE` trong corpus (`TT23-2014→TT17-2024`, `ND101-2012→ND52-2024`, `TT39-2014→TT40-2024`,
`TT46-2014→TT15-2024`). Thay thế ở cấp văn bản **không** đảm bảo từng điều ánh xạ 1-1: một khoản
có thể chuyển sang văn bản khác hoặc bị bỏ hẳn. Vì thế bộ này cố ý **không có
`relevant_articles`** — chỉ đo được ở mức văn bản, và mọi bảng dựng từ nó phải ghi rõ điều này.
Muốn nhãn mức điều ở luật hiện hành thì phải gán tay: `data/overlay/lop_phu.json` không có ánh xạ
điều↔điều giữa văn bản cũ và văn bản thay thế.

Hai file `bo_tvpl_*.jsonl` **sinh ra được**, không phải nhãn tay — corpus đổi thì chạy lại:

```bash
uv run python eval/chuyen_tvpl.py
uv run python -u eval/run_benchmark.py --bo eval/bo_tvpl_dung_thoi.jsonl --bo eval/bo_tvpl_hien_nay.jsonl
```

Trường `cua_so` trong mỗi dòng ghi lại cửa sổ đã suy, để đối chiếu khi corpus thay đổi. Đừng thay
nó bằng một `as_of` hằng số dùng chung: khi nạp thêm văn bản (xem dưới), cửa sổ từng câu sẽ khác
nhau và một mốc chung sẽ âm thầm làm sai nhãn của một phần bộ.

Nạp thêm văn bản sẽ mở khoá thêm câu (tính tham lam trên 251 câu): `+09/2020/TT-NHNN` → 127 câu,
`+34/2012/TT-NHNN` → 148, `+37/2016/TT-NHNN` → 166, `+88/2019/NĐ-CP` → 177 (71%). Đó là mở rộng
**corpus**, không phải tầng đo — mỗi văn bản mới phải kiểm hiệu lực lại từ đầu. Danh sách đầy đủ
44 văn bản còn thiếu, chia theo trong/ngoài phạm vi sản phẩm: `research/crawl_list_eval.txt`
(T20 trong `docs/TASKLIST.md`).

> **Hai bảng dưới đây đo TRƯỚC khi hạ trọng số nhánh thưa** (§7, cùng ngày). Chúng vẫn đúng như
> bằng chứng cho quyết định đó, nhưng **không** phải số của bản hiện tại — cột LexFlow nay cao
> hơn. Đo lại cả hai bộ với trọng số mới là việc còn nợ.

### Kết quả — `bo_tvpl_hien_nay.jsonl`, 76 câu, đo 2026-08-11

`eval/results/20260811-051219-bo_tvpl_hien_nay.json`, 76/76 câu chạy được, 0 lỗi. Index: LanceDB
Cloud chưa re-ingest (T1 còn mở). Retrieval p50 3767 ms.

| | citation_accuracy | tránh văn bản hết hiệu lực |
|---|---|---|
| baseline (dense thuần) | 66/76 | **11/76** |
| LexFlow hybrid | 64/76 | **76/76** |
| LexFlow +graph | **71/76** | **76/76** |

| Model | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0.02 | 0.09 | 0.46 | 0.94 | 0.95 | 0.06 | 0.05 | 0.07 |
| Naive RAG | 0.30 | 0.57 | 0.96 | 1.00 | 1.00 | 0.45 | 0.30 | 0.48 |
| Advanced RAG | 0.03 | 0.12 | 0.66 | 0.96 | 0.96 | 0.08 | 0.07 | 0.11 |
| **LexFlow hybrid** | **0.64** | **0.86** | 0.96 | 1.00 | 1.00 | **0.76** | **0.45** | **0.73** |
| LexFlow +graph | 0.62 | 0.86 | 0.96 | 1.00 | 1.00 | 0.76 | 0.45 | 0.73 |
| LexFlow +router | 0.62 | 0.86 | 0.96 | 1.00 | 1.00 | 0.76 | 0.45 | 0.73 |

Mức điều: bộ này cố ý không có `relevant_articles` (xem trên) ⇒ mẫu số 0, bỏ qua.

Bốn điều bảng này nói:

- **Baseline trả văn bản đã chết ở 65/76 câu** (tránh được 11/76). Các cột LexFlow: 76/76. Đây là
  toàn bộ lý do lớp lọc hiệu lực tồn tại, và là con số duy nhất trong repo đo trực tiếp nó trên
  câu hỏi do người ngoài soạn.
- **BM25 gần như không bao giờ đúng ở hạng 1** (R@1 = 0.02), và Advanced RAG — vốn đè 75% trọng
  số lên BM25 — kéo theo (0.03). Không phải BM25 yếu chung chung: câu hỏi của TVPL được viết
  **từ** văn bản cũ nên dùng đúng từ ngữ của nó, khiến khớp thưa bị **hút về** đúng văn bản đã
  chết. Đây là ca cho thấy điểm khớp từ vựng và tính đúng pháp lý có thể ngược chiều nhau.
- **Đồ thị lần đầu đóng góp đo được.** Trên 36 câu, `+graph` giống hệt `hybrid`; ở đây nó nâng
  citation_accuracy 64/76 → **71/76** (hybrid còn thấp hơn cả baseline 66/76). Cạnh `THAY_THE`
  chính là đường từ văn bản cũ sang văn bản kế thừa, mà bộ này hỏi đúng chỗ đó. Lưu ý R@1 lại
  nhích xuống 0.64 → 0.62: mở rộng 1-hop kéo thêm ứng viên vào top, lợi ở phủ và hại nhẹ ở hạng
  nhất.
- **Lớp phủ chạy thật.** 9/76 câu cho kết quả khác khi bật router (trên 36 câu là 0/36), 169 hit
  được nắn trích dẫn, 1 hit bị loại vì bãi bỏ. Nhưng citation_accuracy ON và OFF đều 71/76 — nắn
  trích dẫn đổi *nội dung* trích dẫn chứ chưa đổi *văn bản* được trả về, nên mức văn bản không
  thấy. Muốn đo nó phải có nhãn cấp điều ở luật hiện hành, tức phải gán tay.

### Kết quả — `bo_tvpl_dung_thoi.jsonl`, 75/76 câu, đo 2026-08-11

`eval/results/20260811-080300-bo_tvpl_dung_thoi.json`. Một câu rơi vì `HttpError` thoáng qua từ
LanceDB Cloud — try/except mỗi câu bắt đúng như thiết kế, **mẫu số là 75, không phải 76**.
Retrieval p50 3594 ms.

citation_accuracy: baseline 64/75 · hybrid 64/75 · **+graph 67/75**. `stale_avoidance` bằng 1.0 ở
mọi cột nhưng **rỗng nghĩa** — bộ này không có `must_not_doc` (ở `as_of` trong cửa sổ thì không
văn bản nào là lỗi thời), nên chỉ số đó mặc định đúng chứ không đo gì.

| Mức **văn bản** (75 câu) | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0.04 | 0.09 | 0.49 | 0.82 | 0.82 | 0.07 | 0.05 | 0.07 |
| Naive RAG | 0.37 | 0.62 | 0.92 | 0.92 | 0.92 | 0.50 | 0.32 | 0.52 |
| Advanced RAG | 0.07 | 0.17 | 0.53 | 0.93 | 0.95 | 0.13 | 0.09 | 0.14 |
| **LexFlow hybrid** | **0.51** | **0.76** | 0.92 | **0.99** | **0.99** | **0.64** | **0.39** | **0.64** |
| LexFlow +graph | 0.51 | 0.76 | 0.92 | 0.99 | 0.99 | 0.64 | 0.39 | 0.64 |
| LexFlow +router | 0.51 | 0.76 | 0.92 | 0.99 | 0.99 | 0.64 | 0.39 | 0.64 |

| Mức **điều** (71 câu) | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0.02 | 0.05 | 0.10 | 0.13 | 0.21 | 0.05 | 0.04 | 0.05 |
| **Naive RAG** | **0.26** | **0.44** | **0.71** | **0.80** | 0.85 | **0.36** | **0.23** | **0.37** |
| Advanced RAG | 0.05 | 0.09 | 0.17 | 0.39 | 0.73 | 0.09 | 0.06 | 0.08 |
| LexFlow hybrid | 0.15 | 0.28 | 0.57 | 0.78 | **0.90** | 0.24 | 0.15 | 0.24 |
| LexFlow +graph | 0.15 | 0.28 | 0.57 | 0.78 | 0.90 | 0.24 | 0.15 | 0.24 |
| LexFlow +router | 0.15 | 0.28 | 0.57 | 0.78 | 0.90 | 0.24 | 0.15 | 0.24 |

**Đây là bảng mức điều đầu tiên của dự án, và nó lật một kết luận.** Ở mức văn bản LexFlow hơn mọi
baseline (R@1 0.51 so với 0.37 của Naive RAG). Ở mức điều thì **ngược lại từ R@1 tới R@10**: Naive
RAG 0.26/0.44/0.71/0.80 so với LexFlow 0.15/0.28/0.57/0.78. Chỉ tới R@20 LexFlow mới vượt lên
(0.90 so với 0.85).

Đọc thẳng: **LexFlow tìm đúng *văn bản* sớm nhưng đẩy đúng *điều* lên muộn.** Trần phủ của nó cao
hơn (R@20), phần xếp hạng trong nhóm đầu thì kém hơn dense thuần. Nguyên nhân nằm ở nhánh thưa của
RRF: BM25 ở mức điều gần như vô dụng (R@1 0.02, R@20 0.21 — thua cả mức văn bản của chính nó rất
xa), nên hợp nhất với nó kéo các điều sai của **đúng văn bản** lên trên. Đây là số đo cụ thể cho
hai mục đã mở sẵn:

- **T8** (BM25 không hiểu từ ghép tiếng Việt, không index tiêu đề) — trước nay chỉ là nhận định,
  nay có số: R@20 mức điều 0.21.
- **T16** (cross-encoder rerank sau RRF) — "đúng văn bản, sai thứ tự điều" đúng là dạng lỗi mà
  reranker sửa. Bảng này là căn cứ để làm T16 trước các mục khác.

`+graph` và `+router` không đổi gì ở cả hai mức trong bộ này (khác bộ `hien_nay`, nơi `+graph` nâng
citation 64→71): ở `as_of` trong cửa sổ, không có văn bản nào bị thay thế để cạnh `THAY_THE` dẫn
qua. Router nắn 150 trích dẫn, 0 hit bị loại vì bãi bỏ, 9/75 câu khác kết quả — nhưng không đổi
citation_accuracy, cùng lý do như bộ kia.

## 7. Trọng số nhánh thưa trong RRF — 1.0 → 0.1 (11/08)

Bảng mức điều ở §6 cho thấy nhánh BM25 kéo kết quả xuống. `eval/quet_trong_so.py` kiểm điều đó
trực tiếp: **truy hồi một lượt cho mỗi câu, quét nhiều trọng số trong bộ nhớ** — RRF là phép xếp
hạng thuần trên hai danh sách đã có, nên chạy full benchmark cho từng trọng số vừa mất mỗi lần một
giờ vừa không cho thêm thông tin nào.

Kết quả trên **cả ba** bộ câu hỏi (R@1 · F2@2):

| bộ / mức | w = 1.0 (cũ) | w = 0.1 | w = 0 |
|---|---|---|---|
| `bo_tvpl_dung_thoi` · **điều** | 0.17 · 0.25 | 0.38 · 0.52 | **0.42 · 0.55** |
| `bo_tvpl_dung_thoi` · văn bản | 0.51 · 0.64 | 0.60 · 0.73 | **0.60 · 0.75** |
| `questions.jsonl` (36 câu) | 0.72 · 0.79 | 0.78 · 0.81 | **0.78 · 0.83** |
| `bo_tvpl_hien_nay` | 0.65 · 0.73 | **0.64 · 0.76** | 0.62 · 0.76 |

Đơn điệu và cùng chiều ở mọi bộ: ở trọng số cân bằng, nhánh thưa là **lỗ ròng**. Nặng nhất ở mức
điều, đúng như §6 đoán — BM25 tìm ra đúng văn bản nhưng không phân biệt nổi điều nào trong đó
(R@20 mức điều 0.21 so với 0.82 ở mức văn bản), nên hợp nhất ngang trọng số đẩy các điều **sai**
của **đúng văn bản** lên top.

**Chốt 0.1, không phải 0.** Lấy gần hết phần lợi ở mọi bộ, và ở `bo_tvpl_hien_nay` còn nhỉnh hơn
w=0. Đặt 0 sẽ là kết luận rộng hơn bằng chứng: ba bộ này đều là câu hỏi diễn đạt tự nhiên, chưa ép
loại truy vấn mà khớp từ khoá chính xác mới có giá trị (số hiệu, số tiền, tên định chế). Và T8 nói
index BM25 **hỏng**, không nói truy hồi thưa vô giá trị — đặt 0 là chôn luôn khả năng T8 cứu lại
nhánh này. Hằng số ở `app/knowledge/retrieval.py::TRONG_SO_THUA`.

Xác nhận bằng lượt chạy thật (`eval/results/20260811-095117.json`): `n_errors` 0/36,
`citation_accuracy` 36/36, **`stale_avoidance` 36/36** (gate hồi quy giữ nguyên), `conflict_recall`
6/7, và `R@1` cột LexFlow **0.72 → 0.78** — khớp đúng con số sweep dự đoán, tức phép quét trong bộ
nhớ tái lập được đường thật.

## 8. Vì sao KHÔNG so trực tiếp với bảng số của bài báo

| | Bài báo | LexFlow |
|---|---|---|
| Corpus | 840 văn bản → 9.661 điều; LKG 5.221 node / 6.019 cạnh | 26 văn bản → 425 điều / 661 chunk; 35 quan hệ |
| Bộ câu hỏi | ALQAC2025 (729 QA) + SBV Legal (100 QA) | 36 câu tự soạn (+ bộ đang soạn) |
| Embedding | `paraphrase-vietnamese-law` (fine-tune trên ViLQA/ALQAC2024) | `gemini-embedding-001`, 768 chiều |
| Rerank | ViRanker + `bge-reranker-v2-m3` (cross-encoder) | **không có** |
| Vector store | Qdrant | LanceDB |

Với 26 văn bản, `R@20` sẽ bão hoà gần 1.0 và mất khả năng phân biệt — đó là tính chất của mẫu nhỏ,
không phải bằng chứng hệ tốt. Bảng ở §5 chỉ dùng để **so các cột với nhau trên cùng corpus**.

## 9. Cảnh báo khi đọc số

- **Index có thể cũ.** `docs/TASKLIST.md` T1: LanceDB Cloud còn giữ chunk cũ của `TT66-2025 Điều 6`.
  Ghi ngày đo và trạng thái index cạnh mỗi bảng kết quả.
- **Trùng id chunk** (T2, TT23-2019): `_rrf` khoá theo `id` nên chunk trùng id bị nuốt. TT23-2019
  đã hết hiệu lực nên các cột LexFlow lọc ra, **nhưng cột BM25 / Naive RAG / Advanced RAG thì không**.
- **Cột Advanced RAG phụ thuộc tên trường điểm của LanceDB** (`_distance`, `_score`). Đổi phiên bản
  mà tên trường đổi theo thì `retrieval._lay_diem` **ném lỗi** thay vì âm thầm cho điểm 0 — nếu
  thấy `KeyError` từ đó, đây là chỗ cần sửa, không phải bỏ qua.

## 10. Chưa làm (khoảng cách còn lại so với bài báo)

Xem `docs/TASKLIST.md` (nhóm "Khoảng cách với bài báo SBV-LawGraph"): cross-encoder rerank, ngưỡng
điểm τ trên đường sản phẩm, NER câu hỏi → anchor đồ thị, hậu kiểm `HasCitations`/`EvidenceMismatch`,
sweep siêu tham số, thang đo Correctness.
