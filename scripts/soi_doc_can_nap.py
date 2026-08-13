"""Đối chiếu `data/corpus.real.json` với bảng LanceDB đang phục vụ. CHỈ ĐỌC, không ghi gì.

Không có bước này thì một lệch kiểu (`None` so với `""`) làm mọi vân tay khác nhau, `can_nap`
thành toàn bộ corpus, và ingest tăng dần thoái hoá về ingest toàn bộ — vẫn ra kết quả đúng,
vẫn tốn đúng ngần ấy tiền, không ai biết.

Chạy: uv run python scripts/soi_doc_can_nap.py

Kết quả 13/08 — ĐỎ, không như brief dự đoán: cần nạp RỖNG (không phải chứa TT66-2025).
```
corpus:  26 văn bản → 661 chunk
bảng:    661 chunk / 26 văn bản

cần nạp (0): (không có)
dư      (0): (không có)

nếu chạy ingest bây giờ: embed 0/661 chunk
```
Đọc theo bảng đối chiếu của task: `cần nạp` rỗng ⇒ ĐỎ (T1 ghi bảng đang giữ 3 chunk cũ của
`TT66-2025 Điều 6`, nên rỗng "không thể xảy ra"). Đã CHẨN ĐOÁN thêm (đọc, không ghi): so từng
cột của 3 chunk `TT66-2025::Điều 6 (phần 1..3)` giữa `build_chunks` và `tbl.search()` — khớp
byte-for-byte (độ dài text 1854/1107/1350, không cắt giữa chữ "ngân"), và quét toàn bảng 661
hàng × 10 cột (trừ `vector`) cho **0 lệch, 0 id chỉ có ở một phía**. Tức KHÔNG phải lệch kiểu
hay vân tay so nhầm — bảng thật trên LanceDB Cloud đã khớp đúng bản vá `8dd53f0` rồi, trong khi
`docs/TASKLIST.md` T1 (viết 09/08) vẫn mô tả nó là "chưa vá". Không tự sửa T1 theo hướng "đã
xong" vì không biết CƠ CHẾ nào đưa bảng tới trạng thái này (ai đó đã chạy ingest? nhánh khác của
`/admin` approve?) — cần chủ repo xác nhận trước khi đóng T1.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import vectordb  # noqa: E402
from app.core.config import LANCEDB_TABLE  # noqa: E402
from app.ingestion.pipeline import _doc_can_nap, build_chunks, load_corpus  # noqa: E402

docs, _ = load_corpus("data/corpus.real.json")
rows = build_chunks(docs)
tbl = vectordb.connect().open_table(LANCEDB_TABLE)

can_nap, du, id_cu = _doc_can_nap(tbl, rows)

print(f"corpus:  {len(docs)} văn bản → {len(rows)} chunk")
print(f"bảng:    {tbl.count_rows()} chunk / {len(id_cu)} văn bản")
print(f"\ncần nạp ({len(can_nap)}): {', '.join(sorted(can_nap)) or '(không có)'}")
print(f"dư      ({len(du)}): {', '.join(sorted(du)) or '(không có)'}")

n = sum(len(r['id']) > 0 for r in rows if r["doc_id"] in can_nap)
print(f"\nnếu chạy ingest bây giờ: embed {n}/{len(rows)} chunk")
