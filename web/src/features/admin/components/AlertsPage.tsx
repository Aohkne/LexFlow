"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@iconify/react";
import { Button } from "@/shared/components/ui/Button";
import { CardEyebrow } from "@/shared/components/ui/Card";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { Spinner } from "@/shared/components/ui/Spinner";
import { listAlerts } from "../api";
import type { RegulatoryAlert } from "../types";
import { AlertsFeed } from "./AlertsFeed";

export function AlertsPage() {
  const [alerts, setAlerts] = useState<RegulatoryAlert[] | null>(null);

  useEffect(() => {
    listAlerts().then(setAlerts);
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <CardEyebrow>Vận hành pháp chế</CardEyebrow>
          <h1 className="font-heading mt-1 text-2xl font-semibold text-foreground sm:text-3xl">
            Cảnh báo thay đổi quy định
          </h1>
          <p className="mt-2 max-w-lg text-sm text-dim">
            Văn bản mới hoặc sắp đến mốc hiệu lực, đối chiếu với các luồng thanh toán đang vận hành.
          </p>
        </div>
        <Link href="/admin">
          <Button variant="ghost" size="sm">
            <Icon icon="ph:arrow-left" /> Duyệt văn bản
          </Button>
        </Link>
      </div>

      <div className="mt-6">
        {!alerts ? (
          <div className="grid h-40 place-items-center">
            <Spinner className="text-2xl" />
          </div>
        ) : alerts.length > 0 ? (
          <AlertsFeed alerts={alerts} />
        ) : (
          <EmptyState icon="ph:bell-slash" title="Chưa có cảnh báo nào" />
        )}
      </div>
    </div>
  );
}
