# Nạp văn bản vbpl qua `/admin` — nhận thẳng bản đã crawl

> Ngày: 2026-08-10 · Nhánh: `feat/software`
>
> Nối tiếp `2026-08-10-t5-luong-duyet-van-ban-design.md`, đường duyệt nay chạy được trên
> production. Nhưng nó được xây quanh việc **upload file PDF/HTML**, trong khi nguồn thật của
> dự án là **crawl vbpl.vn**.

## 1. Vấn đề

`POST /documents/upload` luôn chạy `extract_document`: đọc PDF/HTML → regex tách Điều →
Gemini đoán metadata. Kết quả là một `CorpusDocument` chỉ có `articles` phẳng.

Bản crawl vbpl thì giàu hơn hẳn — cây `provisions`, `char_span` khớp từng ký tự, `so_hieu`,
bảng thuộc tính (`co_quan_ban_hanh`, `nguoi_ky`, `ngay_ban_hanh`, `tinh_trang_hieu_luc`),
`canh_bao`, `trich_dan`. Đẩy một văn bản vbpl qua extractor là **vứt bỏ tất cả** rồi đoán lại
bằng regex và LLM một thứ đã đọc được chính xác.

**Kiểm 10/08:** `data/raw/vbpl/corpus/*.json` (22 file đang được git theo dõi) có đúng bộ khoá
của `CorpusDocument`. Không cần chuyển đổi khuôn dạng nào cả.

## 2. Vì sao không crawl ngay trên server

Đã cân nhắc và **loại**. vbpl nạp nội dung Điều/Khoản qua Server Action **sau khi JS chạy** —
một GET thuần không thấy gì (xem docstring `vbpl.fetch_rendered_main_text`). Nên crawl bắt
buộc dùng Playwright + Chromium.

Image hiện tại chạy không được: `Dockerfile` cài gói Python `playwright` (nó nằm trong
`dependencies`) nhưng **không chạy `playwright install chromium`**, nên không có binary trình
duyệt. Cloud Run đang ở **512Mi**, dưới mức Chromium headless cần. Muốn crawl trong container
phải thêm ~150MB browser và nâng RAM ít nhất bốn lần — trả giá thật cho một thao tác chạy vài
lần một tuần, ngay trước kỳ đánh giá.

Chủ repo chọn: **crawl trên máy mình, `/admin` nhận kết quả.**

## 3. Phạm vi

**Trong phạm vi:** `upload_document` nhận file `.json` đã đúng khuôn `CorpusDocument`; test;
tài liệu thao tác; một mục TASKLIST cho khoảng lệch corpus ở §7.

**Ngoài phạm vi:** crawl trên server; endpoint mới; tự động rút quan hệ từ tab lược đồ; đưa
artefact lớp phủ lên Storage; sửa `dong_goi` để đọc canonical.

## 4. Thiết kế

### 4.1 Một nhánh trong `upload_document`

Trước lời gọi `extract_document`: nếu đuôi file là `.json` và nội dung validate được thành
`CorpusDocument` thì dùng thẳng kết quả đó. Phần còn lại của luồng — lưu Storage, bản ghi
`pending`, trang duyệt, nút Approve, `ingest_one_doc` — **không đổi một dòng nào**, vì cả hai
nhánh cùng cho ra một `CorpusDocument`.

Validate hỏng thì **422 kèm nguyên lý do của Pydantic**, không âm thầm rơi về extractor. Rơi
về là biến một file hỏng thành một văn bản trông như thật với vài điều rỗng — đúng loại hỏng
phải đọc kỹ mới thấy.

`doc_id` vẫn đi qua `kiem_doc_id` như mọi đường khác.

Chọn nhánh trong endpoint sẵn có, **không** thêm `POST /documents/import`: hai đường cùng làm
một việc thì sớm muộn lệch nhau, và người dùng vẫn chỉ đang "upload một file ở /admin".

### 4.2 Cái không kiểm được, và vì sao không sao

Không kiểm được `char_span` có khớp toàn văn hay không: `noi_dung` **không nằm trong** file
corpus (nó ở `data/raw/vbpl/raw/`, không lên server), nên không có gì để đối chiếu.

Điều đó không mở thêm rủi ro: `approve_document` **hôm nay đã** nhận nguyên `body.document` do
admin sửa tay. Biên tin cậy vốn đã nằm ở vai admin, và nhánh này không dịch nó đi đâu cả.

### 4.3 Quan hệ vẫn gán tay — có chủ đích

Bản crawl không mang cạnh. Cạnh nằm ở `CANH_MOI` trong `app/ingestion/nap_corpus.py`, mỗi cạnh
kèm `note` trích nguyên văn làm bằng chứng (`ND52-2024 -THAY_THE-> ND80-2016` dẫn thẳng Điều
37). Đó là lựa chọn chất lượng, không phải chỗ còn thiếu — và `approve_document` đã nhận
`relationships` trong body, nên gán lúc duyệt là đúng chỗ.

### 4.4 Lớp phủ: giới hạn đã biết

`data/overlay/lop_phu.json` dựng **offline** bởi `python -m app.ontology.dong_goi`, đọc
`data/raw/vbpl` **và** `data/corpus.real.json` — cả hai chỉ có trên máy chủ repo. Nên văn bản
vừa duyệt có chunk trong LanceDB và node trong Neo4j, nhưng **không cạnh `TAC_DONG` nào** cho
tới khi artefact được dựng lại và deploy. Biểu hiện: huy hiệu "điều bị tác động" không hiện
gì. Không lỗi, không cảnh báo.

Chỉ đau ở một nửa số ca:

- **Văn bản không sửa đổi ai** (phần lớn): crawl → upload → Approve. Hết.
- **Văn bản có sửa đổi/bãi bỏ**: thêm `nap_corpus` → `dong_goi` → deploy trên máy chủ repo.

**Không tự động hoá** trong đợt này. Đưa artefact lên Storage để cập nhật mà không cần deploy
là làm được, nhưng là thêm một tầng cho thao tác hiếm; chưa có số lần duyệt-có-sửa-đổi nào để
biết nó đáng hay không.

## 5. Thao tác

```powershell
# 1 — crawl (máy chủ repo, có Chromium)
uv run python scripts/crawl_vbpl_batch.py danh_sach_url.txt
#     → data/raw/vbpl/raw/<slug>.json  và  data/raw/vbpl/corpus/<slug>.json

# 2 — upload `corpus/<slug>.json` ở /admin → xem JSON → gán relationships nếu có → Approve

# 3 — CHỈ khi văn bản mới sửa đổi/bãi bỏ văn bản khác
uv run python -m app.ingestion.nap_corpus
uv run python -m app.ontology.dong_goi
gcloud run deploy lexflow-api --source . --region asia-southeast1 --allow-unauthenticated
```

## 6. Kiểm thử

| Ca | Kiểm cái gì |
|---|---|
| Upload một file thật từ `data/raw/vbpl/corpus/` | `provisions` và `so_hieu` sống sót; extractor **không** được gọi |
| JSON không validate được | 422 kèm lý do Pydantic, và **không** rơi về extractor |
| File `.pdf` | vẫn đi đường `extract_document` như cũ |
| `doc_id` bẩn trong JSON | 422, không ghi bản ghi `pending` |

Dùng file thật trong repo, không bịa dữ liệu — 22 file đang tracked. Một mock tự đồng ý với
giả định của chính nó là lỗi đã lặp bốn lần trong nhánh T5; ở đây không có lý do gì để lặp lại.

Backend chạy `uv run pytest -q` + `uv run ruff check .` trước khi push.

## 7. Nợ ghi lại, không sửa ở đây

Sau khi Storage canonical tồn tại, production đọc nó chứ không đọc `data/corpus.real.json`
trong image. Hai bản sẽ trôi xa nhau: file trong image thành ảnh chụp của lần build cuối, và
`dong_goi` đọc đúng file đó — nghĩa là **artefact lớp phủ được dựng từ một corpus không phải
corpus đang phục vụ**. Chưa hỏng gì hôm nay, nhưng khoảng cách lớn dần theo mỗi lượt duyệt.
Mở mục TASKLIST; sửa đúng là cho `dong_goi` đọc được canonical, và đó là việc riêng.
