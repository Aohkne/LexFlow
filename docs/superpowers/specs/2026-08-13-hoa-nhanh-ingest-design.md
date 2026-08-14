# Thiết kế: hoà `feat/ai` với `main` — một cơ chế ghi chunk duy nhất

*Brainstorm 13/08/2026, đã duyệt. Ba câu chốt với chủ repo: **hợp nhất thật sự một cơ chế ghi**
(không giữ hai đường song song) · văn bản rỗng thì **xoá chunk và trả 200**, giữ đúng ngữ nghĩa
main đã cố ý làm · số hiệu TASKLIST **chia dải theo nhánh** để lần sau không đâm nhau.*

## Bối cảnh: vì sao spec này tồn tại

PR #24 (`feat/ai` → `main`) báo xung đột ở 5 file. Truy ra thì phần lớn **không** phải xung đột với
nhánh compliance — PR #19 (`feat/ai-compliance`) chỉ chạm `docs/TASKLIST.md` và `docs/WORKLOG.md`,
71 dòng, không đụng một dòng code nào.

Cái thật sự đâm nhau: **`main` đã giải cùng bài toán từ 10/08**, ba ngày trước plan
`2026-08-13-ingest-tang-dan`. `feat/ai` tách khỏi main ở `1d4aa87` (10/08), rồi main nhận:

| Commit | Nội dung |
|---|---|
| `f0c6ec3` | `ingest_one_doc` — nạp lại đúng một văn bản, `delete` theo `doc_id` rồi `add` |
| `8300b4e` | `/approve` chuyển sang dùng nó |
| `1f1629c` | `push_one_doc` — cập nhật một văn bản trong đồ thị mà không xoá sạch cạnh |
| `2334f9b` | `table_names()` thay `list_tables()`, kèm lý do đo được |
| `2f6936e` | **đóng T1 và T2** |

Nghĩa là tiền đề của plan cũ — *"duyệt một văn bản thì embed lại cả corpus"* — **đúng trên
`feat/ai` nhưng đã sai trên `main` từ 10/08**. Nó cũng giải bí ẩn mà Task 7 của plan cũ gặp: bảng
thật đã mang bản vá chunking vì production chạy main, còn `docs/TASKLIST.md` trên `feat/ai` vẫn là
bản chụp trước lúc T1 bị đóng.

**Một lỗi cần ghi lại.** `2334f9b` đo được `list_tables()` ném `HttpError 400` trên kết nối LanceDB
Cloud thật của dự án (*"PgCatalog::open_database() requires a table name to resolve the storage
path"*), viết ghi chú T18 dặn **đừng** đổi `table_names()` → `list_tables()`, và ghim bằng một test
ném `AssertionError`. Trong Task 3 của plan cũ, controller ra chỉ thị làm đúng cái đó, dựa trên việc
kiểm được `list_tables` *có tồn tại* trên `RemoteDBConnection` — tồn tại không phải là chạy được.
Code cuối cùng không dính lỗi (reviewer bắt được lỗ phân trang, bản vá thay phép dò bằng
`open_table`), nhưng nó thoát nhờ may. Bài học: **đo trên deployment thật thắng phép kiểm thuộc
tính**, và ghi chú "đừng làm X" trong TASKLIST là dữ liệu, không phải ý kiến.

## Hai đường không tranh nhau một chỗ

`ingest_one_doc` trả lời *"tôi biết chính xác văn bản nào đổi"* (đường API). `write_lancedb` tăng
dần trả lời *"tự tìm xem văn bản nào đổi"* (đường CLI / toàn corpus — trên main vẫn là `overwrite`
+ embed lại 661 chunk). Cả hai đều cần, nhưng chúng đang có **hai câu trả lời trái nhau** cho cùng
một câu hỏi an toàn: main dùng `delete`+`add` (có cửa sổ văn bản biến mất khỏi bảng), `feat/ai` dùng
`merge_insert` (không có cửa sổ đó) — mà chủ repo đã loại `delete`+`add` ở bước brainstorm trước
đúng vì cửa sổ ấy.

Spec này hợp nhất **tầng ghi**, giữ nguyên **tầng quyết định**.

## Kiến trúc

```
ingest_one_doc(doc, …) ─► _id_dang_co(tbl, {doc_id}) ─┐
                                                       ├─► _ghi_chunk(tbl, phạm_vi, rows, id_cũ)
write_lancedb(rows, …) ─► _doc_can_nap(tbl, rows) ────┘         │
                                                                 └─► xoá mồ côi → merge_insert → _cho_index
```

`_ghi_chunk` **không tự quyết văn bản nào cần ghi.** Người gọi đã biết: đường API biết vì admin vừa
duyệt đúng văn bản đó, đường corpus biết nhờ `_doc_can_nap`. Ranh giới này là thứ giữ cho đường API
không phải trả phép quét toàn bảng 5,3 giây để suy ra một điều nó đã biết sẵn — trên một đường HTTP
đồng bộ.

## Thành phần

### `_ghi_chunk(tbl, pham_vi: set[str], rows: list[dict], id_cu: dict[str, set[str]]) -> int`

Trả số chunk vừa ghi. Ba bước:

1. **Xoá id mồ côi**: `{i for d in pham_vi for i in id_cu.get(d, set())} - {r["id"] for r in rows}`
2. **`merge_insert("id")`** với `rows` (sau `_embed_rows`), bỏ qua nếu `rows` rỗng
3. **`_cho_index(tbl)`**

Luật ở bước 1 phủ **cả hai** ca, và đây là chỗ thiết kế gọn lại so với bản phác đầu: ca "văn bản
chẻ lại ra ít mảnh hơn" và ca "văn bản không còn điều nào" là **cùng một luật** với `rows` rỗng hay
không. Bản phác ban đầu định thêm tham số `xoa_doc` cho ca thứ hai; nó thừa.

Ca thứ hai là ngữ nghĩa main cố ý làm và phải giữ: admin xoá hết Điều trong ô JSON rồi bấm duyệt.
Bản trước của main về sớm khi `rows` rỗng, và đó là lỗi — chunk cũ nằm lại trong bảng đang phục vụ
nên truy hồi vẫn trả đúng đoạn văn vừa bị xoá, trong khi API trả `200 approved`.

**Thứ tự xoá-trước hay merge-trước — đây là đảo so với spec trước, có chủ ý.** Spec
`2026-08-13-ingest-tang-dan` viết "`merge_insert` trước, xoá mồ côi sau". Ràng buộc thật đằng sau
câu đó là: không có khoảnh khắc nào một chunk **còn tồn tại sau lượt ghi** vắng mặt khỏi bảng. Id
mồ côi theo định nghĩa là id **sẽ không còn** sau lượt ghi, nên xoá chúng trước không vi phạm gì —
chunk có mặt ở cả hai phía không bị bước 1 chạm tới.

Đảo lại còn tốt hơn ở ca chết giữa chừng. Thứ tự cũ: chết sau `merge_insert` để lại mồ côi trong
bảng (thừa). Thứ tự mới: chết sau bước 1 để lại đúng "nội dung cũ trừ phần sắp bỏ" — không hàng
thừa, không hàng thiếu ngoài dự kiến. Cả hai đều tự lành ở lượt sau; thứ tự mới lành từ trạng thái
sạch hơn.

**`_ghi_chunk` giả định bảng ĐÃ TỒN TẠI.** Nó không tạo bảng. Ca chưa có bảng (máy mới, local, CI)
thuộc về người gọi, và **cả hai người gọi đi qua cùng một `_tao_bang_moi`** — đó cũng là một phần
của việc hợp nhất, vì hôm nay main tạo bảng bằng `create_table(...)` + `create_fts_index(...)` viết
tay trong `ingest_one_doc`, còn `feat/ai` có `_tao_bang_moi`. Sau hoà chỉ còn `_tao_bang_moi`.

Hai hàm trả về hình dạng khác nhau — `_ghi_chunk -> int`, `_tao_bang_moi -> tuple[int, int]` — vì
người gọi cần thứ khác nhau: `ingest_one_doc` chỉ cần số chunk của riêng văn bản đó, `write_lancedb`
cần thêm tổng bảng cho audit. Người gọi tự lấy phần mình cần.

### `_id_dang_co(tbl, doc_ids: set[str]) -> dict[str, set[str]]`

Bản có phạm vi của phép đọc mà `_doc_can_nap` đã làm: `where doc_id IN (…)`, `select(["id","doc_id"])`.
Đo 13/08: 0,61s cho một văn bản, so với 5,29s quét toàn bảng.

Gọi `kiem_doc_id` cho **từng** id trước khi dựng vị từ. Lý lẽ lấy nguyên của main: kiểm ở tầng này
làm bất biến đúng cho **mọi** người gọi — CLI, script, test — chứ không chỉ cho đường đi qua API.

### `ingest_one_doc(doc, rels, tat_ca_docs) -> int`

Giữ nguyên chữ ký, docstring và phần Neo4j (`push_one_doc`). Đổi đúng phần ghi LanceDB: bỏ
`delete`+`add`, chuyển sang `_id_dang_co` + `_ghi_chunk`.

### `write_lancedb(rows, ep, xoa_doc_du) -> tuple[int, int]`

Giữ nguyên chữ ký và toàn bộ tầng quyết định (`_doc_can_nap`, `ep`, `DocDuTrongBang`). Phần ghi
chuyển sang gọi `_ghi_chunk`.

## Ba thứ của `main` phải giữ nguyên

**`_FTS_OPTS` — bẫy lớn nhất của lần hoà.** `_tao_bang_moi` và `_cho_index` của `feat/ai` gọi
`create_fts_index("text")` trần. Nếu chúng thắng, index dựng lại mang tham số tokenizer khác index
đang chạy, và nhánh BM25 đổi hành vi mà diff không cho thấy gì. **Mọi** lời gọi `create_fts_index`
phải truyền `**_FTS_OPTS`, có test ghim.

Chú thích của main cũng đã giải quyết `T24` mà `feat/ai` mở: `ascii_folding: True` là lựa chọn có
chủ đích (người dùng gõ không dấu vẫn khớp văn bản có dấu), và main còn thấy thứ `feat/ai` không
thấy — vì `ascii_folding` bỏ dấu **trước** khi lọc stop-word, `thẻ`/`số`/`tổ` thành `the`/`so`/`to`
và rơi vào danh sách stop-word tiếng Anh, nên `remove_stop_words: False` là để tháo mìn đó. `T24`
của `feat/ai` bị **bỏ hẳn**.

**`tests/conftest.py`** — lưới `autouse` chặn `app.core.vectordb.connect` và
`app.knowledge.graph.session` trong mọi ca test. Lấy nguyên. Nó ra đời vì một lượt RED của TDD đã
ghi một thông tư bịa (`TT99-2026`) thẳng vào LanceDB Cloud + Neo4j Aura đang phục vụ. `feat/ai`
không có lưới đó.

**`kiem_doc_id` + `_DOC_ID_RE`**, và pin `_FakeDB.list_tables` ném `AssertionError`.

## Phép dò bảng: bản của `feat/ai` thắng

Main dùng `db.table_names()` vì `list_tables()` ném 400. `feat/ai` không gọi cái nào — `open_table`
trong `try`, bắt `ValueError` **có lọc thông điệp** `"not found"`, không khớp thì `raise` lại. Nó
tránh được cả ba: HttpError 400, `DeprecationWarning`, và lỗ phân trang của `list_tables`.

Đo 13/08, cả hai backend: `ValueError("Table 'x' was not found")`, cùng khung `lancedb/db.py:1722`.

Áp cho cả hai đường ghi. Cập nhật ghi chú `T18` của main để ghi rằng phép dò giờ là `open_table` —
để lần sau không ai đi lại vòng `table_names` ↔ `list_tables`.

Kéo theo: `_FakeDB` trong `tests/test_ingest_mot_van_ban.py` phải học `open_table` ném `ValueError`
khi thiếu bảng. Giữ `list_tables` ném `AssertionError` — nó vẫn canh đúng thứ cần canh.

## Số hiệu TASKLIST

Ghi luật vào `docs/COMMIT-CONVENTION.md`, cạnh bảng nhánh/worktree đã có ở mục "Push rules":

| Dải | Ai dùng |
|---|---|
| T1–T99 | đã tồn tại trên `main` — **không đánh lại** |
| T100+ | `feat/ai` |
| T200+ | `feat/software` |
| T300+ | `feat/ai-compliance` |

Main giữ số vì **13 commit message đã vào lịch sử** dẫn tới chúng, cộng 4 dòng trong `WORKLOG` —
lịch sử git bất biến, tài liệu thì sửa được.

Ánh xạ mục của `feat/ai`:

| Cũ | Mới | Nội dung |
|---|---|---|
| T25 | T100 | cân nhắc `create_scalar_index("doc_id")` |
| T26 | T101 | `count_rows()` sau `merge_insert` có tươi không |
| T27 | T102 | vân tay chunk lệch khi ghi bằng `merge_insert` |
| T28 | T103 | `StarletteDeprecationWarning` là tín hiệu phụ thuộc |
| T21 | T104 | trọng số nhánh thưa lệch giữa luật chết và luật hiện hành |
| T22 | T105 | `HttpError` thoáng qua làm rớt câu khi benchmark |
| T23 | T106 | `so_hieu` dính dấu cách — giữ `[x]`, đã đóng 12/08 |
| T18 | T107 | nhận diện viện dẫn trong CÂU HỎI → anchor đồ thị |
| T24 | — | **bỏ**, `_FTS_OPTS` của main đã phủ và phủ đúng hơn |

`T1`/`T2` lấy bản **đã đóng** của main. Phép đo 13/08 (bảng khớp `build_chunks` từng ô trên 661
hàng × 10 cột) chuyển sang `WORKLOG` — nó là một quan sát tại một thời điểm, không phải việc phải làm.

Các mục có **cùng số và cùng nội dung** ở hai bên (T3, T4, T6, T7, T8, T11–T16, T19, T20) là mục có
từ trước lúc tách nhánh. Chúng là xung đột văn bản thường, giải theo nội dung mới hơn, không phải
xung đột số hiệu.

## Kiểm thử

Giữ 26 ca của `tests/test_ingest_tang_dan.py` và bộ `tests/test_ingest_mot_van_ban.py` của main.
Thêm:

- `_ghi_chunk` qua đường một-văn-bản: văn bản còn điều ⇒ thay tại chỗ, chunk văn bản khác không đụng
- **văn bản rỗng ⇒ chunk cũ biến mất khỏi bảng** — ca main cố ý sửa, giờ rơi ra từ luật mồ côi
- mọi lời gọi `create_fts_index` đều mang `_FTS_OPTS`
- `ingest_one_doc` không gọi `list_tables` **và** không gọi `table_names` — phép dò là `open_table`
- lỗi tạm thời khi `open_table` ⇒ **ném**, không tạo bảng mới (đã có ở `feat/ai`, phải còn sống sau hoà)

`tests/conftest.py` của main chặn ở `app.core.vectordb.connect`; các ca của `feat/ai`
`monkeypatch.setattr(pipeline.vectordb, "connect", …)` — cùng một đối tượng module, và lệnh của ca
test chạy **sau** fixture `autouse` nên đè lên được. Phải xác minh lúc cài, không giả định.

## Ngoài phạm vi

- **Neo4j.** Main đã có `push_one_doc` cho đường một-văn-bản, `push_corpus` cho đường corpus —
  chúng không đâm nhau. Lý do loại trừ trong spec `2026-08-13-ingest-tang-dan` vẫn đúng: đồ thị
  không tốn embedding, và cạnh quan hệ là dữ liệu toàn corpus.
- **Đóng T1.** Main đã đóng, không mở lại.
- **`web/`.** Thay đổi nghĩa `n_chunks` đã xong ở `feat/ai`; lần hoà này không đụng thêm.

## Trình tự

1. `git merge origin/main` vào `feat/ai` — **không rebase**, quy ước repo cấm rebase sau khi push.
2. Giải xung đột theo các luật trên.
3. Viết lại mô tả PR #24 cho đúng trạng thái sau hoà: phần thật sự mới còn lại là phát hiện-đổi
   bằng vân tay, ghi không-cửa-sổ, dọn chunk mồ côi, chặn xoá văn bản dư, chính sách index FTS, CLI.
