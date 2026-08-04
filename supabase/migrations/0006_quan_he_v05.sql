-- 0006 — Đưa `change_events.rel_type` về TẬP ĐÓNG 13 quan hệ của KG v0.5 §6.
-- Apply: dán vào SQL Editor trên dashboard Supabase.
--
-- Vì sao cần: migration 0003 **seed thẳng hai tên đã chết** vào bảng —
--   ('ND52-2024','TT40-2024','HUONG_DAN', …)   và   ('TT39-2014','QD-2023-SUADOI','SUA_DOI', …)
-- Chúng đã chạy, nên hai dòng đó đang nằm trong DB thật. Đây là chỗ DUY NHẤT schema cũ còn
-- sống trong một hệ thống đang chạy: Neo4j thì `push_corpus` xoá sạch mỗi lần nạp nên không
-- tồn đọng được, còn Supabase thì `change_events` tích luỹ.
--
-- Nặng hơn "tên xấu": khoá chống trùng là `unique (doc_id, source_doc_id, rel_type)` — CÓ
-- `rel_type` trong khoá. Nên lần ingest sau, cùng một thay đổi ấy mang tên mới sẽ **được coi
-- là sự kiện khác** và chèn thêm một dòng. Người dùng thấy một thay đổi hiện hai lần, với hai
-- động từ khác nhau, và không có gì trong hệ thống nói rằng đó là một.
--
-- `HUONG_DAN` không phải lệch tên mà là **không có thật**: v0.5 §6.3 tách làm hai quan hệ mà
-- Điều 53 khoản 2 đối xử khác nhau. Với đúng cặp TT40 → ND52 này, lược đồ vbpl.vn xếp TT40 vào
-- nhóm *"Văn bản áp dụng"* — nhãn bị động của `CAN_CU` — chứ KHÔNG vào nhóm *"Văn bản quy định
-- chi tiết, hướng dẫn thi hành"* (nhóm đó chỉ có TT 34/2024). Nên đây là `CAN_CU`.

-- 1) Đổi tên cơ học: cùng một quan hệ, v0.5 gọi tên khác.
update public.change_events set rel_type = 'SUA_DOI_BO_SUNG'    where rel_type = 'SUA_DOI';
update public.change_events set rel_type = 'TAM_NGUNG_HIEU_LUC' where rel_type = 'TAM_NGUNG';

-- 2) `HUONG_DAN` → `CAN_CU`, theo lược đồ chính thống (không phải suy đoán ngữ nghĩa).
update public.change_events set rel_type = 'CAN_CU' where rel_type = 'HUONG_DAN';

-- 3) Chặn ở BIÊN, để lần sau không phải sửa nữa. `Relationship.rel_type` đã có validator phía
--    Python; ràng buộc ở đây canh cả những đường ghi không đi qua nó.
alter table public.change_events drop constraint if exists change_events_rel_type_hop_le;
alter table public.change_events add constraint change_events_rel_type_hop_le
  check (rel_type in (
    'BAI_BO', 'CAN_CU', 'CONG_BO', 'DAN_CHIEU', 'DINH_CHI_THI_HANH', 'DINH_CHINH',
    'GIAI_THICH', 'HOP_NHAT', 'HUONG_DAN_AP_DUNG', 'QUY_DINH_CHI_TIET_HUONG_DAN',
    'SUA_DOI_BO_SUNG', 'TAM_NGUNG_HIEU_LUC', 'THAY_THE'
  ));

comment on column public.change_events.rel_type is
  'Một trong 13 quan hệ KG v0.5 §6 — nguồn sự thật: app/core/schemas.py::REL_TYPES';

-- Soát lại sau khi chạy (phải trả về 0 dòng):
--   select rel_type, count(*) from public.change_events
--   where rel_type in ('SUA_DOI','HUONG_DAN','TAM_NGUNG') group by rel_type;
