// Lưu tạm state ở localStorage — thay cho backend thật trong lúc chờ API.
// Dùng cho các mock store trong features/*/api.ts (vd. danh sách văn bản admin).
export function readLocalStore<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  const raw = window.localStorage.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeLocalStore<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(value));
}
