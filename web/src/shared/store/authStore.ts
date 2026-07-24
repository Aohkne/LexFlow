// External store cho phiên đăng nhập admin (mock — chờ backend/SSO thật).
// Dùng useSyncExternalStore thay vì useState+useEffect để tránh set-state
// trong effect và giữ hydration an toàn giữa server/client.
export type AdminUser = { name: string; email: string };

const STORAGE_KEY = "lexflow_admin_user";

type Listener = () => void;
let listeners: Listener[] = [];

function emitChange() {
  for (const listener of listeners) listener();
}

export function subscribeAuth(listener: Listener) {
  listeners = [...listeners, listener];
  return () => {
    listeners = listeners.filter((l) => l !== listener);
  };
}

export function getAuthSnapshot(): AdminUser | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AdminUser;
  } catch {
    return null;
  }
}

export function getAuthServerSnapshot(): AdminUser | null {
  return null;
}

export function loginAuth(user: AdminUser) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  emitChange();
}

export function logoutAuth() {
  window.localStorage.removeItem(STORAGE_KEY);
  emitChange();
}
