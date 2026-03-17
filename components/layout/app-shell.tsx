"use client";
import { useState } from "react";
import { Sidebar } from "./sidebar";
import { Navbar } from "./navbar";
import { ToastContainer } from "./toast-container";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

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
