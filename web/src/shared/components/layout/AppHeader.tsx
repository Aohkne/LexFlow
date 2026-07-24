"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@iconify/react";
import { MAIN_NAV } from "@/constant/nav";
import { ThemeToggle } from "@/shared/components/layout/ThemeToggle";
import { cn } from "@/shared/utils/cn";

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

export function AppHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-panel/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2 text-[11px] text-faint sm:px-6">
        <span className="mono uppercase tracking-[0.14em]">Vol. I &middot; Payment Integration</span>
        <span className="ml-auto hidden items-center gap-1.5 rounded-full border border-green/30 bg-green/10 px-2.5 py-0.5 font-medium text-green sm:inline-flex">
          <span className="h-1.5 w-1.5 rounded-full bg-green" /> Nguồn dữ liệu đang hiệu lực
        </span>
      </div>
      <div className="mx-auto flex max-w-6xl items-center gap-4 border-t border-border px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-accent text-accent-foreground">
            <Icon icon="ph:compass-tool-fill" className="text-lg" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-heading text-lg font-semibold tracking-tight text-foreground">
              Hoa Tiêu Pháp Lý
            </span>
            <span className="mono text-[10px] uppercase tracking-[0.18em] text-faint">LexFlow</span>
          </span>
        </Link>

        <nav className="ml-auto hidden items-center gap-1 md:flex">
          {MAIN_NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                  active ? "bg-accent text-accent-foreground" : "text-dim hover:text-foreground",
                )}
              >
                <Icon icon={item.icon} className="text-base" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <ThemeToggle className="md:ml-2 ml-auto" />
      </div>
    </header>
  );
}
