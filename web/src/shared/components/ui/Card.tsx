import { type HTMLAttributes } from "react";
import { cn } from "@/shared/utils/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-panel shadow-[0_1px_2px_rgba(32,24,12,0.04)]",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border-b border-border px-5 py-4", className)} {...props} />;
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 py-4", className)} {...props} />;
}

export function CardEyebrow({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "font-heading text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-dim",
        className,
      )}
      {...props}
    />
  );
}
