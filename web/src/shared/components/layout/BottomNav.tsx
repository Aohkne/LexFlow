"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@iconify/react";
import { MAIN_NAV } from "@/constant/nav";
import { cn } from "@/shared/utils/cn";

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="sticky bottom-0 z-20 border-t border-border bg-panel/95 backdrop-blur md:hidden">
      <div className="mx-auto flex max-w-6xl items-stretch justify-between px-2">
        {MAIN_NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[10px] font-medium uppercase tracking-wide transition-colors",
                active ? "text-accent-dim" : "text-faint",
              )}
            >
              <Icon icon={item.icon} className="text-lg" />
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
