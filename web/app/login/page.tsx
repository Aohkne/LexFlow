"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [fullName, setFullName] = useState("");
  const [department, setDepartment] = useState("");
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
          options: { data: { full_name: fullName, department } },
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

  const inputCls =
    "w-full rounded-[10px] border border-border bg-panel px-3 py-[11px] text-sm text-fg-body outline-none transition-shadow placeholder:text-muted focus:border-accent focus:shadow-[0_0_0_3px_rgba(204,120,92,.13)]";

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_.95fr]">
      {/* Trái: form */}
      <div className="flex flex-col bg-background px-8 pb-9 pt-6">
        <Link href="/landing" className="flex w-fit items-center gap-2.5">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-sm font-bold text-white">
            ⎈
          </span>
          <span className="text-sm font-semibold">Hoa Tiêu Pháp Lý</span>
          <span className="mono text-[10px] text-muted">/ LexFlow</span>
        </Link>

        <div className="mx-auto flex w-full max-w-[404px] flex-1 flex-col justify-center py-10">
          <h1 className="serif text-[34px] font-medium leading-[1.1] tracking-[-.02em]">
            {mode === "signin" ? "Chào mừng trở lại" : "Tạo tài khoản LexFlow"}
          </h1>
          <p className="mt-2 text-[14.5px] leading-relaxed text-dim">
            {mode === "signin"
              ? "Đăng nhập để tra cứu quy định với trích dẫn kiểm chứng được."
              : "Dành cho cán bộ khối Pháp chế, Tuân thủ và Nghiệp vụ."}
          </p>

          {/* Tab */}
          <div className="mt-6 flex rounded-[11px] bg-[#E7E3D8] p-[3px] text-[13px]">
            {(
              [
                ["signin", "Đăng nhập"],
                ["signup", "Đăng ký"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => {
                  setMode(id);
                  setError(null);
                  setNotice(null);
                }}
                className={`flex-1 rounded-lg px-3 py-1.5 transition-all ${
                  mode === id
                    ? "bg-panel font-medium shadow-[0_1px_2px_rgba(40,34,24,.12)]"
                    : "text-faint"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-5 space-y-3.5">
            {mode === "signup" && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[12.5px] font-medium text-fg-strong">Họ tên</label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Nguyễn Văn A"
                    className={`mt-1 ${inputCls}`}
                  />
                </div>
                <div>
                  <label className="text-[12.5px] font-medium text-fg-strong">Đơn vị / Phòng ban</label>
                  <input
                    type="text"
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                    placeholder="Pháp chế & Tuân thủ"
                    className={`mt-1 ${inputCls}`}
                  />
                </div>
              </div>
            )}
            <div>
              <label className="text-[12.5px] font-medium text-fg-strong">Email công việc</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ban@nganhang.vn"
                className={`mt-1 ${inputCls}`}
              />
            </div>
            <div>
              <div className="flex items-baseline justify-between">
                <label className="text-[12.5px] font-medium text-fg-strong">Mật khẩu</label>
                {mode === "signin" && (
                  <span className="text-[11.5px] text-muted">Quên mật khẩu? Liên hệ quản trị</span>
                )}
              </div>
              <div className="relative mt-1">
                <input
                  type={showPw ? "text" : "password"}
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••"
                  className={`${inputCls} pr-11`}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  aria-label={showPw ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  className="absolute right-1.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-md text-faint hover:text-foreground"
                >
                  {showPw ? "◡" : "◉"}
                </button>
              </div>
              {mode === "signup" && (
                <p className="mt-1 text-[11.5px] text-muted">Tối thiểu 10 ký tự, gồm chữ và số.</p>
              )}
            </div>

            {error && (
              <div className="rounded-[10px] border border-red-bd bg-red-bg px-3 py-2 text-xs text-red">
                {error}
              </div>
            )}
            {notice && (
              <div className="rounded-[10px] border border-green-bd bg-green-bg px-3 py-2 text-xs text-green">
                {notice}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-[11px] bg-accent px-4 py-[11px] text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
            >
              {loading ? "Đang xử lý…" : mode === "signin" ? "Đăng nhập" : "Tạo tài khoản"}
            </button>
          </form>

          <p className="mt-4 text-center text-[12.5px] text-dim">
            {mode === "signin" ? (
              <>
                Chưa có tài khoản?{" "}
                <button onClick={() => setMode("signup")} className="font-medium text-accent-dim">
                  Đăng ký
                </button>
              </>
            ) : (
              <>
                Đã có tài khoản?{" "}
                <button onClick={() => setMode("signin")} className="font-medium text-accent-dim">
                  Đăng nhập
                </button>
              </>
            )}
          </p>
          <p className="mono mt-5 text-center text-[10px] leading-relaxed text-muted">
            Dữ liệu lưu trữ tại Việt Nam · Đăng nhập được ghi log phục vụ kiểm toán
          </p>
        </div>
      </div>

      {/* Phải: panel tối */}
      <div className="hidden flex-col justify-center bg-dark-bg px-13 py-12 lg:flex lg:px-12">
        <div className="mx-auto w-full max-w-[440px]">
          <span className="inline-block rounded-full border border-dark-bd px-3 py-1 text-[11px] text-[#C9BCA8]">
            Mọi câu trả lời đều truy được nguồn
          </span>
          <h2 className="serif mt-4 text-[32px] font-medium leading-[1.18] tracking-[-.015em] text-cta-heading">
            Tra cứu quy định như hỏi một đồng nghiệp thạo luật
          </h2>

          {/* Mini answer card */}
          <div className="mt-6 rounded-2xl border border-dark-bd bg-dark-card p-4">
            <div className="flex flex-wrap gap-1.5">
              <span className="rounded-full border border-green-bd/40 bg-green/10 px-2 py-0.5 text-[10px] text-[#9DBB9D]">
                2 nguồn đang hiệu lực
              </span>
              <span className="rounded-full border border-amber-bd/40 bg-amber/10 px-2 py-0.5 text-[10px] text-[#D8A183]">
                ⚠ 1 mâu thuẫn
              </span>
            </div>
            <p className="serif mt-3 text-[15px] leading-relaxed text-[#E8E2D4]">
              Tổng hạn mức giao dịch qua ví điện tử cá nhân tối đa là{" "}
              <b className="font-semibold">100 triệu đồng/tháng</b>, theo quy định đang hiệu lực.
            </p>
            <div className="mono mt-3 border-t border-dark-bd pt-2.5 text-[10.5px] text-[#A49A88]">
              TT 40/2024/TT-NHNN · Điều 26 · hiệu lực từ 07/2024
            </div>
          </div>

          <ul className="mt-6 space-y-2.5">
            {[
              "Trích dẫn đúng điều/khoản đang hiệu lực",
              "Cảnh báo khi văn bản mâu thuẫn hoặc bị thay thế",
              "Tra cứu theo mốc thời gian bất kỳ",
            ].map((perk) => (
              <li key={perk} className="flex items-start gap-2.5 text-[13.5px] text-[#C9BCA8]">
                <span className="mt-0.5 text-[#9DBB9D]">✓</span>
                {perk}
              </li>
            ))}
          </ul>

          <div className="mt-7 flex items-start gap-3 border-t border-dark-bd pt-5">
            <span className="grid h-9 w-9 flex-none place-items-center rounded-full bg-avatar text-[12px] font-semibold text-accent-dim">
              NM
            </span>
            <p className="serif text-[13.5px] italic leading-relaxed text-[#A49A88]">
              “Trước đây mỗi câu hỏi hạn mức phải mở ba thông tư để đối chiếu. Giờ chỉ cần hỏi — và
              quan trọng là kiểm chứng được ngay.”
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
