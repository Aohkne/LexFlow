# Danh mục corpus thật — LexFlow

> Nguồn: luatvietnam.vn (HTML snapshot trong `data/raw/`), extract bằng
> `uv run python -m app.ingestion.extract --all`, duyệt tay rồi ingest bằng
> `uv run python -m app.ingestion data/corpus.real.json`. Cập nhật: 2026-07-24.

## Văn bản pháp luật (external) — 11

| doc_id | Văn bản | Hiệu lực | Trạng thái |
|---|---|---|---|
| ND52-2024 | Nghị định 52/2024/NĐ-CP về thanh toán không dùng tiền mặt | 2024-07-01 | Còn hiệu lực |
| TT40-2024 | Thông tư 40/2024/TT-NHNN — hoạt động cung ứng dịch vụ trung gian thanh toán | 2024-07-17 | Còn hiệu lực |
| TT15-2024 | Thông tư 15/2024/TT-NHNN — cung ứng dịch vụ thanh toán không dùng tiền mặt | 2024-07-01 | Còn hiệu lực |
| TT17-2024 | Thông tư 17/2024/TT-NHNN — mở và sử dụng tài khoản thanh toán | 2024-07-01 | Còn hiệu lực |
| TT18-2024 | Thông tư 18/2024/TT-NHNN — hoạt động thẻ ngân hàng | 2024-07-01 | Còn hiệu lực |
| ND101-2012 | Nghị định 101/2012/NĐ-CP về thanh toán không dùng tiền mặt | 2013-03-26 | Hết (bị ND52-2024 thay) |
| TT39-2014 | Thông tư 39/2014/TT-NHNN — dịch vụ trung gian thanh toán | 2015-03-01 | Hết (bị TT40-2024 thay) |
| TT46-2014 | Thông tư 46/2014/TT-NHNN — dịch vụ thanh toán không dùng tiền mặt | 2015-03-01 | Hết (bị TT15-2024 thay) |
| TT23-2014 | Thông tư 23/2014/TT-NHNN — mở và sử dụng tài khoản thanh toán | 2014-10-15 | Hết (bị TT17-2024 thay) |
| TT20-2016 | Thông tư 20/2016/TT-NHNN — sửa đổi TT 36/2012 + TT 39/2014 | 2016-07-01 | Hết cùng TT39-2014 |
| TT23-2019 | Thông tư 23/2019/TT-NHNN — sửa đổi TT 39/2014 (ví điện tử) | 2020-01-07 | Hết cùng TT39-2014 |

Văn bản hết hiệu lực được giữ CHỦ ĐÍCH để nuôi tính năng versioning/as_of
(tra cứu "tại thời điểm") và stale-avoidance.

## Quy định nội bộ SHB mô phỏng (internal) — 4

Mâu thuẫn được cài chủ đích, neo vào điều khoản thật (phục vụ demo conflict detection):

| doc_id | Quy định | Mâu thuẫn cài đặt |
|---|---|---|
| SHB-QD-VI-2023 | Ví điện tử liên kết | Mục 3.1: hạn mức 200tr/tháng (luật: 100tr — TT40 Đ26.1); Mục 4.2: nạp tiền mặt tại quầy vào ví (trái TT40 Đ25) |
| SHB-QD-TK-2022 | Mở tài khoản KHCN | Mục 2.3: 14 tuổi tự mở eKYC (luật: đủ 15 — TT17 Đ11.1) |
| SHB-QD-THE-2023 | Nghiệp vụ thẻ | Mục 5.2: rút ngoại tệ 80tr/ngày (luật: 30tr — TT18 Đ13.2); Mục 6.1: thẻ vô danh 20tr (luật: 5tr — TT18 Đ13.4) |
| SHB-CS-PHI-2024 | Chính sách phí | KHÔNG mâu thuẫn (văn bản đối chứng) |

## Quan hệ (13)

THAY_THE: ND52→ND101, TT40→TT39, TT15→TT46, TT17→TT23-2014 ·
SUA_DOI: TT23-2019→TT39, TT20-2016→TT39 ·
HUONG_DAN: TT40/TT15/TT17/TT18→ND52 ·
DAN_CHIEU: 3 quy định nội bộ → thông tư tương ứng.

## Quy mô

15 văn bản → 278 điều → **449 chunk** (điều >2000 ký tự tách mức Khoản) trên LanceDB Cloud; 15 node + 13 cạnh trên Neo4j Aura.
