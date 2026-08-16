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

**Đo lại 2026-08-15 sau khi nạp 23 văn bản (index mới, 49 doc)** — `eval/results/20260815-101504.json`,
gate hồi quy sau khi mở rộng corpus. LexFlow **không đổi**: `n_errors 0/36`, `citation_accuracy`
36/36 và `stale_avoidance` 36/36 ở cả ba cột hybrid/+graph/+router — y hệt trước khi nạp. IR mức
văn bản dịch lên (LexFlow hybrid R@1 0.72 → **0.83**, MRR@2 0.85 → **0.90**) vì index đã re-ingest
sạch (T1 đóng) và corpus có thêm ứng viên; đây là đo lại tốt hơn, không phải hồi quy. Cột baseline
(dense thuần, không lọc hiệu lực) tụt `citation_accuracy` 36 → 34/36 vì thấy thêm 23 văn bản nên
2 câu bị doc mới chen — đúng bản chất cột đối chứng, không chạm đường sản phẩm.

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

Số dưới đây là **lượt đo 12/08, sau khi hạ trọng số nhánh thưa xuống 0.1** (§7). Bảng của lượt
11/08 (trọng số 1.0) không giữ lại ở đây — nó nằm trong §7 dưới dạng đúng chức năng của nó: bằng
chứng cho quyết định hạ trọng số. File kết quả cũ vẫn còn trong `eval/results/` nếu cần đối chiếu.

**Mẫu số hai lượt khác nhau** (75/76 → 71/76 và 76/76 → 74/76) vì `HttpError` thoáng qua từ
LanceDB Cloud rơi vào các câu khác nhau. Ba cột baseline **không phụ thuộc trọng số**, nên độ lệch
của chúng giữa hai lượt đo đúng bằng nhiễu do đổi mẫu: ≤ 0.02 ở mọi ô (Naive RAG ở `hien_nay`
khớp từng chữ số). Chênh lệch của cột LexFlow lớn hơn mức đó nhiều lần, nên nó là của trọng số,
không phải của mẫu.

### Kết quả — `bo_tvpl_hien_nay.jsonl`, 74/76 câu, đo 2026-08-12

`eval/results/20260812-054048-bo_tvpl_hien_nay.json`. Hai câu rơi vì `HttpError` từ LanceDB Cloud
— try/except mỗi câu bắt đúng như thiết kế, **mẫu số là 74, không phải 76**. Index: LanceDB Cloud
chưa re-ingest (T1 còn mở). Retrieval p50 3535 ms.

| | citation_accuracy | tránh văn bản hết hiệu lực |
|---|---|---|
| baseline (dense thuần) | 64/74 | **11/74** |
| LexFlow hybrid | 69/74 | **74/74** |
| LexFlow +graph | **74/74** | **74/74** |

| Model | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0.02 | 0.09 | 0.45 | 0.93 | 0.93 | 0.06 | 0.05 | 0.07 |
| Naive RAG | 0.30 | 0.57 | 0.96 | 1.00 | 1.00 | 0.45 | 0.30 | 0.48 |
| Advanced RAG | 0.03 | 0.13 | 0.66 | 0.96 | 0.96 | 0.08 | 0.07 | 0.11 |
| **LexFlow hybrid** | **0.63** | **0.91** | **0.99** | 1.00 | 1.00 | **0.78** | **0.47** | **0.77** |
| LexFlow +graph | 0.63 | 0.91 | 0.99 | 1.00 | 1.00 | 0.78 | 0.47 | 0.77 |
| LexFlow +router | 0.63 | 0.91 | 0.99 | 1.00 | 1.00 | 0.78 | 0.47 | 0.77 |

Mức điều: bộ này cố ý không có `relevant_articles` (xem trên) ⇒ mẫu số 0, bỏ qua.

Bốn điều bảng này nói:

- **Baseline trả văn bản đã chết ở 63/74 câu** (tránh được 11/74). Các cột LexFlow: 74/74. Đây là
  toàn bộ lý do lớp lọc hiệu lực tồn tại, và là con số duy nhất trong repo đo trực tiếp nó trên
  câu hỏi do người ngoài soạn.
- **BM25 gần như không bao giờ đúng ở hạng 1** (R@1 = 0.02), và Advanced RAG — vốn đè 75% trọng
  số lên BM25 — kéo theo (0.03). Không phải BM25 yếu chung chung: câu hỏi của TVPL được viết
  **từ** văn bản cũ nên dùng đúng từ ngữ của nó, khiến khớp thưa bị **hút về** đúng văn bản đã
  chết. Đây là ca cho thấy điểm khớp từ vựng và tính đúng pháp lý có thể ngược chiều nhau, và là
  lý do trực tiếp khiến trọng số nhánh thưa bị hạ ở §7.
- **Đồ thị đóng góp đo được, và giờ là trần.** Trên 36 câu, `+graph` giống hệt `hybrid`; ở đây nó
  nâng citation_accuracy 69/74 → **74/74**, tức không còn câu nào sai. Cạnh `THAY_THE` chính là
  đường từ văn bản cũ sang văn bản kế thừa, mà bộ này hỏi đúng chỗ đó. Ở lượt trọng số cũ, `+graph`
  làm R@1 **tụt** 0.64 → 0.62 (mở rộng 1-hop kéo thêm ứng viên vào top); với trọng số 0.1 nó bằng
  đúng `hybrid` ở mọi k — xếp hạng đã đủ chắc để chịu được ứng viên thêm vào.
- **Lớp phủ chạy thật.** 12/74 câu cho kết quả khác khi bật router (trên 36 câu là 0/36), 128 hit
  được nắn trích dẫn, 5 hit bị loại vì bãi bỏ. Nhưng citation_accuracy ON và OFF đều 74/74 — nắn
  trích dẫn đổi *nội dung* trích dẫn chứ chưa đổi *văn bản* được trả về, nên mức văn bản không
  thấy. Muốn đo nó phải có nhãn cấp điều ở luật hiện hành, tức phải gán tay.

### Kết quả — `bo_tvpl_dung_thoi.jsonl`, 71/76 câu, đo 2026-08-12

`eval/results/20260812-042253-bo_tvpl_dung_thoi.json`. Năm câu rơi vì `HttpError` từ LanceDB Cloud
(cùng nguyên nhân như bộ kia, khác câu), **mẫu số là 71**. Retrieval p50 4020 ms.

citation_accuracy: baseline 62/71 · **hybrid 65/71 · +graph 65/71**. `stale_avoidance` bằng 1.0 ở
mọi cột nhưng **rỗng nghĩa** — bộ này không có `must_not_doc` (ở `as_of` trong cửa sổ thì không
văn bản nào là lỗi thời), nên chỉ số đó mặc định đúng chứ không đo gì.

| Mức **văn bản** (71 câu) | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0.06 | 0.11 | 0.50 | 0.84 | 0.84 | 0.08 | 0.06 | 0.09 |
| Naive RAG | 0.37 | 0.63 | 0.92 | 0.92 | 0.92 | 0.51 | 0.32 | 0.53 |
| Advanced RAG | 0.09 | 0.18 | 0.54 | 0.92 | 0.94 | 0.14 | 0.09 | 0.15 |
| **LexFlow hybrid** | **0.60** | **0.86** | **0.97** | **0.97** | **0.97** | **0.74** | **0.45** | **0.73** |
| LexFlow +graph | 0.60 | 0.86 | 0.97 | 0.97 | 0.97 | 0.74 | 0.45 | 0.73 |
| LexFlow +router | 0.60 | 0.86 | 0.97 | 0.97 | 0.97 | 0.74 | 0.45 | 0.73 |

| Mức **điều** (68 câu) | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0.02 | 0.07 | 0.10 | 0.13 | 0.22 | 0.06 | 0.04 | 0.06 |
| Naive RAG | 0.26 | 0.44 | 0.73 | 0.82 | 0.85 | 0.36 | 0.23 | 0.37 |
| Advanced RAG | 0.07 | 0.10 | 0.18 | 0.39 | 0.75 | 0.10 | 0.06 | 0.08 |
| **LexFlow hybrid** | **0.38** | **0.62** | **0.82** | **0.91** | **0.93** | **0.52** | **0.34** | **0.53** |
| LexFlow +graph | 0.38 | 0.62 | 0.82 | 0.91 | 0.93 | 0.52 | 0.34 | 0.53 |
| LexFlow +router | 0.38 | 0.62 | 0.82 | 0.91 | 0.93 | 0.52 | 0.34 | 0.53 |

**Bảng mức điều là bảng đáng đọc nhất ở đây, vì nó đã đảo chiều hai lần.** Lượt 11/08 (trọng số
1.0) cho Naive RAG hơn LexFlow từ R@1 tới R@10 — LexFlow tìm đúng *văn bản* sớm nhưng đẩy đúng
*điều* lên muộn, do nhánh BM25 ở mức điều gần như vô dụng (R@20 0.22, so với 0.84 ở mức văn bản
của chính nó) nên hợp nhất ngang trọng số kéo các điều **sai** của **đúng văn bản** lên top. Hạ
trọng số nhánh thưa xuống 0.1 (§7) xoá hẳn khoảng cách đó: LexFlow nay hơn Naive RAG ở **mọi** k
(0.38/0.62/0.82/0.91/0.93 so với 0.26/0.44/0.73/0.82/0.85), trong khi ba cột baseline đứng yên.

Hai mục đã mở sẵn vẫn giữ nguyên căn cứ, chỉ đổi mốc:

- **T8** (BM25 không hiểu từ ghép tiếng Việt, không index tiêu đề) — R@20 mức điều **0.22**. Chừng
  nào con số đó chưa lên, trọng số 0.1 vẫn là mức đúng; sửa được index thì chạy lại
  `eval/quet_trong_so.py`, trọng số tối ưu nhích lên là bằng chứng index mới có giá trị.
- **T16** (cross-encoder rerank sau RRF) — vẫn là dạng lỗi mà reranker sửa, nhưng **mốc phải vượt
  giờ là R@1 mức điều 0.38, không còn là 0.15**. Phần dễ ăn đã lấy bằng một hằng số.

`+graph` và `+router` không đổi gì ở cả hai mức trong bộ này (khác bộ `hien_nay`, nơi `+graph` nâng
citation 69→74): ở `as_of` trong cửa sổ, không có văn bản nào bị thay thế để cạnh `THAY_THE` dẫn
qua. Router nắn 100 trích dẫn, 0 hit bị loại vì bãi bỏ, 20/71 câu khác kết quả — nhưng không đổi
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

Hai bộ TVPL chạy lại đầy đủ ngày 12/08 (§6) khớp nốt phần còn lại của cột `w = 0.1`, dù mẫu số
lệch vài câu vì lỗi mạng:

| dự đoán của sweep (R@1 · F2@2) | đo thật 12/08 |
|---|---|
| `dung_thoi` · điều — 0.38 · 0.52 | **0.38 · 0.53** |
| `dung_thoi` · văn bản — 0.60 · 0.73 | **0.60 · 0.73** |
| `hien_nay` — 0.64 · 0.76 | **0.63 · 0.77** |

Nghĩa là `quet_trong_so.py` dùng được như công cụ quyết định: quét trong bộ nhớ vài phút thay cho
ba giờ chạy benchmark, và chưa lần nào lệch quá 0.01 so với đường thật. Khi T8 sửa xong index BM25,
quét lại trước rồi mới chạy full.

## 8. Vì sao KHÔNG so trực tiếp với bảng số của bài báo

| | Bài báo | LexFlow |
|---|---|---|
| Corpus | 840 văn bản → 9.661 điều; LKG 5.221 node / 6.019 cạnh | 49 văn bản → 1.041 điều / 1.496 chunk; 35 quan hệ |
| Bộ câu hỏi | ALQAC2025 (729 QA) + SBV Legal (100 QA) | 36 câu tự soạn · 76 câu TVPL · 100/100 câu SBV Legal của chính bài báo |
| Embedding | `paraphrase-vietnamese-law` (fine-tune trên ViLQA/ALQAC2024) | `gemini-embedding-001`, 768 chiều |
| Rerank | ViRanker + `bge-reranker-v2-m3` (cross-encoder) | **không có** |
| Vector store | Qdrant | LanceDB |

Với 49 văn bản, `R@20` vẫn bão hoà gần 1.0 và mất khả năng phân biệt — đó là tính chất của mẫu nhỏ,
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

## 11. Bộ test của bài báo SBV-LawGraph — đo trên luật đang hiệu lực

`data/evaluate/svb_graph/sbv_testset_tvpl.json`: 100 câu hỏi-đáp, nhãn dạng
`"12/2022/tt-nhnn_3"` = số hiệu + số điều, tức **nhãn cấp điều trên 100% câu**. Đây là bộ test
của chính bài báo SBV-LawGraph (`docs/paper/ACIIDS2026a.pdf`). `eval/chuyen_sbv.py` chuyển nó
sang định dạng ở §4, dùng lại các hàm tra cứu corpus của `eval/chuyen_tvpl.py` (`chuan_so_hieu`,
`tra_cuu`, `cua_so`) thay vì chép lại — chép lại thì hai bản quy tắc chuẩn hoá số hiệu sẽ trôi
khỏi nhau, và lệch chuẩn hoá là kiểu lỗi làm phủ tụt về 0 trong khi bảng vẫn trông bình thường.

File nguồn **không có trong repo**: xin trực tiếp từ tác giả bài báo, việc phát tán lại không phải
quyết định của repo này. `data/evaluate/svb_graph/README.md` (có version) giữ checksum SHA-256,
kích thước, số bản ghi và đường dẫn cần đặt file vào — kiểm hash trước khi chạy lại
`chuyen_sbv.py`, vì hash khác nghĩa là dữ liệu khác và split 29/71/100 dưới đây sẽ không tái lập.

Khác ba bộ trước ở ba điểm: (1) hỏi về luật **đang hiệu lực** — mọi văn bản được dẫn đều còn hiệu
lực, trong khi phần lớn số IR trước nay đo trên luật đã chết từ 2024-07, tức ca biên nơi lớp lọc
hiệu lực toả sáng, không phải ca thường ngày của sản phẩm; (2) là **dữ liệu ngoài** —
`TRONG_SO_THUA = 0.1` được chỉnh trên ba bộ tự dựng, đều thiên về luật đã chết, nên bộ này là
hold-out thật để kiểm hằng số đó có overfit không; (3) nhãn cấp điều đầy đủ trên 100% câu, trong
khi bộ TVPL chỉ đạt 68/76 sau chuyển đổi.

**Phủ corpus (cập nhật 14/08):** 100/100 câu dùng được. 27 văn bản được dẫn, corpus có đủ cả 27 sau
khi nạp 23 văn bản SBV (T113). 0 câu có cửa sổ hiệu lực rỗng, 0 nhãn trỏ vào điều corpus không có.
`chuyen_sbv.py` chạy lại tự đưa bộ từ 29 → 100 câu; `eval/bo_sbv_khong_can_cu.jsonl` (trước là 71
câu negative vì thiếu văn bản) nay rỗng — không còn câu nào bị chặn vì corpus thiếu.

Lịch sử: trước 14/08 chỉ 29/100 câu chạy được (corpus khi đó phủ 4/27 văn bản), 71 câu kia là
negative sạch, và hai bảng IR khi ấy phải nhân 0.29 khi đặt cạnh Table 3 của bài báo. Nạp 23 văn
bản đã xoá hệ số đó: từ đợt 15/08 hai bảng đo trên đúng 100 câu như đề bài báo cho. Ở §8, cảnh báo
về **corpus** (`R@20` bão hoà trên mẫu nhỏ) và **rerank** (LexFlow không có) vẫn nguyên giá trị.

### Bộ có trùng câu hỏi — không khử

`eval/bo_sbv.jsonl` có **100 dòng nhưng chỉ 94 câu hỏi khác nhau** (6 dòng trùng). Chúng vì thế bị
**đếm nhiều lần** trong mọi macro-average của bảng dưới.

Cố ý **không khử trùng**: bộ này tồn tại để đối sánh với bài báo, mà bài báo đo trên đúng 100 dòng
như đề cho — khử trùng sẽ làm bộ của LexFlow lệch khỏi 100 dòng đó. Giữ nguyên, chỉ ghi rõ ở đây.

### Kết quả — `bo_sbv.jsonl`, 100/100 câu, đo 2026-08-15

`eval/results/20260815-021257-bo_sbv.json` (gitignored — nhúng query của bài báo). Index: LanceDB
Cloud đã re-ingest đủ 23 văn bản (1496 chunk / 49 doc), FTS phủ chunk mới. Retrieval p50 3074 ms,
0/100 lỗi.

| | citation accuracy | tránh văn bản hết hiệu lực | phát hiện mâu thuẫn |
|---|---|---|---|
| baseline (dense thuần) | 99/100 | 100/100 | — |
| LexFlow hybrid | 99/100 | 100/100 | 0/0 |
| LexFlow +graph | 99/100 | 100/100 | 0/0 |

Router (lớp phủ dưới-văn-bản, áp trên cột +graph): citation accuracy và tránh văn bản hết hiệu
lực giữ nguyên 99/100 và 100/100 cả OFF lẫn ON. 5/100 câu trả về docs khác nhau khi bật router,
1 hit bị loại vì bãi bỏ, 65 hit được nắn trích dẫn (tổng trên 100 câu).

| Mức **văn bản** (100 câu có nhãn) | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0.69 | 0.78 | 0.91 | 0.98 | 0.99 | 0.74 | 0.39 | 0.65 |
| Naive RAG | 0.89 | 0.95 | 0.99 | 0.99 | 0.99 | 0.93 | 0.48 | 0.80 |
| Advanced RAG | 0.73 | 0.83 | 0.96 | 1.00 | 1.00 | 0.79 | 0.42 | 0.70 |
| **LexFlow hybrid** | **0.94** | **0.97** | 0.99 | 0.99 | 0.99 | **0.96** | **0.49** | **0.81** |
| LexFlow +graph | 0.94 | 0.97 | 0.99 | 0.99 | 0.99 | 0.96 | 0.49 | 0.81 |
| LexFlow +router | 0.94 | 0.97 | 0.99 | 0.99 | 0.99 | 0.96 | 0.49 | 0.81 |

| Mức **điều** (100 câu có nhãn) | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0.50 | 0.55 | 0.74 | 0.87 | 0.94 | 0.55 | 0.29 | 0.47 |
| Naive RAG | 0.73 | 0.88 | 0.96 | 0.98 | 0.99 | 0.83 | 0.47 | 0.74 |
| Advanced RAG | 0.56 | 0.72 | 0.87 | 0.94 | 0.98 | 0.67 | 0.38 | 0.61 |
| **LexFlow hybrid** | **0.79** | **0.89** | 0.95 | 0.98 | 0.99 | **0.87** | **0.47** | **0.76** |
| LexFlow +graph | 0.79 | 0.89 | 0.95 | 0.98 | 0.99 | 0.87 | 0.47 | 0.76 |
| LexFlow +router | 0.79 | 0.89 | 0.95 | 0.98 | 0.99 | 0.87 | 0.47 | 0.76 |

**Đọc bảng này phải nhớ bốn điều:**

- **99/100 câu chỉ dẫn đúng một văn bản** (1 câu dẫn hai). Ở mức văn bản `R@k` vì thế gần như suy
  biến thành "đúng văn bản có nằm trong top-k không" và không nói thêm nhiều so với
  `citation_accuracy`. Số đáng đọc nằm ở **mức điều** (91 câu một điều · 5 câu hai · 4 câu ba).
- **Một câu = 1 điểm R@1.** Chênh lệch dưới 0.02 giữa hai cột là chênh của **một câu** — và 6/100
  dòng là bản sao (xem trên), nên số câu độc lập là 94.
- **`stale_avoidance` (tránh văn bản hết hiệu lực) bằng 1.0 nhưng rỗng nghĩa** — bộ này không có
  `must_not_doc` vì không có mặt lỗi thời nào để đo (mọi văn bản được dẫn đều còn hiệu lực), nên
  chỉ số đó mặc định đúng chứ không đo gì. Giống `bo_tvpl_dung_thoi` ở §6.
- **Từ R@5 trở lên các cột hội tụ và hết khả năng phân biệt.** Ở mức điều, LexFlow hybrid đi
  0.95/0.98/0.99 tại R@5/R@10/R@20 — sát nút Naive RAG 0.96/0.98/0.99, tới R@10 hai cột không còn
  phân biệt được nữa. Cùng nguyên nhân đã ghi ở §5: corpus 49 văn bản vẫn chưa đủ để top-20 chứa
  nhiều ứng viên hợp lý, nên mọi cột bão hoà gần 1.0 ở k lớn bất kể xếp hạng tốt hay dở. Chênh lệch
  thật chỉ còn thấy được ở **R@1/MRR@2** — nơi LexFlow hybrid dẫn cả hai mức (văn bản 0.94/0.96,
  điều 0.79/0.87), trên Naive RAG (0.89/0.93 và 0.73/0.83) và bỏ xa BM25, Advanced RAG.

### Sweep hold-out — `TRONG_SO_THUA` trên dữ liệu ngoài

> Sweep dưới đây đo trên **tập 29 câu pre-expansion** (corpus 4/27 văn bản, đo 12/08); chưa sweep
> lại trên 100 câu. Kết luận "không đổi hằng số" vẫn giữ (lý do là mẫu quá mỏng, không phải con số
> cụ thể) — nếu sau này cần chỉnh `TRONG_SO_THUA`, sweep lại trên 100 câu trước.

Mức văn bản (29 câu có nhãn) — trọng số nhánh thưa trong RRF

| trọng số | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.90 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 0.50 | 0.83 |
| 0.1 (nay) | 0.90 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 0.50 | 0.83 |
| **0.25** | **0.93** | 1.00 | 1.00 | 1.00 | 1.00 | **0.97** | 0.50 | 0.83 |
| 0.5 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 0.93 | 0.50 | 0.83 |
| 0.75 | 0.83 | 0.93 | 1.00 | 1.00 | 1.00 | 0.88 | 0.47 | 0.78 |
| 1 | 0.83 | 0.93 | 1.00 | 1.00 | 1.00 | 0.88 | 0.47 | 0.78 |

Mức điều (29 câu có nhãn) — trọng số nhánh thưa trong RRF

| trọng số | R@1 | R@2 | R@5 | R@10 | R@20 | MRR@2 | P@2 | F2@2 |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.66 | 0.90 | 0.98 | 0.98 | 0.99 | 0.79 | 0.48 | 0.77 |
| 0.1 (nay) | 0.69 | 0.91 | 0.98 | 0.98 | 0.99 | 0.83 | 0.50 | 0.78 |
| **0.25** | **0.76** | 0.91 | 0.94 | 0.98 | 0.99 | **0.86** | 0.50 | 0.78 |
| 0.5 | 0.69 | 0.91 | 0.91 | 0.99 | 0.99 | 0.83 | 0.50 | 0.78 |
| 0.75 | 0.67 | 0.75 | 0.91 | 0.94 | 0.99 | 0.74 | 0.41 | 0.65 |
| 1 | 0.67 | 0.75 | 0.94 | 0.94 | 0.99 | 0.74 | 0.41 | 0.65 |

`TRONG_SO_THUA` đang là **0.1**, chỉnh hôm 11/08 bằng ba bộ đều hỏi về luật đã chết (§7). Trên bộ
này — dữ liệu ngoài, hỏi về luật **đang hiệu lực** — 0.1 không thắng ở **R@1/MRR@2**: 0.25 hơn ở
cả hai mức, rõ nhất ở mức điều (R@1 0.76 vs 0.69, chênh 0.07 ≈ 2/29 câu; MRR@2 0.86 vs 0.83) và
cũng hơn ở mức văn bản (R@1 0.93 vs 0.90, MRR@2 0.97 vs 0.95). Nhưng ở mức điều, 0.25 lại **thua**
tại R@5 (0.94 vs 0.98) và **hoà** với 0.1 ở R@2/P@2/F2@2 — tức "0.25 hơn" chỉ đúng cho 2/8 cột của
bảng trên. Đây đúng là hiện tượng đã nói ở bullet cuối phần trên: từ R@5 các cột đã bão hoà và hết
khả năng phân biệt trên mẫu 26 văn bản này, nên R@1/MRR@2 mới là hai cột còn đọc được — thua ở R@5
không phản bác kết luận vì R@5 vốn không phân biệt được ranking tốt hay dở. Trong phạm vi hai cột
đó, đây là bằng chứng cho thấy hằng số chỉnh hôm qua **có thể đang overfit** vào loại câu hỏi luật
đã chết — nên đọc thẳng, không nên chôn.

**Không đổi `TRONG_SO_THUA`.** Luật đã chốt trước khi biết số (thiết kế 12/08): 29 câu với
`|R| = 1` cho gần như mọi câu nghĩa là một câu bằng 3,4 điểm R@1 — quá mỏng để dịch một hằng số
dùng chung cho sản phẩm. Ghi nhận ở `T21` (`docs/TASKLIST.md`), không lặp lại chi tiết ở đây.

### Nạp thêm văn bản mở khoá thêm bao nhiêu câu

Cào đủ 7 văn bản trong phạm vi sản phẩm (thanh toán · tài khoản · thẻ · ngoại hối · PCRT · an
toàn giao dịch) đưa bộ này từ 29 → **56/100** câu, theo thứ tự tham lam: `94/2025/NĐ-CP` → 37,
`64/2024/TT-NHNN` → 43, `58/2024/TT-NHNN` → 48, `50/2024/TT-NHNN` → 51, `12/2022/TT-NHNN` → 53,
`60/2024/TT-NHNN` → 55, `08/2023/TT-NHNN` → 56.

Cào tiếp 16 văn bản còn lại (cho thuê tài chính, bảo lãnh ngân hàng, thư tín dụng, kiểm toán độc
lập, thống kê tiền tệ, …) đưa 56 → **100/100** — không câu nào bị chặn vì lý do gì khác. Nhưng đó
là **mở rộng sản phẩm**, không phải bổ sung dữ liệu — cùng phán đoán đã ghi với bộ TVPL ở §6
(`research/crawl_list_eval.txt`).

Danh sách đầy đủ, đúng định dạng `scripts/crawl_vbpl_batch.py` ăn: `research/crawl_list_sbv.txt`
(23 URL do chủ repo tra 12/08 từ `research/crawl_list_svb.csv`, kèm thứ tự cộng dồn tham lam và tên
đã sửa theo slug). `21/2017/TT-NHNN` có mặt ở cả hai danh sách (`research/crawl_list_eval.txt` của
bộ TVPL và danh sách này) — cào một lần dùng chung cho cả hai bộ.

**Đã xong 14/08 (T113):** cả 23 văn bản đã nhập vào `data/corpus.real.json` (26 → 49 doc, base +
enrich), re-ingest LanceDB (1496 chunk) và Neo4j (49 Document node), `chuyen_sbv.py` đưa split
29 → **100/100**. Bảng IR ở trên là kết quả đo trọn 100 câu (15/08) sau khi nhập.

## 12. Correctness — LLM-judge chất lượng câu trả lời (`eval/judge.py`)

Mọi bảng trên đo **retrieval** (tìm đúng văn bản/điều chưa). Mục này đo **câu trả lời** — thứ người
dùng thực đọc. Chấm trên `bo_sbv.jsonl` (100 dòng / 94 câu khác nhau — không khử trùng, như bảng IR),
sinh câu trả lời qua đường sản phẩm `answer.build_answer`, join `reference_answer` do tác giả bài báo
viết theo `question_id`. Ba tiêu chí Correctness §5.3, chỉ tiêu chí ngữ nghĩa tốn LLM; "có trích dẫn"
và "trích dẫn khớp" kiểm bằng Python (doc_id luôn từ chunk thật nên không bịa được).

### Kết quả — `bo_sbv.jsonl`, 100 câu, đo 2026-08-15

`eval/results/judge-sbv-20260815T110256Z.json` (gitignored). Sinh câu trả lời qua đường sản phẩm
sau khi corpus mở rộng (49 doc), rồi chấm 3 tiêu chí.

| Tiêu chí | 100 câu |
|---|---|
| Điểm ngữ nghĩa TB (dung=1 · thieu=0.5 · sai=0) | **0.885** |
| Tỷ lệ "dung" hoàn toàn | **0.790** (79/100) |
| Tỷ lệ có trích dẫn | 1.000 (100/100) |
| Tỷ lệ trích dẫn khớp văn bản vàng | 0.990 (99/100) |

Phân bố verdict: **79 dung · 19 thiếu · 2 sai**.

> **1 phiếu là đủ.** Độ ổn định đã kiểm trên bộ 29 câu (14/08): 0/29 verdict đổi giữa hai đợt
> (temperature=0 + `reasoning=False` cho kết quả tái lập hoàn toàn), nên đợt 100 câu chỉ chạy 1 vòng.
> `reasoning=False` là **bắt buộc**: model reasoning (mặc định `chat_json`) treo > 2 phút/câu trên nội
> dung pháp lý; model thường chấm ~12s với verdict + giải thích đúng.

**So bộ 29 câu (0.862 · 0.793 dung):** điểm ngữ nghĩa nhích lên 0.885, tỷ lệ dung giữ ~0.79 trên mẫu
lớn gấp hơn ba. Corpus mở rộng đổi một số câu: **qid=5** (trước "sai" vì thiếu Điều 23) nay **dung** —
23 văn bản mới đưa đủ căn cứ; **qid=55** từ "sai" xuống "thiếu" (đúng phạm vi hơn, vẫn sót lối rút
tiền mặt bằng thẻ vật lý).

### 2 câu "sai" + 19 câu "thiếu" — hụt ở đâu

**Trích dẫn khớp 99/100 nghĩa là retriever lấy đúng văn bản vàng gần như mọi câu** — hụt chất lượng
nằm **sau retrieval** (điều/khoản chi tiết hoặc cách sinh câu trả lời), không phải tìm sai văn bản.

| qid | verdict | Hụt gì |
|---|---|---|
| 27 | **sai** | "Bảo lãnh có hình thức nào" — liệt kê đúng 5 hình thức nhưng **thêm** nội dung không phải "hình thức" (vơ rộng), judge tính sai |
| 35 | **sai** | "Open API triển khai từ ngày nào" — trả "không có quy định cụ thể", trong khi Điều 5 TT64-2024 nêu **01/03/2025**. Câu vừa mở khoá (TT64 mới nạp), retrieval đúng văn bản nhưng generation phủ định nhầm |
| 55, 64, 86, 90, 4, … (19 câu thiếu) | thiếu | Phần lớn là **completeness** — đúng hướng, sót một ý/nhánh (qid=55 sót rút tiền mặt bằng thẻ vật lý tại ATM; qid=86 không nói số "03" dù hỏi "mấy") |

Chi tiết `ly_do` từng câu trong file JSON. **Cả hai câu "sai" đều là lỗi GENERATION** (vơ rộng /
phủ định nhầm), retrieval trích đúng văn bản vàng — củng cố hai khoảng cách đã ghi: hậu kiểm câu trả
lời (`T109`) và top-k nông / reranker (`T114`). Riêng qid=35 đáng chú ý: câu vừa mở khoá nhờ nạp
TT64-2024 mà sinh sai — nạp văn bản mở rộng độ phủ nhưng không tự động sửa chất lượng sinh.

### Không so trực tiếp với bài báo

Bài báo dùng **2 annotator người** chấm Correctness; ta dùng **LLM-judge 1 phiếu**. Con số đọc là
"chất lượng câu trả lời trên đúng 100 câu của bài báo, đo bằng LLM-judge tái lập được", không phải
điểm so ngang bảng Correctness của họ.

## 13. Thí nghiệm rerank (T114) — cross-encoder có đáng host không?

Câu hỏi cần trả lời trước khi dựng hạ tầng reranker (Modal/API) cho production: rerank top-20 hybrid
có nhấc thứ hạng đủ để bõ công không? Đo bằng `eval/thu_rerank.py` — **chỉ thí nghiệm, không đụng
đường sản phẩm, không đụng regression gate**. Cách đo: reranker chỉ **xáo lại thứ tự trong cùng
top-20 hybrid**, nên R@20 bất biến; chỉ R@1/R@2/R@5/MRR@2 đổi. So trên `bo_sbv.jsonl` (100 câu,
nhãn cấp điều đầy đủ — bộ khó nhất, chỗ hybrid yếu nhất), mức **điều**.

Baseline `hybrid` đo lại trong chính thí nghiệm (top-20, cùng 100 câu) để so before/after nhất quán;
số này lệch nhẹ bảng §11 vì khác lát cắt câu, không so chéo hai bảng.

Baseline hybrid trôi nhẹ giữa các lần chạy (0.765–0.777 ở R@1) vì LanceDB dùng chỉ mục vector xấp xỉ
(ANN) — không phải bug. Nên **đọc Δ so baseline CÙNG LẦN CHẠY của mỗi dòng**, đừng so absolute chéo dòng.

| Reranker | N | R@1 | R@2 | R@5 | MRR@2 |
|---|---|---|---|---|---|
| hybrid (RRF, không rerank) | 100 | ~0.77 | ~0.89 | ~0.95 | ~0.865 |
| + Jina `reranker-v2-base-multilingual` | 100 | +0.033 | −0.015 | −0.028 | +0.015 |
| + **Cohere `rerank-v3.5`** | 97 | **+0.058** | **−0.002** | **−0.015** | **+0.041** |
| + ViRanker (Modal, `namdp-ptit/ViRanker`) | 100 | +0.022 | −0.018 | −0.025 | +0.015 |

(Δ điểm mức điều so baseline cùng lần chạy. Absolute từng lần: Jina 0.810/0.875/0.922/0.880 trên base
0.777; Cohere 0.823/0.885/0.933/0.902 trên base 0.765 (97 câu, 3 câu vướng 429 trial); ViRanker
0.793/0.872/0.925/0.880 trên base 0.772.)

**Phân tích — Cohere thắng rõ, cả hai model open/generic còn lại tương đương nhau và kém hơn:**
- **Cohere** nhấc đỉnh mạnh nhất (R@1 +5.8pt, MRR@2 +4.1pt) và **gần như không mất đuôi** (R@2 −0.2, R@5
  −1.5) — cân bằng tốt nhất.
- **Jina** và **ViRanker** ngang nhau: R@1 chỉ +2–3pt, MRR@2 +1.5pt, và **tụt đuôi rõ** (R@5 −2.5…−2.8).
  Xáo mạnh hơn RRF, đẩy 1 điều đúng lên top nhưng đá vài điều đúng-nhưng-thấp khỏi top-5.
- **ViRanker (tuned tiếng Việt) lại thua Cohere** — trái kỳ vọng "model tiếng Việt/pháp lý sẽ mạnh hơn
  generic". Một phần có thể do cấu hình phục vụ: `CrossEncoder(max_length=512)` + cắt `_MAX_DOC=1024` ký
  tự, mà điều luật dài → chi tiết phân biệt có thể rơi ngoài 512 token. Test công bằng hơn cần nới
  max_length; nhưng Cohere đã thắng mà **không cần hạ tầng**, nên tinh chỉnh ViRanker ROI thấp.

**Kết luận cho T114:**
1. Rerank có ích **giới hạn**: tốt nhất (Cohere) là +5.8pt R@1 / +4.1pt MRR@2, đổi lấy −1.5pt R@5. Chỉ
   đáng nếu câu trả lời dựa vào top-1..2 căn cứ; nếu nhồi top-5 thì cân nhắc mất recall đuôi.
2. **Nếu làm rerank → dùng Cohere API**, KHÔNG self-host. ViRanker/Modal vừa yếu hơn vừa thêm vận hành
   (GPU, cold-start, endpoint) — không biện minh được. App Modal (`eval/modal_reranker.py`) giữ lại làm
   bàn đo, không đưa lên sản phẩm.
3. Rerank **không** chạm tới điểm yếu thật đã quan sát: 2 câu judge sai (§12) là lỗi **sinh**, không phải
   retrieval. Nên rerank là cải thiện biên, xếp sau các việc chạm generation. Để `[ ]` trong T114, chưa
   đưa lên đường trả lời.

Số ViRanker/bge dựng qua `eval/modal_reranker.py` (Modal, scale-to-zero, endpoint cùng shape Jina).
Provider nào cũng chỉ đổi `RERANK_*` trong `.env`; cache tách theo provider nên không trộn số.
