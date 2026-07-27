"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listDocuments, type DocumentSummary } from "@/lib/api";

const SOURCE_LABEL: Record<string, string> = {
  external: "Văn bản pháp luật",
  internal: "Quy định nội bộ",
};

export default function DocsPage() {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"all" | "external" | "internal">("all");

  useEffect(() => {
    listDocuments()
      .then(setDocs)
      .catch((e) => setError(e instanceof Error ? e.message : "Lỗi tải danh sách"));
  }, []);

  const shown = (docs ?? []).filter((d) => source === "all" || d.source === source);

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-2xl font-semibold">Thư viện văn bản</h1>
      <p className="mt-1 text-sm text-dim">
        Toàn bộ văn bản trong hệ thống tra cứu — mở để xem toàn văn, lược đồ quan hệ và các điều
        khoản đã bị sửa đổi.
      </p>

      <div className="mt-4 flex rounded-lg border border-border bg-background p-0.5 text-sm w-fit">
        {(["all", "external", "internal"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSource(s)}
            className={`rounded-md px-3 py-1 transition-colors ${
              source === s ? "bg-accent text-white" : "text-dim hover:text-foreground"
            }`}
          >
            {s === "all" ? "Tất cả" : SOURCE_LABEL[s]}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red bg-red/5 px-4 py-3 text-sm text-red">{error}</div>
      )}
      {!docs && !error && <p className="mt-6 text-sm text-faint">Đang tải…</p>}

      <div className="mt-4 space-y-2">
        {shown.map((d) => (
          <Link
            key={d.doc_id}
            href={`/docs/${encodeURIComponent(d.doc_id)}`}
            className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-panel px-4 py-3 transition-colors hover:border-accent"
          >
            <span className="rounded bg-inset px-2 py-0.5 text-xs text-dim">{d.doc_type}</span>
            <span className="text-sm font-medium">{d.title}</span>
            <span className="mono text-xs text-accent-dim">{d.doc_id}</span>
            <span className="ml-auto flex items-center gap-2">
              <span className="mono text-xs text-faint">{d.n_articles} điều</span>
              {d.status === "con_hieu_luc" ? (
                <span className="rounded border border-blue px-2 py-0.5 text-xs text-blue">
                  Còn hiệu lực
                </span>
              ) : (
                <span className="rounded border border-red px-2 py-0.5 text-xs text-red">
                  Hết hiệu lực
                </span>
              )}
            </span>
          </Link>
        ))}
        {docs && shown.length === 0 && (
          <p className="text-sm text-faint">Không có văn bản nào trong nhóm này.</p>
        )}
      </div>
    </div>
  );
}
