-- Sprint 2: luồng duyệt văn bản (maker-checker).
-- 1. Cột lưu JSON đã extract (admin xem/sửa trước khi duyệt)
alter table public.legal_documents add column if not exists extracted jsonb;

-- 2. Admin được ghi đè file trong bucket legal-docs (corpus canonical corpus.json
--    được cập nhật mỗi lần approve; 0001 mới chỉ có policy select + insert)
create policy "storage: admin cập nhật" on storage.objects
  for update using (bucket_id = 'legal-docs' and public.is_admin());
create policy "storage: admin xoá" on storage.objects
  for delete using (bucket_id = 'legal-docs' and public.is_admin());
