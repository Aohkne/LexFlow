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
  // Lớp phủ dưới-văn-bản (optional — backend cũ không trả)
  trang_thai?: "nguyen_ven" | "da_sua" | "bi_bai_bo" | "la_loi_sua" | null;
  chu_thich?: string | null;
  sua_boi_doc_id?: string | null;
  sua_boi_article?: string | null;
  ban_hien_hanh?: string | null;
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
  // `false` = node RỖNG: biết văn bản tồn tại và biết nó nối vào đâu, nhưng CHƯA có toàn văn.
  // Xem app/ingestion/bac_cau.py. Node nạp trước khi có trường này thì thiếu — và chúng đều
  // CÓ toàn văn, nên mọi chỗ đọc phải so với `false`, không phải so với falsy.
  co_toan_van?: boolean;
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
    doc_ids?: string[];
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
): Promise<{ status: string; chunks: number; chunks_bang: number; change_events: number }> {
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

export type Provision = {
  id: string | null;
  cap: "chuong" | "muc" | "dieu" | "khoan" | "diem";
  so: string | null;
  tieu_de: string;
  text: string;
  // HTML inline ĐÃ lọc whitelist ở backend — render qua renderInline, không đổ thẳng vào DOM
  html: string;
  bi_tac_dong: string[] | null;
  an: boolean;
  con: Provision[];
};

// Tác động cấp khoản/điểm do lớp phủ dưới-văn-bản suy ra (`GET /documents/{id}.tac_dong`).
// Khác `Provision.bi_tac_dong` — cái kia là cờ thô của nguồn vbpl, cái này mang cả trạng thái
// hiện hành, ai sửa và từ ngày nào.
export type TacDongDonVi = {
  article: string;
  khoan: string | null;
  diem: string | null;
  trang_thai: "da_sua" | "bi_bai_bo";
  boi_doc_id: string | null;
  boi_article: string | null;
  tu_ngay: string | null;
  // Chữ để dựng bảng đối chiếu. Đều optional: backend cũ chưa trả nhóm này, và trong artefact
  // hiện tại thì `bai_bo` không có `loi_van_moi` (bãi bỏ thì không có gì thay thế).
  thao_tac?: "sua_doi" | "bo_sung" | "bai_bo" | "thay_phu_luc" | "thay_cum_tu" | null;
  menh_lenh?: string | null;
  loi_van_moi?: string | null;
};

export type SourceFile = {
  ten: string;
  kich_thuoc: string | null;
  // null = biết là có file nhưng chưa lấy được link tải
  url: string | null;
};

export type DocumentDetail = {
  doc_id: string;
  title: string;
  doc_type: string;
  source: string;
  valid_from: string | null;
  valid_to: string | null;
  // Thuộc tính — corpus duyệt từ trước không có, nên đều có thể null
  so_hieu: string | null;
  co_quan_ban_hanh: string | null;
  nguoi_ky: string | null;
  chuc_danh: string | null;
  nganh: string | null;
  linh_vuc: string | null;
  ngay_ban_hanh: string | null;
  tinh_trang_hieu_luc: string | null;
  source_url: string | null;
  // Backend chưa deploy bản mới sẽ không trả khoá này -> phải chịu được undefined
  source_files?: SourceFile[];
  articles: Article[];
  // Cây điều khoản đầy đủ; backend cũ / văn bản chưa crawl lại sẽ không có
  provisions?: Provision[];
  relationships_out: Relationship[];
  relationships_in: Relationship[];
  doc_titles: Record<string, string>;
  tac_dong?: TacDongDonVi[];
};

/**
 * Tải file gốc về máy.
 *
 * Không dùng thẻ <a download> trực tiếp được: endpoint tải nằm sau xác thực Bearer mà thẻ
 * <a> không gửi được header. Nên fetch kèm header rồi lưu qua blob URL.
 * Link tuyệt đối (bản gốc trên vbpl.vn) thì mở thẳng, không cần đi qua API.
 */
export async function downloadSourceFile(file: SourceFile): Promise<void> {
  if (!file.url) throw new Error("File này chưa có link tải");
  if (file.url.startsWith("http")) {
    window.open(file.url, "_blank", "noopener");
    return;
  }
  const res = await fetch(`${API_BASE}${file.url}`, { headers: await authHeaders() });
  if (!res.ok) {
    throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
  }
  const blobUrl = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = file.ten;
  a.click();
  URL.revokeObjectURL(blobUrl);
}

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

// ---- Kiểm tra tuân thủ ----

export type ReviewFinding = {
  // not_assessed = không tìm thấy căn cứ để đối chiếu (loại khỏi mẫu số điểm)
  verdict: "violation" | "warning" | "pass" | "not_assessed";
  article: string;
  title: string;
  summary: string;
  internal_quote: string;
  legal_doc_id: string | null;
  legal_ref: string | null;
  legal_quote: string | null;
  legal_live: boolean;
  suggestion: string | null;
};

export type ReviewResult = {
  internal_doc_id: string;
  internal_title: string;
  as_of: string;
  against_doc_ids: string[];
  score: number;
  // not_assessed optional — phiên lưu trước bản verdict 4 mức không có khoá này
  counts: Record<"violation" | "warning" | "pass", number> & { not_assessed?: number };
  findings: ReviewFinding[];
  session_id: string | null;
};

export async function runReview(body: {
  internal_doc_id: string;
  against_doc_ids: string[];
  as_of?: string | null;
}): Promise<ReviewResult> {
  const res = await fetch(`${API_BASE}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
  return res.json();
}

export async function getGraph(): Promise<GraphData> {
  const res = await fetch(`${API_BASE}/graph`, { headers: await authHeaders() });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}
