import { Icon } from "@iconify/react";
import type { ConflictAlert, ConflictSeverity } from "../types";

const SEVERITY: Record<ConflictSeverity, { border: string; text: string; label: string }> = {
  info: { border: "border-l-blue", text: "text-blue", label: "Thông tin" },
  warning: { border: "border-l-accent", text: "text-accent-dim", label: "Cảnh báo" },
  critical: { border: "border-l-red", text: "text-red", label: "Nghiêm trọng" },
};

export function ConflictAlertCard({ conflict }: { conflict: ConflictAlert }) {
  const s = SEVERITY[conflict.severity] ?? SEVERITY.warning;
  return (
    <div className={`rounded-lg border-l-4 bg-panel px-4 py-3 ${s.border}`}>
      <div className={`flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide ${s.text}`}>
        <Icon icon="ph:warning-fill" /> Mâu thuẫn · {s.label}
      </div>
      <p className="mt-1 text-sm text-foreground">{conflict.explanation}</p>
      <p className="mono mt-1 text-xs text-faint">
        {conflict.doc_a} ({conflict.article_a}) ↔ {conflict.doc_b} ({conflict.article_b})
      </p>
    </div>
  );
}
