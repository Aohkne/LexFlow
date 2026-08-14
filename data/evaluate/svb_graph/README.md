# `svb_graph/` — bộ test của bài báo SBV-LawGraph

`sbv_testset_tvpl.json` là bộ test 100 câu hỏi-đáp của bài báo SBV-LawGraph
(`docs/paper/ACIIDS2026a.pdf`, ACIIDS 2026), xin trực tiếp từ tác giả bài báo. `eval/chuyen_sbv.py`
đọc file này để sinh `eval/bo_sbv.jsonl` và `eval/bo_sbv_khong_can_cu.jsonl` — xem §11 của
`docs/EVAL-IR.md`.

## Vì sao file KHÔNG có trong repo

File có được do xin phép riêng từ tác giả; việc phát tán lại không phải quyết định của repo này.
Nên file **cố tình không commit** — repo chỉ giữ lại checksum để xác minh, không giữ nội dung.

## Cách lấy lại

Xin file `sbv_testset_tvpl.json` từ tác giả bài báo (hoặc từ nơi bạn đã nhận trước đó), rồi đặt
đúng đường dẫn:

```
data/evaluate/svb_graph/sbv_testset_tvpl.json
```

Trước khi chạy `uv run python eval/chuyen_sbv.py`, **kiểm hash trước**:

```powershell
Get-FileHash data/evaluate/svb_graph/sbv_testset_tvpl.json -Algorithm SHA256
```

## Checksum tham chiếu (đo 2026-08-12)

| Thuộc tính | Giá trị |
|---|---|
| SHA-256 | `75bc6c04c1cdd9e67ead53f1d2111741478ab712367034e8a9642efca7714bd7` |
| Kích thước | 127391 bytes |
| Số bản ghi | 100 (mảng JSON 100 object) |

Hash khác đi nghĩa là dữ liệu khác — split 29/71/100 công bố ở `docs/EVAL-IR.md` §11 sẽ **không**
tái lập được từ một file có hash khác. Đừng chạy `chuyen_sbv.py` trên một bản không khớp hash rồi
so kết quả với số đã công bố.
