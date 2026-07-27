"use client";

import AppSidebar, { type NavId } from "./app-sidebar";

// Khung chuẩn cho các trang một cột: sidebar + vùng nội dung cuộn.
export default function PageShell({
  active,
  children,
}: {
  active: NavId;
  children: React.ReactNode;
}) {
  return (
    <>
      <AppSidebar active={active} />
      <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
    </>
  );
}
