import { Icon } from "@iconify/react";

export function EmptyState({
  icon = "ph:archive",
  title,
  description,
}: {
  icon?: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border px-6 py-14 text-center">
      <Icon icon={icon} className="text-3xl text-faint" />
      <p className="font-heading text-sm font-medium text-foreground">{title}</p>
      {description && <p className="max-w-sm text-xs text-dim">{description}</p>}
    </div>
  );
}
