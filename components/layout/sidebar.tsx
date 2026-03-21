"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, TrendingUp, Sparkles, Brain, ScrollText,
  Building2, Globe, RefreshCw, Newspaper, Shield, BarChart3,
  Activity, Search, Settings, ChevronLeft, ChevronRight
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import { ThemeToggle } from "./theme-toggle";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/technical", label: "Technical Analysis", icon: TrendingUp },
  { href: "/predictions", label: "Predictions", icon: Sparkles },
  { href: "/sentiment", label: "Sentiment & Emotion", icon: Brain },
  { href: "/fno-analysis", label: "F&O Analysis", icon: ScrollText },
  { href: "/fii-dii", label: "FII / DII Tracker", icon: Building2 },
  { href: "/macro", label: "Macro India", icon: Globe },
  { href: "/sector-rotation", label: "Sector Rotation", icon: RefreshCw },
  { href: "/news", label: "News Feed", icon: Newspaper },
  { href: "/risk", label: "Risk Monitor", icon: Shield },
  { href: "/backtest", label: "Backtest Results", icon: BarChart3 },
  { href: "/model-performance", label: "Model Performance", icon: Activity },
  { href: "/audit", label: "Audit Trail", icon: Search },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const { apiConnected } = useApp();

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 h-full z-30 flex flex-col bg-surface border-r border-border transition-all duration-150",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className={cn("flex items-center gap-3 px-4 py-4 border-b border-border min-h-[56px]", collapsed && "px-3 justify-center")}>
        <div className="w-8 h-8 rounded-full bg-saffron flex items-center justify-center flex-shrink-0 text-sm">
          🇮🇳
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="font-bold text-sm text-text-primary truncate">India AI Engine</div>
            <div className="text-xs text-text-muted">NSE • BSE • F&O</div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2 scrollbar-thin">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              className={cn(
                "flex items-center gap-3 px-4 py-2.5 mx-2 rounded-btn text-sm transition-all duration-150 group",
                collapsed && "px-3 justify-center",
                active
                  ? "bg-saffron-light text-saffron font-medium"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-raised"
              )}
            >
              <Icon
                size={18}
                className={cn(
                  "flex-shrink-0 transition-colors duration-150",
                  active ? "text-saffron" : "text-text-muted group-hover:text-text-primary"
                )}
              />
              {!collapsed && <span className="truncate">{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-border py-3 px-3 space-y-1">
        <Link
          href="/settings"
          title={collapsed ? "Settings" : undefined}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-btn text-sm text-text-secondary hover:text-text-primary hover:bg-surface-raised transition-all duration-150",
            collapsed && "justify-center"
          )}
        >
          <Settings size={16} />
          {!collapsed && "Settings"}
        </Link>

        <div className={cn("flex items-center gap-3 px-3 py-2", collapsed && "justify-center")}>
          <ThemeToggle iconOnly />
          {!collapsed && <span className="text-sm text-text-secondary">Theme</span>}
        </div>

        {/* Connection dot */}
        <div className={cn("flex items-center gap-2 px-3 py-2", collapsed && "justify-center")}>
          <div
            className={cn(
              "w-2 h-2 rounded-full flex-shrink-0",
              apiConnected ? "bg-bullish-green" : "bg-bearish-red"
            )}
            title={apiConnected ? "API Connected" : "API Disconnected — using mock data"}
          />
          {!collapsed && (
            <span className="text-xs text-text-muted">
              {apiConnected ? "API Connected" : "API Offline"}
            </span>
          )}
        </div>
      </div>

      {/* Collapse button */}
      <button
        onClick={onToggle}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-surface border border-border shadow-card flex items-center justify-center text-text-muted hover:text-saffron hover:border-saffron/30 transition-all duration-150 z-10"
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  );
}
