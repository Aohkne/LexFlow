# Thiết kế: ingest tăng dần cho LanceDB

*Brainstorm 13/08/2026, đã duyệt. Bốn câu chốt với chủ repo: sửa **tận `write_lancedb`** (không
phải script rời) · **không được thiếu chunk đang tồn tại** trong lúc ghi · văn bản bị gỡ khỏi
corpus thì **xoá nhưng phải xin phép** · phát hiện thay đổi bằng **so vân tay đọc từ chính bảng**.*

## Bài toán

`write_lancedb` (`app/ingestion/pipeline.py:229`) kết thúc bằng:

```python
tbl = db.create_table(LANCEDB_TABLE, data=rows, mode="overwrite")
```

`overwrite` dựng lại bảng từ đầu, mà `_embed_rows(rows)` chạy ngay trước đó — nên **mọi** hàng
đều phải có vector mới. Sửa 3 chunk cũng tốn 661 chunk qua Gemini, 21 lượt gọi batch
(`_BATCH = 32`).

Hệ quả không nằm ở eval mà ở đường sản phẩm: `app/api/documents.py:245` gọi
`ingest_docs(docs, rels)` với **toàn bộ corpus** mỗi lần admin duyệt **một** văn bản. Chi phí
duyệt một văn bản là chi phí embed cả corpus, và nó lớn dần theo số văn bản đã có.

Đây cũng là thứ đang chặn `T1` trong `docs/TASKLIST.md`: bản vá chẻ chunk cho `TT66-2025 Điều 6`
không tới được production vì đường duy nhất để đẩy nó là embed lại cả bảng và ghi đè bảng đang
phục vụ. Và 23 văn bản cào ngày 12/08 đang kẹt cùng chỗ đó.

Neo4j **không** thuộc phạm vi. `push_corpus` cũng xoá sạch (`MATCH (d:Document) DETACH DELETE d`,
`app/knowledge/graph.py:109`, kèm comment `# Xoá sạch để nạp lại (MVP)`), nhưng nó không tốn
embedding — chỉ Cypher, vài giây. Và cạnh quan hệ là dữ liệu **toàn corpus**: `DETACH` một văn
bản sẽ giết cả cạnh do văn bản khác sở hữu, nên tăng dần ở đây vừa khó vừa không đổi được gì
đáng kể. Giữ nguyên, kể cả `_noi_lai_lop_phu` chạy sau.

## Đã đo trên bảng đang phục vụ (13/08, chỉ đọc)

```
lớp bảng                      lancedb.remote.table.RemoteTable   (lancedb 0.34.0)
count_rows()                  661
select() loại được cột vector CÓ  — 23 hàng / 0.61s
quét toàn bảng không vector   661 hàng / 5.29s
merge_insert / delete / add   có mặt trên RemoteTable
FTS index                     text_idx · num_indexed_rows = 661 · tạo 10/08
```

Hai số này đổi thiết kế:

**Quét toàn bảng tốn 5.3s** và lớn tuyến tính. Nên quét đúng các `doc_id` có trong corpus chứ
không quét mù, gộp cùng lượt với việc tìm doc dư.

**Index FTS đã tồn tại và đang phủ đủ 661 hàng.** `write_lancedb` hiện gọi `create_fts_index`
mỗi lượt — bắt buộc khi bảng vừa bị `overwrite` dựng lại. Ghi tăng dần mà vẫn gọi thì thành
**reindex toàn bảng mỗi lần**, đắt hơn chính thứ đang đi tiết kiệm. Thay bằng `wait_for_index`
và kiểm `num_indexed_rows`.

## Kiến trúc

Tách hai việc đang bị trộn trong `write_lancedb`: **quyết định ghi gì** và **ghi**. Cả hai ở
nguyên `app/ingestion/pipeline.py` — không thêm module, chúng chỉ có nghĩa cạnh `build_chunks`.

```
build_chunks(docs)  ──►  rows                    (không đổi một dòng)
                          │
              _doc_can_nap(tbl, rows)  ──►  (can_nap, du)
                          │
              _embed_rows(hàng thuộc can_nap)     ← chỗ tiết kiệm duy nhất
                          │
              merge_insert("id") ──► delete(id mồ côi) ──► wait_for_index
```

## Thành phần

### `_doc_can_nap(tbl, rows) -> tuple[set[str], set[str]]`

Thuần đọc, không ghi. Quét `.select(<cột ≠ vector>).where("doc_id IN (...)")`, gom vân tay
theo `doc_id`, trả `(doc cần nạp, doc dư trong bảng)`.

**Vân tay là cả hàng trừ `vector`**, không phải mình `text`. Luật hết hiệu lực thì cái đổi là
`valid_to` / `superseded` — đúng hai trường mà bộ lọc `as_of` đọc. So mỗi `text` thì một văn bản
vừa chết bị coi là "không đổi", bảng giữ `valid_to` cũ, và hệ thống tiếp tục trả một văn bản đã
chết. Không lỗi, không cảnh báo.

`vector` bị loại vì nó là **hệ quả** của `text`, không phải dữ liệu độc lập — so nó là so 768 số
float để biết một điều mà `text` đã nói. Loại bằng `.select()`, đã xác nhận cloud nhận.

Lấy danh sách cột từ `tbl.schema` chứ không viết tay: thêm cột sau này mà quên cập nhật danh
sách thì cột đó rơi khỏi vân tay và thay đổi trên nó thành vô hình.

### `write_lancedb(rows, ep=frozenset(), xoa_doc_du=False) -> tuple[int, int]`

Trả `(số chunk vừa ghi, tổng chunk trong bảng)`.

`ingest_docs(docs, rels, ep=frozenset(), xoa_doc_du=False)` chuyển tiếp hai cờ và trả *số chunk
vừa ghi*. **Mặc định phải an toàn**: `app/api/documents.py:245` gọi `ingest_docs(docs, rels)`
không tham số, nên mặc định là "không ép nạp gì, không xoá gì" — luồng admin duyệt không bao giờ
xoá được văn bản khỏi bảng dù corpus canonical có sai.

### CLI

`app/ingestion/__main__.py` hiện đọc `sys.argv[1]` bằng tay. Thêm hai cờ thì chuyển sang
`argparse` (stdlib): `corpus` vị trí (mặc định giữ nguyên `data/corpus.sample.json`),
`--doc` lặp lại được, `--xoa-doc-du` cờ bật/tắt. Không thêm thư viện CLI nào.

## Luồng dữ liệu

1. **Bảng chưa tồn tại** → `create_table` + `create_fts_index` như hiện nay. Đường lần-đầu
   (local, test, môi trường mới) giữ nguyên hoàn toàn.
2. `can_nap, du = _doc_can_nap(tbl, rows)`; rồi `can_nap |= ep`. Cờ `--doc X` ép nạp lại X, bỏ
   qua so sánh cho X — dùng khi muốn thử một thay đổi chẻ trên đúng một văn bản.
3. `du` khác rỗng → **in ra từng `doc_id` và dừng**, trừ khi có `--xoa-doc-du`.
4. `can_nap` rỗng → in "không có gì đổi", trả `(0, count_rows())`. **Không gọi embedding lần nào.**
5. `_embed_rows` **chỉ** hàng thuộc `can_nap`.
6. `merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(...)`
7. Xoá mồ côi: id đang có trong bảng thuộc `can_nap` nhưng không có trong `rows` mới → `tbl.delete`.
8. `wait_for_index(["text_idx"])`, rồi so `num_indexed_rows` với `count_rows()`.

### Vì sao `merge_insert` trước rồi mới xoá, chứ không `delete` rồi `add`

`delete` theo `doc_id` rồi `add` ít code hơn, nhưng giữa hai thao tác **cả văn bản biến khỏi
bảng**: một truy vấn rơi vào đúng khoảng đó được trả lời như thể luật ấy không tồn tại, không
có lỗi nào bật lên. `create_table(mode="overwrite")` hiện **không** có cửa sổ này — Lance đánh
version, người đọc thấy hoặc bản cũ hoặc bản mới. Đó là một tính chất đang được cho không, và
đổi sang tăng dần không được phép đánh mất nó.

`merge_insert` theo `id` thì chunk không đổi và chunk có sửa **không bao giờ vắng mặt**. Chỉ
chunk sắp bị bỏ mới có khoảng hở — mà chúng vốn sắp biến mất.

### Vì sao bước 7 tồn tại

`merge_insert` chỉ biết những id ta đưa vào, nên nó không dọn được id **không còn** trong lần
chẻ mới. Ca thật: `id = f"{doc_id}::{label}"` mà `label` suy từ chính nội dung, nên chẻ lại một
văn bản có thể sinh **ít** mảnh hơn (T2 thêm hậu tố `(2)` đã đổi cả tập nhãn của `TT23-2019`).
Không có bước 7 thì nhãn cũ nằm lại vĩnh viễn — chunk ma, vẫn được truy hồi, vẫn được trích dẫn.

### Vì sao bước 8 tồn tại

Sau khi ghi, phần chưa vào index BM25 là phần **nhánh sparse mù** — không lỗi, chỉ là kết quả
kém đi. `num_indexed_rows` lệch `count_rows()` phải in cảnh báo to chứ không được im.

## Xử lý lỗi

**Quét bảng hỏng (mạng) ⇒ ném lỗi, KHÔNG rơi về `overwrite`.** Rơi về âm thầm biến một trục
trặc mạng thoáng qua thành hoá đơn embedding cả bảng, và không ai biết vì kết quả cuối vẫn đúng.
Đây là loại "dự phòng" phải cố ý không viết.

**Chết giữa chừng thì chạy lại tự sửa.** Chết sau bước 6: bảng có hàng mới + mồ côi cũ; lượt sau
vân tay lệch ⇒ nạp lại đúng doc đó ⇒ xoá mồ côi. Không cần cơ chế phục hồi riêng. Trong khoảng
đó bảng **có hàng thừa** — chấp nhận được, vì ràng buộc đã chốt là "không được thiếu chunk đang
tồn tại"; thừa không vi phạm.

**Xoá doc dư mặc định TẮT.** `main()` mặc định đọc `data/corpus.sample.json` (`pipeline.py:329`).
Nếu xoá doc dư là tự động thì gõ thiếu tham số sẽ **xoá sạch corpus thật**. Hôm nay lệnh đó cũng
ghi đè, nhưng ghi đè bằng sample thì thấy ngay; xoá âm thầm thì không.

## `n_chunks` đổi nghĩa — cố ý

`app/api/documents.py:245` trả `n_chunks` cho admin và ghi vào audit log. Hiện nó là *tổng chunk
cả corpus*. Sau thay đổi, `ingest_docs` trả *số chunk vừa ghi* — với ngữ cảnh "duyệt một văn
bản" thì đây đúng hơn hẳn. Tổng bảng đi vào `detail` của audit dưới khoá riêng. Không giữ nghĩa
cũ cho êm: giữ thì con số vẫn là tổng corpus trong khi thao tác chỉ chạm một văn bản, tức là nói
dối một cách trông rất hợp lý.

## Kiểm thử

Dựng bảng giả từ `build_chunks` trên corpus sample — đúng cách `tests/test_lay_chunk_tien_to.py:67`
đã làm, không phát minh lại. **Không test nào chạm cloud.**

Ca ghim:

- không đổi gì ⇒ `can_nap` rỗng, không gọi embedding lần nào
- đổi `text` ⇒ doc đó vào `can_nap`
- đổi `valid_to`, `text` y nguyên ⇒ vẫn vào `can_nap`
- doc mới hoàn toàn ⇒ vào `can_nap`
- doc chẻ ra **ít** mảnh hơn ⇒ id mồ côi bị xoá
- doc dư trong bảng ⇒ mặc định dừng, không xoá; có cờ thì xoá
- cờ `ep` ⇒ nạp lại kể cả khi vân tay khớp
- bảng đã có index ⇒ **không** gọi `create_fts_index`

Ca cuối đáng ghim riêng vì quên nó thì mọi thứ vẫn *đúng*, chỉ đắt — sẽ không ai phát hiện.

## Điều chưa chắc, phải xử ở bước đầu của plan

`merge_insert(...).execute()` trên `RemoteTable` mới chứng minh được là **dựng builder** được,
chưa chứng minh **chạy** được. Bước đầu tiên của plan: chạy nó trên một **bảng nháp** trong cùng
DB cloud rồi drop — không đụng bảng phục vụ.

Nếu remote không hỗ trợ, phương án lùi là `delete` theo `doc_id` rồi `add`, tức chấp nhận cửa sổ
thiếu mà chủ repo đã loại ở bước brainstorm. Phải biết **trước khi viết code**, không phải lúc
chạy thật.

## Ngoài phạm vi

- Neo4j giữ nguyên `DETACH DELETE` + nạp lại (lý do ở phần Bài toán).
- Index FTS đang chạy `ascii_folding: True, language: 'English'` — BM25 gấp "điều"→"dieu",
  "ngân"→"ngan" trước khi khớp. Câu hỏi và văn bản đều bị gấp nên vẫn khớp, nhưng nó xoá phân
  biệt dấu, và đây là nhánh mà `T21` đang chỉnh trọng số. Ghi thành mục riêng trong
  `docs/TASKLIST.md`, không trộn vào việc này.
- `create_scalar_index("doc_id")`: có mặt trên `RemoteTable`, nhưng ở 661 hàng thì `where` theo
  `doc_id` đã chạy 0.61s. Chưa làm; ghi vào TASKLIST kèm ngưỡng để biết khi nào cần.
