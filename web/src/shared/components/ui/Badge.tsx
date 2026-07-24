import { type HTMLAttributes } from "react";
import { cn } from "@/shared/utils/cn";

type Tone = "neutral" | "accent" | "green" | "blue" | "yellow" | "red";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "border-border bg-inset text-dim",
  accent: "border-accent/30 bg-accent/10 text-accent-dim",
  green: "border-green/30 bg-green/10 text-green",
  blue: "border-blue/30 bg-blue/10 text-blue",
  yellow: "border-yellow/30 bg-yellow/10 text-yellow",
  red: "border-red/30 bg-red/10 text-red",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide whitespace-nowrap",
        TONE_CLASSES[tone],
        className,
      )}
      {...props}
    />
  );
}
