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

## 2c · Precision thật ở tầng cặp điều khoản — 10/08

Nhãn cũ (`expect_conflict`) gắn cho **câu hỏi**; bộ phát hiện làm việc trên **tập chunk**. Bộ
nhãn mới `eval/mau_thuan_vang.jsonl` gắn vào **cặp điều khoản** nên không mục khi retrieval
đổi: kỳ vọng của mỗi lượt = cặp vàng có **đủ hai phía** trong chunk lấy về.

5 cặp vàng (xác minh tay: đủ hai phía trong `data/corpus.real.json`, số liệu khớp), 27 ca,
`flash-lite`, bỏ **0/27** ca. Kết quả: `results/precision-cap-20260810-094112.json`.

| chính sách | recall | precision |
|---|---|---|
| A · không lọc | 8/10 = **0,800** | 8/55 = **0,145** |
| C · chỉ cặp nội bộ×luật | 8/10 = **0,800** | 8/13 = **0,615** |

**Hai điều số này nói mà `conflict_recall` không nói được.**

1. **Recall thật là 0,800, không phải 7/7.** Con số cũ hỏi *"ca này có sinh cảnh báo nào
   không"*; ở tầng cặp thì **2/10 cặp bị bỏ sót**. Cùng một cảnh báo có thể "đúng ca, sai cặp".
2. **Không lọc thì precision 0,145** — 47/55 cảnh báo là nhiễu. Lọc cặp nội bộ×luật đưa lên
   **0,615**, gấp 4,2 lần, **recall không đổi**. Đây là bằng chứng đúng thước cho quyết định
   ở §2b, thay cho con số "ca âm bị báo" vốn còn lẫn ca đúng.

**Cặp duy nhất bị bỏ sót** (bỏ ở cả hai ca chạm tới nó): `SHB-QD-VI-2023::Mục 4.2 ↔
TT40-2024::Điều 25` (nạp tiền mặt tại quầy vào ví). Log cho thấy bộ phát hiện **có** xử lý Mục
4.2 nhưng ghép nó với `TT40-2024::Điều 37 Khoản 1(i)(vi)` và `Điều 25 Khoản 1(a)` — hai địa chỉ
không quy được về chunk nào trong tập lấy về. Nghĩa là **chunk chứa khoản 1 Điều 25 không được
truy hồi**: đây là lỗ hổng truy hồi, không phải phán định. Cần xác nhận rồi mới sửa.

**Chốt chặn lượt đo vô hiệu.** `do_precision_cap.py` báo hỏng và thoát mã 1 khi bỏ quá 15% ca
hoặc không ca nào có kỳ vọng. Có chốt vì đã vấp thật cùng ngày: LanceDB Cloud rớt liên tục,
14/27 ca bị bỏ — trong đó **cả 7 ca có mâu thuẫn** — mà bảng vẫn in `recall 0/0` trông như một
kết quả. Lượt đó đã bị huỷ, không lưu.

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

## 3b · `review.py` — phép chấm đầu tiên, 10/08

Trước hôm nay đường đối chiếu tuân thủ **chưa có một con số nào**. Bộ nhãn
`eval/tuan_thu_vang.jsonl` cố ý **nhỏ và sạch**: 5 mục nội bộ có mâu thuẫn cài sẵn + 2 mục đối
chứng (thuần chính sách phí, không có điểm va với luật). 7 mục còn lại của 4 văn bản SHB
**không gắn nhãn** — chưa ai từng phát biểu verdict đúng cho chúng, và tự gán rồi tự chấm là
tự chấm bài của mình.

Đối chiếu với **toàn bộ 22 văn bản external**, không phải nhóm chọn sẵn — người dùng thật
không biết trước điều nội bộ va vào luật nào. `flash-lite`, 2 lượt. Kết quả:
`results/tuan-thu-20260810-100405.json`.

| | lượt 1 | lượt 2 |
|---|---|---|
| đúng | 6/7 | 6/7 |
| nửa đúng (`warning`) | 1 | 1 |
| **sai** | **0** | **0** |
| chưa đánh giá | 0 | 0 |
| tỷ lệ đúng | 0,857 | 0,857 |

**Hai lượt trùng khớp từng mục** — `temperature=0` cộng self-consistency 2+1 lượt của
`_judge` cho kết quả tái lập được, khác hẳn `conflict.py` nơi số cảnh báo nhảy 80↔32 giữa hai
lượt.

**Không ca nào nói "đạt" về một quy định trái luật.** Đây là kiểu hỏng nguy hiểm nhất của sản
phẩm và nó không xảy ra — `bo_sot_vi_pham()` tách riêng chỉ số này chính vì thế.

Điểm trừ duy nhất: `SHB-QD-TK-2022::Mục 2.3` (eKYC từ đủ 14 tuổi trong khi TT17-2024 Điều 11
đòi đủ 15) ra `warning` thay vì `violation`, ổn định ở cả hai lượt. Bắt được mùi nhưng không
dám kết luận. Chưa truy nguyên nhân.

## 4 · Còn nợ ở tầng đo này

- **`run_benchmark` không đo precision.** Nó chỉ gọi `detect_conflicts` khi `expect_conflict`
  là true (7/36 câu), nên một bộ phát hiện báo động mọi thứ vẫn đạt `conflict_recall` 7/7.
  `so_sanh_phan_dinh.py` chạy cả 20 ca âm chính là để bịt chỗ này.
- ~~Nhãn đang gắn sai tầng.~~ **Đã sửa 10/08 — xem §2c.** `eval/mau_thuan_vang.jsonl` gắn nhãn
  vào cặp điều khoản, `eval/cham_mau_thuan.py` chấm, `eval/do_precision_cap.py` chạy.
- **Cặp `Mục 4.2 ↔ TT40 Điều 25` chưa bao giờ bắt được** — nghi do chunk chứa khoản 1 Điều 25
  không lọt vào tập truy hồi. Chưa xác nhận, đừng sửa trước khi xác nhận.
- ~~Chưa phân tích mức nghiêm trọng của cảnh báo thừa.~~ **Đã đo 10/08 — xem §2b.** Giả thuyết
  "phần lớn là `info`" **đúng về tỷ lệ** (~70% ở cả hai nhóm) nhưng **sai về tác dụng**: lọc
  `severity` chỉ đưa ca âm từ 8/20 xuống 5/20, còn lọc theo **cặp nguồn** xuống 4/20 và làm
  luôn phần việc của lọc severity.
- ~~`review.py` chưa có phép đo nào.~~ **Đã chấm 10/08 — xem §3b.** Còn lại ở đó:
  `SHB-QD-TK-2022::Mục 2.3` ra `warning` thay vì `violation`, ổn định qua hai lượt — chưa truy
  nguyên nhân. Và bộ nhãn mới phủ 7/12 mục nội bộ; 5 mục kia cần người có thẩm quyền phát biểu
  verdict đúng trước khi đo được.
