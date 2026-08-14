# Plan: nhập 23 văn bản bộ SBV vào corpus phục vụ

*Theo spec `docs/superpowers/specs/2026-08-14-nhap-23-van-ban-sbv-design.md`. Chạm production —
mỗi pha có nghiệm thu, dừng lại cho người duyệt ở pha 2 (maker-checker) trước khi nhập.*

## Pha 0 — Chốt số staging thật (khử bất định trước khi code)

1. Map 23 số hiệu target → file staging bằng `chuan_so_hieu` (không so chuỗi thẳng). Xác nhận đủ
   **23/23** file có mặt trong `data/raw/vbpl/corpus/`. Đã biết 3 lệch chuẩn hoá (94/2025, 26/2025,
   21/2017) — dump `so_hieu` + tên file của 3 cái này, hiểu vì sao lệch, đừng đoán.
2. In bảng: số hiệu · doc_id · `tinh_trang_hieu_luc` · `valid_to` · số điều. Chốt: 3 văn bản hết
   hiệu lực toàn bộ (TT32-2024, TT37-2024, TT45-2024) có `valid_to`; 9 "một phần" `valid_to` trống.
- **Nghiệm thu:** 23/23 map được, bảng in ra khớp con số đã đo 14/08.

## Pha 1 — Script gộp `scripts/gop_corpus_tu_staging.py`

Đọc danh sách file staging (hoặc `--tu-thu-muc`), với mỗi file:

1. Lấy subset field corpus: `doc_id, title, doc_type, source, valid_from, valid_to, so_hieu, articles`.
2. Chuyển article schema: mỗi điều giữ `article, text, superseded`; **bỏ** `chapter, section,
   char_start, char_end`; **KHÔNG** thêm `valid_from/valid_to` cấp điều.
3. Guard: nếu `doc_id` đã có trong `corpus.real.json` → bỏ qua + báo tên (idempotent, không nhân đôi).
4. APPEND vào `documents`; KHÔNG đụng `relationships`. Ghi lại `corpus.real.json` giữ nguyên thứ tự
   khoá, indent như cũ (giảm nhiễu diff).
5. In tóm tắt: N văn bản thêm, M bỏ qua (đã có), tổng điều thêm.

- **Test** `tests/test_gop_corpus.py` (thuần, không mạng): schema ra đúng subset, article đã lược
  field, guard trùng doc_id chặn, `valid_to` của văn bản hết hiệu lực toàn bộ được giữ.
- **Nghiệm thu:** `uv run pytest tests/test_gop_corpus.py -q` + `ruff` xanh.

## Pha 2 — Dựng nháp + MAKER-CHECKER (dừng cho người duyệt)

1. Chạy script trên bản `corpus.real.json` thật (đã commit trước đó nên `git diff` sạch để soi).
2. **`git diff data/corpus.real.json`** — kiểm bằng mắt:
   - Đúng 23 văn bản mới xuất hiện, **0 văn bản cũ đổi một ký tự**.
   - 3 văn bản hết hiệu lực toàn bộ có `valid_to` đúng ngày.
   - doc_type/title hợp lý; doc_id đúng quy ước.
3. Kiểm 23 doc_id mới tra được ở bảng khoá web (`tach_khoa`) — không lặp lại ca T10/T15 (link tới
   trang trống).
- **DỪNG: người (anh) duyệt diff trước khi sang pha 3.** Đây là cổng maker-checker, không tự vượt.

## Pha 3 — Nhập (LanceDB tăng dần + Neo4j)

1. `uv run python -m app.ingestion data/corpus.real.json` — theo dõi log:
   - **chỉ 23 văn bản embed**; 26 cũ in "không đổi — bỏ qua embedding" (nếu 26 cũ cũng embed lại →
     DỪNG, vân tay đang lệch, điều tra trước).
   - Neo4j: 23 node mới (cô lập, không cạnh — đúng Quyết định 4).
2. `uv run python scripts/sync_corpus_storage.py` nếu luồng yêu cầu đồng bộ Storage (kiểm có cần).
- **Nghiệm thu:** LanceDB `count_rows()` tăng đúng ~số chunk 23 văn bản; `/health` không degraded.

## Pha 4 — Cập nhật split eval + đo lại

1. `uv run python eval/chuyen_sbv.py` — `bo_sbv.jsonl` tăng từ 29. **Ghi số THẬT** (kỳ vọng gần 100
   nếu đủ 23 phủ; nếu ít hơn, dump lý do bị loại như script vẫn in — điều thiếu / cửa sổ rỗng).
2. `uv run python -u eval/run_benchmark.py --bo eval/bo_sbv.jsonl` + các bộ cũ
   (`questions.jsonl`, `bo_tvpl_hien_nay`, `bo_tvpl_dung_thoi`).
3. `uv run python -u eval/judge.py` (bộ SBV mở rộng).
- **Nghiệm thu (regression gate):** 36/76/29 câu cũ **KHÔNG tụt** citation/stale/IR; SBV mới có số;
  `stale_avoidance` kiểm lại (3 văn bản chết có thể thành `must_not_doc` mới).

## Pha 5 — Ghi lại

1. `docs/EVAL-IR.md` §11/§12: cập nhật số SBV (29 → N câu), ghi rõ giới hạn "9 văn bản hết hiệu lực
   một phần nạp ở mức doc, chưa curate cấp điều" và "quan hệ Neo4j hoãn".
2. `docs/TASKLIST.md` T113 → đóng; mở task con nếu cần (curate quan hệ / valid_to cấp điều).
3. `docs/WORKLOG.md` entry hôm nhập.
4. **KHÔNG commit** file eval dẫn xuất bộ SBV (đã gitignore). `corpus.real.json`, script gộp, test,
   docs thì commit.

## Quyết định đã chốt (14/08, chủ repo)

- **3 văn bản hết hiệu lực TOÀN BỘ (TT32/37/45-2024): NẠP cả 3 kèm `valid_to`.** `chuyen_sbv.py`
  xử lý cửa sổ đóng (đo tại as_of trước ngày chết); lọc hiệu lực vẫn đúng vì có `valid_to`.
- **9 văn bản hết hiệu lực một phần: nạp ở MỨC DOC**, chưa curate `valid_to` cấp điều đợt này —
  tách task riêng nếu số liệu cần. Ghi rõ giới hạn cạnh bảng kết quả.
