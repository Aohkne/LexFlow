import Link from "next/link";
import { Icon } from "@iconify/react";
import { Card, CardBody } from "@/shared/components/ui/Card";
import { Badge } from "@/shared/components/ui/Badge";
import type { PainpointSolution } from "../content";

export function PainpointCard({ item }: { item: PainpointSolution }) {
  const body = (
    <Card className={item.href ? "h-full transition-colors hover:border-accent" : "h-full"}>
      <CardBody className="flex h-full flex-col">
        <div className="mono text-[11px] text-faint">{item.index} / 05</div>

        <div className="mt-2 flex items-start gap-2">
          <Icon icon="ph:x-circle-fill" className="mt-0.5 shrink-0 text-red" />
          <p className="text-xs leading-relaxed text-dim">{item.painpoint}</p>
        </div>

        <div className="mt-3 border-l border-border pl-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <Icon icon={item.icon} className="text-accent" />
            <span className="font-heading text-sm font-semibold text-foreground">
              {item.solution}
            </span>
          </div>
          <p className="mt-1 text-xs text-dim">{item.description}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {item.tags.map((t) => (
              <Badge key={t}>{t}</Badge>
            ))}
          </div>
        </div>

        {item.href && (
          <span className="mt-auto flex items-center gap-1 pt-3 text-xs font-medium text-accent-dim">
            Xem thử <Icon icon="ph:arrow-right" />
          </span>
        )}
      </CardBody>
    </Card>
  );

  return item.href ? <Link href={item.href}>{body}</Link> : body;
}
