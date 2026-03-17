"use client";
import { useState } from "react";
import { Info } from "lucide-react";
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

  return (
    <div className={cn("relative inline-block", className)}>
      <button
        type="button"
        aria-label={`Help: ${content.title}`}
        onClick={() => setOpen(!open)}
        className="inline-flex items-center justify-center w-5 h-5 rounded-full text-text-muted hover:text-saffron transition-colors duration-150 hover:bg-saffron-light"
      >
        <Info size={14} />
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />
          {/* Popover */}
          <div
            className="absolute right-0 top-6 z-50 w-72 rounded-card border border-border bg-surface shadow-elevated backdrop-blur-sm animate-in fade-in-0 slide-in-from-top-2 duration-150"
            role="dialog"
            aria-label={content.title}
          >
            <div className="p-4">
              <h4 className="font-semibold text-sm text-saffron mb-2">{content.title}</h4>
              <p className="text-xs text-text-secondary leading-relaxed mb-3">{content.body}</p>
              {content.affectsVerdict && (
                <div className="mb-2">
                  <span className="section-label">Affects Verdict</span>
                  <p className="text-xs text-text-primary mt-1">{content.affectsVerdict}</p>
                </div>
              )}
              {content.source && (
                <div className="mb-3">
                  <span className="section-label">Source</span>
                  <p className="text-xs text-text-secondary mt-1">{content.source}</p>
                </div>
              )}
              <button
                disabled
                className="text-xs text-saffron/50 cursor-not-allowed"
              >
                Learn more →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
