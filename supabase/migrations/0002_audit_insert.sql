-- Backend ghi audit_log bằng chính JWT của user (không dùng service-role key),
-- nên cần policy INSERT: user chỉ được ghi log gắn với user_id của mình.
-- Đọc vẫn giới hạn admin (policy trong 0001).
create policy "audit: user ghi log của mình" on public.audit_log
  for insert with check (user_id = (select auth.uid()));
