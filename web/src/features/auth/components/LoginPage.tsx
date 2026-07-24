"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@iconify/react";
import { Button } from "@/shared/components/ui/Button";
import { Card, CardBody, CardEyebrow } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { useAuth } from "@/shared/providers/AuthProvider";
import { mockLogin } from "../api";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { login } = useAuth();
  const router = useRouter();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const user = await mockLogin(email, password);
      login(user);
      router.push("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col px-4 py-14 sm:px-6">
      <div className="mb-6 flex flex-col items-center text-center">
        <span className="grid h-12 w-12 place-items-center rounded-xl bg-accent text-accent-foreground">
          <Icon icon="ph:shield-check-fill" className="text-2xl" />
        </span>
        <CardEyebrow className="mt-4">Cổng vận hành pháp chế</CardEyebrow>
        <h1 className="font-heading mt-1 text-2xl font-semibold text-foreground">Đăng nhập quản trị</h1>
        <p className="mt-2 text-sm text-dim">
          Duyệt văn bản nguồn và theo dõi cảnh báo thay đổi quy định trước khi đưa vào hệ thống.
        </p>
      </div>

      <Card>
        <CardBody>
          <form className="flex flex-col gap-3" onSubmit={onSubmit}>
            <label className="flex flex-col gap-1 text-xs font-medium text-dim">
              Email nội bộ
              <Input
                type="email"
                required
                placeholder="ten@shb.com.vn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-dim">
              Mật khẩu
              <Input
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>

            {error && (
              <div className="flex items-center gap-1.5 rounded-lg border border-red bg-red/5 px-3 py-2 text-xs text-red">
                <Icon icon="ph:x-circle-fill" /> {error}
              </div>
            )}

            <Button type="submit" disabled={loading} className="mt-1 w-full">
              {loading ? (
                <>
                  <Icon icon="ph:spinner-gap-bold" className="animate-spin" /> Đang xác thực…
                </>
              ) : (
                "Đăng nhập"
              )}
            </Button>
          </form>
        </CardBody>
      </Card>
      <p className="mono mt-4 text-center text-[11px] text-faint">
        Demo — chấp nhận mọi email hợp lệ, mật khẩu ≥ 4 ký tự (chờ SSO nội bộ).
      </p>
    </div>
  );
}
