"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { createClient } from "@/lib/supabase/client";

const NAV = [
  { id: "chat", href: "/", glyph: "⌘", label: "Tra cứu" },
  { id: "docs", href: "/docs", glyph: "▤", label: "Thư viện văn bản" },
  { id: "review", href: "/review", glyph: "⎗", label: "Kiểm tra tài liệu" },
  { id: "graph", href: "/graph", glyph: "◰", label: "Đồ thị tri thức" },
  { id: "alerts", href: "/alerts", glyph: "⚠", label: "Cảnh báo" },
] as const;

export type NavId = (typeof NAV)[number]["id"] | "admin";

export default function AppSidebar({
  active,
  primaryLabel = "✚ Tra cứu mới",
  primaryHref = "/",
  extra,
}: {
  active: NavId;
  primaryLabel?: string;
  primaryHref?: string;
  extra?: ReactNode;
}) {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [alertCount, setAlertCount] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setEmail(data.user?.email ?? null);
      setIsAdmin((data.user?.app_metadata as { role?: string } | undefined)?.role === "admin");
    });
    supabase
      .from("change_events")
      .select("*", { count: "exact", head: true })
      .then(({ count }) => setAlertCount(count ?? null));
  }, []);

  async function signOut() {
    await createClient().auth.signOut();
    router.push("/login");
    router.refresh();
  }

  const initials = (email ?? "?").slice(0, 2).toUpperCase();
  const name = email ? email.split("@")[0] : "…";

  return (
    <aside className="flex h-full w-[260px] flex-none flex-col border-r border-border bg-sidebar">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 pt-4">
        <span className="grid h-7 w-7 flex-none place-items-center rounded-lg bg-accent text-sm font-bold text-white">
          ⎈
        </span>
        <div className="min-w-0 leading-tight">
          <div className="truncate text-sm font-semibold">Hoa Tiêu Pháp Lý</div>
          <div className="mono text-[10px] text-faint">LexFlow</div>
        </div>
      </div>

      {/* Nút chính */}
      <div className="px-3.5 pt-4">
        <Link
          href={primaryHref}
          className="block w-full rounded-[10px] bg-accent px-3.5 py-2.5 text-center text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
        >
          {primaryLabel}
        </Link>
      </div>

      {/* Nav */}
      <nav className="mt-4 space-y-0.5 px-2.5">
        {NAV.map((n) => (
          <Link
            key={n.id}
            href={n.href}
            className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition-colors ${
              active === n.id
                ? "bg-inset-strong font-medium text-foreground"
                : "text-dim hover:bg-[#EFEADF]"
            }`}
          >
            <span className="w-4 text-center">{n.glyph}</span>
            <span className="flex-1">{n.label}</span>
            {n.id === "alerts" && alertCount !== null && alertCount > 0 && (
              <span className="grid h-[18px] min-w-[18px] place-items-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
                {alertCount}
              </span>
            )}
          </Link>
        ))}
        {isAdmin && (
          <Link
            href="/admin"
            className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition-colors ${
              active === "admin"
                ? "bg-inset-strong font-medium text-foreground"
                : "text-dim hover:bg-[#EFEADF]"
            }`}
          >
            <span className="w-4 text-center">⚙</span>
            <span>Quản trị văn bản</span>
          </Link>
        )}
      </nav>

      {/* Slot theo màn hình (Gần đây / Facet / Phiên kiểm tra) */}
      <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-2.5 pb-2">{extra}</div>

      {/* Footer tài khoản */}
      <div className="relative border-t border-border px-3 py-3">
        {menuOpen && (
          <div
            className="absolute bottom-[54px] left-3 right-3 z-30 rounded-xl border border-border bg-panel p-1.5 shadow-[0_18px_46px_rgba(40,34,24,.16)]"
            style={{ animation: "fadeup .16s ease-out" }}
          >
            <button
              onClick={signOut}
              className="w-full rounded-lg px-2.5 py-2 text-left text-[12.5px] text-dim transition-colors hover:bg-inset hover:text-red"
            >
              Đăng xuất
            </button>
          </div>
        )}
        <div className="flex items-center gap-2.5">
          <span className="grid h-[30px] w-[30px] flex-none place-items-center rounded-full bg-avatar text-[11px] font-semibold text-accent-dim">
            {initials}
          </span>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-[12.5px] font-medium">{name}</div>
            <div className="mono truncate text-[10px] text-faint">{email ?? ""}</div>
          </div>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Cài đặt tài khoản"
            className="grid h-7 w-7 place-items-center rounded-lg text-faint transition-colors hover:bg-inset hover:text-foreground"
          >
            ⚙
          </button>
        </div>
      </div>
    </aside>
  );
}

export function SidebarSectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="px-2.5 pb-1.5 pt-3 text-[10px] font-semibold uppercase tracking-[.1em] text-faint">
      {children}
    </div>
  );
}
