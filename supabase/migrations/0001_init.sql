-- LexFlow — schema trạng thái ứng dụng trên Supabase Postgres.
-- Apply: dán vào SQL Editor trên dashboard, hoặc `supabase db push`.
-- Lưu ý phân vai: retrieval (chunks/vectors) nằm ở LanceDB, đồ thị ở Neo4j —
-- Postgres chỉ giữ users / hội thoại / audit / workflow văn bản / cảnh báo.

-- ============ profiles: hồ sơ user + role ============
create table if not exists public.profiles (
  id         uuid primary key references auth.users (id) on delete cascade,
  email      text not null,
  full_name  text,
  role       text not null default 'staff' check (role in ('admin', 'staff')),
  created_at timestamptz not null default now()
);

-- Tự tạo profile khi user đăng ký; đồng bộ role vào app_metadata do backend/admin làm
create or replace function public.handle_new_user()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, email, full_name)
  values (new.id, new.email, coalesce(new.raw_user_meta_data ->> 'full_name', ''));
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============ chat: phiên hội thoại + tin nhắn ============
create table if not exists public.chat_sessions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles (id) on delete cascade,
  title      text not null default 'Phiên mới',
  mode       text not null default 'qa' check (mode in ('qa', 'checklist')),
  created_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id         uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.chat_sessions (id) on delete cascade,
  role       text not null check (role in ('user', 'assistant')),
  content    text not null,
  citations  jsonb,          -- [{doc_id, article, quote}]
  conflicts  jsonb,          -- ConflictAlert[]
  created_at timestamptz not null default now()
);
create index if not exists chat_messages_session_idx
  on public.chat_messages (session_id, created_at);

-- ============ audit_log: ai hỏi gì, hệ thống dựa văn bản nào ============
create table if not exists public.audit_log (
  id         bigint generated always as identity primary key,
  user_id    uuid references public.profiles (id) on delete set null,
  action     text not null,  -- 'chat', 'ingest', 'doc_approve', ...
  detail     jsonb,
  created_at timestamptz not null default now()
);
create index if not exists audit_log_created_idx on public.audit_log (created_at);

-- ============ legal_documents: workflow duyệt văn bản (admin dashboard) ============
create table if not exists public.legal_documents (
  doc_id       text primary key,             -- vd: TT40-2024
  title        text not null,
  doc_type     text not null,                -- Luật / Nghị định / Thông tư / Quyết định / Nội bộ
  source       text not null check (source in ('internal', 'external')),
  status       text not null default 'pending'
               check (status in ('pending', 'approved', 'rejected')),
  valid_from   date,
  valid_to     date,
  storage_path text,                          -- đường dẫn PDF trong Supabase Storage
  uploaded_by  uuid references public.profiles (id) on delete set null,
  reviewed_by  uuid references public.profiles (id) on delete set null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- ============ alert_subscriptions: đăng ký nhận cảnh báo thay đổi ============
create table if not exists public.alert_subscriptions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles (id) on delete cascade,
  channel    text not null default 'email' check (channel in ('email', 'slack')),
  target     text not null,                   -- địa chỉ email / webhook URL
  created_at timestamptz not null default now(),
  unique (user_id, channel, target)
);

-- ============ RLS ============
-- Backend FastAPI dùng service-role key (bypass RLS). Policy dưới đây bảo vệ
-- truy cập trực tiếp từ frontend qua anon key.
alter table public.profiles            enable row level security;
alter table public.chat_sessions       enable row level security;
alter table public.chat_messages       enable row level security;
alter table public.audit_log           enable row level security;
alter table public.legal_documents     enable row level security;
alter table public.alert_subscriptions enable row level security;

create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.profiles where id = (select auth.uid()) and role = 'admin'
  );
$$;

create policy "profiles: đọc của mình hoặc admin" on public.profiles
  for select using (id = (select auth.uid()) or public.is_admin());
create policy "profiles: sửa của mình" on public.profiles
  for update using (id = (select auth.uid()));

create policy "sessions: CRUD của mình" on public.chat_sessions
  for all using (user_id = (select auth.uid()));
create policy "messages: CRUD trong phiên của mình" on public.chat_messages
  for all using (
    exists (
      select 1 from public.chat_sessions s
      where s.id = session_id and s.user_id = (select auth.uid())
    )
  );

create policy "audit: chỉ admin đọc" on public.audit_log
  for select using (public.is_admin());

create policy "docs: mọi user đọc bản đã duyệt" on public.legal_documents
  for select using (status = 'approved' or public.is_admin());
create policy "docs: admin quản lý" on public.legal_documents
  for all using (public.is_admin());

create policy "alerts: CRUD của mình" on public.alert_subscriptions
  for all using (user_id = (select auth.uid()));

-- ============ Storage bucket cho PDF gốc ============
insert into storage.buckets (id, name, public)
values ('legal-docs', 'legal-docs', false)
on conflict (id) do nothing;

create policy "storage: user đăng nhập được đọc" on storage.objects
  for select using (bucket_id = 'legal-docs' and auth.role() = 'authenticated');
create policy "storage: admin upload" on storage.objects
  for insert with check (bucket_id = 'legal-docs' and public.is_admin());
