import { DOC_TYPE_COLOR } from "../api";

export function GraphLegend() {
  return (
    <div className="flex flex-wrap gap-3 text-xs">
      {Object.entries(DOC_TYPE_COLOR).map(([k, v]) => (
        <span key={k} className="flex items-center gap-1.5 text-dim">
          <span className="h-3 w-3 rounded-full" style={{ background: v }} />
          {k}
        </span>
      ))}
    </div>
  );
}
