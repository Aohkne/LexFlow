"use client";

import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/page-shell";
import { createClient } from "@/lib/supabase/client";
import { approveDocument, rejectDocument, uploadDocument } from "@/lib/api";

type LegalDoc = {
  doc_id: string;
  title: string;
  doc_type: string;
  source: string;
  status: "pending" | "approved" | "rejected";
  valid_from: string | null;
  extracted: unknown | null;
  created_at: string;
};

const STATUS_BADGE: Record<string, string> = {
  pending: "border-accent text-accent-dim",
  approved: "border-blue text-blue",
  rejected: "border-red text-red",
};

export default function AdminPage() {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [docs, setDocs] = useState<LegalDoc[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState<"external" | "internal">("external");
  const [editing, setEditing] = useState<string | null>(null); // doc_id đang mở JSON
  const [draft, setDraft] = useState("");
  const [rels, setRels] = useState("[]");

  const reload = useCallback(async () => {
    const supabase = createClient();
    const { data, error } = await supabase
      .from("legal_documents")
      .select("*")
      .order("created_at", { ascending: false });
    if (error) setError(error.message);
    else setDocs((data as LegalDoc[]) ?? []);
  }, []);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      const role = (data.user?.app_metadata as { role?: string } | undefined)?.role;
      setIsAdmin(role === "admin");
    });
    (async () => {
      await reload();
    })();
  }, [reload]);

  async function doUpload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setNotice("Đang upload + extract (Gemini)… có thể mất ~30 giây");
    try {
      const r = await uploadDocument(file, source);
      setNotice(`Đã extract ${r.doc_id}: ${r.n_articles} điều — chờ duyệt bên dưới.`);
      setFile(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload thất bại");
      setNotice(null);
    } finally {
      setBusy(false);
    }
  }

  function openReview(d: LegalDoc) {
    setEditing(d.doc_id);
    setDraft(JSON.stringify(d.extracted, null, 2));
    setRels("[]");
    setNotice(null);
    setError(null);
  }

  async function doApprove(docId: string) {
    setBusy(true);
    setError(null);
    setNotice("Đang duyệt: merge corpus + nạp lại riêng văn bản này… thường vài giây");
    try {
      const document = JSON.parse(draft);
      const relationships = JSON.parse(rels);
      const r = await approveDocument(docId, document, relationships);
      setNotice(`✅ Đã duyệt ${docId}: ${r.chunks} chunk, ${r.change_events} cảnh báo thay đổi.`);
      setEditing(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Duyệt thất bại");
      setNotice(null);
    } finally {
      setBusy(false);
    }
  }

  async function doReject(docId: string) {
    setBusy(true);
    setError(null);
    try {
      await rejectDocument(docId);
      setEditing(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Từ chối thất bại");
    } finally {
      setBusy(false);
    }
  }

  if (isAdmin === false) {
    return (
      <PageShell active="admin">
        <div className="mx-auto max-w-3xl px-6 py-16 text-center text-sm text-dim">
          Trang này dành cho quản trị viên (role <span className="mono">admin</span>).
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell active="admin">
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="serif text-2xl font-medium tracking-[-.015em]">Quản trị văn bản</h1>
      <p className="mt-1 text-sm text-dim">
        Upload → hệ thống extract điều/khoản → bạn duyệt JSON → nạp vào hệ thống tra cứu
        (maker-checker: máy đề xuất, người phê duyệt).
      </p>
      <p className="mt-1 text-sm text-dim">
        File <span className="mono">.json</span> đã crawl từ vbpl thì dùng thẳng, không qua
        extract — giữ nguyên cây điều/khoản và <span className="mono">char_span</span>.
      </p>

      {/* Upload */}
      <div className="mt-6 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-panel p-4">
        {/* `.json` là bản đã crawl từ vbpl (đúng khuôn CorpusDocument): API dùng thẳng, bỏ qua
            extractor, nên giữ được cây provisions và char_span. Thiếu đuôi này thì ô chọn file
            lọc mất chính lối nạp chuẩn của dự án. */}
        <input
          type="file"
          accept=".json,.html,.htm,.pdf,.txt"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm text-dim file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm file:text-foreground"
        />
        <select
          value={source}
          onChange={(e) => setSource(e.target.value as "external" | "internal")}
          className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
        >
          <option value="external">Văn bản pháp luật</option>
          <option value="internal">Quy định nội bộ</option>
        </select>
        <button
          onClick={doUpload}
          disabled={!file || busy}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:bg-accent-dim disabled:opacity-50"
        >
          {busy ? "Đang xử lý…" : "Upload + Extract"}
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red bg-red/5 px-4 py-3 text-sm text-red">{error}</div>
      )}
      {notice && (
        <div className="mt-4 rounded-lg border border-blue bg-blue/5 px-4 py-3 text-sm text-blue">{notice}</div>
      )}

      {/* Danh sách */}
      <div className="mt-6 space-y-2">
        {docs.length === 0 && <p className="text-sm text-faint">Chưa có văn bản nào trong luồng duyệt.</p>}
        {docs.map((d) => (
          <div key={d.doc_id} className="rounded-lg border border-border bg-panel">
            <div className="flex flex-wrap items-center gap-2 px-4 py-3">
              <span className={`rounded border px-2 py-0.5 text-xs uppercase ${STATUS_BADGE[d.status]}`}>
                {d.status}
              </span>
              <span className="mono text-xs text-accent-dim">{d.doc_id}</span>
              <span className="text-sm">{d.title}</span>
              <span className="mono ml-auto text-xs text-faint">{d.source}</span>
              {d.status === "pending" && (
                <button
                  onClick={() => (editing === d.doc_id ? setEditing(null) : openReview(d))}
                  className="rounded-md border border-border px-2.5 py-1 text-xs text-dim hover:border-accent hover:text-accent-dim"
                >
                  {editing === d.doc_id ? "Đóng" : "Xem & duyệt"}
                </button>
              )}
            </div>
            {editing === d.doc_id && (
              <div className="border-t border-border px-4 py-3">
                <label className="text-xs font-semibold uppercase tracking-wide text-dim">
                  JSON điều khoản (sửa trực tiếp nếu extract sai)
                </label>
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={14}
                  className="mono mt-1 w-full rounded-lg border border-border bg-background p-2 text-xs outline-none focus:border-accent"
                />
                <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-dim">
                  {`Quan hệ mới (JSON, vd: [{"source_doc":"TT99-2026","target_doc":"TT40-2024","rel_type":"THAY_THE","valid_from":"2026-01-01"}])`}
                </label>
                <textarea
                  value={rels}
                  onChange={(e) => setRels(e.target.value)}
                  rows={3}
                  className="mono mt-1 w-full rounded-lg border border-border bg-background p-2 text-xs outline-none focus:border-accent"
                />
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => doApprove(d.doc_id)}
                    disabled={busy}
                    className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dim disabled:opacity-50"
                  >
                    ✓ Duyệt & nạp vào hệ thống
                  </button>
                  <button
                    onClick={() => doReject(d.doc_id)}
                    disabled={busy}
                    className="rounded-lg border border-red px-4 py-2 text-sm text-red hover:bg-red/10 disabled:opacity-50"
                  >
                    ✗ Từ chối
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
    </PageShell>
  );
}
