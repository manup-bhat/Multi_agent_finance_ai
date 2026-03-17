"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";
import type { AnalyzeResponse } from "@/lib/api-client";

type AgentEntry = {
  id: string;
  label: string;
  summary: string;
};

function buildAgentEntries(data: AnalyzeResponse): AgentEntry[] {
  return [
    {
      id: "quant",
      label: "Quant Agent",
      summary: data.quant_summary,
    },
    {
      id: "macro",
      label: "Macro Agent",
      summary: data.macro_summary,
    },
    {
      id: "emotion",
      label: "Sentiment / Emotion",
      summary: data.emotion_summary,
    },
    {
      id: "fno",
      label: "F&O Agent",
      summary: data.fno_summary,
    },
    ...(data.recommended_strategy
      ? [
          {
            id: "strategy",
            label: "Recommended Strategy",
            summary: data.recommended_strategy,
          },
        ]
      : []),
  ].filter((e) => e.summary && e.summary !== "");
}

export function AgentAccordion() {
  const { analysisData } = useApp();
  const [openId, setOpenId] = useState<string | null>(null);

  if (!analysisData) return null;

  const agents = buildAgentEntries(analysisData);

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
              body: "Each agent independently analyzes a different dimension: technical, macro, sentiment, F&O. Their weighted conclusions form the final verdict.",
              affectsVerdict: "Agent summaries are synthesized by the orchestrator to produce the final verdict and confidence score.",
              source: "LangGraph multi-agent workflow — Groq / Gemini / local LLM",
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
                <div className="w-36 flex-shrink-0">
                  <div className="text-sm font-medium text-text-primary">{agent.label}</div>
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-xs text-text-secondary truncate">{agent.summary}</p>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  {isOpen
                    ? <ChevronDown size={14} className="text-text-muted" />
                    : <ChevronRight size={14} className="text-text-muted" />}
                </div>
              </button>

              {isOpen && (
                <div className="px-5 pb-5 bg-surface-raised/50 border-t border-border">
                  <div className="pt-4">
                    <p className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">
                      {agent.summary}
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Key risks footer */}
      {analysisData.key_risks.length > 0 && (
        <div className="px-5 py-4 border-t border-border bg-surface-raised/30">
          <div className="text-xs font-medium text-text-muted uppercase tracking-widest mb-2">Key Risks Identified</div>
          <ul className="space-y-1">
            {analysisData.key_risks.map((risk, i) => (
              <li key={i} className="text-xs text-text-secondary flex gap-2">
                <span className="text-warning-amber flex-shrink-0 mt-0.5">•</span>
                <span>{risk}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
