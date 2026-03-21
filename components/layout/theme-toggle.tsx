"use client";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";

export function ThemeToggle({ iconOnly = false }: { iconOnly?: boolean }) {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Only render after mount to avoid hydration mismatch
  // On the server, resolvedTheme is undefined; on client it's "dark"/"light"
  useEffect(() => {
    setMounted(true);
  }, []);

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
      {/* Render static icon before mount to avoid hydration mismatch */}
      {mounted ? (
        isDark ? <Sun size={16} /> : <Moon size={16} />
      ) : (
        <span style={{ width: 16, height: 16, display: "inline-block" }} />
      )}
      {!iconOnly && mounted && <span>{isDark ? "Light" : "Dark"}</span>}
    </button>
  );
}
