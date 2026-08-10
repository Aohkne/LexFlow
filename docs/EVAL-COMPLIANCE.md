# EVAL-COMPLIANCE — lịch sử đo tầng phán định tuân thủ

> Nhật ký **số đo** của đường compliance: phát hiện mâu thuẫn (`app/reasoning/conflict.py`) và
> đối chiếu tuân thủ (`app/reasoning/review.py`). Mỗi mục ghi ngày đo, cách đo, và **giá phải
> trả** — để lần sau quyết có chạy lại hay không thì có căn cứ.
>
> Đo truy hồi (R@k, P@k, MRR@k) nằm ở `docs/EVAL-IR.md` — khác thước, khác mục đích.
>
> Cách dựng lại mọi số dưới đây:
> ```powershell
> uv run python -u eval/run_benchmark.py                    # 36 câu, mọi cột
> uv run python -u eval/so_sanh_phan_dinh.py --lap 3 --mau-am 20   # so model phán định
> ```

---

## 1 · Lịch sử `conflict_recall` (từ `eval/run_benchmark.py`)

| ngày | artefact | mâu thuẫn | citation | tránh hết hiệu lực (baseline → LexFlow) | p50 retrieval | file |
|---|---|---|---|---|---|---|
| 06/08 | lớp phủ 178 cạnh | 6/7 | 36/36 | 21/36 → 36/36 | 5.028 ms | `results/20260806-072821.json` |
| 10/08 | lớp phủ 177 cạnh + vá chunking | **7/7** | 35/35 | 21/35 → 35/35 | 3.970 ms | `results/20260810-073306.json` |

**6/7 → 7/7 là do đâu.** Ca trượt là *"Số dư tối đa trên thẻ trả trước vô danh là bao nhiêu?"*
(nội bộ SHB 20 triệu vs TT18-2024 Đ13.4 trần 5 triệu). Không phải lỗi truy hồi (lấy đủ hai
phía), không phải nhiễu (trượt 5/5 lần), không phải prompt (gọi thẳng `chat_json` bắt 3/3).
Mô hình trả `"TT18-2024::Điều 13 Khoản 4"` — **chi tiết hơn** nhãn chunk `"TT18-2024::Điều 13"`
— nên `by_id.get()` trượt và cảnh báo bị bỏ **trong im lặng**. PR #16.

10/08 có **1/36 câu lỗi** (`HttpError` từ LanceDB Cloud, mạng thoáng qua), bị loại khỏi mẫu số
theo đúng thiết kế của `run_benchmark`, nên các tỷ lệ tính trên 35.

## 2 · So model phán định — 10/08

`eval/so_sanh_phan_dinh.py`, retrieval chạy **một lần** dùng chung nên khác biệt là của riêng
phán định. 7 ca CÓ mâu thuẫn × 3 lượt + 20 ca KHÔNG × 1 lượt. Kết quả:
`results/sosanh-20260810-082207.json`.

| model | recall | ổn định (3/3 lượt) | báo thêm ngoài nhãn | giây | USD |
|---|---|---|---|---|---|
| `gemini-2.5-flash-lite` | 7/7 | 7/7 | 8/20 | 328,8 | 0,042 |
| `gemini-2.5-pro` | 7/7 | 7/7 | 4/20 | 638,8 | **0,911** |

**Recall y hệt, độ ổn định y hệt.** Khác biệt duy nhất nằm ở số cảnh báo phát sinh ngoài nhãn,
và `pro` đắt hơn **21,7 lần**, chậm gấp đôi.

### Vì sao chưa đổi sang `pro`

Cột "báo thêm ngoài nhãn" **không phải** precision: nhãn `expect_conflict` gắn cho **câu hỏi**,
còn bộ phát hiện chạy trên **chunk lấy về**. Soi tay ca cả hai model đều báo:

> *"Tổng hạn mức rút tiền mặt của thẻ tín dụng trong một tháng là bao nhiêu?"* — không gắn
> `expect_conflict`, nhưng truy hồi lấy về `TT18-2024::Điều 13` **và** `SHB-QD-THE-2023::Mục
> 5.2`, và bộ phát hiện chỉ ra luật cho rút ngoại tệ 30tr/ngày còn SHB cho hạng Kim cương
> 80tr/ngày. Đó **đúng là một mâu thuẫn cài sẵn** của corpus (`docs/CORPUS.md`).

Tức là ít nhất một phần "báo thêm" là **báo đúng**, chỉ là bộ nhãn không ghi. Quyết định đổi
model dựa trên một con số đang lẫn hai thứ khác nhau là quyết định trên nền cát.

**Việc phải làm trước:** gắn nhãn ở đúng tầng bộ phát hiện làm việc (tập chunk lấy về), rồi mới
đo lại. Xem §4.

## 2b · Lọc cảnh báo — 10/08: một bộ lọc miễn phí bằng con model đắt gấp 21 lần

Đo trên cùng bộ (7 ca CÓ mâu thuẫn + 20 ca KHÔNG), `gemini-2.5-flash-lite`, đo ở mức **CA**
chứ không phải mức cảnh báo. Kết quả: `results/loc-canh-bao-20260810-085822.json`.

| chính sách | recall | ca âm bị báo | tổng cảnh báo |
|---|---|---|---|
| A · không lọc (hiện trạng cũ) | 7/7 | 8/20 | 32 |
| B · bỏ `severity=info` | 7/7 | 5/20 | 22 |
| **C · chỉ cặp nội bộ×luật** | **7/7** | **4/20** | **13** |
| D · cả hai | 7/7 | 4/20 | 13 |

**Recall không đổi ở mọi chính sách.** Chính sách C đạt đúng **4/20** mà `gemini-2.5-pro` đạt
được ở §2 — nhưng chạy trên `flash-lite`, tức **rẻ hơn 21,7 lần**. D không hơn C nên lọc
`severity` là thừa, không làm.

C không phải mẹo: đầu `conflict.py` **đã tuyên bố** ưu tiên cặp nội bộ↔luật ("rủi ro tuân thủ
lớn nhất") ngay từ đầu — mã chỉ chưa bao giờ thực hiện. Cặp luật↔luật chiếm phần lớn đầu ra cũ
(39/50 ở nhóm dương, 24/30 ở nhóm âm), nên người hỏi *"hạn mức rút tiền thẻ tín dụng"* nhận về
việc TT18 và TT30-2016 lệch nhau chuyện thời hạn tra soát. Đã áp mặc định, có cờ
`chi_noi_bo_voi_luat=False` cho ca rà soát văn bản pháp quy.

**⇒ Không đổi sang `gemini-2.5-pro`.** Lợi thế duy nhất đo được của nó đã lấy lại bằng một bộ
lọc không tốn gì.

**Một cảnh báo về cách đọc số ở tầng này:** *số lượng* cảnh báo rất không ổn định giữa các lượt
— cùng bộ dữ liệu, cùng model, hai lượt đo cho 80 và 32 cảnh báo. Kết luận ở **mức ca** thì ổn
định (7/7 ở cả hai lượt). Đừng so số cảnh báo giữa hai lần chạy.

## 3 · Chi phí — đo thật, không ước

Cách đo: bọc `client.models.generate_content` đọc `usage_metadata` của chính response. Giá tra
ngày **2026-08-10** tại `ai.google.dev/gemini-api/docs/pricing`, paid tier, USD/1M token —
flash-lite `0,10 / 0,40` · flash `0,30 / 2,50` · pro `1,25 / 10,00` · embedding-001 `0,15`.
Token "suy nghĩ" tính theo giá output.

| phép đo | lượt gọi | token vào | token ra | thời gian | USD |
|---|---|---|---|---|---|
| `run_benchmark.py` 36 câu | 14 chat + 36 embed | 38.095 | 7.593 | 12,1 phút | **0,0070** |
| so model — flash-lite | 37 | 93.394 | 81.787 | 5,5 phút | 0,042 |
| so model — pro | 37 | 93.394 | 79.463 | 10,6 phút | 0,911 |

Kết luận thực dụng: **tiền không phải ràng buộc** ở quy mô này — một lượt benchmark đầy đủ tốn
~181 VNĐ. **Thời gian đồng hồ mới là cái giá thật.**

Con số embedding của lượt benchmark là **ký tự quy đổi** (~723 token từ 2.529 ký tự), không
phải token đo được: API embed không trả `usage_metadata`. Nó chiếm ~1,5% tổng nên sai số ở đó
không đổi kết luận.

## 4 · Còn nợ ở tầng đo này

- **`run_benchmark` không đo precision.** Nó chỉ gọi `detect_conflicts` khi `expect_conflict`
  là true (7/36 câu), nên một bộ phát hiện báo động mọi thứ vẫn đạt `conflict_recall` 7/7.
  `so_sanh_phan_dinh.py` chạy cả 20 ca âm chính là để bịt chỗ này.
- **Nhãn đang gắn sai tầng.** `expect_conflict` mô tả câu hỏi; bộ phát hiện làm việc trên tập
  chunk. Cần nhãn ở mức "tập chunk này có chứa cặp mâu thuẫn thật nào" thì mới nói được
  precision. Đây là điều kiện tiên quyết để quyết chuyện đổi model.
- ~~Chưa phân tích mức nghiêm trọng của cảnh báo thừa.~~ **Đã đo 10/08 — xem §2b.** Giả thuyết
  "phần lớn là `info`" **đúng về tỷ lệ** (~70% ở cả hai nhóm) nhưng **sai về tác dụng**: lọc
  `severity` chỉ đưa ca âm từ 8/20 xuống 5/20, còn lọc theo **cặp nguồn** xuống 4/20 và làm
  luôn phần việc của lọc severity.
- **`review.py` chưa có phép đo nào.** Toàn bộ mục này nói về `conflict.py`. Đường đối chiếu
  tuân thủ (verdict violation/warning/pass, self-consistency 2+1 lượt) chưa từng được chấm.
