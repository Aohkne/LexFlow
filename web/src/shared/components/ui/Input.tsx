import { type InputHTMLAttributes, type TextareaHTMLAttributes, forwardRef } from "react";
import { cn } from "@/shared/utils/cn";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none placeholder:text-faint focus:border-accent",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none placeholder:text-faint focus:border-accent",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
