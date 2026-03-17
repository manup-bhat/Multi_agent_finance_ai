import axios, { AxiosError } from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 90000,
});

// ── Types matching api/schemas.py ─────────────────────────────────────────

export interface AnalyzeResponse {
  ticker: string;
  verdict: string;
  confidence: number;
  price_target_p10: number | null;
  price_target_p50: number | null;
  price_target_p90: number | null;
  regime: string;
  risk_level: string;
  quant_summary: string;
  macro_summary: string;
  fno_summary: string;
  emotion_summary: string;
  key_risks: string[];
  circuit_breaker_active: boolean;
  vix_current: number | null;
  fii_net_5d: number | null;
  fear_greed_index: number | null;
  social_bullish_pct: number | null;
  social_post_volume: number | null;
  euphoria_flag: boolean | null;
  sentiment_window: number | null;
  recommended_strategy: string | null;
  errors: string[];
  warnings: string[];
}

export interface PredictResponse {
  ticker: string;
  horizon: number;
  direction: string;
  direction_prob: number;
  class_probs: Record<string, number> | null;
  p10: number | null;
  p50: number | null;
  p90: number | null;
  confidence: number;
  regime: string;
  model_used: string;
}

export interface MacroResponse {
  vix: number | null;
  vix_regime: string;
  usdinr: number | null;
  brent_crude: number | null;
  fii_net_crore: number | null;
  fii_trend: string;
  sgx_nifty: number | null;
  global_cues: string;
  india_summary: string;
}

export interface FIIDIIResponse {
  date: string;
  fii_net_crore: number | null;
  dii_net_crore: number | null;
  fii_trend: string;
  fii_streak_days: number;
  consensus: string;
}

export interface BacktestResponse {
  strategy: string;
  ticker: string;
  sharpe_ratio: number;
  cagr_pct: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  n_trades: number;
  blueprint_gate_passed: boolean;
  dates: string[];
  equity_curve: number[];
  benchmark_curve: number[];
}

export interface SentimentResponse {
  ticker: string;
  composite_score: number;
  composite_label: string;
  fear_greed_index: number;
  fear_greed_label: string;
  institutional_score: number;
  india_specific_score: number;
  social_bullish_pct: number;
  social_post_volume: number;
  alpha_vantage_score: number;
  gdelt_macro_tone: number;
  earnings_tone: number;
  sentiment_window_days: number;
  high_volume_flag: boolean;
  euphoria_flag: boolean;
  warnings: string[];
  articles: Array<{
    source: string;
    headline: string;
    sentiment: number;
    label: string;
    date: string;
  }>;
}

export interface FnOResponse {
  symbol: string;
  expiry: string;
  pcr: number | null;
  pcr_signal: string;
  max_pain: number | null;
  iv_rank_pct: number | null;
  iv_percentile: number | null;
  atm_iv: number | null;
  skew: string | null;
  fii_futures_net: string;
  participant_oi: Record<string, { long: number | null; short: number | null; net: number | null }>;
  strategy_recommendation: string;
  greeks_atm: Record<string, number>;
  source: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  modules: Record<string, string>;
}

// ── Health ────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<HealthResponse | null> {
  try {
    const { data } = await api.get<HealthResponse>("/health", { timeout: 4000 });
    return data;
  } catch {
    return null;
  }
}

// ── Analysis ──────────────────────────────────────────────────────────────

export async function analyzeStock(
  ticker: string,
  horizon = 5,
  includeFno = true,
  includeSentiment = true
): Promise<AnalyzeResponse> {
  const { data } = await api.post<AnalyzeResponse>("/analyze", {
    ticker,
    horizon,
    include_fno: includeFno,
    include_sentiment: includeSentiment,
  });
  return data;
}

// ── Predictions ───────────────────────────────────────────────────────────

export async function getPrediction(
  ticker: string,
  horizon = 5,
  regime?: string
): Promise<PredictResponse> {
  const { data } = await api.post<PredictResponse>("/predict", { ticker, horizon, regime });
  return data;
}

// ── Sentiment ─────────────────────────────────────────────────────────────

export async function getSentiment(
  ticker: string,
  sources?: string[]
): Promise<SentimentResponse> {
  const { data } = await api.post<SentimentResponse>("/sentiment", { ticker, sources });
  return data;
}

// ── F&O ───────────────────────────────────────────────────────────────────

export async function getFnO(symbol: string, expiry?: string): Promise<FnOResponse> {
  const { data } = await api.post<FnOResponse>("/fno/analyze", { symbol, expiry });
  return data;
}

// ── Macro ─────────────────────────────────────────────────────────────────

export async function getMacro(): Promise<MacroResponse> {
  const { data } = await api.get<MacroResponse>("/macro/india-cues");
  return data;
}

// ── FII/DII ───────────────────────────────────────────────────────────────

export async function getFIIDII(): Promise<FIIDIIResponse> {
  const { data } = await api.get<FIIDIIResponse>("/fii-dii/latest");
  return data;
}

// ── Backtest ──────────────────────────────────────────────────────────────

export async function runBacktest(
  strategy: "mean_reversion" | "ema_momentum" | "vix_gated" | "fii_flow",
  ticker: string,
  years: number
): Promise<BacktestResponse> {
  const { data } = await api.post<BacktestResponse>("/backtest", { strategy, ticker, years });
  return data;
}

// ── Error helper ──────────────────────────────────────────────────────────

export function getApiErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail;
    if (detail) return String(detail);
    if (err.code === "ECONNABORTED") return "Request timed out — backend may still be warming up.";
    if (!err.response) return "Backend unreachable. Ensure the FastAPI server is running on port 8000.";
    return `API error ${err.response.status}: ${err.message}`;
  }
  return String(err);
}
