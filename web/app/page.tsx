"use client";

import { useState } from "react";
import { postChat, type ChatResponse } from "@/lib/api";

const SEVERITY: Record<string, { bg: string; label: string }> = {
  info: { bg: "border-blue text-blue", label: "Thông tin" },
  warning: { bg: "border-accent text-accent-dim", label: "Cảnh báo" },
  critical: { bg: "border-red text-red", label: "Nghiêm trọng" },
};

const SAMPLES = [
  "Hạn mức giao dịch qua ví điện tử cá nhân hiện nay là bao nhiêu một tháng?",
  "Khách hàng có được nạp tiền mặt trực tiếp vào ví điện tử không?",
  "Nạp ví điện tử qua ngân hàng liên kết cần tuân thủ quy định gì?",
];

export default function ChatPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"qa" | "checklist">("qa");
  const [asOf, setAsOf] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resp, setResp] = useState<ChatResponse | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  async function ask(q?: string) {
    const question = (q ?? query).trim();
    if (!question) return;
    setLoading(true);
    setError(null);
    setResp(null);
    try {
      const data = await postChat({
        query: question,
        mode,
        as_of: asOf || null,
        top_k: 6,
        session_id: sessionId,
      });
      setResp(data);
      if (data.session_id) setSessionId(data.session_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi không xác định");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold">Tra cứu quy định thanh toán</h1>
      <p className="mt-1 text-sm text-dim">
        Hỏi tự nhiên, nhận câu trả lời có trích dẫn đúng điều/khoản{" "}
        <span className="font-medium text-accent-dim">đang hiệu lực</span> — kèm cảnh báo mâu thuẫn.
      </p>

      {/* Điều khiển */}
      <div className="mt-6 rounded-xl border border-border bg-panel p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
          <div className="flex rounded-lg border border-border bg-background p-0.5">
            {(["qa", "checklist"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`rounded-md px-3 py-1 transition-colors ${
                  mode === m ? "bg-accent text-white" : "text-dim hover:text-foreground"
                }`}
              >
                {m === "qa" ? "Hỏi–đáp" : "Checklist luồng"}
              </button>
            ))}
          </div>
          <label className="ml-auto flex items-center gap-2 text-dim">
            Tại thời điểm
            <input
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              className="mono rounded-md border border-border bg-background px-2 py-1 text-xs"
            />
          </label>
        </div>

        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask();
          }}
          rows={3}
          placeholder="Ví dụ: Hạn mức giao dịch qua ví điện tử cá nhân là bao nhiêu một tháng?"
          className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="mono text-xs text-faint">⌘/Ctrl + Enter để gửi</span>
          <button
            onClick={() => ask()}
            disabled={loading}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:bg-accent-dim disabled:opacity-50"
          >
            {loading ? "Đang tra cứu…" : "Tra cứu"}
          </button>
        </div>
      </div>

      {/* Câu hỏi mẫu */}
      <div className="mt-3 flex flex-wrap gap-2">
        {SAMPLES.map((s) => (
          <button
            key={s}
            onClick={() => {
              setQuery(s);
              ask(s);
            }}
            className="rounded-full border border-border bg-panel px-3 py-1 text-xs text-dim transition-colors hover:border-accent hover:text-accent-dim"
          >
            {s}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-6 rounded-lg border border-red bg-red/5 px-4 py-3 text-sm text-red">
          {error}
        </div>
      )}

      {resp && (
        <div className="mt-8 space-y-6">
          {/* Cảnh báo mâu thuẫn */}
          {resp.conflicts.length > 0 && (
            <section className="space-y-2">
              {resp.conflicts.map((c, i) => {
                const s = SEVERITY[c.severity] ?? SEVERITY.warning;
                return (
                  <div key={i} className={`rounded-lg border-l-4 bg-panel px-4 py-3 ${s.bg}`}>
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">
                      ⚠ Mâu thuẫn · {s.label}
                    </div>
                    <p className="mt-1 text-sm text-foreground">{c.explanation}</p>
                    <p className="mono mt-1 text-xs text-faint">
                      {c.doc_a} ({c.article_a}) ↔ {c.doc_b} ({c.article_b})
                    </p>
                  </div>
                );
              })}
            </section>
          )}

          {/* Câu trả lời */}
          <section className="rounded-xl border border-border bg-panel p-5">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-accent-dim">
              Trả lời
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{resp.answer}</p>
          </section>

          {/* Trích dẫn nguồn */}
          {resp.citations.length > 0 && (
            <section>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-dim">
                Nguồn trích dẫn ({resp.citations.length})
              </div>
              <div className="space-y-2">
                {resp.citations.map((c, i) => (
                  <div key={i} className="rounded-lg border border-border bg-background p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-inset px-2 py-0.5 text-xs text-dim">{c.doc_type}</span>
                      <span className="text-sm font-medium">{c.doc_title}</span>
                      <span className="mono text-xs text-accent-dim">{c.article}</span>
                      <span className="mono ml-auto text-xs text-faint">
                        hiệu lực từ {c.valid_from ?? "—"}
                        {c.valid_to ? ` đến ${c.valid_to}` : ""}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-dim">{c.snippet}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
