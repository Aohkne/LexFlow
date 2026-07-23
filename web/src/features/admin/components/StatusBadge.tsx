import { Badge } from "@/shared/components/ui/Badge";
import type { DocStatus } from "../types";

const STATUS_MAP: Record<DocStatus, { tone: "green" | "yellow" | "red"; label: string }> = {
  approved: { tone: "green", label: "Đã duyệt" },
  pending: { tone: "yellow", label: "Chờ duyệt" },
  rejected: { tone: "red", label: "Từ chối" },
};

export function StatusBadge({ status }: { status: DocStatus }) {
  const s = STATUS_MAP[status];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}
