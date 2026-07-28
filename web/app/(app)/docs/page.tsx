"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppSidebar, { SidebarSectionLabel } from "@/components/app-sidebar";
import {
  getDocument,
  listDocuments,
  type DocumentDetail,
  type DocumentSummary,
} from "@/lib/api";
import { articleAnchor, groupRelationships } from "@/lib/anchors";
import { Lexi } from "@/components/lexi";

type StatusFacet = "all" | "live" | "expired";
type SourceFacet = "all" | "external" | "internal";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function isLiveAt(d: { valid_from: string | null; valid_to: string | null }, date: string): boolean {
  if (d.valid_from && date < d.valid_from) return false;
  if (d.valid_to && date > d.valid_to) return false;
  return true;
}

// Suy ra cơ quan ban hành từ loại văn bản (corpus chưa có trường riêng)
function issuerOf(d: { doc_type: string; doc_id: string }): string {
  if (d.doc_type === "Nội bộ" || d.doc_id.startsWith("SHB")) return "Ngân hàng SHB";
  if (d.doc_type === "Thông tư") return "Ngân hàng Nhà nước";
  if (d.doc_type === "Nghị định") return "Chính phủ";
  if (d.doc_type === "Luật") return "Quốc hội";
  return "—";
}

export default function DocsPage() {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFacet>("all");
  const [source, setSource] = useState<SourceFacet>("all");
  const [docType, setDocType] = useState<string>("all");
  const [sort, setSort] = useState<"new" | "code">("new");
  const [asOf, setAsOf] = useState(todayIso());
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);

  useEffect(() => {
    listDocuments()
      .then((d) => {
        setDocs(d);
        if (d.length > 0) setSelected(d[0].doc_id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Lỗi tải danh sách"));
  }, []);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    getDocument(selected)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const types = useMemo(() => [...new Set((docs ?? []).map((d) => d.doc_type))], [docs]);

  const shown = useMemo(() => {
    let pool = docs ?? [];
    if (status !== "all") pool = pool.filter((d) => (status === "live") === isLiveAt(d, asOf));
    if (source !== "all") pool = pool.filter((d) => d.source === source);
    if (docType !== "all") pool = pool.filter((d) => d.doc_type === docType);
    const q = search.trim().toLowerCase();
    if (q) pool = pool.filter((d) => `${d.doc_id} ${d.title}`.toLowerCase().includes(q));
    return [...pool].sort((a, b) =>
      sort === "new"
        ? (b.valid_from ?? "").localeCompare(a.valid_from ?? "")
        : a.doc_id.localeCompare(b.doc_id, "vi"),
    );
  }, [docs, status, source, docType, search, sort, asOf]);

  const headingLabel =
    status === "live" ? "Đang hiệu lực" : status === "expired" ? "Hết hiệu lực" : "Tất cả văn bản";

  const facetBtn = (on: boolean) =>
    `flex w-full items-center justify-between rounded-[9px] px-2.5 py-2 text-[12.5px] transition-colors ${
      on ? "bg-inset-strong font-medium text-foreground" : "text-dim hover:bg-[#EFEADF]"
    }`;

  return (
    <>
      <AppSidebar
        active="docs"
        extra={
          <div className="border-t border-[#E9E3D5] pt-1">
            <SidebarSectionLabel>Tình trạng</SidebarSectionLabel>
            {(
              [
                ["all", "Tất cả văn bản"],
                ["live", "Đang hiệu lực"],
                ["expired", "Hết hiệu lực"],
              ] as const
            ).map(([id, label]) => (
              <button key={id} onClick={() => setStatus(id)} className={facetBtn(status === id)}>
                {label}
                <span className="mono text-[10px] text-muted">
                  {
                    (docs ?? []).filter(
                      (d) => id === "all" || (id === "live") === isLiveAt(d, asOf),
                    ).length
                  }
                </span>
              </button>
            ))}
            <SidebarSectionLabel>Loại văn bản</SidebarSectionLabel>
            <button onClick={() => setDocType("all")} className={facetBtn(docType === "all")}>
              Tất cả loại
            </button>
            {types.map((t) => (
              <button key={t} onClick={() => setDocType(t)} className={facetBtn(docType === t)}>
                {t}
                <span className="mono text-[10px] text-muted">
                  {(docs ?? []).filter((d) => d.doc_type === t).length}
                </span>
              </button>
            ))}
            <SidebarSectionLabel>Nguồn</SidebarSectionLabel>
            {(
              [
                ["all", "Tất cả nguồn"],
                ["external", "Văn bản pháp luật"],
                ["internal", "Quy định nội bộ"],
              ] as const
            ).map(([id, label]) => (
              <button key={id} onClick={() => setSource(id)} className={facetBtn(source === id)}>
                {label}
              </button>
            ))}
          </div>
        }
      />

      {/* LIST */}
      <div className="min-w-0 flex-1 overflow-y-auto">
        <div className="max-w-[900px] px-8 pb-14 pt-6">
          <h1 className="serif text-3xl font-medium tracking-[-.015em]">Thư viện văn bản</h1>
          <p className="mt-1 text-sm text-dim">
            Toàn bộ văn bản đã lập chỉ mục — mở để xem toàn văn, lược đồ và điều khoản bị sửa đổi.
          </p>

          {/* Tìm kiếm + sort */}
          <div className="mt-4 flex items-center gap-2.5">
            <div className="relative flex-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">⌕</span>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Tìm theo số hiệu hoặc tên văn bản…"
                className="w-full rounded-[10px] border border-border bg-panel py-2 pl-9 pr-3 text-[13px] text-fg-body outline-none placeholder:text-muted focus:border-accent"
              />
            </div>
            <div className="flex rounded-[11px] bg-[#E7E3D8] p-[3px] text-[12px]">
              {(
                [
                  ["new", "Mới nhất"],
                  ["code", "Số hiệu"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setSort(id)}
                  className={`rounded-lg px-3 py-1 transition-all ${
                    sort === id
                      ? "bg-panel font-medium shadow-[0_1px_2px_rgba(40,34,24,.12)]"
                      : "text-faint"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Thanh as-of */}
          <div className="mt-3 flex flex-wrap items-center gap-2.5 rounded-xl border border-border bg-panel px-3.5 py-2.5">
            <span className="text-[12.5px] text-dim">Xem tình trạng hiệu lực tại</span>
            <input
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              className="mono rounded-[7px] border border-border bg-white px-2 py-1 text-[11px] text-fg-strong"
            />
            <button
              onClick={() => {
                setSearch("");
                setStatus("all");
                setSource("all");
                setDocType("all");
              }}
              className="ml-auto text-[11.5px] font-medium text-accent-dim"
            >
              Xóa bộ lọc
            </button>
          </div>

          <div className="mt-5 flex items-baseline gap-2">
            <h2 className="serif text-[17px] font-medium">{headingLabel}</h2>
            <span className="mono text-[11px] text-muted">{shown.length} văn bản</span>
          </div>

          {error && (
            <div className="mt-4 rounded-lg border border-red-bd bg-red-bg px-4 py-3 text-sm text-red">
              {error}
            </div>
          )}
          {!docs && !error && <p className="mt-6 text-sm text-faint">Đang tải…</p>}

          <div className="mt-3 space-y-2.5">
            {shown.map((d) => {
              const live = isLiveAt(d, asOf);
              const on = selected === d.doc_id;
              return (
                <button
                  key={d.doc_id}
                  onClick={() => setSelected(d.doc_id)}
                  className={`w-full rounded-[14px] border bg-panel px-4 py-3.5 text-left transition-colors ${
                    on ? "border-accent" : "border-border hover:border-border-hover"
                  } ${live ? "" : "opacity-[.72]"}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-[5px] bg-inset-strong px-1.5 py-0.5 text-[9.5px] uppercase tracking-[.04em] text-faint">
                      {d.doc_type}
                    </span>
                    <span className="text-sm font-semibold">{d.doc_id}</span>
                    {live ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-green-bd bg-green-bg px-2 py-0.5 text-[10.5px] text-green">
                        <span className="h-[5px] w-[5px] rounded-full bg-green" />
                        Đang hiệu lực
                      </span>
                    ) : (
                      <span className="rounded-full border border-border bg-grey-bg px-2 py-0.5 text-[10.5px] text-grey">
                        Hết hiệu lực
                      </span>
                    )}
                    <span className="mono ml-auto text-[10.5px] text-muted">
                      {d.valid_from ? `hiệu lực từ ${d.valid_from}` : ""}
                      {d.valid_to ? ` đến ${d.valid_to}` : ""}
                    </span>
                  </div>
                  <div className="serif mt-1.5 text-[15.5px] leading-snug text-fg-strong">
                    {d.title}
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[11.5px] text-faint">
                    <span>{issuerOf(d)}</span>
                    <span className="mono">{d.n_articles} điều</span>
                  </div>
                </button>
              );
            })}
            {docs && shown.length === 0 && (
              <div className="py-8 text-center">
                <Lexi state="idle" size={44} className="mx-auto" />
                <p className="mt-2.5 text-sm text-muted">Không tìm thấy văn bản phù hợp.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* DETAIL */}
      <aside className="hidden w-[392px] flex-none overflow-y-auto border-l border-border bg-panel px-5 pb-10 pt-5 xl:block">
        {!detail && selected && <p className="text-sm text-faint">Đang tải chi tiết…</p>}
        {detail && <DetailPanel detail={detail} asOf={asOf} />}
      </aside>
    </>
  );
}

function DetailPanel({ detail, asOf }: { detail: DocumentDetail; asOf: string }) {
  const live = isLiveAt(detail, asOf);
  const groups = groupRelationships(detail);
  const meta: [string, string][] = [
    ["Số hiệu", detail.doc_id],
    ["Cơ quan ban hành", issuerOf(detail)],
    ["Ngày hiệu lực", detail.valid_from ?? "—"],
    ["Hết hiệu lực", detail.valid_to ?? "—"],
    ["Tình trạng", live ? "Đang hiệu lực" : "Hết hiệu lực"],
    ["Nguồn", detail.source === "internal" ? "Quy định nội bộ" : "Văn bản pháp luật"],
  ];

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-[5px] bg-inset-strong px-1.5 py-0.5 text-[9.5px] uppercase tracking-[.04em] text-faint">
          {detail.doc_type}
        </span>
        {live ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-green-bd bg-green-bg px-2 py-0.5 text-[10.5px] text-green">
            <span className="h-[5px] w-[5px] rounded-full bg-green" />
            Đang hiệu lực
          </span>
        ) : (
          <span className="rounded-full border border-border bg-grey-bg px-2 py-0.5 text-[10.5px] text-grey">
            Hết hiệu lực
          </span>
        )}
      </div>
      <div className="mt-2 text-[17px] font-semibold">{detail.doc_id}</div>
      <div className="serif mt-1 text-[15px] leading-snug text-fg-strong">{detail.title}</div>

      {/* Bảng metadata */}
      <div className="mt-4 overflow-hidden rounded-[11px] bg-border-soft">
        <div className="flex flex-col gap-px">
          {meta.map(([k, v]) => (
            <div key={k} className="flex items-center gap-3 bg-background px-3 py-2">
              <span className="w-[112px] flex-none text-[11.5px] text-faint">{k}</span>
              <span className="mono min-w-0 truncate text-[11px] text-fg-strong">{v}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 flex gap-2">
        <Link
          href={`/?scope=${encodeURIComponent(detail.doc_id)}`}
          className="flex-1 rounded-[10px] bg-accent px-3 py-2 text-center text-[12.5px] font-medium text-white transition-colors hover:bg-accent-hover"
        >
          Hỏi về văn bản này
        </Link>
        <Link
          href={`/docs/${encodeURIComponent(detail.doc_id)}`}
          className="rounded-[10px] border border-border bg-panel px-3 py-2 text-[12.5px] font-medium text-dim transition-colors hover:border-border-hover hover:text-foreground"
        >
          Toàn văn ↗
        </Link>
      </div>

      {/* Quan hệ văn bản */}
      {groups.length > 0 && (
        <div className="mt-5">
          <div className="text-[10px] font-semibold uppercase tracking-[.1em] text-faint">
            Quan hệ văn bản
          </div>
          <div className="mt-2 space-y-2">
            {groups.flatMap((g) =>
              g.entries.map((e) => (
                <Link
                  key={`${g.label}-${e.docId}`}
                  href={`/docs/${encodeURIComponent(e.docId)}`}
                  className="block rounded-[10px] border border-border bg-background px-3 py-2.5 transition-colors hover:border-border-hover"
                >
                  <div className="text-[9.5px] font-semibold uppercase tracking-[.08em] text-faint">
                    {g.label}
                  </div>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="mono text-[11.5px] font-medium text-accent-hover">
                      {e.docId}
                    </span>
                    {e.validFrom && (
                      <span className="mono ml-auto text-[10px] text-muted">từ {e.validFrom}</span>
                    )}
                  </div>
                  {e.note && <p className="mt-1 text-[11px] leading-snug text-dim">{e.note}</p>}
                </Link>
              )),
            )}
          </div>
        </div>
      )}

      {/* Mục lục điều khoản */}
      <div className="mt-5">
        <div className="text-[10px] font-semibold uppercase tracking-[.1em] text-faint">
          Mục lục điều khoản
        </div>
        <div className="mt-2 overflow-hidden rounded-[11px] border border-border">
          {detail.articles.map((a) => {
            const anchor = articleAnchor(a.article);
            const firstLine = a.text.split("\n")[0]?.slice(0, 70) ?? "";
            return (
              <Link
                key={a.article}
                href={`/docs/${encodeURIComponent(detail.doc_id)}${anchor ? `#${anchor}` : ""}`}
                className="flex items-baseline gap-2.5 border-b border-border-soft bg-panel px-3 py-2 last:border-b-0 hover:bg-inset"
              >
                <span className="mono w-[52px] flex-none text-[10.5px] text-accent-hover">
                  {a.article.replace(/ Khoản.*$/, "")}
                </span>
                <span className="min-w-0 truncate text-[11.5px] text-dim">{firstLine}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </>
  );
}
