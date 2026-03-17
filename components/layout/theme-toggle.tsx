"use client";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { cn } from "@/lib/utils";

export function ThemeToggle({ iconOnly = false }: { iconOnly?: boolean }) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label="Toggle dark mode"
      className={cn(
        "inline-flex items-center gap-2 rounded-btn text-text-secondary hover:text-text-primary hover:bg-surface-raised transition-all duration-150",
        iconOnly ? "p-1.5" : "px-3 py-1.5 text-sm"
      )}
    >
      {isDark ? <Sun size={16} /> : <Moon size={16} />}
      {!iconOnly && <span>{isDark ? "Light" : "Dark"}</span>}
    </button>
  );
}
