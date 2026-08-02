# Bảng review schema KG + PoC tầng chuẩn tắc

> **Cho người review.** Tài liệu này gộp hai thứ vốn nằm rời: schema KG đã chốt
> (`research/schema-kg-v05.html` — bản v0.5; `docs/SCHEMA_KG.md` — bản v0.4 cũ hơn) và
> PoC tầng chuẩn tắc vừa làm (`app/ontology/`, commit `8ec3ab4`). Mọi con số trong đây
> đo được từ `eval/ontology/`, không phải ước lượng — cột **bằng chứng** chỉ ra chỗ
> kiểm lại.
>
> Đọc §7 trước nếu chỉ có 10 phút: đó là những câu hỏi thật sự cần ý kiến.

---

## 1. Phạm vi — cái gì đã chốt, cái gì đang hỏi

| Tầng | Nguồn | Trạng thái | Cần review? |
|---|---|---|---|
| A · Cấu trúc văn bản (`VanBan` · `Dieu` · `Khoan` · `Diem`) | KG v0.5 §3–5 | **đã chốt**, có dữ liệu | không — trừ điểm ⚠️ ở §3 |
| B · Tổ chức & tham chiếu (`CoQuanBanHanh` · `LinhVuc`) | KG v0.5 §3 | **đã chốt** | không |
| C · Ngữ nghĩa (`KhaiNiem` · `ThucTheChiuDieuChinh`) | KG v0.5 §3 | `KhaiNiem` **đã chạy** (36 bản ghi) · `ThucTheChiuDieuChinh` P2 | có |
| D · Thời gian (`PhienBanDieu`, ngày trên cạnh) | KG v0.5 §7 | **đã chốt**, chưa nạp | không |
| **E · Chuẩn tắc (tuân thủ)** | **KG v0.5 §10.2 — NGOÀI phạm vi v0.5** | **PoC vừa làm, đây là phần cần review** | **có — trọng tâm** |

Bảy node của tầng E (`NghiaVu` · `BuocBatBuoc` · `NgoaiLe` · `ChuThe` · `QuyTrinh` ·
`Buoc` · `PhanQuyet`) đã thiết kế nhưng **dừng lại vì chưa có nguồn gold label độc lập**.
PoC này không mở khoá câu hỏi đó — nó trả lời một câu hỏi nhỏ hơn và trả lời được:
*trích được 4-tuple từ luật Việt Nam thật, với provenance mức ký tự, mà không bịa, hay
không?* Câu trả lời đo được ở §5.

---

## 2. PoC trích cái gì — ánh xạ sang từ vựng KG

Cố ý **không đẻ khái niệm mới**: mọi trường đều ánh xạ về node đã có tên trong v0.5.

| Trường PoC | Node KG v0.5 | Kiểu | Ghi chú thiết kế |
|---|---|---|---|
| `ComplianceUnit.id` | khoá `Khoan` | `52/2024/NĐ-CP#than/dieu_22#khoan_2` | đúng khoá ba nhánh của v0.5 §4 |
| `subject` | `ChuThe` | `GroundedField \| None` | `None` = **KHÔNG ÁP DỤNG**, không phải "chưa trích được" |
| `action` | `NghiaVu` | `GroundedField` | bắt buộc |
| `conditions[]` | `BuocBatBuoc` / `NgoaiLe` | `list[ConditionItem]` | mỗi Điểm một phần tử |
| `role` | — | `actor_cu \| meta_cu` | premise không sinh CU |
| `gates[]` | — *(mới)* | `list[Gate]` | phạm vi chặn của meta-CU |
| `dieu_kien_cong` | — *(mới)* | `DieuKienCong \| None` | mốc hiệu lực **có cấu trúc** |
| `references[]` | cạnh tới `Dieu`/`Khoan` | `list[str]` | khoá node, giải tất định |
| — | `KhaiNiem` | bản ghi riêng | 36 khái niệm, không đi qua CU |

### 2.1. Ba trường tự thiết kế — chỗ cần soi kỹ nhất

| Trường | Vì sao không dùng cái sẵn có | Đánh đổi đã biết |
|---|---|---|
| `Gate{kind, pham_vi, targets, suy_ra_duoc, phu_dinh, ngoai_tru}` | `gates: list[str]` phẳng không diễn đạt được *"toàn văn bản"* (ND52 phải liệt kê 267 khoá, và **sai ngay** khi văn bản được bổ sung) lẫn *"quy định tại Mục này"* (parser không có node Mục ⇒ buộc trả `[]`, không phân biệt được với "không chặn gì") | thêm 6 trường cho một khái niệm mà bài báo gốc **không** công bố listing JSON nào |
| `DieuKienCong{kind, ngay, moc, raw_text, char_span}` | mốc hiệu lực — thứ đáng kể nhất của cổng thời gian — trước đó chỉ sống dưới dạng **chữ tự do** trong `action`, không query được | `gates` là **list** còn trường này **số ít**; downstream phải join hai trường |
| `moc: bat_dau \| ket_thuc` | TT40 Đ52 k6 điểm a/b viết *"có hiệu lực thi hành **đến hết ngày** 14/8/2024"* — mốc **kết thúc**. Một trường tên `ngay_hieu_luc` sẽ **đảo ngược ngữ nghĩa trong im lặng** | — |

**Tiền lệ dựa vào:** Listing 1 của GraphCompliance (arXiv:2510.26309) để `condition` là
object lồng (`{"any": [...]}`) và chấp nhận `"context": null` khi trường không áp dụng.
Nên "ô điều kiện có cấu trúc" và "ô rỗng hợp lệ" **không** phải phát minh riêng.

---

## 3. Ba tầng chống bịa — và tầng nào chịu tải thật

| Tầng | Cơ chế | Bịa được không? | Ghi chú |
|---|---|---|---|
| ① Menu span | LLM **chọn số hiệu đơn vị** trong tập đóng do ta tách; `char_span` do code tính | **không thể** — không có đường khai offset | ⚠️ tập đóng mà sai thì đảm bảo này rỗng — xem §4 mục 7 |
| ② Modality guard | tập dấu hiệu tình thái của nhãn phải là **tập con** của đoạn luật đã neo; thêm nghĩa vụ/cấm/số ⇒ **lỗi cứng** | phát hiện sau khi xảy ra | tầng chịu tải nặng nhất, và là chỗ mọi báo nhầm phát sinh |
| ③ Diff mức từ | in `khi → phải` thay vì "not_grounded" | — | chỉ để người đọc thấy chỗ lệch |

Điểm cốt lõi so với bản đầu: `subject`/`action`/`constraint` **không còn là chữ LLM
viết** — chúng là lát cắt `dieu.text[start:end]`, tức chữ của luật. Diễn giải của mô
hình nằm riêng ở `label` và phải qua tầng ②.

---

## 4. Nhật ký vấn đề — đã gặp và đã xử lý

Cột **bằng chứng** = chỗ kiểm lại được (test hoặc số đo).

| # | Vấn đề | Chẩn đoán | Xử lý | Bằng chứng |
|---|---|---|---|---|
| 1 | `"Điều 35, khoản 4 Điều 47"` bị đọc thành Điều 35, **Điều 4**, Điều 47 | `_NUM_LIST` cho từ nối tiếp danh sách là `khoản` **hoặc** `Điều` bất kể đang đọc cấp nào ⇒ khoá **sai trông y như khoá đúng** | tách `_KHOAN_LIST`/`_DIEU_LIST`, từ nối tiếp phải **cùng cấp** | `test_ontology_citation.py` |
| 2 | Cả Điều "Đối tượng áp dụng" bị xếp `meta_cu` | 4 CU sinh ra đều **suy biến**: `action` trùng khít `subject`; nhãn *"Là đối tượng áp dụng"* là vị ngữ mô hình tự dựng (cụm đó chỉ có trong **tiêu đề Điều**) | mỗi khoản → `premise`/`vai_tro`; cổng chủ thể giữ ở mức Điều | `docs/ONTOLOGY-CLASSIFY.md` §2 |
| 3 | Bẫy `"phải"` phi-deontic | `"tổ chức **không phải là** ngân hàng"` (hệ từ) · `"số tiền **phải thu, phải trả**"` (danh ngữ kế toán) — 6/94 đơn vị bị đẩy nhầm sang `actor_cu` | che hai khuôn **chỉ ở tầng phân loại**; `modality.py` giữ nguyên độ nhạy | `--classify` 94 đơn vị |
| 4 | Cổng hiệu lực bị gán "cả văn bản" cho cả 6 khoản | TT40 Đ52 có **4 khoản** đặt mốc riêng cho từng nhóm Điều ⇒ sai phạm vi gấp nhiều lần | giải bằng `citation.py`, lấy viện dẫn **đứng trước** mệnh đề hiệu lực | cổng 5/9 quy được về khoá node |
| 5 | `subject` bị lấp bừa ở meta-CU | *"Nghị định này có hiệu lực…"* có chủ ngữ **ngữ pháp** nhưng không có **tác nhân** nào để tuân thủ | cho `subject = None` khi cổng `thoi_gian`/`lanh_tho`; cổng `chu_the` **vẫn bắt buộc** | lỗi cứng ô `subject` **3 → 0** |
| 6 | …nhưng tổng lỗi cứng **4 → 5** | diễn giải lệch-neo **dịch sang `conditions[]`**: khoản không có Điểm nào mà mô hình vẫn sinh 1–2 "điều kiện" | rule cấu trúc: meta-CU cổng thời gian **và** khoản không chẻ Điểm ⇒ `conditions` rỗng + tách mốc ngày **tất định** bằng regex | **5 → 2**; `test_ontology_meta_condition.py` (23 test) |
| 7 | TT17 Đ16 k2 — tưởng là mô hình **bịa** *"phải được"* | **sai**. Quét 296 nhãn: đúng 1 lần có từ nghĩa vụ trong nhãn mà không có trong span, và cụm đó **có nguyên văn** trong điểm c — mô hình chọn trọn `[6…14]` rồi `quote` thu hẹp span về câu đầu | `relax_absence`: cáo buộc **vắng mặt** phải kiểm trên **bao lồi các đơn vị đã chọn**. Nới **có chọn lọc** theo tính đơn điệu | **2 → 1**; `test_ontology_quote_scope.py` |
| 8 | TT40 Đ52 k6 — tưởng là mô hình **chọn thiếu đơn vị** | **sai ở tầng**. Điểm a là **một câu 142 ký tự, 7 dòng**: `clean_text` giữ mỗi dòng nguồn một dòng, mà nguồn là HTML nên mỗi viện dẫn trong thẻ `<a>` chiếm một dòng. Menu bày ra 5 "đơn vị", **4 là câu cụt không có vị ngữ** — không có lựa chọn nào đúng để chọn | `segment()` thêm mức 0: gom dòng nối tiếp một câu, **chỉ trong cùng một Điểm** | đơn vị kết thúc giữa câu **64/293 (22%) → 0**; `test_ontology_segmenter.py` |
| 9 | Sửa xong #8 thì lỗi cứng **1 → 3** | span dài hơn phơi ra **hai khiếm khuyết có sẵn** của guard: `flips` nổ trên đoạn `replace` **29↔6 từ** (nhãn nén một danh sách liệt kê); `condition_to_obligation` nổ khi mô hình **chép lại** lệnh cấm rồi bỏ đuôi danh ngữ chứa `"khi"` | cap `_FLIP_MAX_TU = 6` (flip thật đo được là **1↔1**); xét cặp **(dấu hiệu cứng + từ liền sau)** — `"phải đáp"` không có trong nguồn ⇒ vẫn nổ, `"không được thực"` có nguyên văn ⇒ im | **3 → 1**; `test_ontology_modality.py` |
| 10 | TT40 Đ26 k2 — *"Điều này"* → *"Điều 26"* | **lớp lỗi thứ ba**: mô hình suy ra **đúng** (đó *là* Điều 26) nhưng số 26 không có trong đoạn viện dẫn, và bao lồi cũng không ⇒ phép nới ở #7 bất lực | luật hẹp `relax_dereference`, **ba** điều kiện đủ cả: nguồn có `"Điều này"` · số khớp đơn vị đang xét · số đứng **ngay sau** đúng từ đó. Vế cuối chống lọt nhãn kiểu *"áp dụng cho **26** tổ chức"* | **1 → 0**; quét 294 nhãn: khuôn này đụng **1** case, và **0** case "khớp khuôn nhưng số khác" |
| 11 | Khung duyệt hiện bản ghi "sạch" mà giấu lý do | `make_gold_seed` cắt `warnings[:5]`, đúng hai dòng giải thích nằm ở vị trí 6–7/10 | bỏ cắt | `test_ontology_eval.py` |
| 12 | Trang duyệt vỡ ở Điều không chẻ khoản; bí danh có dấu nháy làm vỡ HTML | `build_payload` dùng `dieu.khoan` trực tiếp ⇒ `StopIteration` (9.4% số điều); `esc()` không escape `"`/`'` | `khoan_de_trich`; escape đủ | `test_ontology_review_ui.py` |
| 13 | `"Điều 15đ"` và `"Điều 15"` cùng một anchor ở web | `[a-zA-Z]` **không khớp `đ`** — bảng 23 chữ của VBQPPL Việt Nam không phải ASCII | dựng lớp ký tự từ `VI_LETTERS` | ⚠️ `web/lib/anchors.ts` — **chưa commit** |

### 4.1. Bài học lặp lại ba lần

`"phạt vì trích chính xác"` · `"bịa phải được"` · `"mô hình chọn thiếu đơn vị"` — cả ba
nghe hợp lý và **đều sai** khi mở dữ liệu thật ra xem. Mỗi lần chỉ tốn vài phút để in
nguyên văn đoạn luật; mỗi lần không in thì tốn một vòng sửa nhầm chỗ.

---

## 5. Số đo hiện tại

| Chỉ số | Giá trị | Nguồn |
|---|---|---|
| Corpus | 16 fixture · 11 văn bản gốc | `data/fixtures/` |
| Phân loại mức Khoản | **94 đơn vị** — premise 45 · actor_cu 40 · meta_cu 9 | `--classify` |
| Sau khi trích | **49 CU** (9 meta-CU) · **45 premise** · **36 KhaiNiem** | `pred.jsonl` |
| Bộ test bắt buộc của đề bài | **9/9** khớp kỳ vọng | `classify_testset.py` |
| Cổng quy được về khoá node | **5/9** — 4 cái còn lại khai `suy_ra_duoc=False` **kèm lý do** | `pred.jsonl` |
| Mốc ngày có cấu trúc | **7/9** meta-CU, trong đó **6** đọc ra ngày ISO | `dieu_kien_cong` |
| **Lỗi cứng** | **0/49** — nhưng đọc ghi chú ngay dưới | `pred.jsonl` |
| Bản ghi **được nới**, phải đọc kỹ | **2/49** — mỗi cái kèm cảnh báo nêu đích danh | §5.1 |
| Cảnh báo còn lại | **82 cảnh báo trên 28/49 bản ghi** | `pred.jsonl` |
| Test | **283 pytest + ruff xanh** | `uv run pytest -q` |
| **Bộ nhãn người gán** | **0/94 đã duyệt** ⚠️ | `gold.seed.jsonl` |

### 5.1. Hai con số dễ đọc nhầm

**"0 lỗi cứng" không phải là "không còn gì để duyệt".** Nó là 0 vì hai bản ghi được
**nới**, và mỗi phép nới đều để lại một câu cảnh báo **khác nhau** — có chủ ý, để người
duyệt biết bản ghi sạch vì lý do nào:

| bản ghi | nới bằng | cảnh báo còn lại |
|---|---|---|
| TT17 Đ16 k2 | `relax_absence` | *"`quote` thu hẹp sai chỗ: `text` KHÔNG chứa đoạn mà nhãn đang mô tả"* — hai trường vẫn đang nói về hai đoạn khác nhau |
| TT40 Đ26 k2 | `relax_dereference` | *"khai triển viện dẫn tương đối… khoá node đã có sẵn ở `references`"* |

> ⚠️ **Và đây mới là chỗ yếu nhất: 0/94 nhãn đã duyệt.** Mọi con số ở trên là *máy tự
> chấm máy* — chúng đo tính nhất quán nội bộ, **không** đo tính đúng. `char_span`
> chứng minh chuỗi **có trong luật**, không chứng minh **trích đúng chỗ cần trích**.
> Chưa có một nhãn người gán nào ⇒ chưa có precision/recall thật.

---

## 6. Việc còn đọng — có chẩn đoán, chưa xử lý

| # | Việc | Vì sao chưa làm | Chặn gì | Mức |
|---|---|---|---|---|
| 1 | **Hai phép nới đều làm giảm độ nhạy** — `relax_absence` (bao lồi rộng) và `relax_dereference` (khuôn `"Điều này"`) | **ĐÃ XỬ LÝ** ở #7 và #10, nhưng cả hai đều là nới. Giảm nhẹ: chỉ chạy khi **đã** có lỗi cứng, và **luôn** để lại cảnh báo nêu đích danh — hiện **2/49** bản ghi | cần theo dõi khi corpus lớn hơn | trung bình |
| 2 | **Nguồn gold label độc lập cho tầng chuẩn tắc** | KG v0.5 §10.2 đã dừng ở đây. Tập luồng nghiệp vụ do chính tác giả soạn kèm khuyết tật cài sẵn thì **không đo được năng lực thật**. Bốn hướng đang cân nhắc: kiểm chiều ngược · phân tích tác động khi luật đổi · kiểm mạch lạc tập quy phạm · benchmark cho LLM | **cả tầng E** | **cao** |
| 3 | Bộ nhãn 0/94 | chờ người gán; trang duyệt đã chạy được, sửa bằng chuột | mọi chỉ số thật | **cao** |
| 4 | Văn phạm viện dẫn danh sách phân phối | `"khoản 2 Điều 17, Điều 18, Điều 19…"` (khoản 2 **chỉ** của Điều 17) và `"…khoản 1, …khoản 2 Điều 25"` (Điều ở cuối, dùng chung). **Chọn bỏ thay vì đoán** — `dieu_18#khoan_2` là khoá sai trông y hệt khoá đúng | 4/9 cổng | trung bình |
| 5 | Cấp **Chương/Mục** không có trong parser | cổng phạm vi Mục nhận đúng là meta-CU nhưng không quy được về khoá node | 1 case của bộ test | trung bình |
| 6 | Viện dẫn sang **văn bản khác** không giải | *"Điều 2 của Thông tư số 20/2016/TT-NHNN"* — giải bằng số hiệu văn bản đang xét sẽ ra khoá sai mà không ai biết ⇒ trả rỗng | TT40 Đ52 k6, ND52 Đ37 k2 | trung bình |
| 7 | Bí danh trong đơn vị **actor-CU** chưa vào sổ | sổ đăng ký chỉ nhận premise. Đo trên corpus: **73 lần** `(sau đây gọi là …)` trên 11 văn bản; trong fixture có **1 chỗ** nằm ở actor-CU (TT18 Đ9 k2) | mất mát có thật, đã biết | thấp |
| 8 | `lanh_tho` **cố ý chưa dựng trường** | 0 case trong corpus; `detect_gate` chưa bao giờ phát ra loại cổng đó. Bịa trường cho case chưa từng gặp là thiết kế không có dữ liệu | — | thấp |
| 9 | `_MIN_UNIT = 15` | ngưỡng chọn tay; hết gây lỗi sau khi gom dòng nhưng **vẫn không có căn cứ đo đạc** | — | thấp |
| 10 | Vế chống lọt của `relax_dereference` **chưa kiểm được bằng dữ liệu** | corpus có **0** case "nguồn có viện dẫn tương đối nhưng số thêm vào khác" ⇒ chỉ canh được bằng test dựng tay, và test có ghi rõ là dựng tay | — | thấp |
| 11 | `role` mới **gắn nhãn**, chưa thật sự **gate** | meta-CU đáng ra phải được đánh giá **trước** và chặn actor-CU; hiện chỉ có nhãn | logic tuân thủ | trung bình |
| 12 | Tiết `(i)/(ii)` không có địa chỉ; `connector` = `unknown` khi chỉ ngăn bằng `;` | đo được **4/586** viện dẫn đi tới cấp tiết, cả 4 đều trong văn bản đã hết hiệu lực ⇒ không cấp khoá node. Nhưng **quan hệ logic** thì giữ | `;` trong tiếng Việt pháp lý dùng cho **cả** liệt kê lẫn lựa chọn — đoán là sai | trung bình |
| 13 | **Hai bản schema sống song song** | `docs/SCHEMA_KG.md` là **v0.4** (markdown), `research/schema-kg-v05.html` là **v0.5** (HTML). Mọi trích dẫn của PoC trỏ về bản v0.5 | người review dễ đọc nhầm bản cũ | **cần dọn** |

---

## 7. Câu hỏi cần ý kiến — xếp theo mức đáng bàn

| # | Câu hỏi | Vì sao nó quan trọng |
|---|---|---|
| 1 | **Nguồn gold label độc lập cho tầng chuẩn tắc lấy ở đâu?** Bốn hướng ở §6 mục 2 — hướng nào đứng vững? | Đây là thứ duy nhất đang chặn cả tầng E. Không giải được thì PoC dừng ở "trích được", không lên được "kiểm tra tuân thủ được" |
| 2 | **meta-CU có nên dùng chung schema 4-tuple không?** Chạy thật thì hai ô `subject`/`action` **không hợp** với mệnh đề hiệu lực: chủ thể của *"Quy định tại Điều 11, Điều 12… có hiệu lực từ ngày…"* là một **tập quy định**, không phải tác nhân. Thông tin thật của chúng nằm trọn trong `gates` | Giữ 4-tuple thì trung thành với bài báo nhưng có hai ô luôn phải "miễn"; tách schema riêng thì lệch khỏi bài báo |
| 3 | **`char_span` có đủ tư cách làm nguồn kiểm chứng độc lập không**, hay vẫn bắt buộc phải có nhãn người gán? | Quyết định luôn việc mở khoá 7 node của §10.2 |
| 4 | **Hai phép nới đã đủ hẹp chưa?** Cả hai chỉ chạy khi đã có lỗi cứng và luôn để lại cảnh báo, nhưng cả hai vẫn là nới — và cái nào cũng có thể tha nhầm khi corpus lớn hơn | Chúng là thứ duy nhất đứng giữa "0 lỗi cứng" và một bản ghi hỏng lọt xuống downstream |
| 5 | **Đơn vị trích xuất là Khoản — có đúng không?** Điểm thường lược chủ ngữ vì là mệnh đề tiếp nối chapeau, nên trích riêng từng Điểm sẽ khiến mô hình **đoán bừa chủ ngữ** | Khớp sẵn hai quyết định đã chốt: chunk mức Khoản (`RAG-DESIGN.md` §2) và Điểm dựng theo nhu cầu (KG v0.5) |
| 6 | Bảng v0.4 (markdown) và v0.5 (HTML) — **giữ bản nào làm chính?** | §6 mục 13 |

---

## 8. Cách kiểm lại số trong bảng này

```bash
uv run pytest -q                                       # 283 xanh
uv run ruff check .
uv run python -m eval.ontology.classify_testset        # 9/9
uv run python -m app.ontology --classify data/fixtures # 94 đơn vị: 45/40/9
uv run python -m app.ontology --batch data/fixtures --out eval/ontology/pred.jsonl
uv run python eval/ontology/make_gold_seed.py
uv run python -m eval.ontology.review_ui               # → eval/ontology/review.html
```

Chỉ hai lệnh cuối cùng và `--batch` cần `GEMINI_API_KEY`; toàn bộ phần phân loại, bóc
viện dẫn, tách mốc ngày và mọi test đều **tất định, không gọi LLM**.

**Đọc thêm:** `docs/ONTOLOGY-POC.md` (kiến trúc + ba tầng chống bịa) ·
`docs/ONTOLOGY-CLASSIFY.md` (phân vai, §4.2–4.5 là bốn đợt sửa gần nhất kèm số đo từng
bản ghi) · `research/schema-kg-v05.html` (schema KG bản chính).
