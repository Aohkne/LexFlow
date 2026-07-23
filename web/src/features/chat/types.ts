export type Citation = {
  doc_id: string;
  doc_title: string;
  doc_type: string;
  article: string;
  valid_from: string | null;
  valid_to: string | null;
  snippet: string;
};

export type ConflictSeverity = "info" | "warning" | "critical";

export type ConflictAlert = {
  doc_a: string;
  doc_b: string;
  article_a: string;
  article_b: string;
  explanation: string;
  severity: ConflictSeverity;
};

export type ChatMode = "qa" | "checklist";

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  conflicts: ConflictAlert[];
};

export type ChatRequest = {
  query: string;
  mode: ChatMode;
  as_of?: string | null;
  top_k?: number;
};
