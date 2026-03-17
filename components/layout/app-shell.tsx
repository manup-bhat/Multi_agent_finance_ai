"use client";
import { useState, useEffect } from "react";
import { Sidebar } from "./sidebar";
import { Navbar } from "./navbar";
import { ToastContainer } from "./toast-container";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import { checkHealth } from "@/lib/api-client";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { setApiConnected } = useApp();

  // Poll /health every 30 seconds to update API connection status
  useEffect(() => {
    let cancelled = false;

    async function poll() {
      const result = await checkHealth();
      if (!cancelled) setApiConnected(result !== null);
    }

    poll();
    const interval = setInterval(poll, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [setApiConnected]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((c) => !c)}
      />
      <Navbar
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
      />
      <main
        className={cn(
          "transition-all duration-150 pt-14",
          sidebarCollapsed ? "pl-16" : "pl-60"
        )}
      >
        <div className="p-6 min-h-[calc(100vh-56px)]">
          {children}
        </div>
      </main>
      <ToastContainer />
    </div>
  );
}
