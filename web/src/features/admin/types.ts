export type DocStatus = "pending" | "approved" | "rejected";

export type AdminDocument = {
  id: string;
  title: string;
  doc_type: string;
  status: DocStatus;
  valid_from: string | null;
  valid_to: string | null;
  submitted_by: string;
  submitted_at: string;
  conflict_warning: string | null;
};

export type AlertSeverity = "info" | "warning" | "critical";

export type RegulatoryAlert = {
  id: string;
  title: string;
  doc_type: string;
  published_at: string;
  effective_at: string;
  affected_flows: string[];
  severity: AlertSeverity;
  summary: string;
};
