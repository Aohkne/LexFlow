"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setNotice(null);
    const supabase = createClient();
    try {
      if (mode === "signin") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push("/");
        router.refresh();
      } else {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: fullName } },
        });
        if (error) throw error;
        if (data.session) {
          router.push("/");
          router.refresh();
        } else {
          setNotice("Đã tạo tài khoản — kiểm tra email để xác nhận rồi đăng nhập.");
          setMode("signin");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi không xác định");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col justify-center px-6 py-20">
      <div className="mb-6 text-center">
        <span className="mx-auto grid h-10 w-10 place-items-center rounded-lg bg-accent text-lg font-bold text-white">
          ⎈
        </span>
        <h1 className="mt-3 text-xl font-semibold">Hoa Tiêu Pháp Lý</h1>
        <p className="mt-1 text-sm text-dim">
          {mode === "signin" ? "Đăng nhập để tra cứu quy định" : "Tạo tài khoản mới"}
        </p>
      </div>

      <form onSubmit={submit} className="space-y-3 rounded-xl border border-border bg-panel p-5">
        {mode === "signup" && (
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Họ tên"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
          />
        )}
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <input
          type="password"
          required
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Mật khẩu (≥ 6 ký tự)"
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />

        {error && (
          <div className="rounded-lg border border-red bg-red/5 px-3 py-2 text-xs text-red">{error}</div>
        )}
        {notice && (
          <div className="rounded-lg border border-blue bg-blue/5 px-3 py-2 text-xs text-blue">{notice}</div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:bg-accent-dim disabled:opacity-50"
        >
          {loading ? "Đang xử lý…" : mode === "signin" ? "Đăng nhập" : "Đăng ký"}
        </button>
      </form>

      <button
        onClick={() => {
          setMode(mode === "signin" ? "signup" : "signin");
          setError(null);
          setNotice(null);
        }}
        className="mt-4 text-center text-xs text-dim transition-colors hover:text-accent-dim"
      >
        {mode === "signin" ? "Chưa có tài khoản? Đăng ký" : "Đã có tài khoản? Đăng nhập"}
      </button>
    </div>
  );
}
