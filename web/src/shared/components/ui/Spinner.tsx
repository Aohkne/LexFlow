import { Icon } from "@iconify/react";
import { cn } from "@/shared/utils/cn";

export function Spinner({ className }: { className?: string }) {
  return (
    <Icon icon="ph:spinner-gap-bold" className={cn("animate-spin text-accent", className)} />
  );
}
