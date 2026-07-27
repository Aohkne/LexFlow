"use client";

import { useEffect, useMemo, useState } from "react";
import AppSidebar, { SidebarSectionLabel } from "@/components/app-sidebar";
import { listDocuments, type DocumentSummary } from "@/lib/api";

/**
 * Màn Kiểm tra tài liệu (tuân thủ) — UI theo design handoff.
 * LƯU Ý: backend POST /reviews chưa tồn tại; phần "Kết quả" hiển thị DỮ LIỆU MINH HỌA
 * để chốt UX trước (xem docs/DESIGN-GAP.md).
 */

type Verdict = "violation" | "warning" | "pass";

type Finding = {
  verdict: Verdict;
  location: string;
  title: string;
  summary: string;
  internalQuote: string;
  legalRef: string;
  legalQuote: string;
  legalLive: boolean;
  suggestion: string;
};

const DEMO_FINDINGS: Finding[] = [
  {
    verdict: "violation",
    location: "Mục 3.1, trang 4",
    title: "Hạn mức ví điện tử vượt trần quy định",
    summary: "Tài liệu nội bộ đặt hạn mức 150 triệu đồng/tháng — vượt mức trần 100 triệu.",
    internalQuote:
      "Tổng hạn mức giao dịch qua ví điện tử nhanh của một khách hàng cá nhân tối đa là 150 triệu đồng trong một tháng.",
    legalRef: "TT 40/2024/TT-NHNN · Điều 26",
    legalQuote:
      "Tổng hạn mức giao dịch qua các Ví điện tử cá nhân của 1 khách hàng tại 1 tổ chức cung ứng dịch vụ Ví điện tử tối đa là 100 triệu đồng Việt Nam trong một tháng.",
    legalLive: true,
    suggestion: "Hạ hạn mức tháng về tối đa 100 triệu đồng, hoặc bổ sung căn cứ thỏa thuận riêng theo quy định NHNN.",
  },
  {
    verdict: "warning",
    location: "Mục 2.2, trang 3",
    title: "Kích hoạt ví trước khi hoàn tất liên kết tài khoản",
    summary: "Cho phép dùng ví ngay sau eKYC, hoãn liên kết tài khoản 30 ngày — rủi ro không tuân thủ điều kiện sử dụng ví.",
    internalQuote:
      "Ví điện tử nhanh được kích hoạt và sử dụng ngay sau khi hoàn tất eKYC mà không bắt buộc phải hoàn thành liên kết với tài khoản thanh toán.",
    legalRef: "TT 40/2024/TT-NHNN · Điều 22",
    legalQuote:
      "Khách hàng chỉ được sử dụng Ví điện tử sau khi đã hoàn thành việc liên kết Ví điện tử với tài khoản đồng Việt Nam hoặc thẻ ghi nợ của khách hàng.",
    legalLive: true,
    suggestion: "Yêu cầu hoàn tất liên kết trước khi cho phép giao dịch, hoặc giới hạn ví ở trạng thái 'chưa kích hoạt' đến khi liên kết.",
  },
  {
    verdict: "pass",
    location: "Mục 1, trang 1–2",
    title: "Phạm vi và định danh eKYC",
    summary: "Quy trình định danh khách hàng bằng CCCD gắn chip phù hợp quy định hiện hành.",
    internalQuote:
      "Khách hàng cá nhân được mở ví điện tử nhanh hoàn toàn trực tuyến bằng định danh điện tử (eKYC) với căn cước công dân gắn chip.",
    legalRef: "NĐ 52/2024/NĐ-CP · Điều 25",
    legalQuote: "Việc mở ví điện tử bằng phương thức điện tử thực hiện theo quy định về định danh và xác thực khách hàng.",
    legalLive: true,
    suggestion: "",
  },
];

const VERDICT_META: Record<
  Verdict,
  { label: string; glyph: string; fg: string; bg: string; bd: string }
> = {
  violation: { label: "Vi phạm", glyph: "✕", fg: "text-red", bg: "bg-red-bg", bd: "border-red-bd" },
  warning: { label: "Cảnh báo", glyph: "⚠", fg: "text-amber", bg: "bg-amber-bg", bd: "border-amber-bd" },
  pass: { label: "Tuân thủ", glyph: "✓", fg: "text-green", bg: "bg-green-bg", bd: "border-green-bd" },
};

type TimeMode = "today" | "date" | "future";

export default function ReviewPage() {
  const [lib, setLib] = useState<DocumentSummary[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "live" | "external" | "internal">("all");
  const [timeMode, setTimeMode] = useState<TimeMode>("today");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [ran, setRan] = useState(false);
  const [tab, setTab] = useState<"all" | Verdict>("all");
  const [open, setOpen] = useState<Record<number, boolean>>({ 0: true });

  useEffect(() => {
    listDocuments()
      .then((d) => {
        setLib(d.filter((x) => x.source === "external"));
        setPicked(
          new Set(
            d
              .filter((x) => x.source === "external" && x.status === "con_hieu_luc")
              .slice(0, 3)
              .map((x) => x.doc_id),
          ),
        );
      })
      .catch(() => {});
  }, []);

  const pool = useMemo(() => {
    let p = lib;
    if (filter === "live") p = p.filter((d) => d.status === "con_hieu_luc");
    if (filter === "external") p = p.filter((d) => d.source === "external");
    if (filter === "internal") p = p.filter((d) => d.source === "internal");
    const q = search.trim().toLowerCase();
    if (q) p = p.filter((d) => `${d.doc_id} ${d.title}`.toLowerCase().includes(q));
    return p;
  }, [lib, filter, search]);

  const counts = {
    violation: DEMO_FINDINGS.filter((f) => f.verdict === "violation").length,
    warning: DEMO_FINDINGS.filter((f) => f.verdict === "warning").length,
    pass: DEMO_FINDINGS.filter((f) => f.verdict === "pass").length,
  };
  const findings = tab === "all" ? DEMO_FINDINGS : DEMO_FINDINGS.filter((f) => f.verdict === tab);

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
              Chưa có phiên nào được lưu — lịch sử phiên sẽ nối với backend kiểm tra tuân thủ.
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
          <div className="mt-2 rounded-[12px] border border-border bg-background p-3">
            <div className="flex items-start gap-3">
              <span className="grid h-9 w-[30px] flex-none place-items-center rounded-md border border-border bg-panel text-[9px] font-bold text-accent-hover">
                TXT
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium">
                  SHB-QD-VINHANH-2026 — Quy định ví điện tử nhanh
                </div>
                <div className="mono mt-0.5 text-[10px] text-muted">4 điều · quy định nội bộ mẫu</div>
              </div>
            </div>
            <div className="mt-2.5 flex gap-2">
              <button className="rounded-[7px] bg-inset px-2.5 py-1.5 text-[11.5px] text-faint" disabled>
                Đổi tài liệu
              </button>
              <button className="rounded-[7px] bg-inset px-2.5 py-1.5 text-[11.5px] text-faint" disabled>
                Xem trước
              </button>
            </div>
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
                ["external", "Pháp luật"],
                ["internal", "Nội bộ"],
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
            Mặc định LexFlow đề xuất văn bản theo chủ đề của tài liệu nội bộ.
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
            onClick={() => setRan(true)}
            disabled={picked.size === 0}
            className="w-full rounded-[10px] bg-accent px-3.5 py-2.5 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            Chạy kiểm tra {picked.size} văn bản
          </button>
          <p className="mono mt-1.5 text-center text-[10px] text-muted">
            Bản xem trước UI — kết quả bên phải là dữ liệu minh họa
          </p>
        </div>
      </div>

      {/* RESULTS */}
      <div className="min-w-0 flex-1 overflow-y-auto">
        <div className="max-w-[820px] px-8 pb-14 pt-6">
          {!ran ? (
            <div className="grid h-[70vh] place-items-center text-center">
              <div>
                <span className="inline-grid h-11 w-11 place-items-center rounded-xl bg-accent text-[20px] text-white">
                  ⎗
                </span>
                <h2 className="serif mt-3 text-[22px] font-medium">Chưa có phiên kiểm tra</h2>
                <p className="mx-auto mt-1.5 max-w-[380px] text-[13px] leading-relaxed text-dim">
                  Chọn văn bản đối chiếu ở panel trái rồi bấm{" "}
                  <span className="font-medium text-accent-dim">Chạy kiểm tra</span> để xem báo cáo
                  mẫu.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2.5">
                <h2 className="serif text-[25px] font-medium tracking-[-.015em]">
                  SHB-QD-VINHANH-2026 — Ví điện tử nhanh
                </h2>
                <span className="rounded-full border border-amber-bd bg-amber-bg px-2.5 py-0.5 text-[11px] text-amber">
                  Cần xử lý
                </span>
              </div>
              <div className="mono mt-1 text-[11px] text-muted">
                Đối chiếu {picked.size} văn bản · hiệu lực tại{" "}
                {timeMode === "today" ? new Date().toISOString().slice(0, 10) : date} · dữ liệu minh
                họa
              </div>

              {/* Score strip */}
              <div className="mt-4 grid grid-cols-2 gap-px overflow-hidden rounded-[14px] border border-border bg-border lg:grid-cols-[1.25fr_1fr_1fr_1fr]">
                <div className="bg-panel px-4 py-3.5">
                  <div className="text-[10px] font-semibold uppercase tracking-[.1em] text-faint">
                    Mức tuân thủ
                  </div>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className="serif text-[32px] font-medium">72</span>
                    <span className="mono text-[11px] text-muted">/100</span>
                  </div>
                  <div className="mt-1.5 h-[5px] overflow-hidden rounded-full bg-inset-strong">
                    <div className="h-full rounded-full bg-accent" style={{ width: "72%" }} />
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
                      ["all", `Tất cả ${DEMO_FINDINGS.length}`],
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
                            <span className="mono text-[10px] text-muted">{f.location}</span>
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
                                Tài liệu nội bộ · {f.location}
                              </div>
                              <p className="serif mt-1.5 text-[13px] italic leading-relaxed text-fg-strong">
                                “{f.internalQuote}”
                              </p>
                            </div>
                            <div
                              className={`rounded-[10px] border bg-white p-3 ${
                                f.legalLive ? "border-green-bd" : "border-border"
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                <span className="mono text-[10px] text-accent-hover">{f.legalRef}</span>
                                {f.legalLive && (
                                  <span className="rounded-full border border-green-bd bg-green-bg px-1.5 py-px text-[9.5px] text-green">
                                    Đang hiệu lực
                                  </span>
                                )}
                              </div>
                              <p className="serif mt-1.5 text-[13px] italic leading-relaxed text-fg-strong">
                                “{f.legalQuote}”
                              </p>
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
              </div>

              <p className="mt-6 text-center text-[10.5px] text-muted">
                Kết quả mang tính hỗ trợ rà soát — vui lòng đối chiếu bản gốc trước khi ban hành tài
                liệu.
              </p>
            </>
          )}
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
