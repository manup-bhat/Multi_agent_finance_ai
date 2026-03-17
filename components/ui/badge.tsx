import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "bullish" | "bearish" | "neutral" | "warning" | "saffron" | "muted";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
  pulse?: boolean;
}

const variants: Record<BadgeVariant, string> = {
  default: "bg-surface-raised text-text-secondary border-border",
  bullish: "bg-bullish-bg text-bullish-green border-bullish-green/20",
  bearish: "bg-bearish-bg text-bearish-red border-bearish-red/20",
  neutral: "bg-neutral-bg text-neutral-blue border-neutral-blue/20",
  warning: "bg-warning-bg text-warning-amber border-warning-amber/20",
  saffron: "bg-saffron-light text-saffron border-saffron/20",
  muted: "bg-surface-raised text-text-muted border-border",
};

export function Badge({ children, variant = "default", className, pulse }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-badge text-xs font-medium border",
        variants[variant],
        pulse && "animate-pulse",
        className
      )}
    >
      {children}
    </span>
  );
}

export function SentimentBadge({ sentiment }: { sentiment: string }) {
  const map: Record<string, BadgeVariant> = {
    BULLISH: "bullish",
    BEARISH: "bearish",
    NEUTRAL: "neutral",
  };
  return <Badge variant={map[sentiment] || "default"}>{sentiment}</Badge>;
}
