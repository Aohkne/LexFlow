import { Icon } from "@iconify/react";
import { Badge } from "@/shared/components/ui/Badge";
import { formatDate } from "@/shared/utils/format";
import type { Citation } from "../types";

export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{citation.doc_type}</Badge>
        <span className="text-sm font-medium text-foreground">{citation.doc_title}</span>
        <span className="mono text-xs text-accent-dim">{citation.article}</span>
        <span className="mono ml-auto flex items-center gap-1 text-xs text-faint">
          <Icon icon="ph:calendar-check" />
          hiệu lực từ {formatDate(citation.valid_from)}
          {citation.valid_to ? ` đến ${formatDate(citation.valid_to)}` : ""}
        </span>
      </div>
      <p className="mt-1.5 text-sm text-dim">{citation.snippet}</p>
    </div>
  );
}
