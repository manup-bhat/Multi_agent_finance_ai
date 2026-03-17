"use client";
import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { MOCK_ANALYSIS } from "./mock-data";

export type Notification = {
  id: string;
  type: "success" | "warning" | "error" | "info";
  message: string;
  timestamp: Date;
};

type AppState = {
  selectedTicker: string;
  setSelectedTicker: (t: string) => void;
  analysisData: typeof MOCK_ANALYSIS | null;
  setAnalysisData: (d: typeof MOCK_ANALYSIS | null) => void;
  isAnalyzing: boolean;
  setIsAnalyzing: (v: boolean) => void;
  analysisStage: number;
  setAnalysisStage: (s: number) => void;
  apiConnected: boolean;
  setApiConnected: (v: boolean) => void;
  notifications: Notification[];
  addNotification: (n: Omit<Notification, "id" | "timestamp">) => void;
  removeNotification: (id: string) => void;
  horizon: number;
  setHorizon: (h: number) => void;
  includeFO: boolean;
  setIncludeFO: (v: boolean) => void;
};

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [selectedTicker, setSelectedTicker] = useState("RELIANCE.NS");
  const [analysisData, setAnalysisData] = useState<typeof MOCK_ANALYSIS | null>(MOCK_ANALYSIS);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStage, setAnalysisStage] = useState(0);
  const [apiConnected, setApiConnected] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([
    { id: "1", type: "success", message: "RELIANCE.NS analysis complete — BUY signal", timestamp: new Date() },
    { id: "2", type: "warning", message: "FII selling streak alert — 3 days", timestamp: new Date() },
    { id: "3", type: "info", message: "India VIX: 14.2 — Normal regime", timestamp: new Date() },
  ]);
  const [horizon, setHorizon] = useState(5);
  const [includeFO, setIncludeFO] = useState(false);

  const addNotification = useCallback((n: Omit<Notification, "id" | "timestamp">) => {
    const notification: Notification = {
      ...n,
      id: Math.random().toString(36).slice(2),
      timestamp: new Date(),
    };
    setNotifications((prev) => [notification, ...prev].slice(0, 10));
    // Auto dismiss after 5s
    setTimeout(() => removeNotification(notification.id), 5000);
  }, []);

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return (
    <AppContext.Provider
      value={{
        selectedTicker,
        setSelectedTicker,
        analysisData,
        setAnalysisData,
        isAnalyzing,
        setIsAnalyzing,
        analysisStage,
        setAnalysisStage,
        apiConnected,
        setApiConnected,
        notifications,
        addNotification,
        removeNotification,
        horizon,
        setHorizon,
        includeFO,
        setIncludeFO,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
