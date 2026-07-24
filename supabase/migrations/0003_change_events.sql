-- Change alerts (painpoint 4): sự kiện "văn bản bị thay thế/sửa đổi" sinh ra khi
-- admin ingest corpus. Frontend đọc trực tiếp qua anon key (RLS bên dưới);
-- alert_subscriptions (0001) giữ đăng ký nhận thông báo email — gửi email thật
-- là bước nâng cấp sau (Resend/SMTP + Cloud Run Jobs).
create table if not exists public.change_events (
  id             bigint generated always as identity primary key,
  doc_id         text not null,   -- văn bản bị ảnh hưởng (target)
  source_doc_id  text not null,   -- văn bản mới gây thay đổi (source)
  rel_type       text not null,   -- THAY_THE / SUA_DOI / HUONG_DAN / DAN_CHIEU
  description    text not null,
  effective_date date,
  created_at     timestamptz not null default now(),
  unique (doc_id, source_doc_id, rel_type)  -- ingest lại không tạo trùng
);
create index if not exists change_events_created_idx on public.change_events (created_at desc);

alter table public.change_events enable row level security;

create policy "changes: user đăng nhập đọc" on public.change_events
  for select using (auth.role() = 'authenticated');
create policy "changes: admin ghi" on public.change_events
  for insert with check (public.is_admin());

-- Seed từ corpus mẫu (khớp data/corpus.sample.json) — ingest lại sẽ bỏ qua nhờ unique
insert into public.change_events (doc_id, source_doc_id, rel_type, description, effective_date)
values
  ('TT39-2014', 'TT40-2024', 'THAY_THE',
   'Thông tư 40/2024/TT-NHNN hướng dẫn hoạt động ví điện tử và trung gian thanh toán thay thế Thông tư 39/2014/TT-NHNN hướng dẫn về dịch vụ trung gian thanh toán — Thông tư 40 thay thế Thông tư 39',
   '2024-07-01'),
  ('ND52-2024', 'TT40-2024', 'HUONG_DAN',
   'Thông tư 40/2024/TT-NHNN hướng dẫn hoạt động ví điện tử và trung gian thanh toán hướng dẫn thi hành Nghị định 52/2024/NĐ-CP quy định về thanh toán không dùng tiền mặt — Hướng dẫn thi hành Nghị định 52',
   '2024-07-01'),
  ('TT39-2014', 'QD-2023-SUADOI', 'SUA_DOI',
   'Quyết định 2023 sửa đổi một số điều của Thông tư 39/2014/TT-NHNN sửa đổi, bổ sung Thông tư 39/2014/TT-NHNN hướng dẫn về dịch vụ trung gian thanh toán — Sửa đổi Điều 8 Khoản 2',
   '2023-01-01'),
  ('TT40-2024', 'INTERNAL-WALLET-2023', 'DAN_CHIEU',
   'Quy định nội bộ về hạn mức ví điện tử liên kết (Ngân hàng SHB) dẫn chiếu Thông tư 40/2024/TT-NHNN hướng dẫn hoạt động ví điện tử và trung gian thanh toán — Tham chiếu hạn mức theo Thông tư 40',
   null)
on conflict (doc_id, source_doc_id, rel_type) do nothing;
