import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/shared/utils/cn";

type Variant = "primary" | "outline" | "ghost";
type Size = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-accent text-accent-foreground hover:bg-accent-dim disabled:hover:bg-accent",
  outline:
    "border border-border bg-transparent text-foreground hover:border-accent hover:text-accent-dim",
  ghost: "bg-transparent text-dim hover:bg-inset hover:text-foreground",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-full font-medium tracking-wide transition-colors disabled:cursor-not-allowed disabled:opacity-50",
          VARIANT_CLASSES[variant],
          SIZE_CLASSES[size],
          className,
        )}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
