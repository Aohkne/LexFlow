"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Fragment, Suspense, useCallback, useEffect, useRef, useState } from "react";
import AppSidebar, { SidebarSectionLabel } from "@/components/app-sidebar";
import { createClient } from "@/lib/supabase/client";
import {
  listDocuments,
  streamChat,
  type ChatResponse,
  type Citation,
  type ConflictAlert,
  type DocumentSummary,
} from "@/lib/api";
import { articleAnchor } from "@/lib/anchors";

type Turn = {
  question: string;
  scopeLabel: string;
  narrow: boolean;
  resp: ChatResponse;
};
type Session = { id: string; title: string; created_at: string };

const PRESETS = [
  { id: "live", label: "Toàn bộ đang hiệu lực" },
  { id: "external", label: "Văn bản pháp luật" },
  { id: "internal", label: "Quy định nội bộ" },
  { id: "all", label: "Gồm cả văn bản hết hiệu lực" },
] as const;
type PresetId = (typeof PRESETS)[number]["id"];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export default function ChatPage() {
  return (
    <Suspense>
      <ChatScreen />
    </Suspense>
  );
}

function ChatScreen() {
  const searchParams = useSearchParams();
  const sessionParam = searchParams.get("session");
  const scopeParam = searchParams.get("scope"); // từ nút "Hỏi về văn bản này" ở Thư viện

  const [turns, setTurns] = useState<Turn[]>([]);
  const [live, setLive] = useState<Turn | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [draft, setDraft] = useState("");
  const [asOf, setAsOf] = useState("");
  const [mode, setMode] = useState<"qa" | "checklist">("qa");
  // Phạm vi (khởi tạo từ ?scope= khi đến từ nút "Hỏi về văn bản này")
  const [scope, setScope] = useState<string[]>(() => (scopeParam ? [scopeParam] : []));
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickQuery, setPickQuery] = useState("");
  const [preset, setPreset] = useState<PresetId>("live");
  const [lib, setLib] = useState<DocumentSummary[]>([]);
  const threadRef = useRef<HTMLDivElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);

  const loadSessions = useCallback(async () => {
    const { data } = await createClient()
      .from("chat_sessions")
      .select("id,title,created_at")
      .order("created_at", { ascending: false })
      .limit(15);
    setSessions((data as Session[]) ?? []);
  }, []);

  useEffect(() => {
    (async () => {
      await loadSessions();
    })();
    listDocuments()
      .then(setLib)
      .catch(() => {});
  }, [loadSessions]);

  // Mở lại phiên từ sidebar (?session=id)
  useEffect(() => {
    if (!sessionParam) return;
    (async () => {
      const { data } = await createClient()
        .from("chat_messages")
        .select("role,content,citations,conflicts,created_at")
        .eq("session_id", sessionParam)
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
            scopeLabel: "Toàn bộ đang hiệu lực",
            narrow: false,
            resp: {
              answer: a?.content ?? "",
              citations: a?.citations ?? [],
              conflicts: a?.conflicts ?? [],
              session_id: sessionParam,
            },
          });
        }
      }
      setTurns(loaded);
      setSessionId(sessionParam);
      setLive(null);
      setError(null);
    })();
  }, [sessionParam]);

  // Đóng picker khi click ra ngoài / Esc
  useEffect(() => {
    if (!pickerOpen) return;
    const onDown = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) setPickerOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPickerOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onEsc);
    };
  }, [pickerOpen]);

  function scrollBottom() {
    requestAnimationFrame(() => {
      threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
    });
  }

  function scopeText(): string {
    if (scope.length === 1) return scope[0];
    if (scope.length > 1) return `${scope.length} văn bản đã chọn`;
    return PRESETS.find((p) => p.id === preset)?.label ?? "Toàn bộ đang hiệu lực";
  }

  async function ask(q?: string) {
    const question = (q ?? draft).trim();
    if (!question || loading) return;
    setLoading(true);
    setError(null);
    setDraft("");
    const scopeLabel = scopeText();
    const narrow = scope.length > 0;
    setLive({
      question,
      scopeLabel,
      narrow,
      resp: { answer: "", citations: [], conflicts: [], session_id: null },
    });
    scrollBottom();
    try {
      let finished: ChatResponse = { answer: "", citations: [], conflicts: [], session_id: null };
      await streamChat(
        {
          query: question,
          mode,
          as_of: asOf || null,
          top_k: 6,
          session_id: sessionId,
          doc_ids: scope,
        },
        {
          onMeta: (citations) =>
            setLive((l) => l && { ...l, resp: (finished = { ...finished, citations }) }),
          onDelta: (text) =>
            setLive(
              (l) =>
                l && { ...l, resp: (finished = { ...finished, answer: finished.answer + text }) },
            ),
          onConflicts: (conflicts) =>
            setLive((l) => l && { ...l, resp: (finished = { ...finished, conflicts }) }),
          onDone: (sid) => {
            if (sid) setSessionId(sid);
          },
        },
      );
      setTurns((t) => [...t, { question, scopeLabel, narrow, resp: finished }]);
      setLive(null);
      scrollBottom();
      loadSessions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi không xác định");
      setLive(null);
    } finally {
      setLoading(false);
    }
  }

  // Danh sách trong picker theo preset + tìm kiếm
  const q = pickQuery.trim().toLowerCase();
  let pool =
    preset === "all"
      ? lib
      : preset === "live"
        ? lib.filter((d) => d.status === "con_hieu_luc")
        : lib.filter((d) => d.source === preset && d.status === "con_hieu_luc");
  if (q) pool = pool.filter((d) => `${d.doc_id} ${d.title}`.toLowerCase().includes(q));

  const allTurns = [...turns, ...(live ? [live] : [])];

  return (
    <>
      <AppSidebar
        active="chat"
        extra={
          <div className="border-t border-[#E9E3D5] pt-1">
            <SidebarSectionLabel>Gần đây</SidebarSectionLabel>
            <div className="space-y-px">
              {sessions.map((s) => (
                <Link
                  key={s.id}
                  href={`/?session=${s.id}`}
                  className={`block truncate rounded-[9px] px-2.5 py-2 text-[12.5px] leading-snug transition-colors ${
                    s.id === sessionId
                      ? "bg-inset-strong font-medium text-foreground"
                      : "text-dim hover:bg-[#EFEADF]"
                  }`}
                  title={s.title}
                >
                  {s.title}
                </Link>
              ))}
              {sessions.length === 0 && (
                <p className="px-2.5 py-2 text-xs text-muted">Chưa có phiên nào.</p>
              )}
            </div>
          </div>
        }
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* THREAD */}
        <div ref={threadRef} className="flex-1 overflow-y-auto scroll-smooth">
          <div className="mx-auto w-full max-w-[760px] px-6 pb-7 pt-8">
            {/* Intro */}
            {allTurns.length === 0 && (
              <div className="pb-6 pt-1.5 text-center">
                <span className="inline-grid h-11 w-11 place-items-center rounded-xl bg-accent text-[22px] text-white">
                  ⎈
                </span>
                <h1 className="serif mt-3.5 text-[27px] font-medium tracking-[-.015em]">
                  Hỏi về quy định — nhận câu trả lời truy được nguồn
                </h1>
                <p className="mx-auto mt-2 max-w-[480px] text-sm leading-[1.55] text-dim">
                  Mỗi khẳng định gắn với{" "}
                  <span className="serif italic text-accent-hover">
                    điều &amp; khoản đang hiệu lực
                  </span>
                  . Nhấp số trích dẫn để kiểm chứng ngay tại văn bản gốc.
                </p>
              </div>
            )}

            {allTurns.map((t, i) => (
              <TurnView
                key={i}
                turn={t}
                first={i === 0}
                streaming={live !== null && i === turns.length}
                asOf={asOf}
              />
            ))}

            {error && (
              <div className="mt-4 rounded-[13px] border border-red-bd bg-red-bg px-4 py-3 text-sm text-red">
                {error}
              </div>
            )}
            <div className="h-2" />
          </div>
        </div>

        {/* COMPOSER */}
        <div
          className="flex-none px-6 pb-4 pt-1.5"
          style={{ background: "linear-gradient(to top,#F0EEE6 62%,rgba(240,238,230,0))" }}
        >
          <div className="relative mx-auto w-full max-w-[760px]" ref={pickerRef}>
            {/* Popover chọn văn bản */}
            {pickerOpen && (
              <div
                className="absolute inset-x-0 z-30 overflow-hidden rounded-2xl border border-border bg-panel shadow-[0_18px_46px_rgba(40,34,24,.16)]"
                style={{ bottom: "calc(100% + 10px)", animation: "fadeup .16s ease-out" }}
              >
                <div className="flex items-center gap-2.5 border-b border-border-soft px-4 pb-3 pt-3.5">
                  <span className="text-[13.5px] font-semibold tracking-[-.01em]">
                    Chọn văn bản để hỏi
                  </span>
                  <span className="text-[11.5px] text-muted">
                    Giới hạn câu trả lời trong các văn bản bạn chọn
                  </span>
                  <button
                    onClick={() => setPickerOpen(false)}
                    className="ml-auto grid h-6 w-6 place-items-center rounded-[7px] bg-inset text-xs text-faint hover:text-foreground"
                  >
                    ✕
                  </button>
                </div>

                <div className="px-4 pt-3">
                  <input
                    value={pickQuery}
                    onChange={(e) => setPickQuery(e.target.value)}
                    placeholder="Tìm theo số hiệu hoặc tên văn bản…"
                    className="w-full rounded-[10px] border border-border bg-white px-3 py-2 text-[13px] text-fg-body outline-none placeholder:text-muted"
                  />
                  <div className="flex flex-wrap gap-1.5 pb-0.5 pt-2.5">
                    {PRESETS.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => setPreset(p.id)}
                        className={`rounded-full border px-3 py-[5px] text-[11.5px] transition-all ${
                          preset === p.id
                            ? "border-accent bg-accent-wash text-accent-dim"
                            : "border-border bg-panel text-dim hover:border-accent hover:bg-accent-wash hover:text-accent-dim"
                        }`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex max-h-[262px] flex-col gap-0.5 overflow-y-auto px-3 pb-2.5 pt-2">
                  {pool.map((d) => {
                    const on = scope.includes(d.doc_id);
                    return (
                      <button
                        key={d.doc_id}
                        onClick={() =>
                          setScope((s) =>
                            s.includes(d.doc_id)
                              ? s.filter((c) => c !== d.doc_id)
                              : [...s, d.doc_id],
                          )
                        }
                        className={`flex w-full items-start gap-2.5 rounded-[11px] border px-2.5 py-2 text-left transition-colors ${
                          on ? "border-accent-wash-border bg-accent-wash" : "border-transparent"
                        }`}
                      >
                        <span
                          className={`mt-0.5 grid h-[18px] w-[18px] flex-none place-items-center rounded-md border text-[11px] text-white ${
                            on ? "border-accent bg-accent" : "border-[#D8CFBB] bg-white"
                          }`}
                        >
                          {on ? "✓" : ""}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-1.5">
                            <span className="rounded-[5px] bg-[#EFE9DC] px-1.5 py-0.5 text-[9.5px] uppercase tracking-[.04em] text-faint">
                              {d.doc_type}
                            </span>
                            <span className="text-[13px] font-semibold">{d.doc_id}</span>
                            <StatusPill live={d.status === "con_hieu_luc"} small />
                          </span>
                          <span className="mt-1 block truncate text-[11.5px] leading-[1.45] text-dim">
                            {d.title}
                          </span>
                        </span>
                        <span className="mono flex-none text-[10px] text-muted">
                          {d.n_articles} điều
                        </span>
                      </button>
                    );
                  })}
                  {pool.length === 0 && (
                    <div className="px-3 py-5 text-center text-[12.5px] text-muted">
                      Không tìm thấy văn bản phù hợp.
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2.5 border-t border-border-soft bg-sidebar px-4 py-2.5">
                  <span className="text-[11.5px] text-dim">
                    {scope.length
                      ? `${scope.length} văn bản đã chọn`
                      : "Chưa chọn — hỏi trên toàn bộ phạm vi"}
                  </span>
                  <button
                    onClick={() => setScope([])}
                    className="text-[11.5px] font-medium text-accent-dim"
                  >
                    Bỏ chọn tất cả
                  </button>
                  <button
                    onClick={() => setPickerOpen(false)}
                    className="ml-auto rounded-[9px] bg-accent px-3.5 py-1.5 text-[12.5px] font-medium text-white transition-colors hover:bg-accent-hover"
                  >
                    Áp dụng
                  </button>
                </div>
              </div>
            )}

            {/* Khung soạn */}
            <div className="rounded-2xl border border-border bg-panel p-1.5 pl-2 shadow-[0_4px_20px_rgba(40,34,24,.07)]">
              <div className="mb-0.5 flex flex-wrap items-center gap-1.5 border-b border-border-soft pb-2 pt-1">
                <button
                  onClick={() => setPickerOpen(!pickerOpen)}
                  className="flex items-center gap-1.5 rounded-full border border-dashed border-[#D8CFBB] bg-sidebar px-2.5 py-[5px] text-[11.5px] font-medium text-dim transition-all hover:border-accent hover:bg-accent-wash hover:text-accent-dim"
                >
                  ◈ Phạm vi
                  <span className="mono text-[10px] text-muted">
                    {scope.length ? scope.length : "tất cả"}
                  </span>
                </button>
                {scope.map((code) => (
                  <span
                    key={code}
                    className="flex items-center gap-1.5 rounded-full border border-accent-wash-border bg-accent-wash py-1 pl-2.5 pr-1.5 text-[11.5px] text-accent-dim"
                  >
                    {code}
                    <button
                      onClick={() => setScope((s) => s.filter((c) => c !== code))}
                      className="grid h-[15px] w-[15px] place-items-center rounded-full bg-[#EDDCCF] text-[9px] leading-none text-accent-dim"
                    >
                      ✕
                    </button>
                  </span>
                ))}
                {scope.length === 0 && (
                  <span className="text-[11.5px] text-muted">
                    Đang hỏi trên toàn bộ văn bản còn hiệu lực
                  </span>
                )}
              </div>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    ask();
                  }
                }}
                rows={1}
                placeholder="Hỏi tiếp về quy định thanh toán…"
                className="max-h-[120px] w-full resize-none bg-transparent px-2 pb-1 pt-2 text-[15.5px] leading-normal text-fg-body outline-none placeholder:text-muted"
              />
              <div className="flex items-center gap-2 py-0.5 pl-1.5 pr-1">
                <label className="flex items-center gap-1.5 text-[11.5px] text-faint">
                  Hiệu lực tại
                  <input
                    type="date"
                    value={asOf || todayIso()}
                    onChange={(e) => setAsOf(e.target.value)}
                    className="mono rounded-[7px] border border-border bg-white px-2 py-1 text-[11px] text-fg-strong"
                  />
                </label>
                <div className="flex rounded-[7px] border border-border bg-white p-0.5">
                  {(["qa", "checklist"] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={`rounded-[5px] px-2 py-0.5 text-[10.5px] transition-colors ${
                        mode === m ? "bg-inset-strong font-medium text-foreground" : "text-faint"
                      }`}
                    >
                      {m === "qa" ? "Hỏi–đáp" : "Checklist"}
                    </button>
                  ))}
                </div>
                <span className="mono ml-auto text-[10.5px] text-muted">
                  Enter để gửi · Shift+Enter xuống dòng
                </span>
                <button
                  onClick={() => ask()}
                  disabled={loading}
                  className="grid h-[34px] w-[34px] flex-none place-items-center rounded-[10px] bg-accent text-[15px] text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
                >
                  ↑
                </button>
              </div>
            </div>
            <p className="mt-2 text-center text-[10.5px] leading-snug text-muted">
              Thông tin mang tính tham khảo — đối chiếu bản gốc trước khi ra quyết định.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

function StatusPill({ live, small }: { live: boolean; small?: boolean }) {
  return live ? (
    <span
      className={`inline-flex items-center gap-1 rounded-full border border-green-bd bg-green-bg text-green ${
        small ? "px-2 py-px text-[10px]" : "px-2 py-0.5 text-[10.5px]"
      }`}
    >
      <span className="h-[5px] w-[5px] rounded-full bg-green" />
      Đang hiệu lực
    </span>
  ) : (
    <span
      className={`inline-flex items-center rounded-full border border-border bg-grey-bg text-grey ${
        small ? "px-2 py-px text-[10px]" : "px-2 py-0.5 text-[10.5px]"
      }`}
    >
      Hết hiệu lực
    </span>
  );
}

// Tách answer thành đoạn text + nút trích dẫn superscript từ các ngoặc [Văn bản — Điều X].
function renderAnswer(answer: string, citations: Citation[], onCite: (i: number) => void) {
  const parts = answer.split(/(\[[^\[\]\n]{3,90}\])/g);
  return parts.map((part, pi) => {
    const m = part.match(/^\[([^\[\]\n]{3,90})\]$/);
    if (m) {
      const inner = m[1].toLowerCase();
      const idx = citations.findIndex(
        (c) =>
          inner.includes(c.article.toLowerCase()) ||
          inner.includes(c.doc_title.toLowerCase().slice(0, 20)),
      );
      if (idx >= 0) {
        return (
          <button
            key={pi}
            onClick={() => onCite(idx)}
            title={m[1]}
            className="mono mx-px cursor-pointer rounded-md bg-cite px-1.5 py-0.5 align-super text-[10px] font-semibold leading-none text-accent-dim transition-all hover:bg-accent hover:text-white"
          >
            {idx + 1}
          </button>
        );
      }
    }
    return <Fragment key={pi}>{part}</Fragment>;
  });
}

function TurnView({
  turn,
  first,
  streaming,
  asOf,
}: {
  turn: Turn;
  first: boolean;
  streaming: boolean;
  asOf: string;
}) {
  const { resp } = turn;
  const [conflictOpen, setConflictOpen] = useState(true);
  const [sourcesOpen, setSourcesOpen] = useState(true);
  const [copied, setCopied] = useState(false);
  const [active, setActive] = useState<number | null>(null);
  const liveCount = resp.citations.filter((c) => !c.valid_to).length;

  function cite(i: number) {
    setSourcesOpen(true);
    setActive(i);
    requestAnimationFrame(() => {
      const nodes = document.querySelectorAll(`[data-src="${i}"]`);
      (nodes[nodes.length - 1] as HTMLElement | undefined)?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    });
    setTimeout(() => setActive(null), 1500);
  }

  function copyAnswer() {
    try {
      navigator.clipboard.writeText(resp.answer);
    } catch {}
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className={`fadeup py-[22px] ${first ? "" : "mt-1 border-t border-border"}`}>
      {/* Phạm vi ghim theo lượt */}
      <div className="mb-1.5 mr-[38px] flex items-center justify-end gap-1.5">
        <span className="mono text-[10px] text-muted">Phạm vi</span>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-[10.5px] ${
            turn.narrow
              ? "border-accent-wash-border bg-accent-wash text-accent-dim"
              : "border-border bg-sidebar text-faint"
          }`}
        >
          {turn.scopeLabel}
        </span>
      </div>

      {/* Bong bóng người dùng */}
      <div className="mb-1 flex justify-end gap-2.5">
        <div className="serif max-w-[78%] rounded-[16px_16px_5px_16px] border border-user-bubble-border bg-user-bubble px-4 py-[11px] text-base leading-normal text-fg-strong">
          {turn.question}
        </div>
        <span className="mt-0.5 grid h-7 w-7 flex-none place-items-center rounded-full bg-avatar text-[11px] font-semibold text-accent-dim">
          ⚑
        </span>
      </div>

      {/* Trả lời */}
      <div className="mt-4 flex gap-2.5">
        <span className="mt-0.5 grid h-7 w-7 flex-none place-items-center rounded-lg bg-accent text-sm text-white">
          ⎈
        </span>
        <div className="min-w-0 flex-1">
          {/* Trust bar */}
          <div className="mb-3 flex flex-wrap items-center gap-1.5">
            {resp.citations.length > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-green-bd bg-green-bg px-2.5 py-[3px] text-[11.5px] text-green">
                <span className="h-1.5 w-1.5 rounded-full bg-green" />
                {liveCount} nguồn đang hiệu lực
              </span>
            )}
            {resp.conflicts.length > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-bd bg-amber-bg px-2.5 py-[3px] text-[11.5px] text-amber">
                ⚠ {resp.conflicts.length} mâu thuẫn
              </span>
            )}
            <span className="mono ml-0.5 text-[10.5px] text-muted">
              tra tại {fmtDate(asOf || todayIso())}
            </span>
          </div>

          {/* Cảnh báo mâu thuẫn */}
          {resp.conflicts.length > 0 && (
            <div className="mb-3.5 overflow-hidden rounded-[13px] border border-amber-bd bg-amber-bg">
              <button
                onClick={() => setConflictOpen(!conflictOpen)}
                className="flex w-full items-center gap-3 px-3.5 py-3 text-left"
              >
                <span className="grid h-7 w-7 flex-none place-items-center rounded-lg bg-accent text-sm text-white">
                  ⚠
                </span>
                <span className="flex-1">
                  <span className="block text-[9.5px] font-semibold uppercase tracking-[.09em] text-accent-hover">
                    Mâu thuẫn ·{" "}
                    {resp.conflicts[0].severity === "critical"
                      ? "Nghiêm trọng"
                      : resp.conflicts[0].severity === "info"
                        ? "Thông tin"
                        : "Cảnh báo"}
                  </span>
                  <span className="mt-0.5 block text-[13px] leading-[1.4] text-[#5C4A40]">
                    {resp.conflicts.length === 1
                      ? "Phát hiện quy định không thống nhất giữa hai văn bản."
                      : `Phát hiện ${resp.conflicts.length} điểm không thống nhất giữa các văn bản.`}
                  </span>
                </span>
                <span className="mono flex-none text-[11px] text-accent-hover">
                  {conflictOpen ? "Thu gọn ▲" : "Chi tiết ▼"}
                </span>
              </button>
              {conflictOpen && (
                <div className="space-y-3 px-3.5 pb-3.5 pl-[53px]">
                  {resp.conflicts.map((c, i) => (
                    <div key={i}>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 rounded-[10px] border border-amber-bd bg-white px-3 py-2.5">
                          <div className="mono text-[10px] text-accent-hover">
                            {c.doc_a} · {c.article_a}
                          </div>
                        </div>
                        <div className="text-[15px] text-accent-hover">↔</div>
                        <div className="flex-1 rounded-[10px] border border-amber-bd bg-white px-3 py-2.5">
                          <div className="mono text-[10px] text-accent-hover">
                            {c.doc_b} · {c.article_b}
                          </div>
                        </div>
                      </div>
                      <p className="mt-2 text-xs leading-normal text-dim">{c.explanation}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Câu trả lời */}
          <p className="serif whitespace-pre-wrap text-[17.5px] leading-[1.68] text-fg-body">
            {resp.answer ? renderAnswer(resp.answer, resp.citations, cite) : streaming ? "…" : ""}
          </p>

          {/* Action row */}
          {!streaming && resp.answer && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <button
                onClick={copyAnswer}
                className="flex items-center gap-1 rounded-[7px] bg-inset px-2.5 py-1.5 text-[11.5px] text-faint transition-colors hover:text-foreground"
              >
                {copied ? "✓ Đã sao chép" : "⧉ Sao chép kèm nguồn"}
              </button>
              {resp.citations.length > 0 && (
                <button
                  onClick={() => setSourcesOpen(!sourcesOpen)}
                  className="flex items-center gap-1 rounded-[7px] bg-inset px-2.5 py-1.5 text-[11.5px] text-faint transition-colors hover:text-foreground"
                >
                  {sourcesOpen ? "⌄ Ẩn nguồn" : `⌃ Hiện ${resp.citations.length} nguồn`}
                </button>
              )}
              {resp.citations.length > 0 && (
                <span className="ml-0.5 text-[11px] text-muted">Nhấp số ¹ ² để kiểm chứng</span>
              )}
            </div>
          )}

          {/* Nguồn */}
          {sourcesOpen && resp.citations.length > 0 && (
            <div className="mt-3.5 flex flex-col gap-2.5">
              {resp.citations.map((c, i) => {
                const anchor = articleAnchor(c.article);
                return (
                  <div
                    key={i}
                    data-src={i}
                    className="rounded-[13px] border bg-panel transition-colors"
                    style={{
                      borderColor: active === i ? "#CC785C" : "var(--border)",
                      animation: active === i ? "srcflash 1.4s ease-out" : undefined,
                    }}
                  >
                    <div className="flex items-start gap-3 px-4 py-3">
                      <span className="mono grid h-[23px] w-[23px] flex-none place-items-center rounded-[7px] bg-cite text-[11.5px] font-semibold text-accent-dim">
                        {i + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-[5px] bg-inset px-1.5 py-0.5 text-[9.5px] uppercase tracking-[.04em] text-faint">
                            {c.doc_type}
                          </span>
                          <span className="text-[13.5px] font-semibold">{c.doc_title}</span>
                          <span className="mono text-[11px] text-accent-hover">{c.article}</span>
                          <StatusPill live={!c.valid_to} />
                          <span className="mono ml-auto text-[10px] text-muted">
                            từ {c.valid_from ?? "—"}
                          </span>
                        </div>
                        <p className="serif mt-2.5 text-sm italic leading-[1.6] text-fg-strong">
                          “{c.snippet}
                          {c.snippet.length >= 280 ? "…" : ""}”
                        </p>
                        <div className="mt-2.5 flex items-center gap-3.5">
                          <Link
                            href={`/docs/${encodeURIComponent(c.doc_id)}${anchor ? `#${anchor}` : ""}`}
                            className="text-[11.5px] font-medium text-accent-hover hover:text-accent-dim"
                          >
                            Mở toàn văn điều khoản ↗
                          </Link>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
