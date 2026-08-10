# T5 — Cho luồng `/admin` duyệt văn bản chạy được thật

> Ngày: 2026-08-10 · Nhánh: `feat/software` · Mục tồn đọng: **T5** trong `docs/TASKLIST.md`
>
> Trạng thái trước thiết kế này: bucket `legal-docs` rỗng, bảng `legal_documents` rỗng —
> **chưa văn bản nào từng đi qua workflow duyệt** trên production. `app/core/corpus.py`
> fallback về file đóng gói trong image nên sản phẩm vẫn chạy, và đó chính là lý do
> không ai phát hiện.

## 1. Nguyên nhân gốc

**"Admin" trong hệ này có hai định nghĩa độc lập, không cái nào ghi sang cái kia.**

| Nơi hỏi | Hỏi cái gì | File |
|---|---|---|
| FastAPI `require_admin` | `app_metadata.role` trong JWT | `app/core/auth.py:68` |
| Web (4 chỗ) | `app_metadata.role` trong JWT | `app-sidebar.tsx:39`, `user-menu.tsx:17,23`, `admin/page.tsx:50` |
| RLS `is_admin()` | `public.profiles.role` | `supabase/migrations/0001_init.sql:104` |

Trigger `handle_new_user` luôn tạo profile với `role` mặc định `staff`, còn `app_metadata`
thì không đường nào tự đặt. Chính comment ở `0001_init.sql:15` đã thú nhận yêu cầu này —
*"đồng bộ role vào app_metadata do backend/admin làm"* — tức một bước bắt buộc chỉ tồn tại
trong một dòng chú thích.

Hệ quả: luồng `/admin` hỏng theo hai kiểu khác nhau tuỳ người vận hành sửa chỗ nào.

- Chỉ đặt `profiles.role='admin'` → FastAPI chặn ở `require_admin`, trả 403, **chưa từng
  chạm Supabase**.
- Chỉ đặt `app_metadata.role='admin'` → FastAPI cho qua, rồi chết sâu bên trong khi
  `upload_storage` và `insert_document` đụng RLS.

Đây là giả thuyết khớp với triệu chứng "bucket rỗng, bảng rỗng" hơn hẳn giả thuyết hiệu
năng: không phải chạy rồi hỏng, mà là **chưa bao giờ qua nổi cửa đầu tiên**.

### 1b. Một giả thuyết đã bị số đo bác bỏ

Bản nháp đầu của thiết kế này cho rằng `approve_document` sẽ **timeout**, vì nó gọi
`ingest_docs` — nạp lại toàn bộ corpus, đồng bộ, ngay trong request — trong khi Cloud Run
đặt `timeoutSeconds=300`, `memory=512Mi`, `cpu=1000m`.

Đo lại thì **sai**: phần nặng nhất là embedding và nó chỉ ~52 giây cho cả 661 chunk. Một
lượt duyệt đầy đủ ước chừng 90–120 giây, **vẫn nằm trong trần 300 giây**. Bấm approve hôm
nay nhiều khả năng chạy được, chỉ là chậm — nếu qua được cửa quyền.

Ghi lại ở đây để không ai đi lại con đường đó.

## 2. Số đo (10/08, LanceDB Cloud, trên bảng thăm dò riêng — không đụng bảng đang phục vụ)

```
embed 23 chunk (1 thông tư)                1,79s
embed cả 661 chunk (suy ra)                ~52s
delete theo doc_id + add 23 hàng           1,23s
FTS thấy hàng mới                          13s      (tự cập nhật, KHÔNG dựng lại chỉ mục)
vector search thấy hàng mới                ngay
Cloud Run                                  300s · 512Mi · 1000m
```

Số này nói: nạp lại toàn bộ **không phải** vấn đề thời gian, mà là vấn đề **cái giá và
tính sẵn sàng** — `write_lancedb` gọi `create_table(mode="overwrite")`, tức mỗi lần duyệt
một văn bản là ghi đè cả bảng đang phục vụ trong lúc người dùng đang tra, và embed lại 660
chunk không hề đổi. Tăng dần đưa việc đó xuống ~3 giây, chỉ đụng số hàng của đúng văn bản
vừa duyệt.

## 3. Phạm vi

**Trong phạm vi:** một nguồn sự thật cho vai trò; `ingest_one_doc`; xử lý lỗi của
`approve_document`; tài liệu cấp quyền admin; một lượt chạy thật trên production.

**Ngoài phạm vi:** worker/hàng đợi chạy nền; đổi model embedding; T19 (nghiệm thu truy hồi
không cần đăng nhập); giao diện `/admin` (giữ nguyên).

## 4. Thiết kế

### 4.1 Vai trò — một nguồn sự thật

Đổi `is_admin()` sang đọc đúng chỗ FastAPI và web đang đọc:

```sql
create or replace function public.is_admin()
returns boolean language sql stable set search_path = ''
as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', 'staff') = 'admin';
$$;
```

Bỏ `security definer` vì hàm không còn đọc bảng nào.

**`public.profiles.role` sau thay đổi này không còn ai đọc** — không backend, không web,
không RLS. Cân nhắc rồi **quyết định giữ nguyên cột**, chỉ thêm comment đánh dấu nó đã
chết. Lý do: lỗ hổng leo thang quyền (policy `profiles: sửa của mình` ở `0001:110` không có
`with check` nên user tự đặt được `role='admin'` cho chính mình) tồn tại *chỉ vì* `is_admin()`
đọc cột đó; đổi hàm là lỗ hổng tắt theo. `drop column` là lệnh không lùi được trên dữ liệu
thật để đổi lấy sự gọn mắt, còn trigger khoá cột thì nhiều dòng hơn cho đúng số 0 lợi ích ấy.

Cấp quyền admin là **thao tác tay trên Supabase Dashboard** (Auth → Users → user →
`app_metadata` → `{"role": "admin"}`), cố ý để tay: chỉ service-role đặt được `app_metadata`,
mà dự án đã quyết không giữ service-role key trong backend (`app/core/appdb.py` docstring).
Ghi các bước vào tài liệu, không viết script cần key.

Sửa kèm: comment sai ở `0001_init.sql:91` (*"Backend FastAPI dùng service-role key (bypass
RLS)"*) — quyết định đã đổi từ lâu, chú thích thì chưa.

### 4.2 `ingest_one_doc` — nạp lại đúng một văn bản

Đặt cạnh `ingest_docs` trong `app/ingestion/pipeline.py`, dùng lại nguyên `build_chunks`,
`_embed_rows`, `_FTS_OPTS` đang có.

```
ingest_one_doc(doc, rels_cua_doc) -> int
  1. kiểm doc_id khớp ^[A-Za-z0-9._-]+$   (xem 4.4)
  2. rows = build_chunks([doc]); _embed_rows(rows)
  3. bảng chưa tồn tại  -> create_table + create_fts_index
     bảng đã tồn tại    -> delete("doc_id = '<id>'") rồi add(rows)
  4. Neo4j (nếu bật): MERGE node của doc; xoá cạnh ĐI RA của đúng node đó rồi
     dựng lại từ rels_cua_doc; sinh node rỗng cho đích ngoài corpus
  5. trả về số chunk
```

Điểm mấu chốt ở bước 4: **không `DETACH DELETE` toàn bộ `Document` nữa**. Cạnh `THUOC` của
lớp phủ (`DonVi → Document`) là cạnh *đi vào* node văn bản, nên nó không bị đụng, và cái nợ
"phải nhớ gọi lại `push_overlay` sau mỗi `push_corpus`" biến mất ở đường này.

**Giới hạn đã biết:** văn bản vừa duyệt mà lại có mặt trong artefact lớp phủ thì cạnh `THUOC`
của nó chưa được dựng (artefact sinh offline từ `data/raw/vbpl/raw/`, không có trong image).
Hiếm, và cách xử là chạy lại `push_overlay` — ghi vào tài liệu, không tự động hoá cho một ca
chưa từng xảy ra.

Nhãn chunk: `_lam_duy_nhat` khử trùng **trong phạm vi một điều**, không phải toàn corpus, nên
nạp một văn bản cho ra nhãn y hệt nạp cả corpus. Đã kiểm ở `pipeline.py:171`.

### 4.3 `approve_document` — thứ tự ghi và hỏng giữa chừng

**Giữ nguyên thứ tự hiện tại**: ghi Storage → `invalidate_cache` → ingest → đổi status →
change events → audit. Lý do chọn thứ tự này chứ không đảo lại:

- Storage hỏng trước ⇒ chưa có gì đổi ở đâu cả.
- Ingest hỏng sau ⇒ thư viện thấy văn bản nhưng tra chưa ra. Chat sẽ không trích dẫn thứ nó
  không tìm thấy, nên không có trích dẫn gãy. Đảo lại thì ngược: retrieval có văn bản mà thư
  viện không dựng được trang, tức trích dẫn trỏ vào 404.
- `status` vẫn `pending` khi ingest hỏng ⇒ nhìn là biết dở dang.

Thay đổi duy nhất: bọc bước ingest, hỏng thì trả **502** kèm câu nói rõ corpus canonical đã
cập nhật còn chỉ mục thì chưa, bấm duyệt lại là đủ. Bấm lại an toàn vì `delete + add` và
upsert Storage đều lặp lại vô hại.

`ingest_docs` (nạp toàn bộ) **giữ nguyên** cho đường CLI — đó vẫn là cách đúng khi corpus đổi
hàng loạt.

### 4.4 Biên tin cậy

`doc_id` đi thẳng vào chuỗi điều kiện của `tbl.delete(...)`, mà nó đến từ JSON admin sửa được
bằng tay. Kiểm `^[A-Za-z0-9._-]+$` trước khi dùng, không khớp thì **422** kèm lý do. Không
thoát chuỗi, không đoán: bộ ký tự này phủ đủ mọi `doc_id` đang có (`TT40-2024`, `ND101-2012`,
nhóm nội bộ SHB) và từ chối phần còn lại.

## 5. Kiểm thử

| Ca | Kiểm cái gì |
|---|---|
| `ingest_one_doc` chỉ đụng văn bản của nó | Nạp doc A rồi doc B, chunk của A còn nguyên số lượng và nội dung |
| `ingest_one_doc` thay chứ không nhân đôi | Nạp doc A hai lần, số hàng của A không đổi |
| Bảng chưa tồn tại | Nhánh `create_table` chạy được, có chỉ mục FTS |
| `doc_id` bẩn bị chặn | `doc_id` chứa `'` hoặc khoảng trắng ⇒ 422, và **không** có lệnh delete nào phát đi |
| Ingest hỏng ⇒ status giữ `pending` | Giả lập lỗi ingest, kiểm response 502 và `update_document` không bị gọi với `approved` |
| `is_admin()` đọc JWT | Test SQL trên migration: claim có/không có `app_metadata.role` |

Backend chạy `uv run pytest -q` + `uv run ruff check .` trước khi push.

## 6. Nghiệm thu trên production (phần T5 thực sự đòi)

Test xanh **không** chứng minh được điều T5 hỏi. Cần một lượt chạy thật, theo đúng bài học
của T9 và T17 — nghiệm thu bằng thứ đúng chỗ chứ không nhìn exit code:

1. Cấp `app_metadata.role='admin'` cho một tài khoản trên Dashboard, đăng nhập lại lấy JWT mới.
2. Upload một văn bản nhỏ qua `/admin`.
3. Approve.
4. Kiểm bốn chỗ, tất cả **trên dữ liệu đang phục vụ**:
   - `legal-docs/corpus.json` tồn tại và chứa `doc_id` vừa duyệt (trước đó bucket rỗng);
   - `legal_documents` có hàng với `status='approved'`;
   - LanceDB: số hàng của `doc_id` đó đúng bằng số chunk, và tổng số hàng của các văn bản
     khác **không đổi** (đây là thứ chứng minh "tăng dần", không phải "nạp lại");
   - Neo4j: có node `Document` của văn bản đó, và số cạnh `THUOC` **không đổi** (chứng minh
     lớp phủ không bị `DETACH DELETE` cuốn theo).

Ghi kết quả vào `docs/WORKLOG.md` và đóng T5 trong `docs/TASKLIST.md`.

## 7. Rủi ro

- **Đổi `is_admin()` là đổi RLS trên production.** Nếu chưa tài khoản nào có
  `app_metadata.role='admin'` thì ngay sau migration **không ai là admin** — đúng như hiện
  trạng, không tệ hơn, nhưng phải cấp quyền trước khi thử duyệt.
- **BM25 trễ ~13 giây** mới thấy văn bản mới. Vector thấy ngay, nên trong 13 giây đó truy hồi
  vẫn ra kết quả, chỉ là thiếu một nhánh. Chấp nhận; ghi vào tài liệu.
- **Chưa từng có ai chạy hết luồng này**, nên bước 6 gần như chắc chắn sẽ lộ thêm thứ chưa
  biết. Đó là mục đích của nó.
