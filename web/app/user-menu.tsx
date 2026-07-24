"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function UserMenu() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setEmail(data.user?.email ?? null);
      setIsAdmin((data.user?.app_metadata as { role?: string } | undefined)?.role === "admin");
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user?.email ?? null);
      setIsAdmin((session?.user?.app_metadata as { role?: string } | undefined)?.role === "admin");
    });
    return () => subscription.unsubscribe();
  }, []);

  if (!email) return null;

  async function signOut() {
    await createClient().auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      {isAdmin && (
        <Link
          href="/admin"
          className="rounded-md border border-accent px-2.5 py-1 text-accent-dim transition-colors hover:bg-accent/10"
        >
          Quản trị
        </Link>
      )}
      <span className="mono hidden text-faint sm:inline">{email}</span>
      <button
        onClick={signOut}
        className="rounded-md border border-border px-2.5 py-1 text-dim transition-colors hover:border-red hover:text-red"
      >
        Đăng xuất
      </button>
    </div>
  );
}
