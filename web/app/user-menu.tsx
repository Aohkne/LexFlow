"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function UserMenu() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user?.email ?? null);
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
