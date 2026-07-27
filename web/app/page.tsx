"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { streamChat, type ChatResponse, type Citation, type ConflictAlert } from "@/lib/api";
import { articleAnchor } from "@/lib/anchors";

const SEVERITY: Record<string, { bg: string; label: string }> = {
  info: { bg: "border-blue text-blue", label: "Thông tin" },
  warning: { bg: "border-accent text-accent-dim", label: "Cảnh báo" },
  critical: { bg: "border-red text-red", label: "Nghiêm trọng" },
};

const SAMPLES = [
  "Hạn mức giao dịch qua ví điện tử cá nhân hiện nay là bao nhiêu một tháng?",
  "Người 14 tuổi có được tự mở tài khoản thanh toán không?",
  "Một thẻ được rút tối đa bao nhiêu ngoại tệ tiền mặt tại nước ngoài trong một ngày?",
];

type Turn = { question: string; resp: ChatResponse };
type Session = { id: string; title: string; created_at: string };

export default function ChatPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"qa" | "checklist">("qa");
  const [asOf, setAsOf] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [live, setLive] = useState<Turn | null>(null); // lượt đang stream
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const loadSessions = useCallback(async () => {
    const supabase = createClient();
    const { data } = await supabase
      .from("chat_sessions")
      .select("id,title,created_at")
      .order("created_at", { ascending: false })
      .limit(30);
    setSessions((data as Session[]) ?? []);
  }, []);

  useEffect(() => {
    (async () => {
      await loadSessions();
    })();
  }, [loadSessions]);

  async function openSession(sid: string) {
    const supabase = createClient();
    const { data } = await supabase
      .from("chat_messages")
      .select("role,content,citations,conflicts,created_at")
      .eq("session_id", sid)
      .order("created_at", { ascending: true });
    const rows = (data ?? []) as {
      role: string;
      content: string;
      citations: Citation[] | null;
      conflicts: ConflictAlert[] | null;
    }[];
    const loaded: Turn[] = [];
    for (let i = 0; i < rows.length; i++) {
      if (rows[i].role === "user") {
        const a = rows[i + 1]?.role === "assistant" ? rows[i + 1] : null;
        loaded.push({
          question: rows[i].content,
          resp: {
            answer: a?.content ?? "",
            citations: a?.citations ?? [],
            conflicts: a?.conflicts ?? [],
            session_id: sid,
          },
        });
      }
    }
    setTurns(loaded);
    setSessionId(sid);
    setLive(null);
    setError(null);
    setShowHistory(false);
  }

  function newSession() {
    setTurns([]);
    setLive(null);
    setSessionId(null);
    setError(null);
    setShowHistory(false);
  }

  async function ask(q?: string) {
    const question = (q ?? query).trim();
    if (!question || loading) return;
    setLoading(true);
    setError(null);
    setQuery("");
    setLive({ question, resp: { answer: "", citations: [], conflicts: [], session_id: null } });
    try {
      let finished: ChatResponse = { answer: "", citations: [], conflicts: [], session_id: null };
      await streamChat(
        { query: question, mode, as_of: asOf || null, top_k: 6, session_id: sessionId },
        {
          onMeta: (citations) =>
            setLive((l) => l && { ...l, resp: (finished = { ...finished, citations }) }),
          onDelta: (text) =>
            setLive((l) => l && { ...l, resp: (finished = { ...finished, answer: finished.answer + text }) }),
          onConflicts: (conflicts) =>
            setLive((l) => l && { ...l, resp: (finished = { ...finished, conflicts }) }),
          onDone: (sid) => {
            if (sid) setSessionId(sid);
          },
        },
      );
      setTurns((t) => [...t, { question, resp: finished }]);
      setLive(null);
      loadSessions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi không xác định");
      setLive(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl gap-6 px-6 py-8">
      {/* Sidebar lịch sử */}
      <aside
        className={`${showHistory ? "block" : "hidden"} w-60 shrink-0 md:block`}
      >
        <button
          onClick={newSession}
          className="w-full rounded-lg border border-accent px-3 py-2 text-sm text-accent-dim transition-colors hover:bg-accent/10"
        >
          + Phiên mới
        </button>
        <div className="mt-3 space-y-1">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => openSession(s.id)}
              className={`w-full truncate rounded-md px-3 py-2 text-left text-xs transition-colors ${
                s.id === sessionId ? "bg-inset text-foreground" : "text-dim hover:bg-inset"
              }`}
              title={s.title}
            >
              {s.title}
            </button>
          ))}
          {sessions.length === 0 && (
            <p className="px-3 py-2 text-xs text-faint">Chưa có phiên nào.</p>
          )}
        </div>
      </aside>

      {/* Khu chat */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Tra cứu quy định thanh toán</h1>
            <p className="mt-1 text-sm text-dim">
              Trích dẫn đúng điều/khoản{" "}
              <span className="font-medium text-accent-dim">đang hiệu lực</span> — kèm cảnh báo mâu thuẫn.
            </p>
          </div>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="rounded-md border border-border px-3 py-1.5 text-xs text-dim md:hidden"
          >
            Lịch sử
          </button>
        </div>

        {/* Các lượt đã xong + lượt đang stream */}
        <div className="mt-6 space-y-6">
          {[...turns, ...(live ? [live] : [])].map((t, i) => (
            <TurnView key={i} turn={t} streaming={live !== null && i === turns.length} />
          ))}
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-red bg-red/5 px-4 py-3 text-sm text-red">
            {error}
          </div>
        )}

        {/* Ô nhập */}
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

        {turns.length === 0 && !live && (
          <div className="mt-3 flex flex-wrap gap-2">
            {SAMPLES.map((s) => (
              <button
                key={s}
                onClick={() => ask(s)}
                className="rounded-full border border-border bg-panel px-3 py-1 text-xs text-dim transition-colors hover:border-accent hover:text-accent-dim"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TurnView({ turn, streaming }: { turn: Turn; streaming: boolean }) {
  const { question, resp } = turn;
  return (
    <div className="space-y-3">
      {/* Câu hỏi */}
      <div className="ml-auto max-w-[85%] rounded-xl bg-inset px-4 py-2 text-sm">{question}</div>

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

      {/* Trả lời */}
      <section className="rounded-xl border border-border bg-panel p-5">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-accent-dim">
          Trả lời{streaming ? " · đang soạn…" : ""}
        </div>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {resp.answer || (streaming ? "…" : "")}
        </p>
      </section>

      {/* Trích dẫn */}
      {resp.citations.length > 0 && (
        <section>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-dim">
            Nguồn trích dẫn ({resp.citations.length})
          </div>
          <div className="space-y-2">
            {resp.citations.map((c, i) => {
              const anchor = articleAnchor(c.article);
              return (
                <Link
                  key={i}
                  href={`/docs/${encodeURIComponent(c.doc_id)}${anchor ? `#${anchor}` : ""}`}
                  className="block rounded-lg border border-border bg-background p-3 transition-colors hover:border-accent"
                  title="Mở toàn văn tại đúng điều khoản"
                >
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
                </Link>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
