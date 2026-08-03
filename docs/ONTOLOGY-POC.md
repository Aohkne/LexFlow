# PoC — Trích Compliance Unit mức Khoản (`app/ontology/`)

> **Đây là bản thử nghiệm (proof-of-concept)**, chưa nối vào Neo4j/LanceDB, chưa vào đường ingest.
> Mục đích: kiểm chứng một cách tiếp cận trước khi quyết định có đưa vào KG thật hay không.

## 1. Vì sao có bản này

KG v0.5 (`research/schema-kg-v05.html` §10.2) đã **thiết kế xong** tầng chuẩn tắc phục vụ kiểm tra
tuân thủ — 7 node `NghiaVu`, `BuocBatBuoc`, `NgoaiLe`, `ChuThe`, `QuyTrinh`, `Buoc`, `PhanQuyet` — nhưng
**dừng lại**, lý do ghi rõ: *"chưa xác định được nguồn gold label độc lập"*. Đây là câu hỏi đang chờ mentor.

PoC này tấn công đúng chỗ nghẽn đó, lấy khung từ **GraphCompliance** (arXiv:2510.26309).

Toàn repo trước bản này **không có bất kỳ provenance mức ký tự nào** (`grep char_span|offset` = 0 hit);
provenance hiện chỉ là địa chỉ ký hiệu (`…#than/dieu_41#khoan_3`).

### 1.0. Quy công: cái gì của bài báo, cái gì của PoC này

Bản trước của tài liệu này ghi `char_span` là *"ý tưởng chống hallucination của GraphCompliance"*.
**Sai, và đã sửa.** Bài báo **không dùng chữ "hallucination"** ở đâu cả; `char_span` ở đó phục vụ
**truy vết (verifiability)**, và bài báo **không** mô tả việc đối chiếu span lúc trích xuất. Cơ chế
chống bịa bằng span là phần tự làm. Tách bạch cho đúng:

| Lấy từ bài báo | Tự làm trong PoC này |
|---|---|
| Tuple 4 thành phần ⟨S, Θ, Π, κ⟩ | **Giao thức menu-span**: LLM chọn ID trong tập đóng ⇒ bịa provenance bất khả thi |
| `char_span` cho từng field (để truy vết) | **Đối chiếu span lúc trích** + phân bậc `exact/unit/invalid` |
| `condition: {"any": [...]}` | **Modality guard** tất định (từ điển deontic tiếng Việt, 4 quy tắc chặn) |
| Phân vai `premise` / `actor_cu` / `meta_cu` | **Ánh xạ vai sang cấu trúc văn bản QPPL Việt Nam** (§13) |
| Trường `references` | Quyết định **không địa chỉ hoá tiết** kèm số liệu (§10) |
| | `text` của mọi trường là **lát cắt của luật**, không phải chữ LLM viết |

Bài báo **không có**: gold label cho chất lượng trích CU, chỉ số đồng thuận giữa người gán (IAA), và
chữ "hallucination". Họ kiểm đồ thị bằng cycle-consistency (text→graph→text) chứ không bằng nhãn người.
Nên phần §6 (bộ nhãn người gán) cũng là bổ sung, không phải chép.

### 1.1. TRUNG THÀNH ≠ ĐÚNG ĐẮN — vì sao char_span không thay được bộ nhãn

Đây là điều dễ hiểu nhầm nhất về cách tiếp cận này, nên nói thẳng:

| | char_span chứng minh được | char_span KHÔNG chứng minh được |
|---|---|---|
| **Tính trung thành** (faithfulness) | ✅ chữ này có thật trong luật, đúng chỗ này | |
| **Tính đúng đắn** (adequacy) | | ❌ đây có thật là Subject không? phân rã vậy đúng chưa? bỏ sót điều kiện nào không? |

Một trích xuất **neo hoàn hảo vẫn có thể phân tích sai**: mô hình chỉ vào đúng một đoạn có thật trong
luật, nhưng gán nhầm vai, hoặc chọn nhầm mệnh đề. Máy không tự phát hiện được — phải có người gán nhãn.

Vậy PoC này dùng **hai cơ chế cho hai việc khác nhau**:
- **§4 — ba tầng chống bịa (tất định, miễn phí, chạy mọi lúc)** → tính trung thành.
- **§6 — bộ nhãn người gán + bộ đo** → tính đúng đắn.

## 2. Đơn vị trích xuất là KHOẢN, không phải ĐIỂM

Văn bản luật VN phổ biến theo mẫu **câu bao trùm (chapeau)**: Khoản mang câu chủ đạo có đủ Subject +
Action + phần dẫn nhập điều kiện; các Điểm `a) b) c)` bên dưới là mệnh đề **tiếp nối ngữ pháp** của
Khoản, thường **lược bỏ chủ ngữ**. Trích Subject/Action riêng cho từng Điểm sẽ ép LLM đoán bừa chủ ngữ.

Vậy: **1 Khoản = 1 Compliance Unit**; mỗi Điểm con thành **một hoặc nhiều phần tử** trong `conditions` —
tương ứng `condition: {"all": [...]}` / `{"any": [...]}` mà GraphCompliance dùng cho Article 37 GDPR
(cũng đúng mẫu chapeau này). Pipeline nhận cả hai dạng: Khoản chẻ Điểm và Khoản là câu hoàn chỉnh độc
lập (khi đó `source_diem = null`).

Kết luận này **khớp sẵn** với hai quyết định đã chốt trong repo, không phải thiết kế lại:
- `docs/RAG-DESIGN.md` §2 — *"chunking: giữ mức Khoản, phiên bản hoá ở mức Điều"*.
- KG v0.5 §9 — *"Điểm dựng theo nhu cầu ở tầng nóng, không dựng đại trà"*.

## 3. Ánh xạ sang từ vựng KG v0.5 (không đẻ thêm khái niệm mới)

| PoC | Node đã thiết kế ở v0.5 §10.2 |
|---|---|
| Subject | `ChuThe` |
| Action | `NghiaVu` |
| Constraint | `BuocBatBuoc` / `NgoaiLe` |
| Object | `ThucTheChiuDieuChinh` (P2) |

Khoá node theo chuẩn v0.5 §4, nhánh `than` ghi tường minh:
`52/2024/NĐ-CP#than/dieu_22#khoan_2#diem_b` — để output PoC join thẳng được vào graph sau này.

## 4. Kiến trúc — ba tầng chống bịa

```
data/raw/ND52-2024.html
   │  extract.read_text()                    (dùng lại, không viết lại BeautifulSoup)
   ▼
parser.clean_text() / slice_dieu()           bỏ rác biên tập, cắt khối một Điều
   ▼
data/fixtures/<DOC>-dieu<N>.txt              ← offset neo vào ĐÚNG file này, nên phải commit
   │  parser.parse_dieu()
   ▼
DieuNode → KhoanNode[] → DiemNode[]          bất biến: dieu.text[start:end] == node.text
   │  segmenter.segment()
   ▼
Unit[]  — đơn vị nguyên tử ĐÁNH SỐ           ① tầng NGĂN
   │       (tách theo dòng → ';' → ranh giới câu; uid 0 = tiêu đề Điều)
   │  extractor.extract_cu() → Gemini (chat_json, temperature=0)
   ▼  LLM chỉ CHỌN SỐ HIỆU ĐƠN VỊ, không tự khai offset, không tự chép chuỗi
extractor.resolve()  → char_span do TA tính  ② tầng KIỂM
   │  modality.modality_delta() / numeral_delta()
   ▼  modality.explain()                     ③ tầng CHỈ ĐÍCH DANH
ComplianceUnit (+ errors / warnings)  →  report.render() → trang HTML kiểm
```

### ① Ngăn từ gốc — menu span

LLM **chọn ID trong một tập đóng** do ta tách, nên `char_span` do ta tính ⇒ **bịa provenance là bất khả
thi**. Đây là khác biệt căn bản so với bản đầu (LLM chép chuỗi, ta dò lại): ở đó ta *phát hiện* bịa sau
khi đã xảy ra; ở đây bịa không xảy ra được.

`quote` chỉ là **tuỳ chọn** để thu hẹp vào một cụm nhỏ hơn *bên trong* các đơn vị đã chọn:

| status | nghĩa |
|---|---|
| `exact` | quote khớp chính xác trong bao lồi → span mịn |
| `unit` | không có quote, hoặc quote không nằm trong đơn vị đã chọn → lùi về span đơn vị (**vẫn neo được**) |
| `invalid` | LLM trả uid không tồn tại → mất provenance, **lỗi cứng** |

Và quan trọng nhất: **`subject`/`action`/`constraint` không còn là chữ LLM viết.** Chúng là lát cắt
`dieu.text[start:end]` — chữ của luật. Diễn giải của mô hình nằm riêng ở `label`, đánh dấu rõ là diễn
giải. Đây là lỗ hổng lớn nhất của bản đầu: khi đó `action` là text tự do và **không hề được kiểm**.

### ② Kiểm bằng từ điển tình thái (tất định, không LLM)

Repo trước đó không có từ điển modality nào. `app/ontology/modality.py`:

| nhóm | ví dụ |
|---|---|
| `nghia_vu` | phải, có trách nhiệm, có nghĩa vụ, buộc phải, bắt buộc |
| `cam` | không được phép, không được, nghiêm cấm, cấm |
| `cho_phep` | được phép, có quyền, được |
| `dieu_kien` | trong trường hợp, với điều kiện, trừ trường hợp, khi, nếu |
| `dinh_luong` | tối thiểu, tối đa, ít nhất, không quá, chậm nhất, trong thời hạn, trở lên |

**Bẫy chính: `"được"` là chuỗi con của `"không được"`.** Khớp ngắn trước thì mọi câu CẤM bị đọc thành
CHO PHÉP — đảo ngược nghĩa pháp lý. Regex dựng theo thứ tự **dài nhất trước** + biên từ có dấu tiếng
Việt. Test `test_khop_dai_nhat_truoc` canh vĩnh viễn.

Bốn quy tắc chặn:

1. **Bịa nhóm ràng buộc** — diễn giải khẳng định `nghia_vu`/`cam` mà nguồn **không có dấu hiệu nào**
   thuộc nhóm đó → lỗi cứng.
2. **Bịa số** (mọi số trong diễn giải phải có trong nguồn; `1.000` = `1000`) → lỗi cứng.
3. **Đảo cực tình thái** theo vị trí (`modality_flips`) → lỗi cứng.
4. **Điều kiện → nghĩa vụ** — nguồn có `khi/nếu`, diễn giải làm mất, lại phát biểu nghĩa vụ, **và không
   còn dấu hiệu điều kiện nào** → lỗi cứng.

Cả hai quy tắc 1 và 4 đều đã được **siết lại sau khi chạy thật và thấy báo nhầm**, chứ không phải thiết
kế trên giấy:

- Quy tắc 1 ban đầu đếm **số lần xuất hiện** (`Counter(claim) - Counter(source)`). Chạy trên TT40 Điều 25
  khoản 5 thì báo nhầm: luật cấm hai vế (*"không được X; không được **phép** Y, Z"*), mô hình viết lại
  thành ba vế *"không được"* — đếm ra "thêm 2 lệnh cấm" trong khi nguồn đã cấm sẵn, mô hình chỉ phân phối
  lệnh cấm ra từng ý. Sửa: chỉ tính là bịa khi nguồn **hoàn toàn không có** nhóm đó.
- Quy tắc 4 ban đầu chỉ cần "mất `dieu_kien` + có `nghia_vu`". Chạy trên TT17 Điều 16 khoản 2 điểm d thì
  báo nhầm: luật viết *"**trong trường hợp** có dấu hiệu mất an toàn"*, mô hình viết *"**khi** có dấu
  hiệu mất an toàn"* — cùng nhóm, điều kiện vẫn còn. Sửa: thêm vế "diễn giải không còn dấu hiệu điều kiện
  nào".

Quy tắc 4 tồn tại vì phép đếm **một mình bỏ lọt** đúng lỗi thật đã gặp: câu bao trùm của ND52 Đ22 K2
tình cờ đã có sẵn hai chữ "phải" ở chỗ khác (*"không **phải** là ngân hàng"*, *"**phải** đảm bảo duy
trì"*), nên hiệu bằng 0. Xem `test_hallucination_that_bi_chan_cung`.

**Đánh đổi đã biết:** vẫn có thể báo nhầm khi đoạn nguồn chứa nghĩa vụ ở một mệnh đề khác với mệnh đề
đang diễn giải. Với bài toán pháp lý, chọn nghiêng về báo thừa: bản ghi bị gắn cờ đi vào luồng người
duyệt (§6), chứ không bị vứt.

### ③ Chỉ đích danh — diff mức từ

`modality.explain()` dùng `difflib` trên chuỗi **từ**, in `'khi' → 'phải'` thay vì báo `not_grounded`
chung chung. Người rà soát nhìn một cái là thấy chữ nào bị đổi.

## 5. Ba cái bẫy đã kiểm chứng trên văn bản thật

1. **Bảng chữ cái 23 chữ.** Điểm của Điều 22 khoản 2 là `a) b) c) d) đ) e) g) h)`. Trong Python
   `[a-z]\)` **không khớp `đ)`** → điểm đ bị nuốt im lặng thành dòng nối của điểm d, không báo lỗi.
   Mọi regex marker dựng từ `VI_LETTERS` (KG v0.5 §5: 23 chữ, không f/j/w/z, sau `e` là `g`);
   `so_hau_to` tra bảng, **không bao giờ dùng `ord()`** (`ord` cho `đ`=3, `e`=4 — đều sai).
2. **Chapeau không nằm trên dòng đánh số.** Dòng `"2. Điều kiện cung ứng dịch vụ trung gian thanh toán:"`
   chỉ là tiêu đề; Subject + Action nằm ở dòng kế tiếp. Nên Khoản = dòng đánh số + mọi dòng không-marker
   theo sau, và prompt nói rõ điều này với LLM.
3. **Rác biên tập trong nguồn.** Snapshot luatvietnam chèn dòng `"Phân tích"` và khối chú giải (ví dụ
   bình luận về Nghị quyết 24/2026/NQ-CP) **nằm giữa chapeau và điểm a)** — chữ của biên tập viên, không
   phải chữ của luật. `clean_text()` bỏ dòng rác + mọi dòng theo sau tới marker cấu trúc kế tiếp. Khảo
   sát cả văn bản: 71 dòng `"Phân tích"`, 66 dòng theo sau đã là marker (không cắt gì), chỉ 5 dòng mở
   khối chú giải thật. Ngược lại, mảnh vỡ do hyperlink cắt dòng (`… Mẫu số 08 …` / `;`) là chữ của luật
   nên được **nối lại**, không bỏ.

Ngoài ra, PDF: Phụ lục I ấn định cỡ chữ 13–14 cho **mọi** cấp bố cục, nên mọi giải thuật tách cấu trúc
dựa vào cỡ chữ chắc chắn thất bại — phải tách bằng mẫu đánh số đầu dòng, như ở đây.

### 5.1. Kỷ luật encoding — vấn đề ĐÚNG/SAI, không phải thẩm mỹ

`char_span` đếm theo **Unicode code point**. Nếu một file bị đọc/ghi sai codec thì `đ` thành 2 ký tự và
**mọi offset phía sau lệch hết**. Bốn nguồn rủi ro trên Windows, đều đã chặn:

| Rủi ro | Vì sao | Cách chặn |
|---|---|---|
| `python … > out.html` | PowerShell **re-encode lại** bằng codec riêng, vòng qua Python | CLI nhận `--html <path>` và **tự ghi** bằng `write_text(encoding="utf-8")`. Tài liệu không bao giờ viết dấu `>` |
| `print()` ra console cp1252 | `UnicodeEncodeError` hoặc nuốt ký tự | Deliverable là file; stdout chỉ in đường dẫn |
| HTML thiếu `<meta charset="utf-8">` | Bytes đúng nhưng browser đoán sai | Luôn emit thẻ này |
| `json.dumps` thiếu `ensure_ascii=False` | Ra `đ`, máy đọc được người không | Dùng `ensure_ascii=False` mọi nơi |

`tests/test_ontology_report.py` canh cả bốn: ghi → đọc lại → kiểm `đ)`, `Điều 22`, chữ ký mojibake,
thẻ charset, và bytes UTF-8 không BOM.

## 6. Bộ nhãn người gán + bộ đo (`eval/ontology/`)

Đây là phần trả lời tính **đúng đắn** ở §1.1 — thứ char_span không làm được.

**Quy trình maker-checker**, đúng triết lý đã có trong `app/ingestion/extract.py`
(*"NGƯỜI DUYỆT file này trước khi ingest"*) và UI admin duyệt JSON:

```bash
# 1. máy trích
uv run python -m app.ontology --batch data/fixtures --out eval/ontology/pred.jsonl
uv run python -m eval.ontology.make_gold_seed      # pred → khung gold, reviewed=false

# 2. người duyệt — mở trang duyệt, sửa bằng chuột, bấm Lưu
uv run python -m eval.ontology.review_ui --serve

# 3. đo
uv run python -m eval.ontology.run_eval
```

### 6.1. Trang duyệt (`eval/ontology/review_ui.py`)

Duyệt bằng editor là bất khả thi: `gold.seed.jsonl` lưu span dạng `[295, 391]`, muốn biết đó là chữ gì
phải tự đếm ký tự trong fixture. Trang này là **HTML tự chứa**, cố ý **không nhét vào app Next.js** — nó
là công cụ gán nhãn nội bộ, không phải tính năng cho người dùng cuối.

- Toàn văn Điều, tô màu span theo vai; phần **ngoài Khoản đang xét bị làm mờ**.
- Sửa span bằng **bôi đen chữ** rồi bấm *Gán Subject / Gán Action / + Điều kiện*, hoặc bấm **chip đơn vị**
  để gán nhanh cả đơn vị.
- Cột phải: `subject_source`, `logic`, `expect_hard_error`, danh sách điều kiện (đổi `source_diem`, xoá,
  gán lại), ô ghi chú, và **hộp đỏ hiện đúng cảnh báo máy đã tự gắn** để biết chỗ nào cần soi kỹ.
- Cột trái: 41 CU với chấm trạng thái (chưa duyệt / đã duyệt / máy gắn cờ lỗi), bộ đếm tiến độ.
- Lưu: có `--serve` thì nút **Lưu** ghi thẳng `eval/ontology/gold.jsonl` (server chỉ nghe `127.0.0.1`);
  không có thì tải file về. Ngoài ra tự lưu `localStorage` nên đóng tab không mất tiến độ, và có **Nhập
  JSONL** để tiếp tục từ bản đã lưu.
- Phím tắt: `j`/`k` chuyển CU, `Ctrl+S` lưu.

Cơ chế offset: văn bản được cắt thành lát tại **mọi biên** (đơn vị + span đã gán), mỗi lát là một text
node mang `data-s` = offset toàn cục, nên `selection → offset` chỉ là phép cộng. Đã kiểm trong Chrome:
mọi lát cắt khớp văn bản gốc, ghép lại bằng đúng `dieu.text`, bôi đen *"Dịch vụ trung gian thanh toán"*
đọc ra đúng `[76, 105]`.

### 6.2. Định dạng bộ nhãn

`gold.jsonl` mỗi dòng một Khoản: `id`, `fixture`, `reviewed`, `subject_span`, `subject_source`,
`action_span`, `logic`, `conditions[{source_diem, span}]`, `expect_hard_error`, `note`. **Trường để
`null` = không áp dụng**, bị loại khỏi mẫu số — theo đúng quy ước đã dùng hai chỗ trong repo
(`review._score` chỉ tính verdict có trong `_WEIGHT`; `run_benchmark` dùng `conflict_total`). Không đẻ
ngữ nghĩa "N/A" mới. Trường `_may_de_xuat` (ghi chú của máy) **bị loại khi xuất**, không lọt vào bộ nhãn.

Chỉ số: span khớp chính xác · span IoU ≥ 0.8 (điểm từng phần) · condition-set F1 khoá theo `source_diem`
· accuracy của `subject_source` và `logic` · khớp phán định lỗi cứng.

**Hạn chế phải ghi rõ khi báo cáo:** một người gán ⇒ **không đo được inter-annotator agreement**. Giảm
thiểu bằng gán 2 lượt cách nhau trên một tập con và công bố **self-agreement** — không được gọi đó là
IAA. Ngoài ra bộ nhãn được gán trên nền output của máy (maker-checker) nên có rủi ro **anchoring**;
đổi lại nhanh hơn gán tay khoảng 5 lần.

## 7. Cách chạy

Không cần cài thêm gì (dùng Gemini qua `app/core/llm.py`, key `GEMINI_API_KEY` trong `.env`).

```bash
# Sinh fixture từ HTML gốc — không gọi LLM
uv run python -m app.ontology --from-html data/raw/ND52-2024.html --dieu 22,23,26

# Xem cây cấu trúc / menu đơn vị — không gọi LLM
uv run python -m app.ontology data/fixtures/ND52-2024-dieu22.txt --no-llm
uv run python -m app.ontology data/fixtures/ND52-2024-dieu22.txt --units 2

# Trích Compliance Unit + trang kiểm (cần GEMINI_API_KEY)
uv run python -m app.ontology data/fixtures/ND52-2024-dieu22.txt --khoan 2 --html out.html
uv run python -m app.ontology --batch data/fixtures --out eval/ontology/pred.jsonl --html-dir eval/ontology/reports

# Gán nhãn + đo (không gọi Gemini)
uv run python -m eval.ontology.make_gold_seed     # pred → khung gold
uv run python -m eval.ontology.review_ui --serve  # trang duyệt, nút Lưu ghi gold.jsonl
uv run python -m eval.ontology.make_reports       # sinh lại 41 trang kiểm từ pred.jsonl
uv run python -m eval.ontology.run_eval           # đo pred so với gold

# Test (offline, không gọi Gemini)
uv run pytest -q tests/test_ontology_*.py
```

Các script trong `eval/ontology/` **phải gọi bằng `-m`**: chạy trực tiếp (`python eval/ontology/x.py`)
thì `sys.path[0]` là thư mục script nên không import được `app`.

## 8. Kết quả

### 8.1. Diện rộng — 41 Compliance Unit

10 Điều trên 4 văn bản (ND52-2024, TT40-2024, TT17-2024, TT18-2024) → **41 CU, 102 điều kiện,
184 trường được neo**:

| Chỉ số | Kết quả |
|---|---|
| Mất provenance (`invalid`) | **0 / 184** |
| Neo chính xác (`exact`) | 124 (67.4%) |
| Neo ở mức đơn vị (`unit`) | 60 (32.6%) |
| CU bị chặn vì lỗi cứng | **1 / 41** |

Case bị chặn — TT17-2024 Điều 16 khoản 2 điểm c. Luật viết:

> "Lưu trữ, bảo quản đầy đủ, chi tiết đối với các tài liệu, thông tin, dữ liệu nhận biết khách hàng…"

Mô hình diễn giải thành:

> "phải được lưu trữ **an toàn, bảo mật, sao lưu dự phòng**, đảm bảo tính đầy đủ, **toàn vẹn**, thực hiện
> theo **quy định phòng, chống rửa tiền và giao dịch điện tử**"

Toàn bộ phần in đậm **không có trong đoạn được neo**. Đây là kiểu bịa nguy hiểm vì nghe rất hợp lý về
mặt nghiệp vụ ngân hàng.

**Và đây là ví dụ sống cho §1.1**: ở ND52 Đ22 K1, mô hình neo `subject` vào *"Hoạt động cung ứng dịch vụ
trung gian thanh toán…"* trong khi chủ thể đúng phải là *"Dịch vụ trung gian thanh toán"* ở câu trước.
Span **hoàn toàn hợp lệ**, chữ **hoàn toàn có thật** — nhưng gán **sai vai**. Không tầng tất định nào bắt
được; chỉ người gán nhãn mới thấy.

### 8.2. Chi tiết — ND52-2024 Điều 22 khoản 2

Parser: 3 khoản; khoản 2 → **8 điểm `a, b, c, d, đ, e, g, h`** (điểm `đ` không bị nuốt); khoản 1 và 3
là câu độc lập. Segmenter: khoản 2 → 24 đơn vị nguyên tử (điểm b tách thành 3 vế: 50 tỷ / 300 tỷ /
trách nhiệm về nguồn vốn).

| | Giai đoạn 1 (LLM chép chuỗi) | Giai đoạn 2 (LLM chọn đơn vị) |
|---|---|---|
| Mất provenance | 1 | **0** |
| Neo chính xác | 6/10 | **21/22** |
| Neo ở mức thô | 3 (`normalized`) | 1 (`unit`) |
| Lỗi cứng | — (chỉ có warning) | 0 |
| `action` trong bản ghi | `"**phải** đáp ứng đầy đủ…"` ❌ | `"…cấp Giấy phép **khi** đáp ứng…"` ✅ |

**Lỗi thật ở giai đoạn 1** — Gemini viết *"**phải** đáp ứng đầy đủ"* trong khi luật viết *"cấp Giấy phép
**khi** đáp ứng đầy đủ"*, tự biến **điều kiện được cấp phép** thành **nghĩa vụ**. Câu vẫn xuôi nên đọc
lướt JSON gần như không phát hiện được. Giai đoạn 1 chỉ ghi một dòng cảnh báo và **vẫn để chuỗi sai đi
tiếp** vào trường `action`.

Giai đoạn 2 xử lý theo hai đường độc lập:
- **Cấu trúc**: `action.text` giờ là lát cắt của luật, nên chữ *"khi"* được giữ nguyên — lỗi không thể
  xảy ra ở trường mà downstream dùng.
- **Kiểm tra**: nếu mô hình vẫn viết *"phải"* ở `label`, `modality_delta` chặn cứng
  (`test_hallucination_phai_la_loi_cung`).

## 9. Giới hạn đã biết

- **Nguồn là snapshot luatvietnam**, chưa đối chiếu Công báo. Theo thang 3 mức của KG v0.5 §8 thì đây là
  `da_xac_minh_nguon = "thu_cap"`, không phải `so_cap`. Chưa đủ để làm ground truth công bố.
- **Chưa có tầng kiểm bằng LLM** (self-consistency 2+1 phiếu như `review._judge`, hoặc verifier
  entailment). Chủ đích: đo tầng tất định trước để biết còn sót bao nhiêu, rồi mới quyết có cần trả thêm
  token hay không.
- Độ mịn của span bị chặn bởi phép tách đơn vị: không chỉ được vào cụm nhỏ hơn một vế `;` trừ khi mô
  hình đưa `quote` khớp chính xác.
- Chưa xử lý Phụ lục / văn bản ban hành kèm theo (nhánh `kemtheo_*`, `phuluc_*` của KG v0.5 §4).
- Tiết `(i)/(ii)` **cố ý không có địa chỉ node** — xem §10.
- Gạch đầu dòng không đánh số vẫn nằm trong `text` của nút cha — **giới hạn được ghi nhận** theo đúng
  KG v0.5 (không có số ⇒ không có địa chỉ ⇒ không viện dẫn tới được).
- `logic` mới chỉ `all|any|unknown`; điều kiện lồng (điểm g/h chỉ áp dụng cho một số loại dịch vụ) chưa
  mô hình hoá được.
- Chưa nối `char_span` vào `Citation`/`ReviewFinding` và trình xem Next.js — cần giải bài toán rebase
  offset từ fixture sang `Article.text` của corpus.
- Chưa ghi Neo4j/LanceDB, không đụng `app/core/schemas.py` hay đường ingest đang chạy.

## 10. Tiết `(i)/(ii)` — nhận diện logic, KHÔNG cấp địa chỉ

Nhiều Điểm còn chẻ tiếp thành `(i)`, `(ii)`. Câu hỏi: có nên cho chúng một khoá node không?

**Đã đo, và kết luận là KHÔNG.**

| | Số liệu trên corpus 15 văn bản |
|---|---|
| Viện dẫn tới **Khoản** | 356 |
| Viện dẫn tới **Điểm** | 226 |
| Viện dẫn tới **tiết** | **4** |
| …ở văn bản **còn hiệu lực** | **0** — cả 4 nằm trong TT23-2019, `valid_to = 2024-07-17` |
| Chữ "tiết" trong 557k ký tự | **0** |
| Chi phí nếu dựng node | +270 nút (**+12.2%**) |

Bốn lý do: (1) không có nhu cầu ở văn bản đang áp dụng; (2) cả 4 viện dẫn đều là **tự tham chiếu nội bộ**
(`"điểm b(i) khoản này"`) nên giải được ngay trong chunk đang đọc, không cần khoá toàn cục;
(3) `RAG-DESIGN.md` §2 chốt chunk mức **Khoản** ⇒ tiết luôn nằm sẵn trong chunk, địa chỉ hoá chỉ tăng độ
mịn khi *hiển thị*, không tăng recall; (4) KG v0.5 §9 đã chọn nguyên tắc *"Điểm dựng theo nhu cầu, không
dựng đại trà"* — tiết là bậc tiếp theo trên cùng cái thang đó.

**Nếu có ngày phải làm thì hình dạng là HẬU TỐ, không phải cấp mới.** Văn bản thật viết `điểm a(ii)`,
`điểm b(i)` — số La Mã dính vào chữ cái điểm. Không ai viết "tiết (i) điểm b". Người soạn luật coi nó
như hậu tố, đúng cách KG v0.5 §5 xử lý `Điều 15a` bằng `so_hau_to`. Nên đúng hình là `so_hien_thi =
"b(i)"` trên chính node `Diem`, **không** phải `#diem_b#tiet_i`.

**Điều kiện xét lại:** kết luận này yếu theo dữ liệu, không phải theo nguyên lý. Nếu nạp thêm Thông tư
NHNN (nhóm dùng `(i)/(ii)` dày nhất: TT40 ×75, TT23-2019 ×74, TT17 ×64) mà viện dẫn tới tiết **ở văn bản
còn hiệu lực** vượt ~20 thì đo lại.

### 10.1. Nhưng quan hệ logic thì BẮT BUỘC phải giữ

Không cấp địa chỉ ≠ bỏ qua. TT17 Đ16 K1 điểm b:

```
b) …phải thực hiện đối chiếu khớp đúng với:
   (i)  Dữ liệu sinh trắc học lưu trong thẻ căn cước…tạo lập;  hoặc
   (ii) Dữ liệu sinh trắc học đã được thu thập và kiểm tra…
```

Đó là **phép TUYỂN bên trong một Điểm**. Bỏ đi thì "thoả (i) HOẶC (ii)" biến thành "thoả cả hai" — sai
nghĩa pháp lý. Nên `DiemNode.tiet: list[TietSpan]` (không có `id`) + `ConditionItem.logic`/`sub`.

Từ nối suy ra **tất định** từ đuôi câu, **không hỏi LLM** (không tốn token, tái lập được):

| đuôi tiết | logic |
|---|---|
| `…; hoặc` | `any` |
| `…; và` | `all` |
| chỉ `;` trần | **`unknown`** + cảnh báo cho người duyệt |

`unknown` là cố ý: tiếng Việt pháp lý dùng `;` cho cả liệt kê lẫn lựa chọn, đoán bừa chính là kiểu đổi
nghĩa mà cả pipeline này sinh ra để chặn. Đo trên fixture: TT40 Đ25 K6 điểm c có **4 tiết nối bằng
"hoặc"** → `any`; TT17 Đ16 K1 điểm a chỉ có `;` → `unknown`, chuyển người đọc chốt.

## 11. Bóc viện dẫn (`app/ontology/citation.py`)

Trước file này repo **không có parser viện dẫn nào** — văn phạm chỉ nằm trong spec `SCHEMA_KG.md` §2.b,
chưa ai hiện thực; `web/lib/anchors.ts` chỉ cắt slug mức Điều.

Ba thứ spec chưa phủ mà văn bản thật có:

1. **Hậu tố La Mã** `điểm b(i)`. Văn phạm spec `(điểm <chữ cái>\s+)?…` khớp `"điểm b"` rồi **bỏ im lặng
   phần `(i)`** ⇒ giải viện dẫn về đích rộng hơn thực tế mà không báo. Nay `(i)` nằm trong `DiemRef.tiet`:
   không vào khoá node, nhưng `co_tiet` ghi lại sự thật "viện dẫn hẹp hơn node trả về".
2. **Nhiều đích một câu** — spec nhắc trong lời văn nhưng để ngoài regex.
3. **Tự tham chiếu** `Điều này` / `khoản này` — spec không nhắc. Thiếu ngữ cảnh thì `to_node_ids` trả
   **rỗng**, không tụt lên khoá rộng hơn: trả "Điều 16" cho câu viết `"điểm b(i) khoản này"` là mở rộng
   đích gấp nhiều lần một cách lặng lẽ.

**Phân biệt viện dẫn thật với chữ thường** — phần đắt nhất, đã đếm trên corpus:

| mẫu | khớp | vì sao cần |
|---|---|---|
| `điểm` + chữ **đơn lẻ** | 210 | mẫu ngây thơ ra 298: dính *"**điểm** nhận được lệnh chuyển tiền"* |
| `khoản` + **số** | 401 | mẫu ngây thơ ra 1846: dính *"tài **khoản** thanh toán"* (69 lần) |
| `Điều` **viết hoa** + số/`này` | 537 | loại đúng 154 chữ *"**điều** kiện"*, *"**điều** chỉnh"* |

Bẫy đã sập một lần khi làm: tách chữ cái không có lookbehind thì chính chữ `"điểm"` và `"và"` trong
danh sách bị đọc thành điểm giả `đ`, `i`, `m`, `v` — `"điểm a, điểm b, … và điểm đ"` ra 18 điểm thay vì 5.

### 11.1. Bug đã sửa ở phía web

`web/lib/anchors.ts` dùng `/Điều\s+(\d+[a-zA-Z]?)/`. `[a-zA-Z]` **không khớp `đ`**, nên `"Điều 15đ"` cắt
thành `dieu-15` — **đụng slug với `Điều 15`**, deep-link nhảy sai điều mà không báo lỗi. Đây đúng cái bẫy
23 chữ mà phía Python đã chặn từ đầu nhưng phía TS thì chưa. Nay lớp ký tự dựng từ bảng `VI_LETTERS`.

## 13. Phân vai: premise · meta-CU · actor-CU

Trước đợt này pipeline mặc định **mọi Khoản đều là Compliance Unit**. Đo trên corpus thì
**40/278 điều (14.4%) không phải vậy** — 24 điều định nghĩa/phạm vi, 16 điều hiệu lực. Ép Điều 3
*"Giải thích từ ngữ"* thành CU sẽ sinh `subject="Dịch vụ thanh toán không dùng tiền mặt"`,
`action="bao gồm…"` — một "nghĩa vụ" không tồn tại.

Ba vai theo GraphCompliance: **premise** = chất liệu định nghĩa/diễn giải, *"not itself judged for
(non)compliance"*; **meta-CU** = nêu phạm vi áp dụng, **đánh giá trước**, không bao giờ báo vi phạm độc
lập, *chặn cổng* xem actor-CU có áp dụng không; **actor-CU** = nghĩa vụ nhắm vào chủ thể.

Lưu ý meta-CU **không phải lớp bọc mức văn bản** — nó là trường `type` trên chính node CU.

### 13.1. Ánh xạ sang cấu trúc văn bản QPPL Việt Nam (phần tự thiết kế)

| Tiêu đề Điều | Vai | Lý do |
|---|---|---|
| Phạm vi điều chỉnh | `premise` | scope statement — bài báo xếp vào premise |
| Giải thích từ ngữ | `premise` | định nghĩa thuật ngữ → node `KhaiNiem` của KG v0.5 |
| **Đối tượng áp dụng** | **`meta_cu`** | *role qualification* — chặn cổng chủ thể |
| Hiệu lực thi hành · Điều khoản chuyển tiếp | `meta_cu` | phạm vi thời gian |
| **Trách nhiệm thi hành** | **`actor_cu`** | giao nghĩa vụ thật cho cơ quan, **không** phải meta |
| còn lại | `actor_cu` | mặc định |

Dòng "Trách nhiệm thi hành" là bẫy: khảo sát đầu tiên xếp nhầm nó vào meta vì khớp chữ *"thi hành"*.
Nó giao nghĩa vụ thật (*"Bộ trưởng… chịu trách nhiệm thi hành"*). Test canh.

### 13.2. Ba tầng dò, tất định trước

1. **Regex tiêu đề** — bắt 40/278 điều, **không tốn token nào**.
2. **Đối chứng vị trí**: Điều 1 = phạm vi, Điều 2 = đối tượng áp dụng. Đo trên corpus: **9/11** và
   **8/11**. Bất đồng với tiêu đề ⇒ lấy tiêu đề + cảnh báo (tiêu đề đo được đúng hơn).
3. **LLM** một lượt cho điều không khớp khuôn nào (`allow_llm=True`, mặc định tắt).

**Ngoại lệ đã đo — văn bản sửa đổi.** Cả hai chỗ quy ước vị trí sai đều là TT20-2016 và TT23-2019, nơi
Điều 1 là *"Sửa đổi, bổ sung một số điều của Thông tư…"*. `is_van_ban_sua_doi()` nhận diện lớp này và
**tắt luật vị trí**. (TT39-2014 lại gộp cả hai vào Điều 1: *"Phạm vi điều chỉnh và đối tượng áp dụng"*.)

### 13.3. Điều không chẻ Khoản — lỗi im lặng đã tìm ra khi làm

Test hỏng lộ ra ND52 Điều 1 **không có khoản nào** (thân là một đoạn liền). Vòng lặp
`for k in dieu.khoan` chạy 0 lần ⇒ **cả điều bị bỏ qua không một lời báo**. Đo lại:
**25/267 điều (9.4%)** ở dạng này, và không chỉ điều định nghĩa — Điều 9 *"Mở và sử dụng tài khoản
thanh toán"*, Điều 38 *"Trách nhiệm thi hành"* của ND52 cũng vậy.

`parser.khoan_de_trich(dieu)` trả một **khoản ảo** phủ thân điều, mang `id` của chính Điều
(không bịa ra "khoản 1" không tồn tại) và `so_hien_thi = ""`.

## 14. Bóc viện dẫn đã được nối vào CU

`citation.py` (§11) trước đó **chỉ có test dùng**. Nay `_resolve_references()` quét `khoan.text`, giải
thành khoá node và điền vào `ComplianceUnit.references`; `references_hep_hon` bật khi có viện dẫn đi tới
cấp tiết mà khoá node không tới được — tiết cố ý không có địa chỉ, nhưng mất mát phải hiện ra.

Ví dụ điểm g của ND52 Đ22 K2: *"ngoài các điều kiện quy định tại điểm a, điểm b, điểm c, điểm d và điểm
đ khoản 2 Điều này"* — trước đây nằm chết trong `text`, giờ thành 5 khoá `…#khoan_2#diem_{a,b,c,d,đ}`.

## 14b. Phân loại xuống mức KHOẢN — xem `docs/ONTOLOGY-CLASSIFY.md`

§13 phân vai ở **mức Điều**. Đợt sau đó hạ xuống **mức Khoản** (`app/ontology/classify.py`,
`classify_unit(text, position_context)`), chạy trước bước trích S-O-A-C, theo ba phép thử A/B/C.

Hai chỗ đổi kết luận so với §13, cả hai đều có số liệu đi kèm:

- **"Đối tượng áp dụng"**: cả Điều vẫn là `meta_cu` (cổng chủ thể), nhưng **từng khoản là
  `premise`/`vai_tro`** — mỗi khoản chỉ là một danh ngữ trần, không có vị ngữ để vi phạm hay chặn cổng.
  Bằng chứng: 4/4 CU mà bản trước sinh ra từ ND52 Điều 2 đều có `action` suy biến (trùng khít `subject`
  hoặc là định ngữ của chính nó).
- **Cổng hiệu lực không mặc nhiên phủ cả văn bản**: TT40 Điều 52 có 4 khoản đặt mốc hiệu lực riêng cho
  từng nhóm Điều. Gán tất cả thành "cả văn bản" là sai phạm vi gấp nhiều lần.

Kèm theo: `Gate` (phạm vi · đích · **cực phủ định** · ngoại trừ · đã-suy-ra-được), sổ đăng ký
`premise.jsonl` có bí danh trích tất định, và một lỗi văn phạm viện dẫn đã sửa
(`Điều 35, khoản 4 Điều 47` từng bị đọc thành `Điều 4`).

## 14c. B22 — guard `ap_dung_khi`: "vế này áp dụng khi nào"

### Vấn đề

TT17 Đ16 k1 điểm a: *"…theo quy định tại khoản 2, 3 Điều 12 Thông tư này **và**:
(i) Thông tin sinh trắc học của chủ tài khoản **đối với khách hàng là cá nhân**;
(ii) Thông tin sinh trắc học của người đại diện hợp pháp **đối với khách hàng là tổ chức**;"*

Hai tiết **loại trừ nhau theo loại chủ thể**. Với một khách hàng cụ thể, đúng một tiết áp
dụng — nhưng đó **không phải** `any` (không được chọn bừa một vế: ghi `any` là cho phép lấy
sinh trắc học người đại diện của một khách hàng **cá nhân** mà vẫn "đạt"), cũng **không phải**
`all` (không ai đòi cả hai). Bộ phân tách chỉ thấy dấu `;` trần nên trả `unknown`.

### Quyết định

**Không thêm giá trị vào `connector`.** Nó giữ nguyên `all|any|unknown`. Đây là **hai câu hỏi
khác nhau**, và nhét cả hai vào một enum là đúng loại mơ hồ im lặng mà `menh_de` đã phải tách
khỏi `action`:

| trường | trả lời |
|---|---|
| `connector` | các vế **kết hợp** thế nào |
| `ap_dung_khi` | vế này **khi nào** áp dụng |

Thêm `GuardApDung {thuoc_tinh, gia_tri, raw_text, char_span}` ở **cả hai tầng** —
`ConditionItem` **và** `SubCondition` — vì đo được mô thức này ở cả hai:
**4/71 Điểm** và **5/12 tiết** (gần một nửa số tiết).

### Bốn tính chất phải giữ

1. **Do parser sinh 100%, LLM không tham gia.** Không có ô nào trong prompt, `build_cu` không
   đọc `ap_dung_khi` từ JSON của mô hình. Bất biến **theo thiết kế**, không theo số đo. Cùng
   kỷ luật với `DieuKienCong` (mốc ngày) và `tiet_logic` (và/hoặc): *thứ gì regex bắt được thì
   đừng đưa cho mô hình* — mỗi ô hỏi thêm là một ô có thể bị lấp bừa.
2. **`thuoc_tinh`/`gia_tri` là chuỗi tự do, KHÔNG chuẩn hoá.** 18 fixture đã có ba họ:
   `khách hàng` · `tài khoản thanh toán` · `thẻ`. Enum sẽ phải nới mỗi lần thêm văn bản.
   Chuẩn hoá về từ vựng có kiểm soát là việc của **bước nạp KG** qua `KhaiNiem`, không phải
   của tầng trích.
3. **`raw_text` round-trip đúng `char_span`.** Kiểm bắt buộc trước khi nhận guard: sai một
   nhịp `base` thì span vẫn hợp lệ về kiểu và vẫn hiện ra một đoạn luật **trông có lý**.
4. **KHÔNG tái dùng `Gate`.** `Gate` chặn theo *bên bị ràng buộc* (mức meta-CU, ai phải tuân
   thủ); guard chặn theo *thuộc tính của đối tượng hành vi* (mức phần tử, quy tắc này nói về
   loại gì). Hai nghĩa ⇒ hai kiểu.

### Ngữ nghĩa

**Hợp dọc cấu trúc — AND.** Guard hiệu lực của một nút = AND của mọi `ap_dung_khi` dọc đường
đi Điểm → tiết. Điểm *"đối với khách hàng là cá nhân"* chứa tiết *"trường hợp mở bằng eKYC"*
⇒ tiết áp dụng khi **cá nhân ∧ eKYC**. Guard tại **mỗi nút** vẫn PHẲNG, MỘT CẤP: không guard
lồng guard, không `else`, không thứ tự ưu tiên (`hop_guard()` trong `parser.py`).

**Đánh giá** (ngữ nghĩa đã chốt, chưa cần runtime): guard không khớp case ⇒ phần tử
`khong_ap_dung` — *miễn trừ chân không*, không phải "đạt". `connector` chạy trên phần còn lại.

### Ranh giới guard ↔ chapeau — hai cơ chế bù nhau

TT18 Đ9 k3 điểm c viết *"phải đảm bảo **các nguyên tắc sau**"* — đó là `all`, **không** phải
phân nhánh, và giải bằng **luật chapeau** (`"các … sau"`), **không sinh guard**. Hai cơ chế
phủ hai hình thái khác nhau, không chồng lên nhau. Sau khi có cả hai, `connector = unknown`
còn **0** trên bộ fixture hiện tại — nhưng đó là *kết quả đo*, không phải bất biến: `unknown`
vẫn là giá trị hợp lệ cho ca mơ hồ thật về sau.

### Ba dạng được nhận — rút từ ĐO, không từ suy đoán văn phạm

| | mẫu | ví dụ | ra |
|---|---|---|---|
| **A** | `… LÀ …` | *"đối với khách hàng là cá nhân"* | `(khách hàng, cá nhân)` |
| **B** | `… CỦA …:` | *"Đối với tài khoản thanh toán của cá nhân:"* | `(tài khoản thanh toán, cá nhân)` |
| **C** | danh ngữ trần **mở đầu đơn vị** | *"Đối với thẻ trả trước,"* | `(thẻ, thẻ trả trước)` |

Dạng C **chỉ** nhận khi cụm mở đầu đơn vị (tức phủ cả đơn vị), ≤ 4 từ, và không mở đầu bằng
từ cho biết đây không phải tên một loại. Nới vế đó ra thì mẫu nền bắt **36 ca mà phần lớn là
rác** — đã đo: `thuoc_tinh='các'`, `'phát'`, `'trường'`.

**Không đoán, nhưng cũng không im lặng.** Cụm khớp `đối với/trường hợp` mà không tách sạch:
- chứa viện dẫn (*"đối với các trường hợp quy định tại Điều 5"*) ⇒ bỏ hẳn, **không** cảnh báo —
  đó là địa chỉ, không phải loại;
- trông như tên một loại (≤ 6 từ) mà vẫn không tách được ⇒ `ap_dung_khi=None` + cảnh báo
  `guard_ngoai_mau` **kèm cụm bắt được**.

Ngưỡng đó có lý do: toàn corpus có **48** ca khớp trigger. Cảnh báo cho cả 48 sẽ dìm chết hàng
đợi duyệt (hiện 82 cảnh báo tổng cộng) — nên chỉ **16** ca đáng ngờ nhất được nêu.

### Một lỗi đường ống chỉ lộ ra khi đối chiếu batch

Lần chạy `--batch` đầu tiên ra **10 guard** nhưng **thiếu TT18 Đ13 k4** — đúng một trong bốn ca
thử bắt buộc — dù test đơn vị của parser cho ca đó **xanh**.

Nguyên nhân không nằm ở regex mà ở chỗ **đọc guard trên text nào**. Với Khoản không chẻ Điểm,
bản đầu đọc trên *đoạn đã neo của điều kiện* thay vì trên *cả Khoản*. Mà *"4. **Đối với thẻ trả
trước**, TCPHT quy định…"* là guard phủ trọn khoản: mô hình neo điều kiện vào nửa sau câu thì
cụm guard rơi ra ngoài và guard **biến mất**.

Hệ quả đáng ghi hơn bản thân cái bug: **một tầng TẤT ĐỊNH lại phụ thuộc đầu ra của LLM** — đúng
thứ mà cả thiết kế "parser sinh 100%" sinh ra để tránh. Test đơn vị không bắt được vì nó gọi
thẳng `tach_guard(khoan.text, khoan.start)`, tức đã tự cho mình đúng đầu vào. Nay có thêm một
test đi qua `build_cu` và cố ý neo vào **đơn vị cuối cùng**, xa cụm guard nhất.

## 15. Câu hỏi mở cho mentor

1. Ba tầng tất định ở §4 có đủ để coi là **kiểm soát tính trung thành** cho tầng chuẩn tắc, hay vẫn cần
   thêm tầng verifier bằng LLM?
2. Bộ nhãn ~30 Khoản do **một người** gán theo lối maker-checker có đủ tư cách làm gold để mở khoá 7 node
   ở KG v0.5 §10.2, hay bắt buộc phải có người gán thứ hai để đo IAA?
