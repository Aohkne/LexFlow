"use client";

import { cn } from "@/shared/utils/cn";

export interface TabOption<T extends string> {
  value: T;
  label: string;
}

export function Tabs<T extends string>({
  options,
  value,
  onChange,
  className,
}: {
  options: TabOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex rounded-full border border-border bg-background p-1",
        className,
      )}
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            "rounded-full px-3.5 py-1.5 text-xs font-medium tracking-wide transition-colors",
            value === opt.value
              ? "bg-accent text-accent-foreground"
              : "text-dim hover:text-foreground",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
