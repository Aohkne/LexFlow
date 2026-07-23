"use client";

import { usePathname } from "next/navigation";
import { AdminRoute } from "@/shared/components/AdminRoute";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/admin/login") return <>{children}</>;
  return <AdminRoute>{children}</AdminRoute>;
}
