"use client";

import { useEffect, useState } from "react";
import PageShell from "@/components/page-shell";
import { createClient } from "@/lib/supabase/client";

type ChangeEvent = {
  id: number;
  doc_id: string;
  source_doc_id: string;
  rel_type: string;
  description: string;
  effective_date: string | null;
  created_at: string;
};

const REL_BADGE: Record<string, { cls: string; label: string }> = {
  THAY_THE: { cls: "border-red text-red", label: "Thay thế" },
  SUA_DOI: { cls: "border-accent text-accent-dim", label: "Sửa đổi" },
  HUONG_DAN: { cls: "border-blue text-blue", label: "Hướng dẫn" },
  DAN_CHIEU: { cls: "border-border text-dim", label: "Dẫn chiếu" },
};

export default function AlertsPage() {
  const [events, setEvents] = useState<ChangeEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<{ id: string; email: string } | null>(null);
  const [subId, setSubId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    (async () => {
      try {
        const { data: auth } = await supabase.auth.getUser();
        const u = auth.user;
        if (u?.email) setUser({ id: u.id, email: u.email });

        const { data, error } = await supabase
          .from("change_events")
          .select("*")
          .order("created_at", { ascending: false })
          .limit(50);
        if (error) throw error;
        setEvents(data ?? []);

        if (u) {
          const { data: subs } = await supabase
            .from("alert_subscriptions")
            .select("id")
            .eq("user_id", u.id)
            .eq("channel", "email")
            .limit(1);
          setSubId(subs?.[0]?.id ?? null);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Không tải được dữ liệu");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function toggleSubscribe() {
    if (!user) return;
    setBusy(true);
    const supabase = createClient();
    try {
      if (subId) {
        await supabase.from("alert_subscriptions").delete().eq("id", subId);
        setSubId(null);
      } else {
        const { data, error } = await supabase
          .from("alert_subscriptions")
          .insert({ user_id: user.id, channel: "email", target: user.email })
          .select("id")
          .single();
        if (error) throw error;
        setSubId(data.id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi cập nhật đăng ký");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell active="alerts">
    <div className="mx-auto max-w-3xl px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Cảnh báo thay đổi</h1>
          <p className="mt-1 text-sm text-dim">
            Văn bản bị <span className="text-red">thay thế</span> /{" "}
            <span className="text-accent-dim">sửa đổi</span> — phát hiện tự động khi nạp văn bản mới.
          </p>
        </div>
        <button
          onClick={toggleSubscribe}
          disabled={busy || !user}
          className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
            subId
              ? "border-accent bg-accent/10 text-accent-dim hover:bg-accent/20"
              : "border-border bg-panel text-dim hover:border-accent hover:text-accent-dim"
          }`}
        >
          {subId ? "🔔 Đang nhận cảnh báo" : "🔕 Đăng ký nhận cảnh báo"}
        </button>
      </div>

      {error && (
        <div className="mt-6 rounded-lg border border-red bg-red/5 px-4 py-3 text-sm text-red">
          {error}
        </div>
      )}
      {loading && <p className="mt-8 text-sm text-faint">Đang tải…</p>}
      {!loading && events.length === 0 && !error && (
        <p className="mt-8 text-sm text-faint">
          Chưa có thay đổi nào được ghi nhận. Sự kiện xuất hiện khi admin nạp corpus có quan hệ
          thay thế/sửa đổi.
        </p>
      )}

      <div className="mt-6 space-y-2">
        {events.map((ev) => {
          const badge = REL_BADGE[ev.rel_type] ?? REL_BADGE.DAN_CHIEU;
          return (
            <div key={ev.id} className={`rounded-lg border-l-4 bg-panel px-4 py-3 ${badge.cls}`}>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-semibold uppercase tracking-wide">{badge.label}</span>
                <span className="mono text-faint">
                  {ev.source_doc_id} → {ev.doc_id}
                </span>
                <span className="mono ml-auto text-faint">
                  {ev.effective_date ? `hiệu lực ${ev.effective_date}` : ""}
                </span>
              </div>
              <p className="mt-1 text-sm text-foreground">{ev.description}</p>
            </div>
          );
        })}
      </div>
    </div>
    </PageShell>
  );
}
