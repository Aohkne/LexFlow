"""Đối chiếu `data/corpus.real.json` với bảng LanceDB đang phục vụ. CHỈ ĐỌC, không ghi gì.

Không có bước này thì một lệch kiểu (`None` so với `""`) làm mọi vân tay khác nhau, `can_nap`
thành toàn bộ corpus, và ingest tăng dần thoái hoá về ingest toàn bộ — vẫn ra kết quả đúng,
vẫn tốn đúng ngần ấy tiền, không ai biết.

Chạy: uv run python scripts/soi_doc_can_nap.py

Kết quả 13/08 — cần nạp RỖNG, khác ca "chứa TT66-2025" mà brief dự đoán, nhưng ĐÃ XÁC MINH là
xanh (xem "chẩn đoán cột" + "đối chứng dương" bên dưới), không phải vân tay so nhầm. Output đầy
đủ, chạy lại được nguyên văn bằng lệnh `Chạy:` ở trên:
```
corpus:  26 văn bản → 661 chunk
bảng:    661 chunk / 26 văn bản

cần nạp (0): (không có)
dư      (0): (không có)

nếu chạy ingest bây giờ: embed 0/661 chunk

chẩn đoán cột: 661 hàng chung × 10 cột → 0 ô lệch
cột lệch: (không có)

đối chứng dương: sửa 1 chunk của 'ND101-2012' (RAM, không ghi bảng) → cần nạp = ['ND101-2012'] — ĐẠT
```
Đối chiếu bảng của task: `cần nạp` rỗng đứng một mình đọc là ĐỎ (T1 ghi bảng đang giữ 3 chunk cũ
của `TT66-2025 Điều 6`, "không thể rỗng"). "Chẩn đoán cột" ở trên chính là phép brief yêu cầu khi
gặp ca lệch kiểu (so từng cột một hàng `build_chunks` cạnh một hàng bảng cùng `id`) — chạy trên
CẢ 661 hàng chung chứ không riêng `TT66-2025`, cho **0 ô lệch trên 10 cột** (kể cả `superseded`:
`bool` Python so `bool` LanceDB trả về khớp, không có `numpy.bool_` hay `None`/`""` lẫn vào).
Bảng thật trên LanceDB Cloud đã khớp đúng bản vá `8dd53f0` (09/08) rồi — triệu chứng T1 mô tả
không còn tồn tại tính đến 13/08; cơ chế đưa bảng tới trạng thái này chưa rõ (không có gì trong
`docs/WORKLOG.md` ghi một lượt ingest sau 09/08).

**Đối chứng dương** (thêm sau khi phát hiện `cần nạp` rỗng): một hàm `_doc_can_nap` luôn trả về
tập rỗng cũng qua được phép thử "0 lệch" ở trên — nó chỉ chứng minh không báo động giả, chưa
chứng minh bắt được thay đổi thật. Sửa một chunk trong RAM (không ghi bảng) rồi gọi lại
`_doc_can_nap`: kết quả bắt ĐÚNG và CHỈ đúng một văn bản đó — ĐẠT. Vậy `cần nạp` rỗng ở lượt đọc
thật là xanh thật, không phải hàm hỏng đang im lặng.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import vectordb  # noqa: E402
from app.core.config import LANCEDB_TABLE  # noqa: E402
from app.ingestion.pipeline import _cot_du_lieu, _doc_can_nap, build_chunks, load_corpus  # noqa: E402

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

# --- Chẩn đoán cột lệch: đúng phép mà brief nói phải làm khi `cần nạp` = toàn bộ văn bản (so
# TỪNG CỘT một hàng `build_chunks` cạnh một hàng bảng cùng `id`, tìm cột lệch KIỂU — `None` so
# `""`, `bool` so `numpy.bool_`), gộp thẳng vào đây thay vì viết script tạm rồi xoá: lượt chẩn
# đoán ca `cần nạp` rỗng 13/08 đã làm đúng phép này một lần bằng tay, ngoài git — người sau rơi
# vào đúng nhánh đỏ đó không có gì để chạy lại. Đây là lượt quét bảng riêng (không tái dùng được
# lượt trong `_doc_can_nap` vì hàm đó chỉ trả tập hợp, không trả hàng thô) — chấp nhận được vì
# script này chạy tay, không phải trên đường nóng.
cot = _cot_du_lieu(tbl)
tb_by_id = {r["id"]: r for r in tbl.search().select(cot).limit(tbl.count_rows()).to_list()}
bc_by_id = {r["id"]: r for r in rows}
chung = sorted(set(bc_by_id) & set(tb_by_id))

lech = [
    (i, k, bc_by_id[i].get(k), tb_by_id[i].get(k))
    for i in chung
    for k in cot
    if bc_by_id[i].get(k) != tb_by_id[i].get(k)
    or type(bc_by_id[i].get(k)) is not type(tb_by_id[i].get(k))
]
cot_lech = sorted({k for _, k, _, _ in lech})
print(f"\nchẩn đoán cột: {len(chung)} hàng chung × {len(cot)} cột → {len(lech)} ô lệch")
print(f"cột lệch: {cot_lech or '(không có)'}")
for i, k, va, vb in lech[:20]:
    print(f"  id={i!r} cột={k!r} build={va!r} ({type(va).__name__}) bảng={vb!r} ({type(vb).__name__})")

# --- Đối chứng dương: sửa một chunk TRONG BỘ NHỚ, không ghi gì lên bảng ---
# Lượt trên chỉ chứng minh "không báo động giả" (`cần nạp` rỗng) — một `_doc_can_nap` luôn trả
# về tập rỗng (bug) cũng qua được phép thử đó. Lượt này chứng minh "báo được khi có thật đổi":
# sửa đúng MỘT chunk của MỘT văn bản, kỳ vọng vân tay bắt đúng NGUYÊN văn bản đó, không hơn.
rows_sua = [dict(r) for r in rows]
doc_doi_chung = rows_sua[0]["doc_id"]
rows_sua[0]["text"] += " [ĐỐI CHỨNG]"

can_nap_sua, _, _ = _doc_can_nap(tbl, rows_sua)
dat = can_nap_sua == {doc_doi_chung}
print(
    f"\nđối chứng dương: sửa 1 chunk của {doc_doi_chung!r} (RAM, không ghi bảng) "
    f"→ cần nạp = {sorted(can_nap_sua)} — {'ĐẠT' if dat else 'KHÔNG ĐẠT'}"
)
if not dat:
    raise SystemExit(1)
