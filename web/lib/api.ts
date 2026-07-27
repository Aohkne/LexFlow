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

export type StreamHandlers = {
  onMeta?: (citations: Citation[]) => void;
  onDelta?: (text: string) => void;
  onConflicts?: (conflicts: ConflictAlert[]) => void;
  onDone?: (sessionId: string | null) => void;
};

// Gọi /chat/stream (SSE): meta → delta* → conflicts → done.
export async function streamChat(
  body: {
    query: string;
    mode: "qa" | "checklist";
    as_of?: string | null;
    top_k?: number;
    session_id?: string | null;
  },
  handlers: StreamHandlers,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data) continue;
      const parsed = JSON.parse(data);
      if (event === "meta") handlers.onMeta?.(parsed.citations ?? []);
      else if (event === "delta") handlers.onDelta?.(parsed.text ?? "");
      else if (event === "conflicts") handlers.onConflicts?.(parsed.conflicts ?? []);
      else if (event === "done") handlers.onDone?.(parsed.session_id ?? null);
      else if (event === "error") throw new Error(parsed.detail ?? "Lỗi streaming");
    }
  }
}

// ---- Luồng duyệt văn bản (admin) ----

export type UploadResult = {
  doc_id: string;
  title: string;
  n_articles: number;
  status: string;
};

export async function uploadDocument(file: File, source: "external" | "internal"): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/documents/upload?source=${source}`, {
    method: "POST",
    headers: await authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
  return res.json();
}

export async function approveDocument(
  docId: string,
  document: unknown | null,
  relationships: unknown[],
): Promise<{ status: string; chunks: number; change_events: number }> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ document, relationships }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
  return res.json();
}

export async function rejectDocument(docId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}/reject`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
}

// ---- Thư viện văn bản (đọc) ----

export type RelAnchor = {
  source_article: string | null;
  target_article: string | null;
  detail: string | null;
};

export type Relationship = {
  source_doc: string;
  target_doc: string;
  rel_type: string;
  valid_from: string | null;
  note: string | null;
  anchors: RelAnchor[];
};

export type Article = {
  article: string;
  text: string;
  valid_from: string | null;
  valid_to: string | null;
  superseded: boolean;
  chapter: string | null;
  section: string | null;
};

export type DocumentSummary = {
  doc_id: string;
  title: string;
  doc_type: string;
  source: string;
  valid_from: string | null;
  valid_to: string | null;
  n_articles: number;
  status: "con_hieu_luc" | "het_hieu_luc";
};

export type DocumentDetail = {
  doc_id: string;
  title: string;
  doc_type: string;
  source: string;
  valid_from: string | null;
  valid_to: string | null;
  articles: Article[];
  relationships_out: Relationship[];
  relationships_in: Relationship[];
  doc_titles: Record<string, string>;
};

export async function listDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch(`${API_BASE}/documents`, { headers: await authHeaders() });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
  return res.json();
}

export async function getDocument(docId: string): Promise<DocumentDetail> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
  return res.json();
}

export async function getGraph(): Promise<GraphData> {
  const res = await fetch(`${API_BASE}/graph`, { headers: await authHeaders() });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}
