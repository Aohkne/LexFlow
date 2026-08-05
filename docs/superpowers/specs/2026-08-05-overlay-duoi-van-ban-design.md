# Thiết kế: lớp phủ dưới-văn-bản (overlay Điều/Khoản/Điểm)

*Brainstorm 05/08/2026, đã duyệt. Ba câu chốt với người dùng: mục tiêu **CU/compliance + Q&A** ·
sống ở **PoC offline trước** · trục thời gian **chỉ-hiện-tại trước** (không đóng đường as-of).*

## Bài toán

Đồ thị hiện có 26 node cấp văn bản + 35 cạnh curated; truy vấn §6.2 đã chạy thật. Nhưng
tầng CU/Q&A cần biết **khoản nào còn hiệu lực và bản hiện hành viết gì** — mà ngữ nghĩa sửa
đổi sống ở cấp khoản (*"sửa điểm c khoản 7 Điều 8"*), không phải cấp văn bản. Đồng thời Q&A
đang có một lỗi im lặng: chunk rơi vào khối trích dẫn của văn bản sửa được trích dẫn dưới
tên văn bản sửa ("TT41 Điều 1") trong khi chữ là của văn bản nền (TT40 Đ8 k7) — lỗ hổng
phạm-vi-đánh-số (§3.8) hiện diện ở tầng retrieval.

## Quyết định kiến trúc: HAI TẦNG, mỗi tầng một loại cạnh

- **Tầng văn bản giữ nguyên** (35 cạnh: `THAY_THE`/`BAI_BO`/`CAN_CU`/`DAN_CHIEU` +
  `SUA_DOI_BO_SUNG` làm tóm tắt). Quan hệ về *số phận cả văn bản* nằm ở đây — "TT15 thay thế
  TT46" không trỏ vào khoản nào cả.
- **Tầng con mới**: cạnh tác động thật nối **con ↔ con**, đúng cấp mà lời văn của luật đặt
  lệnh. Một cạnh văn bản bung ra thành nhiều cạnh con (TT41→TT40 ≈ 30 cạnh).

**Lớp phủ THƯA — chỉ dựng node cho đơn vị "có chuyện để nói"**, đúng triết lý node rỗng
(node chỉ tồn tại khi có cạnh cần đầu mút). Hai vai:

1. *Đích bị tác động* (văn bản nền): `40/2024/TT-NHNN#than/dieu_11#khoan_4#diem_b`.
2. *Nguồn phát lệnh* (văn bản sửa): `41/2025/TT-NHNN#than/dieu_3`.

Đơn vị nguyên vẹn KHÔNG có node — khoá của nó vẫn **tính được tại chỗ** từ chunk-id, và
"không có cạnh nào chạm khoá này" chính là câu trả lời: nguyên vẹn, hiệu lực theo văn bản mẹ.
Quy mô: ~300–400 node trên 26 văn bản (thay vì ~2.900 nếu dựng đủ); crawl thêm thì overlay
tự mọc đúng chỗ mới bị chạm.

## Ngữ nghĩa đi đường nào (không có vector DB thứ hai)

Một LanceDB duy nhất; đồ thị không làm việc ngữ nghĩa. Chunk đã ở cấp khoản
(`id = doc_id::Điều N Khoản M` — `pipeline.build_chunks`). Đồ thị là **bộ định tuyến SAU
truy hồi**, ba nhánh:

1. Hit không chạm overlay (đa số) → dùng thẳng, hiệu lực kế thừa Document.
2. Hit là nền-đã-bị-sửa → cạnh trỏ lời văn mới → thay/chú "bản hiện hành là…".
3. Hit là trích-trong-văn-bản-sửa → map ngược về đích → trích dẫn đúng chủ
   *"TT40 Đ8 k7 (sửa bởi TT41 Đ1)"*.

Pha sau (chờ gật riêng): ~169 đơn vị bị chạm sinh **chunk phái sinh bản-hiện-hành**
(`derived=true` + xuất xứ) vào cùng LanceDB — vì người dùng hỏi bằng từ ngữ hiện hành
("Cục Quản lý, giám sát tổ chức tín dụng" chỉ tồn tại trong lời văn TT66).

## Schema (PoC, JSONL)

- `DonViOverlay`: khoá ba nhánh v0.5 · `doc_id` (cầu `so_hieu`) · `vai` · span.
- `CanhTacDong`: `nguon` · `dich` · `thao_tac` (sua_doi | bo_sung | bai_bo | thay_phu_luc |
  thay_cum_tu — loại cuối chỉ ghi nhận, chưa áp) · `loi_van_moi` (span trong `noi_dung` văn
  bản sửa — bất biến char_span làm xuất xứ) · `valid_from`.
- `PhienBanHienHanh` (suy ra, không lưu tay): text nền + áp tuần tự cạnh
  `valid_from ≤ hôm nay`; xuất xứ từng đoạn là span.

## Nguyên liệu có sẵn

`parser.py` (khoá ba nhánh, `trong_trich_dan` — 11 test ca ND80) · `citation.py` (giải viện
dẫn → khoá node, 23 ca tiết) · `raw/<slug>.json` (`trich_dan`, `dieu_khoan_bi_tac_dong`
169 mục làm **đối chứng độc lập**, cờ `bi_tac_dong`) · `bac_cau.py` (cầu số hiệu ↔ doc_id) ·
oracle `29/VBHN-NHNN` (TT40+TT41, mốc 08/12/2025) nếu tải được PDF.

## Ba pha, đóng bằng số

- **P1** `app/ontology/tac_dong.py`: điều sửa → `CanhTacDong` (viện dẫn qua `citation.py`,
  thao_tac quét IGNORECASE, khối trích qua `trich_dan`). Đối chứng hai chiều với
  `dieu_khoan_bi_tac_dong`, lệch ⇒ cảnh báo có địa chỉ, không nắn. Kỳ vọng ≥90% khớp.
- **P2** dựng overlay + `PhienBanHienHanh` cho TT40 (chuỗi TT40 ← TT41 ← TT22; sửa đổi của
  Đ16/17/18 TT41 đã bị TT22 bãi bỏ thì KHÔNG áp). Đo: char_span 100%, ca bãi-bỏ ra đúng.
- **P3** định tuyến sau truy hồi (hàm thuần): chunk-id → khoá → 3 nhánh. Đo bằng ≥10 câu hỏi
  gắn nhãn tay chạm cả 3 nhánh.
- **P4** (chờ gật riêng): derived chunks vào LanceDB + overlay vào Neo4j.

## Ngoài phạm vi (cố ý)

as-of bất kỳ · áp `thay_cum_tu` · sửa §3.1/§3.2 · VBHN làm nguồn.

## Thực thi

`superpowers:writing-plans` → `superpowers:subagent-driven-development`: P1→P2→P3 tuần tự,
mỗi task TDD, nghiệm thu bằng số đo của pha.
