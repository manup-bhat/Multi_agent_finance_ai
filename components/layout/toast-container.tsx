"use client";
import { X, CheckCircle, AlertTriangle, XCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import type { Notification } from "@/lib/app-context";

const icons = {
  success: <CheckCircle size={16} className="text-bullish-green flex-shrink-0" />,
  warning: <AlertTriangle size={16} className="text-warning-amber flex-shrink-0" />,
  error: <XCircle size={16} className="text-bearish-red flex-shrink-0" />,
  info: <Info size={16} className="text-neutral-blue flex-shrink-0" />,
};

const borderColors = {
  success: "border-bullish-green/30",
  warning: "border-warning-amber/30",
  error: "border-bearish-red/30",
  info: "border-neutral-blue/30",
};

export function ToastContainer() {
  const { notifications, removeNotification } = useApp();

  if (notifications.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {notifications.slice(0, 5).map((n: Notification) => (
        <div
          key={n.id}
          className={cn(
            "flex items-start gap-3 p-4 bg-surface border rounded-card shadow-elevated pointer-events-auto animate-in slide-in-from-right-4 duration-150",
            borderColors[n.type]
          )}
        >
          {icons[n.type]}
          <p className="text-sm text-text-primary flex-1">{n.message}</p>
          <button
            onClick={() => removeNotification(n.id)}
            className="p-0.5 text-text-muted hover:text-text-primary flex-shrink-0 transition-colors duration-150"
            aria-label="Dismiss notification"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
