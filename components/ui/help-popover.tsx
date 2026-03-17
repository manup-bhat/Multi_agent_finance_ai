"use client";
import { useState, useEffect, useRef } from "react";
import { Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface HelpContent {
  title: string;
  body: string;
  affectsVerdict?: string;
  source?: string;
}

interface HelpPopoverProps {
  content: HelpContent;
  className?: string;
}

export function HelpPopover({ content, className }: HelpPopoverProps) {
  const [open, setOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

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
            className="absolute right-0 top-7 z-50 w-80 rounded-card border border-border bg-surface shadow-elevated animate-in fade-in-0 slide-in-from-top-2 duration-150"
            role="dialog"
            aria-modal="true"
            aria-label={content.title}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 pt-4 pb-2 border-b border-border">
              <h4 className="font-semibold text-sm text-saffron">{content.title}</h4>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close help"
                className="text-text-muted hover:text-text-primary transition-colors"
              >
                <X size={13} />
              </button>
            </div>

            <div className="p-4 space-y-3">
              {/* Plain-English explanation */}
              <p className="text-xs text-text-secondary leading-relaxed">{content.body}</p>

              {content.affectsVerdict && (
                <div className="rounded-btn bg-saffron-light px-3 py-2">
                  <div className="text-xs font-semibold text-saffron uppercase tracking-widest mb-1">
                    How it affects the verdict
                  </div>
                  <p className="text-xs text-text-primary leading-relaxed">{content.affectsVerdict}</p>
                </div>
              )}

              {content.source && (
                <div>
                  <div className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-1">
                    Data source
                  </div>
                  <p className="text-xs text-text-secondary">{content.source}</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
