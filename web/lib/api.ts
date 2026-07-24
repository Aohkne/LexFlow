// Client gọi FastAPI backend.
import { createClient } from "@/lib/supabase/client";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// Header Authorization từ session Supabase (nếu đã đăng nhập).
async function authHeaders(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return session ? { Authorization: `Bearer ${session.access_token}` } : {};
}

export type Citation = {
  doc_id: string;
  doc_title: string;
  doc_type: string;
  article: string;
  valid_from: string | null;
  valid_to: string | null;
  snippet: string;
};

export type ConflictAlert = {
  doc_a: string;
  doc_b: string;
  article_a: string;
  article_b: string;
  explanation: string;
  severity: "info" | "warning" | "critical";
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  conflicts: ConflictAlert[];
  session_id: string | null;
};

export type GraphNode = {
  id: string;
  label: string;
  doc_type: string;
  valid_from: string | null;
  valid_to: string | null;
};

export type GraphEdge = { source: string; target: string; rel_type: string };
export type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] };

export async function postChat(body: {
  query: string;
  mode: "qa" | "checklist";
  as_of?: string | null;
  top_k?: number;
  session_id?: string | null;
}): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

export async function getGraph(): Promise<GraphData> {
  const res = await fetch(`${API_BASE}/graph`, { headers: await authHeaders() });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}
