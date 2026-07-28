-- 0005 — Lưu lịch sử phiên kiểm tra tuân thủ + phạm vi/as-of theo lượt chat.
-- Apply: dán vào SQL Editor trên dashboard Supabase.

-- ============ review_sessions: kết quả mỗi lần chạy Kiểm tra tuân thủ ============
create table if not exists public.review_sessions (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.profiles (id) on delete cascade,
  internal_doc_id text not null,
  internal_title  text not null default '',
  against_doc_ids jsonb not null default '[]',   -- ["TT40-2024", ...]
  as_of           date,
  score           int  not null default 0,
  counts          jsonb not null default '{}',   -- {violation, warning, pass}
  findings        jsonb not null default '[]',   -- ReviewFinding[]
  created_at      timestamptz not null default now()
);
create index if not exists review_sessions_user_idx
  on public.review_sessions (user_id, created_at desc);

alter table public.review_sessions enable row level security;
create policy "reviews: CRUD của mình" on public.review_sessions
  for all using (user_id = (select auth.uid()));

-- ============ chat_messages: ghim phạm vi + thời điểm hiệu lực theo lượt ============
-- (design yêu cầu để audit: mở lại phiên cũ vẫn biết câu hỏi giới hạn văn bản nào)
alter table public.chat_messages add column if not exists scope jsonb;  -- ["TT40-2024"]; null = toàn bộ
alter table public.chat_messages add column if not exists as_of date;   -- null = hôm nay tại thời điểm hỏi
