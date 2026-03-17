import axios from "axios";
import {
  MOCK_ANALYSIS,
  MOCK_PRICE_DATA,
  MOCK_FORECAST,
  MOCK_FII_DII,
  MOCK_VIX_DATA,
  MOCK_SENTIMENT_TIMELINE,
  MOCK_OPTION_CHAIN,
  MOCK_SECTOR_DATA,
  MOCK_NEWS,
  MOCK_BACKTEST,
  MOCK_MODELS,
  MOCK_AUDIT,
} from "./mock-data";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
});

export let apiConnected = false;

export async function checkHealth(): Promise<boolean> {
  try {
    await api.get("/health", { timeout: 3000 });
    apiConnected = true;
    return true;
  } catch {
    apiConnected = false;
    return false;
  }
}

export async function analyzeStock(ticker: string, horizon = 5, includeFO = false) {
  try {
    const { data } = await api.post("/analyze", { ticker, horizon, include_fo: includeFO });
    return data;
  } catch {
    // Fallback to mock
    return { ...MOCK_ANALYSIS, ticker, horizon };
  }
}

export async function getPriceData(ticker: string, period = "3M") {
  try {
    const { data } = await api.get(`/price/${ticker}?period=${period}`);
    return data;
  } catch {
    return MOCK_PRICE_DATA;
  }
}

export async function getForecast(ticker: string) {
  try {
    const { data } = await api.get(`/forecast/${ticker}`);
    return data;
  } catch {
    return MOCK_FORECAST;
  }
}

export async function getFIIDII() {
  try {
    const { data } = await api.get("/fii-dii");
    return data;
  } catch {
    return MOCK_FII_DII;
  }
}

export async function getVIXData() {
  try {
    const { data } = await api.get("/vix");
    return data;
  } catch {
    return MOCK_VIX_DATA;
  }
}

export async function getSentimentTimeline(ticker: string) {
  try {
    const { data } = await api.get(`/sentiment/${ticker}`);
    return data;
  } catch {
    return MOCK_SENTIMENT_TIMELINE;
  }
}

export async function getOptionChain(symbol: string) {
  try {
    const { data } = await api.get(`/option-chain/${symbol}`);
    return data;
  } catch {
    return MOCK_OPTION_CHAIN;
  }
}

export async function getSectorData() {
  try {
    const { data } = await api.get("/sectors");
    return data;
  } catch {
    return MOCK_SECTOR_DATA;
  }
}

export async function getNews(ticker?: string) {
  try {
    const { data } = await api.get(`/news${ticker ? `?ticker=${ticker}` : ""}`);
    return data;
  } catch {
    return MOCK_NEWS;
  }
}

export async function getBacktest() {
  try {
    const { data } = await api.get("/backtest");
    return data;
  } catch {
    return MOCK_BACKTEST;
  }
}

export async function getModelPerformance() {
  try {
    const { data } = await api.get("/model-performance");
    return data;
  } catch {
    return MOCK_MODELS;
  }
}

export async function getAuditTrail(ticker: string) {
  try {
    const { data } = await api.get(`/audit/${ticker}`);
    return data;
  } catch {
    return MOCK_AUDIT;
  }
}

export async function getMarketStatus(): Promise<{
  isOpen: boolean;
  vix: number;
  fiiFlow: number;
  notifications: number;
}> {
  try {
    const { data } = await api.get("/market-status");
    return data;
  } catch {
    return { isOpen: true, vix: 14.2, fiiFlow: 3200, notifications: 3 };
  }
}
