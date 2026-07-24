"use client";

import { createContext, useContext, useSyncExternalStore, type ReactNode } from "react";
import { useHasMounted } from "@/shared/hooks/useHasMounted";
import {
  type AdminUser,
  subscribeAuth,
  getAuthSnapshot,
  getAuthServerSnapshot,
  loginAuth,
  logoutAuth,
} from "@/shared/store/authStore";

export type { AdminUser };

type AuthContextValue = {
  user: AdminUser | null;
  status: "loading" | "authenticated" | "unauthenticated";
  login: (user: AdminUser) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const hasMounted = useHasMounted();
  const user = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthServerSnapshot);
  const status: AuthContextValue["status"] = !hasMounted
    ? "loading"
    : user
      ? "authenticated"
      : "unauthenticated";

  return (
    <AuthContext.Provider value={{ user, status, login: loginAuth, logout: logoutAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải được dùng bên trong AuthProvider");
  return ctx;
}
