import type { AdminUser } from "@/shared/providers/AuthProvider";

// Backend chưa sẵn sàng — mô phỏng độ trễ mạng, chấp nhận mọi email/mật khẩu hợp lệ.
export async function mockLogin(email: string, password: string): Promise<AdminUser> {
  await new Promise((r) => setTimeout(r, 500));
  if (!email.includes("@") || password.length < 4) {
    throw new Error("Email hoặc mật khẩu không hợp lệ.");
  }
  return { name: email.split("@")[0], email };
}
