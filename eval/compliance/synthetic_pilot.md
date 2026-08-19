# Pilot dữ liệu synthetic (T30) — 15 case từ 5 CU, đo 18/08

> **Đã người duyệt 18/08** (chủ repo, qua `synthetic_pilot.html`): 12 giữ nhãn · 2 sửa
> `thieu_thong_tin → khong_ap_dung` (Đ25k5, Đ26k1 — điều khoản mơ hồ tới mức "không áp
> dụng" đúng hơn "thiếu thông tin") · 1 loại (NĐ52-Đ26k2::thieu_thong_tin). Nhãn sửa đã
> hợp nhất vào `synthetic_pilot.jsonl` (`nhan_goc` giữ vết, `duyet` ghi quyết định).
>
> **Điểm sau duyệt: 8/14 khớp.** 6 ca lệch còn lại đều là lỗi hệ thống đã xác nhận:
> 4 gate miss (cả 3 biến thể Đ26k1 + Đ13k4::thieu_thong_tin), 1 judge FP phủ-định
> (Đ25k5::tuan_thu — chủ repo ghi chú "judge bỏ qua chữ 'không'"), 1 judge chấm
> `khong_ap_dung` cho cam kết thông báo NHNN mà chủ repo phân xử là `tuan_thu`
> (NĐ52-Đ26k2::tuan_thu).

Sinh điều khoản hợp đồng từ CU luật có ngưỡng/tình thái rõ, **nhãn biết trước theo cách
sinh** (LLM chỉ viết văn, không gán nhãn), rồi chấm bằng đúng pipeline thật
(trich_triples → map_hypernym → lap_cu_plan → phan_dinh). Model sinh = chat model,
model chấm = reasoning model (khác nhau, tránh chung điểm mù).

- Case: `synthetic_pilot.jsonl` · Kết quả thô: `synthetic_pilot.kq.jsonl`
- 5 CU: TT18-Đ13k3 (trần rút tiền mặt thẻ tín dụng 100tr/tháng) · TT18-Đ13k4 (cấm + trần
  thẻ trả trước vô danh 5tr) · TT40-Đ25k5 (cấm nhận tiền mặt nạp ví, cấm cấp tín dụng/trả
  lãi số dư ví) · TT40-Đ26k1 (trần giao dịch ví 100tr/tháng) · NĐ52-Đ26k2 (nghĩa vụ thông
  báo NHNN khi thay đổi nội dung Giấy phép)
- 3 biến thể/CU: `tuan_thu` · `vi_pham` · `thieu_thong_tin` (im lặng về khía cạnh quy định)

## Bài học ngay từ khâu sinh

Lượt sinh đầu: **4/5 case `vi_pham` sai nhãn** — model né viết điều khoản trái luật, thay
bằng điều khoản *xử lý khi vi phạm* ("vượt 100tr sẽ bị từ chối" — bản chất là tuân thủ).
Phải siết prompt ("chính nội dung cam kết phải trái quy định, cấm viết điều khoản chế
tài") mới ra vi phạm thật. ⇒ đúng như dự liệu: nhãn synthetic vẫn cần người duyệt.

## Kết quả: 7/15 khớp end-to-end

| Case (CU::biến thể) | Expected | Gate chọn CU? | Verdict | Khớp |
|---|---|---|---|---|
| Đ13k3::tuan_thu | tuan_thu | ✓ | tuan_thu | ✓ |
| Đ13k3::vi_pham | vi_pham | ✓ | vi_pham | ✓ |
| Đ13k3::thieu_thong_tin | thieu_thong_tin | ✓ | thieu_thong_tin | ✓ |
| Đ13k4::tuan_thu | tuan_thu | ✓ | tuan_thu | ✓ |
| Đ13k4::vi_pham | vi_pham | ✓ | vi_pham | ✓ |
| Đ13k4::thieu_thong_tin | thieu_thong_tin | ✗ gate miss | — | ✗ |
| Đ25k5::tuan_thu | tuan_thu | ✓ | **vi_pham** | ✗ |
| Đ25k5::vi_pham | vi_pham | ✓ | vi_pham | ✓ |
| Đ25k5::thieu_thong_tin | thieu_thong_tin | ✓ | khong_ap_dung | ✗ |
| Đ26k1::tuan_thu | tuan_thu | ✗ gate miss | — | ✗ |
| Đ26k1::vi_pham | vi_pham | ✗ gate miss | — | ✗ |
| Đ26k1::thieu_thong_tin | thieu_thong_tin | ✗ gate miss | — | ✗ |
| NĐ52-Đ26k2::tuan_thu | tuan_thu | ✓ | khong_ap_dung | ✗ |
| NĐ52-Đ26k2::vi_pham | vi_pham | ✓ | vi_pham | ✓ |
| NĐ52-Đ26k2::thieu_thong_tin | thieu_thong_tin | ✗ gate miss | — | ✗ |

Theo biến thể: `vi_pham` **4/5** · `tuan_thu` 3/5 · `thieu_thong_tin` 1/5.

## Ba nhóm lệch — mỗi nhóm một câu hỏi duyệt

### 1 · Gate miss (5 ca) — nặng nhất: TT40-Đ26k1 trượt CẢ 3 biến thể — ĐÃ SỬA 18/08

Case vi_pham của Đ26k1 viết thẳng "hạn mức giao dịch qua ví điện tử cá nhân…
150.000.000 đồng trong một tháng" mà CU trần-100tr không vào plan (plan có 14-23 CU
khác). ~~Nghi subject/label CU nghèo~~ — **probe 18/08 bác giả thuyết đó**: retrieval
trúng "TT40 Điều 26" top-1 cả 3 case, CU CÓ vào ứng viên, rồi bị meta-CU Đ26k2 ("hạn
mức không áp dụng đối với…") **xóa oan**: phép khớp phủ-định cũ nhận hypernym là khớp
khi nó là substring của văn xuôi điều kiện — "giao dịch thanh toán" nằm gọn trong "Các
giao dịch thanh toán: Thanh toán trực tuyến trên Cổng DVC quốc gia; điện; nước…" dù
ngoại lệ thật chỉ dành cho thanh-toán tiện ích/dịch vụ công.

**Fix (gate v3, `PHIEN_BAN_GATE="3"`):** phân bậc chứng cứ — hypernym BẰNG nguyên cụm
`object_label`/`constraint_label` mới được xóa; chỉ substring văn xuôi → fail-open +
cờ `gate_chua_xac_quyet`, judge quyết. Chấm lại 3 case: gate ✓ cả 3; `tuan_thu` ✓,
`vi_pham` ✓ (case 150tr bắt được vi phạm); case im-lặng judge ra `thieu_thong_tin` vs
nhãn duyệt `khong_ap_dung` — thêm một ca biên lớp T29. **Điểm sau fix: 10/14.**

2 gate miss còn lại (đoạn dưới) không đổi.

### Chấm lại toàn bộ 18/08 (từ vựng hypernym mới — premise raw_text + 46 alias corpus)

Sau khi từ vựng hypernym mang định nghĩa (fix "Ngân hàng"→ĐVCNT) và thu hoạch alias
"(sau đây gọi tắt là X)", chấm lại cả 15 case: **9/14** — gate hit **14/15** (chỉ còn
Đ13k4::thieu_thong_tin, artefact chấm từng-điều). Cấu trúc lệch:

| Ca lệch | Diễn giải |
|---|---|
| Đ25k5::tuan_thu → vi_pham | FP phủ-định **lần 2 liên tiếp** ⇒ lỗi ổn định mức prompt, không phải flip — **đã sửa 19/08** (mục 2 dưới), điểm lên 10/14 |
| Đ26k1::thieu_thong_tin → thieu_thong_tin (duyệt: khong_ap_dung) | biên T29 |
| NĐ52-Đ26k2 cả 3 → khong_ap_dung | `vi_pham` case **lật** vi_pham→khong_ap_dung so với lần trước — lần lật thứ 3 đo được của lớp T29, lần này ở cặp vi_pham↔khong_ap_dung |
| Đ13k4::thieu_thong_tin gate miss | việc của lượt toàn-văn |

Điểm giảm 10/14 → 9/14 hoàn toàn do 1 cú lật judge, KHÔNG do từ vựng mới làm hỏng
gate (gate hit tăng 11/15 → 14/15). Không re-roll để câu lại điểm.

2 gate miss còn lại đều là biến thể `thieu_thong_tin` — điều khoản cố tình mơ hồ nên
entity không khớp. **Caveat quan trọng:** trong pipeline thật, bắt "im lặng" là việc của
lượt **toàn-văn** (lap_plan_toan_van), pilot này chỉ chấm từng điều đơn lẻ ⇒ 1/5 của
thieu_thong_tin KHÔNG được đọc là recall thật của lớp này.

### 2 · Judge phán vi_pham cho điều khoản PHỦ ĐỊNH đúng luật (1 ca) — ĐÃ SỬA 19/08

Đ25k5::tuan_thu: điều khoản cam kết "**sẽ không** nhận tiền mặt nạp ví, **không** cấp tín
dụng, **không** trả lãi số dư ví" — thuận luật hoàn toàn — nhưng judge ra `vi_pham`, và
can_cu chỉ… chép lại nội dung điều khoản. Nghi model bắt bề mặt cụm "cấp tín dụng/trả
lãi" mà bỏ qua phủ định. Ca false-positive lớp phủ-định đầu tiên đo được.

**Fix 19/08, mất 2 vòng — chẩn đoán ban đầu sai một nửa:** vòng 1 thêm chỉ dẫn trừu
tượng "cam kết KHÔNG làm điều cấm là tuan_thu" vào `_SYSTEM` → vẫn `vi_pham`, nhưng
can_cu lộ bản chất: "*Hợp đồng cam kết không thực hiện hành vi mà luật cấm*" — model
ĐỌC ĐÚNG phủ định, chỉ **đảo nhãn** (lý do tuân thủ, nhãn vi phạm). Vòng 2 thay bằng
ví dụ cặp đôi cụ thể (cấm trả lãi ví: "không được trả lãi"→tuan_thu / "trả lãi
0,5%/năm"→vi_pham) → cả 3 case Đ25k5 đúng, case `vi_pham` thật không regress.
**Điểm sau fix: 10/14.** Đổi `_SYSTEM` cũng đổi khoá cache (vốn đã vô hiệu từ 18/08).

### 3 · Biên thieu_thong_tin ↔ khong_ap_dung (2 ca) — đúng lớp T29

Đ25k5::thieu_thong_tin và NĐ52-Đ26k2::tuan_thu đều bị đẩy sang `khong_ap_dung`. Ca
NĐ52-Đ26k2::tuan_thu có phần lỗi ở **case sinh**: điều khoản cam kết "gửi thông báo NHNN"
chung chung, không nói về thay đổi Giấy phép — judge chê ngoài phạm vi CU cũng có lý.
**Cần chủ repo phân xử nhãn ca này** (giữ tuan_thu hay sửa expected thành khong_ap_dung).

## Đề xuất bước tiếp (chờ duyệt)

1. Duyệt 15 case trong `synthetic_pilot.jsonl` (đặc biệt ca NĐ52-Đ26k2::tuan_thu ở trên).
2. Mở việc sửa lỗ gate TT40-Đ26k1 (kiểm tra subject/label CU trong pred.jsonl).
3. Ca phủ-định (nhóm 2) → thêm vào hàng đợi chất lượng judge; chạy lại vài lần xem có
   phải flip ngẫu nhiên không trước khi sửa prompt.
4. Nếu duyệt đạt: mở rộng dần (thêm CU `chi_duoc`, `cho_phep`; case toàn-văn cho lớp
   thieu_thong_tin) — dữ liệu sinh từ luật công khai nên commit được.
