import { Icon } from "@iconify/react";
import { Badge } from "@/shared/components/ui/Badge";
import { Card, CardBody } from "@/shared/components/ui/Card";
import { formatDate } from "@/shared/utils/format";
import type { AlertSeverity, RegulatoryAlert } from "../types";

const SEVERITY_TONE: Record<AlertSeverity, "blue" | "accent" | "red"> = {
  info: "blue",
  warning: "accent",
  critical: "red",
};

const SEVERITY_LABEL: Record<AlertSeverity, string> = {
  info: "Thông tin",
  warning: "Cảnh báo",
  critical: "Nghiêm trọng",
};

export function AlertsFeed({ alerts }: { alerts: RegulatoryAlert[] }) {
  return (
    <div className="space-y-3">
      {alerts.map((alert) => (
        <Card key={alert.id}>
          <CardBody>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={SEVERITY_TONE[alert.severity]}>
                <Icon icon="ph:bell-ringing-fill" /> {SEVERITY_LABEL[alert.severity]}
              </Badge>
              <Badge>{alert.doc_type}</Badge>
              <span className="mono ml-auto text-[11px] text-faint">
                ban hành {formatDate(alert.published_at)} · hiệu lực {formatDate(alert.effective_at)}
              </span>
            </div>
            <p className="font-heading mt-2 text-sm font-semibold text-foreground">{alert.title}</p>
            <p className="mt-1 text-sm text-dim">{alert.summary}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {alert.affected_flows.map((flow) => (
                <span
                  key={flow}
                  className="rounded-full bg-inset px-2.5 py-0.5 text-[11px] text-dim"
                >
                  ⏵ {flow}
                </span>
              ))}
            </div>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}
