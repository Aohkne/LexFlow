# Thiết kế: nối lớp phủ dưới-văn-bản vào sản phẩm (P4)

*Brainstorm 06/08/2026, đã duyệt. Năm câu chốt với người dùng: mục tiêu **nối lớp phủ vào sản
phẩm** · chặng này **chạm tới người dùng trên web** · cơ chế **C = router hậu truy hồi + hiển
thị bản hiện hành** · nguồn lớp phủ **artefact trong image, Neo4j để xem** · `corpus.real.json`
thành **canonical mới**.*

## Bài toán

Đợt 05/08 dựng xong ba module offline — `tac_dong.py` (178 cạnh con↔con), `hien_hanh.py`
(293 node thưa, luật cạnh-chết), `dinh_tuyen.py` (router ba nhánh, bộ nhãn 13/13). Không dòng
nào trong số đó chạm sản phẩm: `app/reasoning/answer.py` không gọi tới, LanceDB/Neo4j
production vẫn mang corpus 15 văn bản của tháng 7, benchmark mới nhất là
`eval/results/20260724-*.json`.

Người dùng thấy đúng hai triệu chứng mà lớp phủ đã giải xong ở tầng offline:

1. Hỏi một khoản **đã bị bãi bỏ** (TT41 Điều 16/17/18 — TT22 bãi từ 2026) → hệ thống vẫn trích
   nó như đang hiệu lực, vì bộ lọc hiệu lực chỉ chạy ở **cấp văn bản** (`is_effective` đọc
   `valid_from`/`valid_to`/`superseded` của chunk, mà chunk kế thừa ngày của văn bản mẹ).
2. Hỏi một khoản **đã bị sửa** → trích chữ nền cũ, không chỉ sang lời văn mới nằm trong văn
   bản sửa.

Chặng này đưa lớp phủ lên web trước kỳ đánh giá tại SHB (~04/09).

## Cơ chế: router hậu truy hồi, KHÔNG sinh chữ (+ một ngoại lệ có kiểm soát)

Ba đường đã cân nhắc:

- **A — chunk phái sinh**: ghép sẵn text hiện hành thành chunk mới đè chunk gốc trong LanceDB.
  Loại: phải re-embed, và **ta tự ghép một văn bản chưa từng tồn tại nguyên bản** — chỉ sạch
  với `sua_doi` thay trọn khoản, còn `bo_sung`/`thay_cum_tu` phải đoán. Trái nguyên tắc "không
  nắn nguồn" giữ suốt tháng 8.
- **B — router thuần**: giữ nguyên LanceDB, chú thích sau retrieval. Rẻ, an toàn.
- **C — B + hiển thị bản hiện hành** (đã chọn): như B, nhưng khi thao tác là `sua_doi` thay
  **trọn** khoản/điều và lời văn mới giải được thành chữ, thì kèm thêm khối "bản hiện hành"
  **trích nguyên văn từ văn bản sửa**, luôn có xuất xứ. Không nối, không ghép, không viết lại —
  chỉ đặt cạnh nhau hai đoạn chữ có thật kèm nhãn ai-sửa-ai.

`bo_sung` / `thay_cum_tu` / `bai_bo` ⇒ **không** có khối bản hiện hành, chỉ nhãn. Đây là ranh
giới cứng: một lệnh "bổ sung điểm d vào khoản 2" hay "thay cụm từ X bằng Y" chỉ ghép đúng khi
ta thực thi phép biến đổi văn bản — việc đó nằm ngoài phạm vi.

## Kiến trúc — bốn lớp

### 1. Artefact tự chứa · `app/ontology/dong_goi.py` → `data/overlay/lop_phu.json`

**Ràng buộc nắn thiết kế này:** `data/corpus.real.json` không mang `noi_dung` (chỉ
`articles[].text`, không có toạ độ ký tự), trong khi `loi_van_moi` là cặp span vào `noi_dung`
của văn bản sửa. Hai thứ cần để giải span đều **gitignored, chỉ có trên đĩa máy này**:
`data/raw/vbpl/raw/*.json` giữ `noi_dung`, `data/raw/vbpl/corpus/*.json` (22 file) giữ
`articles[].char_start/char_end` để biết span rơi vào điều nào. Nếu runtime mới giải span thì
một checkout sạch hoặc một image Cloud Run sẽ không có gì để giải.

⇒ Giải span thành chữ **lúc build**, đóng gói vào artefact tracked. Đầu vào build:
`eval/overlay/canh_tac_dong.jsonl` (cạnh) · `raw/` (`noi_dung` để cắt chữ) · `corpus/`
(`articles[].char_start/char_end` để biết span rơi vào điều nào → `xuat_xu`) ·
`data/corpus.real.json` (bảng `so_hieu ↔ doc_id`).

```jsonc
{ "sinh_luc": "2026-08-06",
  "so_hieu_theo_doc": {"TT40-2024": "40/2024/TT-NHNN", ...},
  "canh": [{ "nguon": "41/2025/TT-NHNN#than/dieu_1#khoan_2",
             "dich":  "40/2024/TT-NHNN#than/dieu_8#khoan_7",
             "thao_tac": "sua_doi", "valid_from": "2025-07-01",
             "loi_van_moi_text": "…chữ đã giải từ span…" | null,
             "xuat_xu": {"doc_id": "TT41-2025", "article": "Điều 1"} | null,   // cấp ĐIỀU
             "menh_lenh": "..." }] }
```

Bất biến, kiểm bằng test:

- số cạnh trong artefact **bằng** số dòng `eval/overlay/canh_tac_dong.jsonl` (178);
- mọi `loi_van_moi_text` là **lát cắt nguyên văn** `noi_dung[char_start:char_end]` — không
  strip, không chuẩn hoá khoảng trắng (bất biến char_span của cả tháng 8);
- span không giải được (thiếu file raw, lệch độ dài) ⇒ `loi_van_moi_text = null` **kèm cảnh báo
  có địa chỉ**, không bịa chữ và không im lặng bỏ.

CLI `uv run python -m app.ontology.dong_goi` in: tổng cạnh · số span giải được · số cảnh báo.

### 2. Cổng runtime · `app/knowledge/lop_phu.py`

Một cổng duy nhất giữa sản phẩm và ba module ontology — sản phẩm không gọi thẳng
`dinh_tuyen`/`phien_ban_hien_hanh`, để đường nóng có đúng một chỗ để đọc và để tắt.

- `tai_lop_phu()` — `lru_cache`, đọc artefact một lần.
- `chu_thich_chunk(chunk, as_of) -> ChuThichHieuLuc | None` — trả `nhanh`, `trang_thai`
  (`nguyen_ven`/`da_sua`/`bi_bai_bo`), `trich_dan_dung_chu`, `khoa_dich`, `sua_boi`
  (doc_id + article), `ban_hien_hanh: str | None`, `xuat_xu`.
- `chu_thich_ket_qua(chunks, as_of)` — chú thích cả danh sách hit; **loại** hit `bi_bai_bo`;
  với hit `da_sua` **không có** `ban_hien_hanh` thì kéo thêm chunk chứa lời văn mới, tra thẳng
  theo `id = f"{doc_id}::{article}"` của `xuat_xu` (không tốn lượt embedding). Cần một hàm mới
  `lay_chunk_theo_id(ids)` trong `retrieval.py` — LanceDB hiện chưa có đường tra theo id.
  Không khớp id (nhãn chunk bị gộp khác đi) ⇒ **bỏ qua**, không đoán chunk gần đúng.
- **Loại hết thì giữ lại**: nếu sau khi bỏ các hit `bi_bai_bo` mà danh sách rỗng, giữ nguyên
  chúng kèm nhãn thay vì trả `_NOT_FOUND`. Người hỏi đúng một điều đã bị bãi bỏ xứng đáng nghe
  "điều này đã bị bãi bỏ bởi TT22 từ …", không phải "chưa tìm thấy quy định phù hợp".
- **Fail-open**, đúng khuôn `graph_augmented_search`: artefact thiếu/hỏng ⇒ trả nguyên danh
  sách chưa chú thích, chat không gãy. Lớp phủ là thứ làm câu trả lời **đúng hơn**, không phải
  điều kiện để có câu trả lời.

**Nhánh 3 nhận diện bằng chữ, không bằng toạ độ.** `dinh_tuyen` nhận `span_chunk` để biết một
chunk của văn bản sửa có trùng khối lời văn mới hay không — nhưng hàng LanceDB **không mang
toạ độ ký tự** (chỉ `id/doc_id/article/text/…`), và thêm toạ độ vào chunk là đổi ingest, kéo
theo re-embed. Thay vào đó `lop_phu` kiểm bằng **chứa nhau về chữ**: chunk thuộc văn bản phát
lệnh **và** (`loi_van_moi_text` nằm trong `chunk["text"]` hoặc ngược lại). Khi khớp, gọi
`dinh_tuyen` với `span_chunk = canh.loi_van_moi` — span của chính cạnh đó, chắc chắn tự giao —
để **toàn bộ luật trích dẫn nằm nguyên trong `dinh_tuyen`** (cổng cạnh-chết, câu "từng được sửa
bởi … đã bị bãi bỏ bởi …") thay vì chép lại lần hai. Các nhánh 2/1 gọi `dinh_tuyen` với
`span_chunk=None` như thường.

`ban_hien_hanh` chỉ điền khi: `thao_tac == "sua_doi"` **và** `dich` là chính khoá của chunk
(thay trọn đơn vị, không phải sửa một điểm bên trong) **và** `loi_van_moi_text` khác `null`.

### 3. Đường trả lời · `answer.py` · `review.py`

- `answer._prepare`: gọi `chu_thich_ket_qua` sau retrieval, trước khi dựng prompt.
- `_format_context` in nhãn ngay trên đoạn trích:
  `[TT40-2024 — Điều 8 Khoản 7] (đã sửa bởi TT41-2025 Điều 1 Khoản 2, từ 2025-07-01)`
  và, khi có, khối `Bản hiện hành (theo TT41-2025 Điều 1 Khoản 2): …`.
- `_QA_SYSTEM` thêm một câu: trích dẫn **theo đúng nhãn được cung cấp**; nếu căn cứ đã bị sửa
  hoặc bãi bỏ thì phải nói rõ, không trích chữ cũ như đang hiệu lực.
- `review.py` dùng chung `chu_thich_ket_qua` trên kết quả `search_in_docs` — không đối chiếu
  quy định nội bộ SHB với điều luật đã hết hiệu lực.
- Cờ `settings.overlay_router: bool = True` (theo mẫu `graph_augment`) — tắt được, và là cách
  đo delta ON/OFF ở P4.6.

### 4. Mặt UI

`Citation` (`app/core/schemas.py`) thêm **trường optional**: `trang_thai`, `chu_thich`,
`sua_boi_doc_id`, `sua_boi_article`, `ban_hien_hanh`. Optional ⇒ FE hiện tại không vỡ khi
backend lên trước.

- **Chat** (`web/app/(app)/page.tsx`): thẻ nguồn hiện badge trạng thái + khối "Bản hiện hành"
  thu gọn, link sang xuất xứ.
- **/review**: badge tương tự trên căn cứ đối chiếu.
- **/docs/[docId]**: `GET /documents/{id}` thêm `tac_dong: [{article, khoan, trang_thai, boi,
  tu_ngay}]`; viewer đánh dấu ở **mức khoản** thay vì chỉ mức điều như hiện nay.

### 5. Neo4j — chỉ để xem

`graph.push_overlay()`: `(:DonVi {khoa, doc_id, vai})`,
`(:DonVi)-[:TAC_DONG {thao_tac, valid_from}]->(:DonVi)`, `(:DonVi)-[:THUOC]->(:Document)`,
idempotent bằng `MERGE` trên `khoa`. Không nằm trên đường trả lời (Aura free tự pause). UI
`/graph` không đụng chặng này.

## Corpus production

`data/corpus.real.json` (26 văn bản — bao trùm corpus tháng 7, gồm cả 4 quy định nội bộ SHB)
thành canonical mới trên Supabase Storage. Rủi ro đã nêu và người dùng đã chấp nhận: văn bản
nào duyệt qua `/admin` từ tháng 7 mà không có trong file này sẽ mất. Trước khi ghi đè vẫn tải
bản cũ về `data/backup/` — rẻ, và là lối quay đầu duy nhất.

## Các pha

| pha | việc | đóng bằng số |
|---|---|---|
| P4.1 | `dong_goi.py` + artefact | 178 cạnh; N span giải được; 0 span bịa |
| P4.2 | `lop_phu.py` — cổng runtime, fail-open | test offline phủ 3 nhánh + ca cạnh-chết |
| P4.3 | Nối `answer.py`/`review.py` + cờ config | hit `bi_bai_bo` bị loại; prompt có nhãn |
| P4.4 | `Citation` + `/documents/{id}` + 3 mặt web | `npm run build` xanh |
| P4.5 | Backup canonical → Storage → re-ingest LanceDB + push Neo4j → deploy | số chunk; `/health`; e2e |
| P4.6 | Benchmark ON/OFF + bộ nhãn ~20 câu + cập nhật docs | `eval/results/<ngày>.json` hai cột |

Ghi **dự đoán trước khi chạy** P4.6 (thói quen từ P1–P3): số hit bị loại vì bãi bỏ, số hit được
nắn trích dẫn, độ lệch stale-avoidance so với 36/36 của 24/07.

## Ngoài phạm vi (cố ý)

as-of bất kỳ · áp thật `thay_cum_tu` · `/graph` cấp khoản · cào 89 văn bản tồn đọng · trích
Compliance Unit · **đổi ngưỡng chunking** (2000 ký tự — đổi là vỡ bộ nhãn 13/13 đã đo, vì nhãn
gộp `"Điều 8 Khoản 1-6"` chiếm 21.8% chunk và `khoa_tu_chunk_id` đã canh theo đúng dạng đó).

## Verification

```powershell
uv run ruff check . ; uv run pytest -q                    # nền 555 không đỏ
uv run python -m app.ontology.dong_goi                    # P4.1
uv run python -m app.ingestion data/corpus.real.json      # P4.5
uv run python eval/run_benchmark.py                       # P4.6
cd web ; npm run build                                    # P4.4
```

Verify prod sau deploy: `/health`; hỏi một khoản **đã bị bãi bỏ** (TT41 Điều 16) → không được
trích như đang hiệu lực; hỏi một khoản **đã bị sửa** (TT40 Điều 8) → thẻ nguồn chỉ đúng sang
lời văn mới của TT41; mở `/docs/TT40-2024` → khoản bị sửa được đánh dấu.
