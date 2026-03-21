"use client";
import useSWR from "swr";
import dynamic from "next/dynamic";
import { ChartSkeleton } from "@/components/charts";

const SectorRotationChart = dynamic(
  () => import('@/components/charts/SectorRotationChart').then(m => m.SectorRotationChart),
  { ssr: false, loading: () => <ChartSkeleton height={400} /> }
);
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchSectorData() {
  const res = await fetch(`${BASE_URL}/macro/sector-rotation`);
  // Return null for 404 — endpoint not yet implemented in backend
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

interface SectorPoint {
  sector: string;
  momentum: number;
  relative_strength: number;
  flow: number;
  phase: string;
}

const PHASE_COLORS: Record<string, string> = {
  LEADING:   "#059669",
  IMPROVING: "#65A30D",
  LAGGING:   "#DC2626",
  WEAKENING: "#D97706",
};

const QUADRANTS = [
  { phase: "LEADING",   label: "Leading",   desc: "High RS + Rising Momentum — best to invest",  bg: "bg-bullish-bg",  color: "text-bullish-green" },
  { phase: "IMPROVING", label: "Improving", desc: "Low RS + Rising Momentum — early entry zone",  bg: "bg-surface-raised", color: "text-text-secondary" },
  { phase: "WEAKENING", label: "Weakening", desc: "High RS + Falling Momentum — consider exit",   bg: "bg-warning-bg",  color: "text-warning-amber" },
  { phase: "LAGGING",   label: "Lagging",   desc: "Low RS + Falling Momentum — avoid",            bg: "bg-bearish-bg",  color: "text-bearish-red" },
];

export default function SectorRotationPage() {
  const { data, error, isLoading } = useSWR<SectorPoint[] | null>(
    "sector-rotation",
    fetchSectorData,
    { revalidateOnFocus: false, refreshInterval: 15 * 60 * 1000 }
  );

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <Skeleton className="h-7 w-44" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  const heading = (
    <div className="flex items-center gap-2">
      <h1 className="text-xl font-semibold text-text-primary">Sector Rotation</h1>
        <HelpPopover content={{
          title: "Sector Rotation & Relative Rotation Graph (RRG)",
          body: "Every economic cycle, institutional money rotates between sectors — from defensive sectors (FMCG, Pharma) during downturns to cyclical sectors (Metals, Auto, Real Estate) during recoveries. The Relative Rotation Graph (RRG) visualises this rotation in real time by plotting each sector's relative strength and momentum against the Nifty50 benchmark.",
          level: "intermediate",
          tips: [
            "Leading (top-right) = outperforming and still gaining — best to invest",
            "Weakening (top-left) = still strong but losing momentum — consider exit",
            "Lagging (bottom-left) = underperforming and still falling — avoid",
            "Improving (bottom-right) = weak but gaining momentum — early entry",
            "Sectors rotate clockwise through these quadrants over time",
          ],
          affectsVerdict: "If a stock's sector is in the Leading quadrant, bullish signals receive a 10–15% confidence boost. Lagging sectors reduce confidence by the same amount.",
          source: "NSE sector indices (Nifty Auto, IT, FMCG etc.) via yfinance — rolling 12-week RS and momentum calculation",
        }} />
    </div>
  );

  // ── Endpoint not yet available ─────────────────────────────────────────
  if (!data || (Array.isArray(data) && data.length === 0) || error) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        {heading}

        {error && (
          <div className="rounded-btn border border-warning-amber/30 bg-warning-bg px-4 py-3 text-sm text-warning-amber">
            API returned an error — sector rotation data unavailable right now.
          </div>
        )}

        {/* Educational content while endpoint is pending */}
        <div className="card-base p-6">
          <h3 className="text-base font-semibold text-text-primary mb-1">
            Relative Rotation Graph (RRG) — How to Read It
          </h3>
          <p className="text-sm text-text-secondary leading-relaxed mb-6">
            The RRG divides the market into four quadrants based on two axes: Relative Strength (RS) versus
            the benchmark and Momentum of that RS. Sectors rotate clockwise through the quadrants over time.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {QUADRANTS.map((q) => (
              <div key={q.phase} className={cn("p-4 rounded-card border border-border", q.bg)}>
                <div className={cn("font-bold text-sm mb-1", q.color)}>{q.label}</div>
                <p className="text-xs text-text-secondary leading-relaxed">{q.desc}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-text-muted mt-6 border-t border-border pt-4">
            This page will populate automatically once the backend exposes{" "}
            <code className="text-text-secondary">GET /macro/sector-rotation</code>. The endpoint
            computes rolling 12-week momentum and RS for each NSE sector index using yfinance.
          </p>
        </div>

        {/* How to interpret */}
        <div className="card-base p-5">
          <h3 className="text-base font-semibold text-text-primary mb-4">How to Use Sector Rotation in Your Decisions</h3>
          <div className="space-y-3">
            {[
              {
                step: "1",
                title: "Find your stock's sector",
                body: "Every NSE stock belongs to one of 13 GICS sectors — IT, Banking, FMCG, Auto, Pharma, Energy, Metals, Realty, Media, Telecom, Infrastructure, Chemicals, and Consumer Durables.",
              },
              {
                step: "2",
                title: "Check the quadrant",
                body: "If your sector is in Leading: tailwind for bullish positions. If Lagging: headwind. Improving sectors are early-entry opportunities; Weakening sectors may be past their peak.",
              },
              {
                step: "3",
                title: "Watch for rotations",
                body: "Sectors rotate clockwise. A sector moving from Improving → Leading is gaining momentum. A sector drifting from Leading → Weakening is topping out.",
              },
              {
                step: "4",
                title: "Combine with FII flows",
                body: "FII inflows into a specific sector (visible in the F&O participant OI data) combined with a Leading quadrant position is the strongest confirmation of a sector trade.",
              },
            ].map((item) => (
              <div key={item.step} className="flex gap-4 p-4 rounded-btn bg-surface-raised">
                <div className="flex-shrink-0 w-7 h-7 rounded-full bg-saffron flex items-center justify-center text-white text-xs font-bold">
                  {item.step}
                </div>
                <div>
                  <div className="text-sm font-semibold text-text-primary mb-0.5">{item.title}</div>
                  <p className="text-xs text-text-secondary leading-relaxed">{item.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── Live RRG when endpoint is available ────────────────────────────────
  const grouped = data.reduce<Record<string, SectorPoint[]>>((acc, d) => {
    (acc[d.phase] = acc[d.phase] ?? []).push(d);
    return acc;
  }, {});

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      {heading}

      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">Relative Rotation Graph (RRG)</h3>
        <SectorRotationChart
          data={data.map((d) => ({
            sector: d.sector,
            rs: +(d.relative_strength - 100).toFixed(2),
            rsMomentum: +(d.momentum - 100).toFixed(2),
            volumeRatio: d.flow != null ? Math.abs(d.flow) : undefined,
          }))}
          height={400}
        />
        <div className="grid grid-cols-2 gap-3 mt-4 text-xs">
          {QUADRANTS.map((q) => (
            <div key={q.phase} className={cn("p-3 rounded-btn", q.bg)}>
              <div className={cn("font-semibold mb-0.5", q.color)}>{q.label}</div>
              <div className="text-text-muted">{q.desc}</div>
              <div className={cn("mt-1 font-medium text-xs", q.color)}>
                {grouped[q.phase]?.map((s) => s.sector).join(", ") || "None"}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">All Sectors</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted">
                <th className="text-left py-2 font-medium">Sector</th>
                <th className="text-right py-2 font-medium">Momentum</th>
                <th className="text-right py-2 font-medium">Relative Strength</th>
                <th className="text-right py-2 font-medium">FII Flow</th>
                <th className="text-left py-2 font-medium pl-4">Phase</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {[...data].sort((a, b) => b.momentum - a.momentum).map((row) => (
                <tr key={row.sector} className="hover:bg-surface-raised transition-colors duration-150">
                  <td className="py-2.5 font-medium text-text-primary">{row.sector}</td>
                  <td className={cn("py-2.5 text-right tabular-nums", row.momentum >= 100 ? "text-bullish-green" : "text-bearish-red")}>
                    {row.momentum.toFixed(1)}
                  </td>
                  <td className={cn("py-2.5 text-right tabular-nums", row.relative_strength >= 100 ? "text-bullish-green" : "text-bearish-red")}>
                    {row.relative_strength.toFixed(1)}
                  </td>
                  <td className={cn("py-2.5 text-right tabular-nums", row.flow >= 0 ? "text-bullish-green" : "text-bearish-red")}>
                    {row.flow >= 0 ? "+" : ""}{row.flow.toFixed(0)}Cr
                  </td>
                  <td className="py-2.5 pl-4">
                    <span
                      className="px-2 py-0.5 rounded-badge text-xs font-semibold"
                      style={{ color: PHASE_COLORS[row.phase] ?? "#94A3B8", background: `${PHASE_COLORS[row.phase] ?? "#94A3B8"}18` }}
                    >
                      {row.phase}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
