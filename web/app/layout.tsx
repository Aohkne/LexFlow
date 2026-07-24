import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import UserMenu from "./user-menu";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Hoa Tiêu Pháp Lý — LexFlow",
  description: "Trợ lý pháp lý tra cứu quy định ngân hàng (Advanced RAG + Knowledge Graph)",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-10 flex items-center gap-6 border-b border-border bg-panel px-6 py-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-sm font-bold text-white">
              ⎈
            </span>
            <span className="font-semibold">Hoa Tiêu Pháp Lý</span>
            <span className="mono text-xs text-faint">/ LexFlow</span>
          </Link>
          <nav className="ml-auto flex items-center gap-1 text-sm">
            <NavLink href="/" label="Tra cứu" />
            <NavLink href="/graph" label="Đồ thị tri thức" />
            <NavLink href="/alerts" label="Cảnh báo" />
          </nav>
          <UserMenu />
        </header>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="rounded-md px-3 py-1.5 text-dim transition-colors hover:bg-inset hover:text-foreground"
    >
      {label}
    </Link>
  );
}
