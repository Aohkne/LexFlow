"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import PageShell from "@/components/page-shell";
import {
  downloadSourceFile,
  getDocument,
  type DocumentDetail,
  type Provision,
  type SourceFile,
} from "@/lib/api";
import { renderInline } from "@/lib/inline-html";
import {
  articleAnchor,
  buildAmendmentMap,
  groupRelationships,
  type AmendmentInfo,
} from "@/lib/anchors";

export default function DocViewerPage() {
  const params = useParams<{ docId: string }>();
  const docId = decodeURIComponent(params.docId);
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"content" | "properties" | "schema">("content");

  useEffect(() => {
    getDocument(docId)
      .then(setDoc)
      .catch((e) => setError(e instanceof Error ? e.message : "Lỗi tải văn bản"));
  }, [docId]);

  // Cuộn tới #dieu-N sau khi nội dung render.
  useEffect(() => {
    if (!doc || tab !== "content") return;
    const hash = window.location.hash.slice(1);
    if (hash) document.getElementById(hash)?.scrollIntoView({ block: "start" });
  }, [doc, tab]);

  if (error) {
    return (
      <PageShell active="docs">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <div className="rounded-lg border border-red-bd bg-red-bg px-4 py-3 text-sm text-red">{error}</div>
        </div>
      </PageShell>
    );
  }
  if (!doc) {
    return (
      <PageShell active="docs">
        <div className="mx-auto max-w-4xl px-6 py-10 text-sm text-faint">Đang tải…</div>
      </PageShell>
    );
  }

  const amendments = buildAmendmentMap(doc);
  const replacedBy = doc.relationships_in.filter((r) => r.rel_type === "THAY_THE");
  const expired =
    replacedBy.length > 0 || (doc.valid_to !== null && doc.valid_to <= new Date().toISOString().slice(0, 10));

  return (
    <PageShell active="docs">
    <div className="mx-auto max-w-4xl px-6 py-10">
      <Link href="/docs" className="text-xs text-dim hover:text-accent-dim">
        ← Thư viện văn bản
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="rounded bg-inset px-2 py-0.5 text-xs text-dim">{doc.doc_type}</span>
        <span className="mono text-xs text-accent-dim">{doc.doc_id}</span>
        <span className="mono ml-auto text-xs text-faint">
          hiệu lực từ {doc.valid_from ?? "—"}
          {doc.valid_to ? ` đến ${doc.valid_to}` : ""}
        </span>
      </div>
      <h1 className="mt-1 text-xl font-semibold leading-snug">{doc.title}</h1>

      {expired && (
        <div className="mt-4 rounded-lg border-l-4 border-red bg-panel px-4 py-3 text-sm">
          <span className="font-semibold text-red">⚠ Văn bản đã hết hiệu lực</span>
          {replacedBy.map((r) => (
            <span key={r.source_doc} className="text-foreground">
              {" "}
              — được thay thế bởi{" "}
              <Link
                href={`/docs/${encodeURIComponent(r.source_doc)}`}
                className="font-medium text-accent-dim underline decoration-dotted hover:text-accent"
              >
                {doc.doc_titles[r.source_doc] ?? r.source_doc}
              </Link>
              {r.valid_from ? ` (từ ${r.valid_from})` : ""}
            </span>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="mt-6 flex rounded-lg border border-border bg-background p-0.5 text-sm w-fit">
        {(
          [
            ["content", "Nội dung"],
            ["properties", "Thuộc tính"],
            ["schema", "Lược đồ"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-md px-4 py-1 transition-colors ${
              tab === key ? "bg-accent text-white" : "text-dim hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "content" && <ContentTab doc={doc} amendments={amendments} />}
      {tab === "properties" && <PropertiesTab doc={doc} />}
      {tab === "schema" && <SchemaTab doc={doc} />}
    </div>
    </PageShell>
  );
}

// Tính heading Chương/Mục cho từng điều (chỉ hiện khi nhãn đổi so với điều trước) — hàm thuần.
function withHeadings(articles: DocumentDetail["articles"]) {
  let lastChapter: string | null = null;
  let lastSection: string | null = null;
  return articles.map((a) => {
    const chapterHeading = a.chapter && a.chapter !== lastChapter ? a.chapter : null;
    const sectionHeading = a.section && a.section !== lastSection ? a.section : null;
    lastChapter = a.chapter ?? lastChapter;
    lastSection = a.section ?? lastSection;
    return { a, chapterHeading, sectionHeading };
  });
}

const AMEND_LABELS: Record<string, string> = {
  sua_doi_bo_sung: "Sửa đổi, bổ sung",
  thay_the: "Thay thế",
  bo_sung: "Bổ sung",
  bai_bo: "Bãi bỏ",
  het_hieu_luc: "Hết hiệu lực",
};

function AmendBadge({ kind }: { kind: string }) {
  const danger = kind === "thay_the" || kind === "bai_bo" || kind === "het_hieu_luc";
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[11px] ${
        danger ? "border border-red text-red" : "border border-accent text-accent-dim"
      }`}
    >
      {/* nhãn lạ từ nguồn (khac:...) vẫn hiện nguyên văn thay vì bị nuốt */}
      {AMEND_LABELS[kind] ?? kind.replace(/^khac:/, "")}
    </span>
  );
}

/** Toàn văn dựng lại từ cây Chương → Mục → Điều → Khoản → Điểm. */
function ProvisionNodes({ nodes, depth = 0 }: { nodes: Provision[]; depth?: number }) {
  return (
    <>
      {nodes.map((n, i) => {
        const marks = n.bi_tac_dong ?? [];
        if (n.cap === "chuong" || n.cap === "muc" || n.cap === "dieu") {
          const prefix =
            n.cap === "chuong" ? "Chương" : n.cap === "muc" ? "Mục" : "Điều";
          const heading = [`${prefix} ${n.so ?? ""}`.trim(), n.tieu_de]
            .filter(Boolean)
            .join(". ");
          const anchor = n.cap === "dieu" && n.so ? `dieu-${n.so}` : undefined;
          return (
            <section
              key={n.id ?? `${n.cap}-${n.so}-${i}`}
              id={anchor}
              className={
                n.cap === "dieu"
                  ? "scroll-mt-20 rounded-lg border border-border bg-panel p-4"
                  : "mt-6"
              }
            >
              <div className="flex flex-wrap items-center gap-2">
                <h2
                  className={
                    n.cap === "chuong"
                      ? "text-sm font-semibold uppercase tracking-wide text-accent-dim"
                      : n.cap === "muc"
                        ? "text-sm font-semibold text-dim"
                        : "text-sm font-semibold"
                  }
                >
                  {heading}
                </h2>
                {marks.map((k) => (
                  <AmendBadge key={k} kind={k} />
                ))}
              </div>
              {n.html && (
                <p className="mt-2 text-sm leading-relaxed">{renderInline(n.html)}</p>
              )}
              {n.con.length > 0 && (
                <div className={n.cap === "dieu" ? "mt-2 space-y-2" : "space-y-3"}>
                  <ProvisionNodes nodes={n.con} depth={depth + 1} />
                </div>
              )}
            </section>
          );
        }
        // Khoản / Điểm: thụt lề theo cấp, giữ tiền tố số như bản gốc
        return (
          <div
            key={n.id ?? `${n.cap}-${n.so}-${i}`}
            className={`${n.cap === "diem" ? "ml-5" : ""} ${
              marks.length ? "border-l-2 border-accent pl-3" : ""
            }`}
          >
            <p className="text-sm leading-relaxed">
              {n.html ? renderInline(n.html) : n.text}
              {marks.map((k) => (
                <span key={k} className="ml-2 align-middle">
                  <AmendBadge kind={k} />
                </span>
              ))}
            </p>
            {n.con.length > 0 && (
              <div className="mt-1 space-y-1">
                <ProvisionNodes nodes={n.con} depth={depth + 1} />
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

function ContentTab({
  doc,
  amendments,
}: {
  doc: DocumentDetail;
  amendments: Map<string, AmendmentInfo[]>;
}) {
  // Có cây thì dựng toàn văn đúng phân cấp như bản gốc; chưa crawl lại thì vẫn dùng
  // danh sách Điều phẳng cũ, không để trang trống.
  if (doc.provisions && doc.provisions.length > 0) {
    return (
      <div className="mt-4 space-y-3">
        <ProvisionNodes nodes={doc.provisions} />
      </div>
    );
  }
  return (
    <div className="mt-4 space-y-3">
      {withHeadings(doc.articles).map(({ a, chapterHeading, sectionHeading }) => {
        const anchor = articleAnchor(a.article);
        const hits = anchor ? amendments.get(anchor) ?? [] : [];
        const inactive = a.superseded || (a.valid_to !== null && a.valid_to <= new Date().toISOString().slice(0, 10));
        return (
          <div key={a.article}>
            {chapterHeading && (
              <h2 className="mt-6 text-sm font-semibold uppercase tracking-wide text-accent-dim">
                {chapterHeading}
              </h2>
            )}
            {sectionHeading && (
              <h3 className="mt-2 text-sm font-semibold text-dim">{sectionHeading}</h3>
            )}
            <section
              id={anchor ?? undefined}
              className={`scroll-mt-20 rounded-lg border bg-panel p-4 ${
                hits.some((h) => h.relType === "THAY_THE")
                  ? "border-l-4 border-red"
                  : hits.length > 0
                    ? "border-l-4 border-accent"
                    : "border-border"
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="mono text-sm font-semibold text-accent-dim">{a.article}</span>
                {hits.length > 0 && (
                  <span className="rounded border border-accent px-2 py-0.5 text-xs text-accent-dim">
                    Bị sửa đổi
                  </span>
                )}
                {inactive && (
                  <span className="rounded border border-red px-2 py-0.5 text-xs text-red">
                    Hết hiệu lực{a.valid_to ? ` từ ${a.valid_to}` : ""}
                  </span>
                )}
              </div>
              {hits.length > 0 && (
                <div className="mt-2 space-y-1 rounded-md bg-inset px-3 py-2 text-xs">
                  {hits.map((h, i) => (
                    <p key={i} className="text-dim">
                      {h.relType === "THAY_THE" ? "Điều này bị thay thế bởi" : "Điều này bị sửa đổi, bổ sung bởi"}{" "}
                      <span className="font-medium text-foreground">{h.sourceTitle}</span>
                      {h.sourceArticle ? ` — ${h.sourceArticle}` : ""}
                      {h.detail ? ` (${h.detail})` : ""}
                      {h.validFrom ? `, hiệu lực từ ${h.validFrom}` : ""}{" "}
                      <Link
                        href={`/docs/${encodeURIComponent(h.sourceDoc)}${
                          h.sourceArticle && articleAnchor(h.sourceArticle)
                            ? `#${articleAnchor(h.sourceArticle)}`
                            : ""
                        }`}
                        className="text-accent-dim underline decoration-dotted hover:text-accent"
                      >
                        [xem]
                      </Link>
                    </p>
                  ))}
                </div>
              )}
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{a.text}</p>
            </section>
          </div>
        );
      })}
    </div>
  );
}

// Thứ tự hiển thị bám theo bảng Thuộc tính của vbpl.vn để người dùng đối chiếu được.
const PROPERTY_ROWS: [label: string, key: keyof DocumentDetail][] = [
  ["Số hiệu", "so_hieu"],
  ["Loại văn bản", "doc_type"],
  ["Ngành", "nganh"],
  ["Ngày ban hành", "ngay_ban_hanh"],
  ["Lĩnh vực", "linh_vuc"],
  ["Ngày có hiệu lực", "valid_from"],
  ["Tình trạng hiệu lực", "tinh_trang_hieu_luc"],
  ["Ngày hết hiệu lực", "valid_to"],
  ["Cơ quan ban hành", "co_quan_ban_hanh"],
  ["Chức danh", "chuc_danh"],
  ["Người ký", "nguoi_ky"],
];

function PropertiesTab({ doc }: { doc: DocumentDetail }) {
  const rows = PROPERTY_ROWS.map(([label, key]) => {
    const raw = doc[key];
    return { label, value: typeof raw === "string" && raw.trim() ? raw : null };
  });
  const known = rows.filter((r) => r.value !== null).length;

  return (
    <div className="mt-4 space-y-4">
      {known === 0 && (
        <p className="rounded-lg border border-border bg-panel px-4 py-3 text-sm text-dim">
          Văn bản này chưa có thuộc tính chi tiết — bản ghi được duyệt trước khi hệ thống lưu
          nhóm trường này. Nội dung và lược đồ vẫn đầy đủ.
        </p>
      )}
      <section className="overflow-hidden rounded-xl border border-border bg-panel">
        <h2 className="border-b border-border px-4 py-2 text-xs font-semibold uppercase tracking-wide text-dim">
          Thuộc tính
        </h2>
        <dl className="grid grid-cols-1 sm:grid-cols-2">
          {rows.map(({ label, value }) => (
            <div
              key={label}
              className="flex gap-3 border-b border-border px-4 py-2.5 last:border-b-0 sm:odd:border-r"
            >
              <dt className="w-40 shrink-0 text-xs text-dim">{label}</dt>
              <dd className={`text-sm ${value ? "" : "text-faint"}`}>{value ?? "—"}</dd>
            </div>
          ))}
        </dl>
      </section>

      <SourceFiles doc={doc} />
    </div>
  );
}

function SourceFiles({ doc }: { doc: DocumentDetail }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Backend cũ chưa trả khoá này -> undefined, không phải mảng rỗng.
  const files = doc.source_files ?? [];

  async function onDownload(file: SourceFile) {
    setError(null);
    setBusy(file.ten);
    try {
      await downloadSourceFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tải file thất bại");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="rounded-xl border border-border bg-panel p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-dim">Văn bản gốc</h2>

      {doc.source_url && (
        <a
          href={doc.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-sm text-accent-dim underline decoration-dotted hover:text-accent"
        >
          Xem bản gốc tại nguồn ↗
        </a>
      )}

      {files.length === 0 ? (
        <p className="mt-2 text-sm text-faint">Chưa có file gốc đính kèm văn bản này.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {files.map((f) => (
            <li
              key={f.ten}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-background px-3 py-2"
            >
              <span className="min-w-0 flex-1 truncate text-sm">{f.ten}</span>
              {f.kich_thuoc && <span className="mono text-xs text-faint">{f.kich_thuoc}</span>}
              {f.url ? (
                <button
                  onClick={() => onDownload(f)}
                  disabled={busy === f.ten}
                  className="rounded-md border border-accent px-3 py-1 text-xs text-accent-dim transition-colors hover:bg-accent hover:text-white disabled:opacity-50"
                >
                  {busy === f.ten ? "Đang tải…" : "Tải về"}
                </button>
              ) : (
                // Biết là có file nhưng nguồn không cho link — nói rõ thay vì nút bấm không chạy
                <span className="text-xs text-faint">chưa có link tải</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {error && (
        <div className="mt-2 rounded-lg border border-red-bd bg-red-bg px-3 py-2 text-xs text-red">
          {error}
        </div>
      )}
    </section>
  );
}

function SchemaTab({ doc }: { doc: DocumentDetail }) {
  const groups = groupRelationships(doc);
  if (groups.length === 0) {
    return <p className="mt-6 text-sm text-faint">Chưa ghi nhận quan hệ nào với văn bản khác.</p>;
  }
  return (
    <div className="mt-4 space-y-4">
      {groups.map((g) => (
        <section key={g.label} className="rounded-xl border border-border bg-panel p-4">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-dim">{g.label}</h2>
          <div className="mt-2 space-y-2">
            {g.entries.map((e) => (
              <Link
                key={e.docId}
                href={`/docs/${encodeURIComponent(e.docId)}`}
                className="block rounded-lg border border-border bg-background p-3 transition-colors hover:border-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{e.title}</span>
                  <span className="mono text-xs text-accent-dim">{e.docId}</span>
                  {e.validFrom && (
                    <span className="mono ml-auto text-xs text-faint">từ {e.validFrom}</span>
                  )}
                </div>
                {e.note && <p className="mt-1 text-xs text-dim">{e.note}</p>}
                {e.anchors.length > 0 && (
                  <p className="mono mt-1 text-xs text-faint">
                    {e.anchors
                      .map((a) =>
                        [a.source_article, a.target_article].filter(Boolean).join(" → "),
                      )
                      .join(" · ")}
                  </p>
                )}
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
