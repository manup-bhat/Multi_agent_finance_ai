"use client";
import { useState, useEffect, useRef } from "react";
import { Info, X, BookOpen, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

export interface HelpContent {
  title: string;
  /** Plain-English summary — aim for 2–3 sentences a beginner can understand */
  body: string;
  /** How this indicator or metric affects the AI verdict/confidence */
  affectsVerdict?: string;
  /** What technical level this is: beginner / intermediate / advanced */
  level?: "beginner" | "intermediate" | "advanced";
  /** Where the data comes from */
  source?: string;
  /** Optional quick-reference bullet points (max 4) */
  tips?: string[];
}

interface HelpPopoverProps {
  content: HelpContent;
  className?: string;
}

const LEVEL_STYLES: Record<NonNullable<HelpContent["level"]>, { label: string; cls: string }> = {
  beginner:     { label: "Beginner Friendly", cls: "bg-bullish-bg text-bullish-green" },
  intermediate: { label: "Intermediate",      cls: "bg-saffron-light text-saffron" },
  advanced:     { label: "Advanced",          cls: "bg-neutral-bg text-neutral-blue" },
};

export function HelpPopover({ content, className }: HelpPopoverProps) {
  const [open, setOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // Determine popup alignment — avoid going off-screen to the right
  const [alignLeft, setAlignLeft] = useState(false);
  useEffect(() => {
    if (!open || !popoverRef.current) return;
    const rect = popoverRef.current.getBoundingClientRect();
    setAlignLeft(rect.right + 320 > window.innerWidth);
  }, [open]);

  const level = content.level ? LEVEL_STYLES[content.level] : null;

  return (
    <div className={cn("relative inline-block", className)} ref={popoverRef}>
      <button
        type="button"
        aria-label={`Help: ${content.title}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center justify-center w-5 h-5 rounded-full text-text-muted hover:text-saffron transition-colors duration-150 hover:bg-saffron-light focus:outline-none focus:ring-2 focus:ring-saffron/40"
      >
        <Info size={14} />
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden="true" />

          {/* Popover panel */}
          <div
            className={cn(
              "absolute top-7 z-50 w-88 max-w-[min(22rem,calc(100vw-2rem))] rounded-card border border-border bg-surface shadow-elevated",
              "animate-in fade-in-0 slide-in-from-top-2 duration-150",
              alignLeft ? "left-0" : "right-0"
            )}
            style={{ width: "22rem" }}
            role="dialog"
            aria-modal="true"
            aria-label={content.title}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b border-border">
              <div className="flex items-center gap-2 min-w-0">
                <BookOpen size={13} className="text-saffron flex-shrink-0" />
                <h4 className="font-semibold text-sm text-saffron truncate">{content.title}</h4>
                {level && (
                  <span className={cn("text-[10px] px-1.5 py-0.5 rounded-badge font-medium flex-shrink-0 hidden sm:inline-flex", level.cls)}>
                    {level.label}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close help"
                className="p-0.5 text-text-muted hover:text-text-primary transition-colors flex-shrink-0 ml-2"
              >
                <X size={13} />
              </button>
            </div>

            <div className="p-4 space-y-3">
              {/* Plain-English explanation */}
              <p className="text-xs text-text-secondary leading-relaxed">{content.body}</p>

              {/* Quick tips */}
              {content.tips && content.tips.length > 0 && (
                <div className="space-y-1.5">
                  {content.tips.map((tip, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-saffron flex-shrink-0 mt-1.5" />
                      <p className="text-xs text-text-secondary leading-relaxed">{tip}</p>
                    </div>
                  ))}
                </div>
              )}

              {content.affectsVerdict && (
                <div className="rounded-btn bg-saffron-light px-3 py-2.5">
                  <div className="flex items-center gap-1.5 mb-1">
                    <TrendingUp size={11} className="text-saffron" />
                    <div className="text-[10px] font-semibold text-saffron uppercase tracking-widest">
                      How it affects the verdict
                    </div>
                  </div>
                  <p className="text-xs text-text-primary leading-relaxed">{content.affectsVerdict}</p>
                </div>
              )}

              {content.source && (
                <div className="pt-2 border-t border-border">
                  <div className="text-[10px] font-semibold text-text-muted uppercase tracking-widest mb-0.5">
                    Data source
                  </div>
                  <p className="text-[11px] text-text-muted leading-relaxed">{content.source}</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
