"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Icon } from "@iconify/react";
import { Button } from "@/shared/components/ui/Button";
import { Card, CardEyebrow } from "@/shared/components/ui/Card";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { Spinner } from "@/shared/components/ui/Spinner";
import { Tabs } from "@/shared/components/ui/Tabs";
import { useAuth } from "@/shared/providers/AuthProvider";
import { listDocuments, setDocumentStatus } from "../api";
import type { AdminDocument, DocStatus } from "../types";
import { DocumentTable } from "./DocumentTable";

type Filter = "all" | DocStatus;

export function AdminDashboardPage() {
  const [documents, setDocuments] = useState<AdminDocument[] | null>(null);
  const [filter, setFilter] = useState<Filter>("pending");
  const [busyId, setBusyId] = useState<string | null>(null);
  const { user, logout } = useAuth();

  useEffect(() => {
    listDocuments().then(setDocuments);
  }, []);

  const filtered = useMemo(() => {
    if (!documents) return [];
    if (filter === "all") return documents;
    return documents.filter((d) => d.status === filter);
  }, [documents, filter]);

  const counts = useMemo(() => {
    const base = { all: 0, pending: 0, approved: 0, rejected: 0 };
    for (const d of documents ?? []) {
      base.all += 1;
      base[d.status] += 1;
    }
    return base;
  }, [documents]);

  async function updateStatus(id: string, status: DocStatus) {
    setBusyId(id);
    const next = await setDocumentStatus(id, status);
    setDocuments(next);
    setBusyId(null);
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-10">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <CardEyebrow>Vận hành pháp chế</CardEyebrow>
          <h1 className="font-heading mt-1 text-2xl font-semibold text-foreground sm:text-3xl">
            Duyệt văn bản nguồn
          </h1>
          <p className="mt-2 max-w-lg text-sm text-dim">
            Cổng kiểm soát chất lượng dữ liệu đầu vào — văn bản chỉ được dùng làm nguồn trả lời sau
            khi được gắn ngày hiệu lực và duyệt tại đây.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/admin/alerts">
            <Button variant="outline" size="sm">
              <Icon icon="ph:bell-ringing" /> Cảnh báo quy định
            </Button>
          </Link>
          <Button variant="ghost" size="sm" onClick={logout}>
            <Icon icon="ph:sign-out" /> {user?.name ?? "Đăng xuất"}
          </Button>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <Tabs
          value={filter}
          onChange={setFilter}
          options={[
            { value: "pending", label: `Chờ duyệt (${counts.pending})` },
            { value: "approved", label: `Đã duyệt (${counts.approved})` },
            { value: "rejected", label: `Từ chối (${counts.rejected})` },
            { value: "all", label: `Tất cả (${counts.all})` },
          ]}
        />
      </div>

      <Card className="mt-4">
        {!documents ? (
          <div className="grid h-40 place-items-center">
            <Spinner className="text-2xl" />
          </div>
        ) : filtered.length > 0 ? (
          <DocumentTable
            documents={filtered}
            busyId={busyId}
            onApprove={(id) => updateStatus(id, "approved")}
            onReject={(id) => updateStatus(id, "rejected")}
          />
        ) : (
          <EmptyState icon="ph:check-circle" title="Không có văn bản nào trong mục này" />
        )}
      </Card>
    </div>
  );
}
