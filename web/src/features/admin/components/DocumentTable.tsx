import { Icon } from "@iconify/react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { formatDate, formatDateTime } from "@/shared/utils/format";
import type { AdminDocument } from "../types";
import { StatusBadge } from "./StatusBadge";

export function DocumentTable({
  documents,
  onApprove,
  onReject,
  busyId,
}: {
  documents: AdminDocument[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  busyId: string | null;
}) {
  return (
    <div className="divide-y divide-border">
      {documents.map((doc) => (
        <div key={doc.id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{doc.doc_type}</Badge>
              <StatusBadge status={doc.status} />
              <span className="truncate text-sm font-medium text-foreground">{doc.title}</span>
            </div>
            <div className="mono mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-faint">
              <span>hiệu lực từ {formatDate(doc.valid_from)}</span>
              <span>nộp bởi {doc.submitted_by}</span>
              <span>{formatDateTime(doc.submitted_at)}</span>
            </div>
            {doc.conflict_warning && (
              <p className="mt-1.5 flex items-start gap-1.5 text-xs text-red">
                <Icon icon="ph:warning-fill" className="mt-0.5 shrink-0" />
                {doc.conflict_warning}
              </p>
            )}
          </div>

          {doc.status === "pending" && (
            <div className="flex shrink-0 gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => onReject(doc.id)}
                disabled={busyId === doc.id}
                className="border-red/40 text-red hover:border-red hover:text-red"
              >
                <Icon icon="ph:x-bold" /> Từ chối
              </Button>
              <Button size="sm" onClick={() => onApprove(doc.id)} disabled={busyId === doc.id}>
                <Icon icon="ph:check-bold" /> Duyệt
              </Button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
