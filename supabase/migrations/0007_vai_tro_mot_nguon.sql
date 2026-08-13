-- 0007 — "admin" chỉ còn MỘT định nghĩa.
--
-- Trước migration này có hai, không cái nào ghi sang cái kia:
--   * FastAPI `require_admin`  -> app_metadata.role trong JWT   (app/core/auth.py:68)
--   * web, 4 chỗ               -> app_metadata.role trong JWT
--   * RLS `is_admin()`         -> public.profiles.role          (0001_init.sql:104)
--
-- Trigger `handle_new_user` luôn đặt profiles.role = 'staff', còn app_metadata thì không
-- đường nào tự đặt. Hệ quả: đặt profiles.role='admin' thì FastAPI chặn ở cửa (403); đặt
-- app_metadata.role='admin' thì FastAPI cho qua rồi RLS chặn lúc ghi Storage. Luồng /admin
-- chưa bao giờ qua nổi cửa đầu tiên — bucket legal-docs và bảng legal_documents đều rỗng.
--
-- Nay RLS hỏi đúng chỗ hai bên kia đang hỏi.
create or replace function public.is_admin()
returns boolean language sql stable set search_path = ''
as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', 'staff') = 'admin';
$$;

-- `security definer` bỏ đi cùng lúc: hàm không còn đọc bảng nào nên không cần mượn quyền.

-- public.profiles.role sau đây KHÔNG còn ai đọc — không backend, không web, không RLS.
-- Cố ý giữ cột lại: lỗ hổng leo thang quyền (policy "profiles: sửa của mình" ở 0001:110
-- thiếu `with check` nên user tự đặt được role='admin' cho chính mình) tồn tại CHỈ VÌ
-- is_admin() đọc cột này; đổi hàm là nó tắt theo. `drop column` là lệnh không lùi được
-- trên dữ liệu thật để đổi lấy sự gọn mắt.
comment on column public.profiles.role is
  'ĐÃ CHẾT từ migration 0007 — nguồn sự thật là app_metadata.role trong JWT. Đừng đọc cột này.';

-- Đính chính comment sai ở 0001_init.sql:91 ("Backend FastAPI dùng service-role key
-- (bypass RLS)"): quyết định đã đổi từ lâu — backend gọi PostgREST bằng chính JWT của
-- user, RLS được thực thi thật. Xem docstring app/core/appdb.py.

-- Cấp quyền admin (thao tác tay, cố ý — chỉ service-role đặt được app_metadata):
--   Supabase Dashboard -> Authentication -> Users -> chọn user -> Edit user
--   -> App Metadata -> {"role": "admin"} -> Save. Người dùng phải ĐĂNG NHẬP LẠI
--   để nhận JWT mới; token cũ vẫn mang role cũ tới lúc hết hạn.
-- Kiểm ngay trong SQL Editor sau khi áp (SQL Editor chạy dưới vai service-role, không có
--   JWT người dùng, nên hàm phải trả false):
--   select public.is_admin();   -- kỳ vọng: false
