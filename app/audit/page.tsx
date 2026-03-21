"use client";
import useSWR from "swr";
import { useState } from "react";
import { Search, ChevronDown, ChevronRight } from "lucide-react";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import { getApiErrorMessage } from "@/lib/api-client";
import { TICKERS } from "@/lib/nse-tickers";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAudit(ticker: string) {
  const res = await fetch(`${BASE_URL}/audit/${encodeURIComponent(ticker)}`);
  // 404 → endpoint not yet registered; return empty array (not an error)
  if (res.status === 404) return [];
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

interface AuditEntry {
  run_id: string;
  timestamp: string;
  ticker: string;
  verdict: string;
  confidence: number;
  regime: string;
  vix_at_run: number | null;
  fii_net_at_run: number | null;
  agents_used: string[];
  feature_snapshot: Record<string, number | string | null>;
  errors: string[];
  warnings: string[];
}

const VERDICT_STYLES: Record<string, string> = {
  "STRONG BUY": "bg-bullish-bg text-bullish-green",
  "BUY": "bg-bullish-bg text-bullish-green",
  "HOLD": "bg-warning-bg text-warning-amber",
  "SELL": "bg-bearish-bg text-bearish-red",
  "STRONG SELL": "bg-bearish-bg text-bearish-red",
};

export default function AuditPage() {
  const { selectedTicker } = useApp();
  const [auditTicker, setAuditTicker] = useState(selectedTicker);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: entries, error, isLoading } = useSWR<AuditEntry[]>(
    auditTicker ? ["audit", auditTicker] : null,
    () => fetchAudit(auditTicker),
    { revalidateOnFocus: false }
  );

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold text-text-primary">Audit Trail</h1>
        <HelpPopover content={{
          title: "AI Decision Audit Trail",
          body: "Complete immutable log of every analysis run — including the exact feature snapshot, agent outputs, and reasoning at the time of each decision.",
          affectsVerdict: "Audit trail enables post-trade review and debugging of AI decisions. Each run is timestamped and hashed for integrity.",
          source: "Internal audit log — appended on every /analyze call",
        }} />
      </div>

      {/* Ticker selector */}
      <div className="card-base p-4">
        <label className="text-xs text-text-muted uppercase tracking-widest font-medium mb-3 block">
          Select Ticker to Audit
        </label>
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
            <select
              value={auditTicker}
              onChange={(e) => setAuditTicker(e.target.value)}
              className="w-full pl-8 pr-3 py-2 text-sm rounded-btn border border-border bg-surface text-text-primary focus:outline-none focus:ring-1 focus:ring-saffron/50 appearance-none"
            >
              {TICKERS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
        </div>
      )}

      {error && (
        <div className="card-base p-8 text-center">
          <p className="text-bearish-red font-medium mb-2">Failed to load audit trail</p>
          <p className="text-sm text-text-muted">{getApiErrorMessage(error)}</p>
          <p className="text-xs text-text-muted mt-2">Ensure the API exposes <code className="text-text-secondary">/audit/{"{ticker}"}</code>.</p>
        </div>
      )}

      {!isLoading && !error && (!entries || entries.length === 0) && (
        <div className="space-y-4">
          <div className="card-base p-6 text-center">
            <p className="font-medium text-text-secondary mb-2">No audit entries for {auditTicker} yet</p>
            <p className="text-sm text-text-muted mb-4">
              Run an analysis from the Dashboard to start building the audit trail.
              Every run is automatically logged with a full feature snapshot.
            </p>
          </div>
          <div className="card-base p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">What is the Audit Trail?</h3>
            <div className="space-y-3">
              {[
                { title: "Immutable run log", body: "Every analysis run is recorded with a unique run ID, timestamp, and full inputs — so you can always trace why a verdict was given." },
                { title: "Feature snapshot", body: "Captures the exact value of every input feature (RSI, VIX, FII net, MACD, etc.) at the moment of the prediction — no ambiguity." },
                { title: "Agent outputs", body: "Lists which agents ran, what they returned, and whether any errors or warnings were raised during the pipeline." },
                { title: "Post-trade review", body: "Use the audit trail to review whether signals were based on clean data, or to debug unexpected verdicts after the fact." },
              ].map((item) => (
                <div key={item.title} className="flex gap-3 p-3 rounded-btn bg-surface-raised">
                  <div className="w-1.5 h-1.5 rounded-full bg-saffron flex-shrink-0 mt-1.5" />
                  <div>
                    <div className="text-xs font-semibold text-text-primary">{item.title}</div>
                    <p className="text-xs text-text-muted mt-0.5 leading-relaxed">{item.body}</p>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-text-muted mt-4 pt-3 border-t border-border">
              The backend must expose <code className="text-text-secondary">GET /audit/{"{ticker}"}</code> to populate this page.
            </p>
          </div>
        </div>
      )}

      {!isLoading && entries && entries.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs text-text-muted px-1">
            Showing {entries.length} run{entries.length !== 1 ? "s" : ""} for {auditTicker}
          </div>
          {entries.map((entry) => {
            const isExpanded = expandedId === entry.run_id;
            return (
              <div key={entry.run_id} className="card-base overflow-hidden">
                {/* Header row */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : entry.run_id)}
                  className="w-full flex items-center gap-4 p-4 hover:bg-surface-raised transition-colors duration-150 text-left"
                >
                  {isExpanded ? (
                    <ChevronDown size={14} className="text-text-muted flex-shrink-0" />
                  ) : (
                    <ChevronRight size={14} className="text-text-muted flex-shrink-0" />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-text-primary">{entry.ticker}</span>
                      <span className={cn(
                        "text-xs px-2 py-0.5 rounded-badge font-bold",
                        VERDICT_STYLES[entry.verdict] ?? "bg-surface-raised text-text-muted"
                      )}>
                        {entry.verdict}
                      </span>
                      <span className="text-xs text-text-muted">
                        {(entry.confidence * 100).toFixed(0)}% confidence
                      </span>
                      <span className="text-xs px-1.5 py-0.5 bg-surface-raised rounded-badge text-text-secondary">
                        {entry.regime}
                      </span>
                    </div>
                    <div className="text-xs text-text-muted mt-0.5">{entry.timestamp}</div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {entry.errors.length > 0 && (
                      <span className="text-xs text-bearish-red">
                        {entry.errors.length} error{entry.errors.length !== 1 ? "s" : ""}
                      </span>
                    )}
                    {entry.warnings.length > 0 && (
                      <span className="text-xs text-warning-amber">
                        {entry.warnings.length} warning{entry.warnings.length !== 1 ? "s" : ""}
                      </span>
                    )}
                    <code className="text-xs text-text-muted font-mono">{entry.run_id.slice(0, 8)}</code>
                  </div>
                </button>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-border space-y-4 pt-4">
                    {/* Agents + context */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs text-text-muted uppercase tracking-widest mb-2">Agents Used</div>
                        <div className="flex flex-wrap gap-1.5">
                          {entry.agents_used.map((agent) => (
                            <span key={agent} className="text-xs px-2 py-0.5 rounded-badge bg-saffron-light text-saffron font-medium">
                              {agent}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-text-muted uppercase tracking-widest mb-2">Run Context</div>
                        <div className="space-y-1 text-xs">
                          <div className="flex justify-between">
                            <span className="text-text-muted">VIX at run</span>
                            <span className="text-text-secondary tabular-nums">
                              {entry.vix_at_run != null ? entry.vix_at_run.toFixed(2) : "—"}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-text-muted">FII net</span>
                            <span className={cn(
                              "tabular-nums font-medium text-xs",
                              entry.fii_net_at_run == null ? "text-text-muted"
                                : entry.fii_net_at_run >= 0 ? "text-bullish-green"
                                : "text-bearish-red"
                            )}>
                              {entry.fii_net_at_run != null
                                ? `${entry.fii_net_at_run >= 0 ? "+" : ""}₹${Math.abs(entry.fii_net_at_run).toLocaleString("en-IN", { maximumFractionDigits: 0 })}Cr`
                                : "—"}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Feature snapshot */}
                    {Object.keys(entry.feature_snapshot).length > 0 && (
                      <div>
                        <div className="text-xs text-text-muted uppercase tracking-widest mb-2">Feature Snapshot</div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b border-border">
                                <th className="text-left py-1.5 text-text-muted font-medium">Feature</th>
                                <th className="text-right py-1.5 text-text-muted font-medium">Value</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border/50">
                              {Object.entries(entry.feature_snapshot).map(([key, val]) => (
                                <tr key={key} className="hover:bg-surface-raised/50">
                                  <td className="py-1.5 font-mono text-text-secondary">{key}</td>
                                  <td className="py-1.5 text-right tabular-nums text-text-primary">
                                    {val != null ? String(val) : "null"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Errors/Warnings */}
                    {(entry.errors.length > 0 || entry.warnings.length > 0) && (
                      <div className="space-y-2">
                        {entry.errors.map((e, i) => (
                          <div key={i} className="px-3 py-2 rounded-btn bg-bearish-bg border border-bearish-red/20">
                            <span className="text-xs text-bearish-red font-medium">ERROR: </span>
                            <span className="text-xs text-bearish-red">{e}</span>
                          </div>
                        ))}
                        {entry.warnings.map((w, i) => (
                          <div key={i} className="px-3 py-2 rounded-btn bg-warning-bg border border-warning-amber/20">
                            <span className="text-xs text-warning-amber font-medium">WARN: </span>
                            <span className="text-xs text-warning-amber">{w}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
