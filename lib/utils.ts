import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number, compact = false): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "+";
  if (compact && abs >= 10000000) {
    return `${sign}₹${(abs / 10000000).toFixed(1)}Cr`;
  }
  if (compact && abs >= 100000) {
    return `${sign}₹${(abs / 100000).toFixed(1)}L`;
  }
  return `${sign}₹${abs.toLocaleString("en-IN")}`;
}

export function formatCrore(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}₹${value.toLocaleString("en-IN")}Cr`;
}

export function formatPct(value: number, decimals = 1): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

export function getVixStatus(vix: number): { label: string; color: string; bg: string } {
  if (vix < 18) return { label: "NORMAL", color: "text-bullish-green", bg: "bg-bullish-bg" };
  if (vix <= 25) return { label: "ELEVATED", color: "text-warning-amber", bg: "bg-warning-bg" };
  return { label: "HIGH", color: "text-bearish-red", bg: "bg-bearish-bg" };
}

export function getVerdictColors(verdict: string) {
  switch (verdict) {
    case "STRONG_BUY":
      return { from: "#059669", to: "#047857", label: "STRONG BUY", textColor: "text-white" };
    case "BUY":
      return { from: "#059669", to: "#065F46", label: "BUY", textColor: "text-white" };
    case "HOLD":
      return { from: "#1D4ED8", to: "#1E40AF", label: "HOLD", textColor: "text-white" };
    case "SELL":
      return { from: "#DC2626", to: "#B91C1C", label: "SELL", textColor: "text-white" };
    case "STRONG_SELL":
      return { from: "#DC2626", to: "#991B1B", label: "STRONG SELL", textColor: "text-white" };
    default:
      return { from: "#1D4ED8", to: "#1E40AF", label: verdict, textColor: "text-white" };
  }
}

export function getRiskColors(level: string) {
  switch (level) {
    case "LOW": return { bg: "from-bullish-green/10 to-bullish-green/5", text: "text-bullish-green", border: "border-bullish-green/30" };
    case "MEDIUM": return { bg: "from-neutral-blue/10 to-neutral-blue/5", text: "text-neutral-blue", border: "border-neutral-blue/30" };
    case "HIGH": return { bg: "from-warning-amber/10 to-warning-amber/5", text: "text-warning-amber", border: "border-warning-amber/30" };
    case "EXTREME": return { bg: "from-bearish-red/10 to-bearish-red/5", text: "text-bearish-red", border: "border-bearish-red/30" };
    default: return { bg: "from-neutral-blue/10 to-neutral-blue/5", text: "text-neutral-blue", border: "border-neutral-blue/30" };
  }
}

export function getSentimentColor(score: number): string {
  if (score > 0.2) return "text-bullish-green";
  if (score < -0.2) return "text-bearish-red";
  return "text-warning-amber";
}

export function getFearGreedLabel(score: number): { label: string; color: string } {
  if (score <= 20) return { label: "Extreme Fear", color: "#DC2626" };
  if (score <= 40) return { label: "Fear", color: "#D97706" };
  if (score <= 60) return { label: "Neutral", color: "#D97706" };
  if (score <= 80) return { label: "Greed", color: "#059669" };
  return { label: "Extreme Greed", color: "#059669" };
}

export function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
