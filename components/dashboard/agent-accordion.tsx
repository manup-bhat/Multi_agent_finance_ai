"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { SentimentBadge } from "@/components/ui/badge";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";

export function AgentAccordion() {
  const { analysisData } = useApp();
  const [openId, setOpenId] = useState<string | null>(null);

  if (!analysisData) return null;
  const { agents } = analysisData;

  return (
    <div className="card-base">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-text-primary">AI Agent Reports</h3>
          <span className="inline-flex items-center px-2 py-0.5 rounded-badge bg-saffron-light text-saffron text-xs font-medium">
            {agents.length} agents
          </span>
          <HelpPopover
            content={{
              title: "AI Agent Reports — Multi-Agent Analysis",
              body: "Each agent independently analyzes a different dimension of the market: technical, macro, fundamental, prediction, emotion, F&O, and contrarian. Their weighted conclusions form the final verdict.",
              affectsVerdict: "Agent sentiments are weighted and synthesized by the orchestrator to produce the final verdict. Devil's Advocate can reduce confidence even in bullish scenarios.",
              source: "Groq 70B / Groq 8B / Gemini Pro / Local LLM via LangGraph",
            }}
          />
        </div>
      </div>

      <div className="divide-y divide-border">
        {agents.map((agent) => {
          const isOpen = openId === agent.id;
          return (
            <div key={agent.id}>
              <button
                onClick={() => setOpenId(isOpen ? null : agent.id)}
                className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-surface-raised transition-colors duration-150 text-left"
                aria-expanded={isOpen}
              >
                {/* Icon */}
                <span className="text-lg w-7 flex-shrink-0">{agent.icon}</span>

                {/* Name */}
                <div className="w-36 flex-shrink-0">
                  <div className="text-sm font-medium text-text-primary">{agent.name}</div>
                </div>

                {/* Summary */}
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-text-secondary truncate">{agent.summary}</p>
                </div>

                {/* Sentiment + chevron */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <SentimentBadge sentiment={agent.sentiment} />
                  {isOpen
                    ? <ChevronDown size={14} className="text-text-muted" />
                    : <ChevronRight size={14} className="text-text-muted" />
                  }
                </div>
              </button>

              {/* Expanded content */}
              {isOpen && (
                <div className="px-5 pb-5 bg-surface-raised/50 border-t border-border">
                  <div className="pt-4 prose prose-sm max-w-none">
                    <AgentMarkdown text={agent.full_report} />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Simple markdown renderer for bold/bullet
function AgentMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1.5 text-xs text-text-secondary leading-relaxed">
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-1" />;
        if (line.startsWith("**") && line.endsWith("**")) {
          return (
            <h4 key={i} className="font-semibold text-text-primary text-sm">
              {line.replace(/\*\*/g, "")}
            </h4>
          );
        }
        // Bold inline **text**
        const parts = line.split(/(\*\*[^*]+\*\*)/g);
        return (
          <p key={i} className="text-xs text-text-secondary">
            {parts.map((part, j) =>
              part.startsWith("**") && part.endsWith("**")
                ? <strong key={j} className="text-text-primary font-semibold">{part.replace(/\*\*/g, "")}</strong>
                : <span key={j}>{part}</span>
            )}
          </p>
        );
      })}
    </div>
  );
}
