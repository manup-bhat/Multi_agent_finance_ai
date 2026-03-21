"use client";
import { useState, useMemo } from "react";
import useSWR from "swr";
import { Menu, Search, Bell, X } from "lucide-react";
import { cn, getVixStatus, formatCrore } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "./theme-toggle";
import { useApp } from "@/lib/app-context";
import { getMacro } from "@/lib/api-client";
import { NSE_TICKERS } from "@/lib/nse-tickers";

interface NavbarProps {
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
}

export function Navbar({ sidebarCollapsed, onToggleSidebar }: NavbarProps) {
  const { selectedTicker, setSelectedTicker, notifications, removeNotification } = useApp();
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);

  // Live macro data for header badges — refresh every 5 min
  const { data: macro } = useSWR("navbar-macro", getMacro, {
    refreshInterval: 5 * 60 * 1000,
    revalidateOnFocus: false,
  });

  const vix = macro?.vix ?? null;
  const fiiFlow = macro?.fii_net_crore ?? null;
  const vixStatus = getVixStatus(vix ?? 15);

  // Market is open on weekdays 9:15–15:30 IST
  const now = new Date();
  const istOffset = 5.5 * 60 * 60 * 1000;
  const ist = new Date(now.getTime() + istOffset);
  const day = ist.getUTCDay();
  const hour = ist.getUTCHours();
  const min = ist.getUTCMinutes();
  const timeMin = hour * 60 + min;
  const marketOpen = day >= 1 && day <= 5 && timeMin >= 555 && timeMin <= 930;

  const filteredTickers = useMemo(() => {
    if (!searchQuery.trim()) return NSE_TICKERS.slice(0, 6);
    const q = searchQuery.toLowerCase();
    return NSE_TICKERS.filter(
      (t) => t.symbol.toLowerCase().includes(q) || t.name.toLowerCase().includes(q)
    ).slice(0, 6);
  }, [searchQuery]);

  return (
    <header
      className={cn(
        "fixed top-0 z-20 h-14 border-b border-border bg-surface/80 backdrop-blur-sm transition-all duration-150",
        sidebarCollapsed ? "left-16" : "left-60",
        "right-0"
      )}
    >
      <div className="flex items-center justify-between h-full px-4 gap-4">
        {/* Left */}
        <button
          onClick={onToggleSidebar}
          className="p-1 text-text-muted hover:text-text-primary transition-colors duration-150 lg:hidden"
          aria-label="Toggle sidebar"
        >
          <Menu size={20} />
        </button>

        {/* Center: Search */}
        <div className="relative flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" size={16} />
            <input
              type="text"
              placeholder="Search NSE ticker... e.g. RELIANCE.NS"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              className="w-full pl-10 pr-4 py-2 rounded-pill border border-border bg-surface text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-saffron/50 focus:ring-2 focus:ring-saffron/20 transition-all duration-150"
            />
          </div>

          {/* Dropdown */}
          {searchOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setSearchOpen(false)}
              />
              <div className="absolute top-full left-0 right-0 mt-2 bg-surface border border-border rounded-card shadow-elevated z-20 max-h-80 overflow-y-auto scrollbar-thin">
                {filteredTickers.length > 0 ? (
                  filteredTickers.map((ticker) => (
                    <button
                      key={ticker.symbol}
                      onClick={() => {
                        setSelectedTicker(ticker.symbol);
                        setSearchQuery("");
                        setSearchOpen(false);
                      }}
                      className="w-full text-left px-4 py-3 hover:bg-surface-raised transition-colors duration-150 border-b border-border last:border-0"
                    >
                      <div className="font-medium text-sm text-text-primary">
                        {ticker.symbol.replace(".NS", "")}
                        <span className="ml-1 text-xs text-text-muted font-normal">.NS</span>
                      </div>
                      <div className="text-xs text-text-muted">{ticker.name} · {ticker.sector}</div>
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-sm text-text-muted">No tickers found</div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Right: Badges + Actions */}
        <div className="flex items-center gap-2">
          {/* VIX Badge */}
          {vix != null && (
            <Badge
              variant={vix < 18 ? "bullish" : vix < 25 ? "warning" : "bearish"}
              pulse={vix > 25}
              className="hidden sm:inline-flex"
            >
              VIX {vix.toFixed(1)} {vixStatus.label}
            </Badge>
          )}

          {/* FII Flow */}
          {fiiFlow != null && (
            <Badge
              variant={fiiFlow >= 0 ? "bullish" : "bearish"}
              className="hidden md:inline-flex"
            >
              FII {formatCrore(fiiFlow)}
            </Badge>
          )}

          {/* Market Status */}
          <Badge variant={marketOpen ? "bullish" : "muted"} className="hidden lg:inline-flex">
            NSE {marketOpen ? "OPEN" : "CLOSED"}
          </Badge>

          {/* Theme Toggle */}
          <ThemeToggle iconOnly />

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => setNotifOpen(!notifOpen)}
              className="relative p-1.5 text-text-muted hover:text-text-primary transition-colors duration-150"
              aria-label="Notifications"
            >
              <Bell size={18} />
              {notifications.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-bearish-red text-white text-[10px] font-bold flex items-center justify-center">
                  {notifications.length}
                </span>
              )}
            </button>

            {notifOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setNotifOpen(false)}
                />
                <div className="absolute top-full right-0 mt-2 w-80 bg-surface border border-border rounded-card shadow-elevated z-20 max-h-96 overflow-y-auto scrollbar-thin">
                  <div className="sticky top-0 bg-surface border-b border-border px-4 py-2 flex items-center justify-between">
                    <span className="text-sm font-medium text-text-primary">Notifications</span>
                    <button
                      onClick={() => setNotifOpen(false)}
                      className="p-1 text-text-muted hover:text-text-primary"
                      aria-label="Close"
                    >
                      <X size={14} />
                    </button>
                  </div>
                  {notifications.length > 0 ? (
                    notifications.map((n) => (
                      <div
                        key={n.id}
                        className="px-4 py-3 border-b border-border last:border-0 hover:bg-surface-raised"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-text-primary">{n.message}</p>
                            <p className="text-xs text-text-muted mt-1">
                              {Math.floor((Date.now() - n.timestamp.getTime()) / 1000 / 60)}m ago
                            </p>
                          </div>
                          <button
                            onClick={() => removeNotification(n.id)}
                            className="p-1 text-text-muted hover:text-text-primary flex-shrink-0"
                            aria-label="Dismiss"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="px-4 py-8 text-center text-sm text-text-muted">
                      No notifications
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
