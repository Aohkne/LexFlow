import { AppHeader } from "@/shared/components/layout/AppHeader";
import { BottomNav } from "@/shared/components/layout/BottomNav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <AppHeader />
      <main className="flex-1 pb-4">{children}</main>
      <BottomNav />
    </div>
  );
}
