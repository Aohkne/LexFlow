---
description: Ghi/cập nhật mục hôm nay trong docs/WORKLOG.md từ công việc vừa làm
---

Cập nhật nhật ký công việc `docs/WORKLOG.md`:

1. Đọc `docs/WORKLOG.md` và xem mục mới nhất.
2. Chạy `git log --oneline` từ commit cuối cùng đã ghi trong worklog đến HEAD để nắm các thay đổi chưa được ghi.
3. Kết hợp với ngữ cảnh phiên làm việc hiện tại, viết (hoặc bổ sung vào) mục của **ngày hôm nay** theo đúng template ở cuối file: Giai đoạn / Done / Ship / Decision / Next. Mục mới nhất nằm trên cùng.
4. Viết bằng tiếng Việt, ngắn gọn theo phong cách các mục sẵn có — mentor đọc được ngay không cần mở code.
5. Commit riêng file này theo quy ước (`docs: update worklog YYYY-MM-DD`) và push.

Nếu hôm nay chưa có gì đáng ghi (không commit mới, không quyết định mới), nói rõ thay vì bịa nội dung.
