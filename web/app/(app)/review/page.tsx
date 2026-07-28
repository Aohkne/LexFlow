"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppSidebar, { SidebarSectionLabel } from "@/components/app-sidebar";
import { Lexi } from "@/components/lexi";
import { articleAnchor } from "@/lib/anchors";
import {
  listDocuments,
  runReview,
  type DocumentSummary,
  type ReviewFinding,
  type ReviewResult,
} from "@/lib/api";

/** Màn Kiểm tra tài liệu (tuân thủ) — gọi backend POST /reviews thật:
 *  mỗi điều nội bộ → retrieval điều luật trong phạm vi chọn → Gemini phán định
 *  violation/warning/pass → findings + điểm tuân thủ. */

type Verdict = ReviewFinding["verdict"];

const VERDICT_META: Record<
  Verdict,
  { label: string; glyph: string; fg: string; bg: string; bd: string }
> = {
  violation: { label: "Vi phạm", glyph: "✕", fg: "text-red", bg: "bg-red-bg", bd: "border-red-bd" },
  warning: { label: "Cảnh báo", glyph: "⚠", fg: "text-amber", bg: "bg-amber-bg", bd: "border-amber-bd" },
  pass: { label: "Tuân thủ", glyph: "✓", fg: "text-green", bg: "bg-green-bg", bd: "border-green-bd" },
};

type TimeMode = "today" | "date" | "future";
type Phase = "idle" | "running" | "done" | "error";

export default function ReviewPage() {
  const [internals, setInternals] = useState<DocumentSummary[]>([]);
  const [externals, setExternals] = useState<DocumentSummary[]>([]);
  const [internalId, setInternalId] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "live">("all");
  const [timeMode, setTimeMode] = useState<TimeMode>("today");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"all" | Verdict>("all");
  const [open, setOpen] = useState<Record<number, boolean>>({ 0: true });

  useEffect(() => {
    listDocuments()
      .then((d) => {
        const ins = d.filter((x) => x.source === "internal");
        setInternals(ins);
        setInternalId((cur) => cur ?? ins[0]?.doc_id ?? null);
        const ext = d.filter((x) => x.source === "external");
        setExternals(ext);
        setPicked(
          new Set(
            ext.filter((x) => x.status === "con_hieu_luc").slice(0, 3).map((x) => x.doc_id),
          ),
        );
      })
      .catch(() => {});
  }, []);

  const pool = useMemo(() => {
    let p = externals;
    if (filter === "live") p = p.filter((d) => d.status === "con_hieu_luc");
    const q = search.trim().toLowerCase();
    if (q) p = p.filter((d) => `${d.doc_id} ${d.title}`.toLowerCase().includes(q));
    return p;
  }, [externals, filter, search]);

  async function execute() {
    if (!internalId || picked.size === 0) return;
    setPhase("running");
    setError(null);
    try {
      const res = await runReview({
        internal_doc_id: internalId,
        against_doc_ids: [...picked],
        as_of: timeMode === "today" ? null : date,
      });
      setResult(res);
      setTab("all");
      setOpen({ 0: true });
      setPhase("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi không xác định");
      setPhase("error");
    }
  }

  const counts = result?.counts ?? { violation: 0, warning: 0, pass: 0 };
  const findings = result
    ? tab === "all"
      ? result.findings
      : result.findings.filter((f) => f.verdict === tab)
    : [];

  const timeHint: Record<TimeMode, string> = {
    today: "Đối chiếu với các văn bản đang hiệu lực hôm nay.",
    date: "Đối chiếu tại một ngày cụ thể — dùng khi rà soát hồi tố.",
    future: "Kiểm tra trước với văn bản sắp có hiệu lực để chủ động chỉnh sửa.",
  };

  return (
    <>
      <AppSidebar
        active="review"
        primaryLabel="✚ Phiên kiểm tra mới"
        primaryHref="/review"
        extra={
          <div className="border-t border-[#E9E3D5] pt-1">
            <SidebarSectionLabel>Phiên kiểm tra gần đây</SidebarSectionLabel>
            <div className="px-2.5 py-2 text-xs leading-relaxed text-muted">
              Kết quả chưa được lưu giữa các phiên — lịch sử kiểm tra sẽ bổ sung sau.
            </div>
          </div>
        }
      />

      {/* CONFIG PANEL */}
      <div className="flex w-[352px] flex-none flex-col border-r border-border bg-panel">
        <div className="border-b border-border-soft px-5 pb-3.5 pt-5">
          <h1 className="serif text-[22px] font-medium tracking-[-.015em]">Kiểm tra tuân thủ</h1>
          <p className="mt-1 text-[12.5px] leading-snug text-dim">
            Đối chiếu tài liệu nội bộ với văn bản pháp luật tại một mốc thời gian.
          </p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {/* Bước 1 */}
          <StepLabel n={1} label="Tài liệu nội bộ" />
          <div className="mt-2 overflow-hidden rounded-[11px] border border-border">
            {internals.map((d) => {
              const on = d.doc_id === internalId;
              return (
                <label
                  key={d.doc_id}
                  className={`flex cursor-pointer items-start gap-2.5 border-b border-border-soft px-3 py-2.5 last:border-b-0 ${
                    on ? "bg-accent-wash" : "bg-panel"
                  }`}
                >
                  <input
                    type="radio"
                    name="internal-doc"
                    checked={on}
                    onChange={() => setInternalId(d.doc_id)}
                    className="mt-0.5 accent-[#CC785C]"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[12px] font-semibold">{d.doc_id}</span>
                    <span className="mt-0.5 block truncate text-[11px] text-dim">{d.title}</span>
                  </span>
                  <span className="mono mt-0.5 flex-none text-[10px] text-muted">
                    {d.n_articles} điều
                  </span>
                </label>
              );
            })}
            {internals.length === 0 && (
              <div className="bg-panel px-3 py-4 text-center text-[11.5px] text-muted">
                Chưa tải được danh sách tài liệu nội bộ.
              </div>
            )}
          </div>

          {/* Bước 2 */}
          <div className="mt-5 flex items-center">
            <StepLabel n={2} label="Văn bản đối chiếu" />
            <span className="ml-auto rounded-full border border-accent-wash-border bg-accent-wash px-2 py-0.5 text-[10.5px] text-accent-dim">
              {picked.size} đã chọn
            </span>
          </div>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm văn bản…"
            className="mt-2 w-full rounded-[10px] border border-border bg-white px-3 py-2 text-[12.5px] outline-none placeholder:text-muted focus:border-accent"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(
              [
                ["all", "Tất cả"],
                ["live", "Đang hiệu lực"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                onClick={() => setFilter(id)}
                className={`rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                  filter === id ? "bg-accent text-white" : "bg-inset text-dim hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="mt-2.5 overflow-hidden rounded-[11px] border border-border">
            {pool.map((d) => {
              const on = picked.has(d.doc_id);
              const expired = d.status !== "con_hieu_luc";
              return (
                <label
                  key={d.doc_id}
                  className={`flex cursor-pointer items-start gap-2.5 border-b border-border-soft px-3 py-2.5 last:border-b-0 ${
                    on ? "bg-[#F3F0E7]" : "bg-panel"
                  } ${expired ? "opacity-60" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() =>
                      setPicked((p) => {
                        const next = new Set(p);
                        if (next.has(d.doc_id)) next.delete(d.doc_id);
                        else next.add(d.doc_id);
                        return next;
                      })
                    }
                    className="mt-0.5 accent-[#CC785C]"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[12px] font-semibold">{d.doc_id}</span>
                      {expired ? (
                        <span className="rounded-full border border-border bg-grey-bg px-1.5 py-px text-[9.5px] text-grey">
                          Hết hiệu lực
                        </span>
                      ) : (
                        <span className="rounded-full border border-green-bd bg-green-bg px-1.5 py-px text-[9.5px] text-green">
                          Đang hiệu lực
                        </span>
                      )}
                    </span>
                    <span className="mt-0.5 block truncate text-[11px] text-dim">{d.title}</span>
                  </span>
                </label>
              );
            })}
            {pool.length === 0 && (
              <div className="bg-panel px-3 py-4 text-center text-[11.5px] text-muted">
                Không tìm thấy văn bản.
              </div>
            )}
          </div>
          <p className="mt-2 text-[10.5px] leading-snug text-muted">
            Câu trả lời chỉ đối chiếu trong các văn bản được chọn.
          </p>

          {/* Bước 3 */}
          <div className="mt-5">
            <StepLabel n={3} label="Thời điểm kiểm tra" />
          </div>
          <div className="mt-2 flex rounded-[11px] bg-[#E7E3D8] p-[3px] text-[11.5px]">
            {(
              [
                ["today", "Hôm nay"],
                ["date", "Ngày cụ thể"],
                ["future", "Mốc sắp tới"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                onClick={() => setTimeMode(id)}
                className={`flex-1 rounded-lg px-2 py-1 transition-all ${
                  timeMode === id
                    ? "bg-panel font-medium shadow-[0_1px_2px_rgba(40,34,24,.12)]"
                    : "text-faint"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {timeMode !== "today" && (
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mono mt-2 w-full rounded-[8px] border border-border bg-white px-2.5 py-1.5 text-[11.5px] text-fg-strong"
            />
          )}
          <p className="mt-1.5 text-[10.5px] leading-snug text-muted">{timeHint[timeMode]}</p>
        </div>

        <div className="border-t border-border-soft px-5 py-3.5">
          <button
            onClick={execute}
            disabled={!internalId || picked.size === 0 || phase === "running"}
            className="w-full rounded-[10px] bg-accent px-3.5 py-2.5 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {phase === "running" ? "Đang kiểm tra…" : `Chạy kiểm tra ${picked.size} văn bản`}
          </button>
          <p className="mono mt-1.5 text-center text-[10px] text-muted">
            Mỗi điều nội bộ được đối chiếu bằng AI — có thể mất ~30 giây
          </p>
        </div>
      </div>

      {/* RESULTS */}
      <div className="min-w-0 flex-1 overflow-y-auto">
        <div className="max-w-[820px] px-8 pb-14 pt-6">
          {phase === "idle" ? (
            <div className="grid h-[70vh] place-items-center text-center">
              <div>
                <span className="inline-grid h-24 w-24 place-items-center rounded-[26px] border border-accent-wash-border bg-accent-wash">
                  <Lexi state="idle" size={66} />
                </span>
                <h2 className="serif mt-3 text-[22px] font-medium">Chưa có phiên kiểm tra</h2>
                <p className="mx-auto mt-1.5 max-w-[380px] text-[13px] leading-relaxed text-dim">
                  Chọn tài liệu nội bộ và văn bản đối chiếu ở panel trái rồi bấm{" "}
                  <span className="font-medium text-accent-dim">Chạy kiểm tra</span>.
                </p>
              </div>
            </div>
          ) : phase === "running" ? (
            <div className="grid h-[70vh] place-items-center text-center">
              <div>
                <span className="inline-grid h-24 w-24 place-items-center rounded-[26px] border border-accent-wash-border bg-accent-wash">
                  <Lexi state="reading" size={66} />
                </span>
                <h2 className="serif mt-3 text-[22px] font-medium">
                  Đang đối chiếu {picked.size} văn bản…
                </h2>
                <p className="mx-auto mt-1.5 max-w-[380px] text-[13px] leading-relaxed text-dim">
                  Lexi rà từng điều của tài liệu nội bộ với quy định pháp luật đã chọn.
                </p>
              </div>
            </div>
          ) : phase === "error" ? (
            <div className="grid h-[70vh] place-items-center text-center">
              <div>
                <span className="inline-grid h-24 w-24 place-items-center rounded-[26px] border border-red-bd bg-red-bg">
                  <Lexi state="error" size={66} />
                </span>
                <h2 className="serif mt-3 text-[22px] font-medium">Không kiểm tra được</h2>
                <p className="mx-auto mt-1.5 max-w-[400px] text-[13px] leading-relaxed text-red">
                  {error}
                </p>
                <button
                  onClick={execute}
                  className="mt-4 rounded-[10px] bg-accent px-5 py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
                >
                  Thử lại
                </button>
              </div>
            </div>
          ) : result ? (
            <>
              <div className="flex flex-wrap items-center gap-2.5">
                <Lexi state={counts.violation > 0 ? "conflict" : "found"} size={40} />
                <h2 className="serif text-[25px] font-medium tracking-[-.015em]">
                  {result.internal_doc_id} — {result.internal_title}
                </h2>
                {counts.violation > 0 ? (
                  <span className="rounded-full border border-red-bd bg-red-bg px-2.5 py-0.5 text-[11px] text-red">
                    Cần xử lý
                  </span>
                ) : counts.warning > 0 ? (
                  <span className="rounded-full border border-amber-bd bg-amber-bg px-2.5 py-0.5 text-[11px] text-amber">
                    Cần rà soát
                  </span>
                ) : (
                  <span className="rounded-full border border-green-bd bg-green-bg px-2.5 py-0.5 text-[11px] text-green">
                    Đạt
                  </span>
                )}
              </div>
              <div className="mono mt-1 text-[11px] text-muted">
                Đối chiếu {result.against_doc_ids.length} văn bản · hiệu lực tại {result.as_of}
              </div>

              {/* Score strip */}
              <div className="mt-4 grid grid-cols-2 gap-px overflow-hidden rounded-[14px] border border-border bg-border lg:grid-cols-[1.25fr_1fr_1fr_1fr]">
                <div className="bg-panel px-4 py-3.5">
                  <div className="text-[10px] font-semibold uppercase tracking-[.1em] text-faint">
                    Mức tuân thủ
                  </div>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className="serif text-[32px] font-medium">{result.score}</span>
                    <span className="mono text-[11px] text-muted">/100</span>
                  </div>
                  <div className="mt-1.5 h-[5px] overflow-hidden rounded-full bg-inset-strong">
                    <div
                      className="h-full rounded-full bg-accent"
                      style={{ width: `${result.score}%` }}
                    />
                  </div>
                </div>
                {(
                  [
                    ["Vi phạm", counts.violation, "text-red"],
                    ["Cảnh báo", counts.warning, "text-amber"],
                    ["Tuân thủ", counts.pass, "text-green"],
                  ] as const
                ).map(([label, n, cls]) => (
                  <div key={label} className="bg-panel px-4 py-3.5">
                    <div className="text-[10px] font-semibold uppercase tracking-[.1em] text-faint">
                      {label}
                    </div>
                    <div className={`serif mt-1 text-[32px] font-medium ${cls}`}>{n}</div>
                  </div>
                ))}
              </div>

              {/* Findings */}
              <div className="mt-6 flex items-center gap-3">
                <h3 className="serif text-[17px] font-medium">Phát hiện</h3>
                <div className="flex rounded-[11px] bg-[#E7E3D8] p-[3px] text-[11.5px]">
                  {(
                    [
                      ["all", `Tất cả ${result.findings.length}`],
                      ["violation", `Vi phạm ${counts.violation}`],
                      ["warning", `Cảnh báo ${counts.warning}`],
                      ["pass", `Tuân thủ ${counts.pass}`],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      onClick={() => setTab(id)}
                      className={`rounded-lg px-2.5 py-1 transition-all ${
                        tab === id
                          ? "bg-panel font-medium shadow-[0_1px_2px_rgba(40,34,24,.12)]"
                          : "text-faint"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-3 space-y-2.5">
                {findings.map((f, i) => {
                  const meta = VERDICT_META[f.verdict];
                  const isOpen = !!open[i];
                  const anchor = f.legal_ref ? articleAnchor(f.legal_ref) : "";
                  return (
                    <div key={i} className="overflow-hidden rounded-[14px] border border-border bg-panel">
                      <button
                        onClick={() => setOpen((o) => ({ ...o, [i]: !o[i] }))}
                        className="flex w-full items-start gap-3 px-4 py-3.5 text-left"
                      >
                        <span
                          className={`grid h-[30px] w-[30px] flex-none place-items-center rounded-[9px] border text-sm ${meta.bg} ${meta.bd} ${meta.fg}`}
                        >
                          {meta.glyph}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-2">
                            <span
                              className={`rounded-full border px-2 py-px text-[10px] ${meta.bg} ${meta.bd} ${meta.fg}`}
                            >
                              {meta.label}
                            </span>
                            <span className="mono text-[10px] text-muted">{f.article}</span>
                          </span>
                          <span className="mt-1 block text-[14.5px] font-semibold leading-snug">
                            {f.title}
                          </span>
                          <span className="mt-0.5 block text-[12.5px] leading-snug text-dim">
                            {f.summary}
                          </span>
                        </span>
                        <span className="mono flex-none text-[11px] text-accent-hover">
                          {isOpen ? "Thu gọn ▲" : "Chi tiết ▼"}
                        </span>
                      </button>
                      {isOpen && (
                        <div className="px-4 pb-4 pl-[54px]">
                          <div className="grid gap-2.5 md:grid-cols-2">
                            <div className="rounded-[10px] bg-background p-3">
                              <div className="mono text-[10px] text-faint">
                                Tài liệu nội bộ · {f.article}
                              </div>
                              <p className="serif mt-1.5 text-[13px] italic leading-relaxed text-fg-strong">
                                “{f.internal_quote}”
                              </p>
                            </div>
                            <div
                              className={`rounded-[10px] border bg-white p-3 ${
                                f.legal_live ? "border-green-bd" : "border-border"
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                <span className="mono text-[10px] text-accent-hover">
                                  {f.legal_ref ?? "Không có căn cứ đối chiếu"}
                                </span>
                                {f.legal_ref && f.legal_live && (
                                  <span className="rounded-full border border-green-bd bg-green-bg px-1.5 py-px text-[9.5px] text-green">
                                    Đang hiệu lực
                                  </span>
                                )}
                              </div>
                              {f.legal_quote && (
                                <p className="serif mt-1.5 text-[13px] italic leading-relaxed text-fg-strong">
                                  “{f.legal_quote}”
                                </p>
                              )}
                              {f.legal_doc_id && (
                                <Link
                                  href={`/docs/${encodeURIComponent(f.legal_doc_id)}${anchor ? `#${anchor}` : ""}`}
                                  className="mt-2 inline-block text-[11px] font-medium text-accent-hover hover:text-accent-dim"
                                >
                                  Mở toàn văn điều khoản ↗
                                </Link>
                              )}
                            </div>
                          </div>
                          {f.suggestion && (
                            <div className="mt-2.5 rounded-[10px] border border-amber-bd bg-amber-bg p-3">
                              <div className="text-[10px] font-semibold uppercase tracking-[.08em] text-accent-hover">
                                Đề xuất chỉnh sửa
                              </div>
                              <p className="mt-1 text-[12.5px] leading-relaxed text-fg-strong">
                                {f.suggestion}
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
                {findings.length === 0 && (
                  <p className="py-6 text-center text-[12.5px] text-muted">
                    Không có phát hiện nào trong nhóm này.
                  </p>
                )}
              </div>

              <p className="mt-6 text-center text-[10.5px] text-muted">
                Kết quả do AI đối chiếu, mang tính hỗ trợ rà soát — vui lòng kiểm chứng với bản gốc
                trước khi ban hành tài liệu.
              </p>
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}

function StepLabel({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="mono text-[20px] font-semibold leading-none text-accent">{n}</span>
      <span className="text-[12.5px] font-semibold uppercase tracking-[.06em] text-fg-strong">
        {label}
      </span>
    </div>
  );
}
