// Client gọi FastAPI backend (LexFlow/app). Đến khi backend sẵn sàng, các
// hàm trong features/*/api.ts sẽ dùng mock data thay vì gọi các endpoint này.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export const ENDPOINTS = {
  chat: `${API_BASE}/chat`,
  graph: `${API_BASE}/graph`,
  adminDocuments: `${API_BASE}/admin/documents`,
  adminAlerts: `${API_BASE}/admin/alerts`,
} as const;
