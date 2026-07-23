"use client";

import { useTheme } from "next-themes";
import { Icon } from "@iconify/react";
import { motion, AnimatePresence } from "motion/react";
import { useHasMounted } from "@/shared/hooks/useHasMounted";
import { cn } from "@/shared/utils/cn";

export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const hasMounted = useHasMounted();

  const isDark = hasMounted && resolvedTheme === "dark";

  return (
    <button
      type="button"
      aria-label="Chuyển giao diện sáng/tối"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={cn(
        "grid h-8 w-8 place-items-center rounded-full border border-border text-dim transition-colors hover:border-accent hover:text-accent-dim",
        className,
      )}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={isDark ? "moon" : "sun"}
          initial={{ opacity: 0, rotate: -90, scale: 0.6 }}
          animate={{ opacity: 1, rotate: 0, scale: 1 }}
          exit={{ opacity: 0, rotate: 90, scale: 0.6 }}
          transition={{ duration: 0.18 }}
          className="grid place-items-center"
        >
          <Icon icon={isDark ? "ph:moon-stars-fill" : "ph:sun-fill"} className="text-base" />
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
