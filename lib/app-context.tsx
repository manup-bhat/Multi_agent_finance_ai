"use client";
import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import type { AnalyzeResponse } from "./api-client";

export type Notification = {
  id: string;
  type: "success" | "warning" | "error" | "info";
  message: string;
  timestamp: Date;
};

type AppState = {
  selectedTicker: string;
  setSelectedTicker: (t: string) => void;
  analysisData: AnalyzeResponse | null;
  setAnalysisData: (d: AnalyzeResponse | null) => void;
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
  includeFno: boolean;
  setIncludeFno: (v: boolean) => void;
  includeSentiment: boolean;
  setIncludeSentiment: (v: boolean) => void;
};

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [selectedTicker, setSelectedTicker] = useState("RELIANCE.NS");
  const [analysisData, setAnalysisData] = useState<AnalyzeResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStage, setAnalysisStage] = useState(0);
  const [apiConnected, setApiConnected] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [horizon, setHorizon] = useState(5);
  const [includeFno, setIncludeFno] = useState(true);
  const [includeSentiment, setIncludeSentiment] = useState(true);

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const addNotification = useCallback((n: Omit<Notification, "id" | "timestamp">) => {
    const notification: Notification = {
      ...n,
      id: Math.random().toString(36).slice(2),
      timestamp: new Date(),
    };
    setNotifications((prev) => [notification, ...prev].slice(0, 10));
    setTimeout(() => removeNotification(notification.id), 6000);
  }, [removeNotification]);

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
        includeFno,
        setIncludeFno,
        includeSentiment,
        setIncludeSentiment,
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
