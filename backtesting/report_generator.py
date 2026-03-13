"""
Report Generator — BacktestResult → Structured Output
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Formats BacktestResult into:
  - dict for API consumption
  - human-readable text for agent (Orchestrator) consumption
"""
from __future__ import annotations

from backtesting.engine import BacktestResult

# Blueprint thresholds for pass/fail assessment
SHARPE_PASS_THRESHOLD = 0.8   # Blueprint gate: Sharpe > 0.8
MAX_DD_WARN_THRESHOLD = -0.15  # Warn if drawdown > 15%


def build_backtest_report(result: BacktestResult) -> dict:
    """
    Convert BacktestResult to a structured dict for API/agent consumption.

    Returns:
        dict with all performance metrics + metadata
    """
    m = result.metrics
    passed_sharpe = m.sharpe_ratio >= SHARPE_PASS_THRESHOLD
    positive_alpha = m.alpha > 0.0

    return {
        "strategy_name":        result.strategy_name,
        "ticker":               result.ticker,
        "period":               f"{result.start_date} → {result.end_date}",
        "n_days":               result.n_days,
        "n_trades":             result.n_trades,
        "initial_capital_inr":  result.initial_capital,
        "final_equity_inr":     round(result.final_equity, 2),
        "total_return_pct":     round(m.total_return_pct * 100, 2),
        "cagr_pct":             round(m.cagr_pct * 100, 2),
        "sharpe_ratio":         m.sharpe_ratio,
        "sortino_ratio":        m.sortino_ratio,
        "calmar_ratio":         m.calmar_ratio,
        "max_drawdown_pct":     round(m.max_drawdown_pct * 100, 2),
        "win_rate_pct":         round(m.win_rate * 100, 2),
        "alpha_annual":         m.alpha,
        "beta":                 m.beta,
        "commission_paid_inr":  result.commission_paid,
        # Blueprint gate results
        "blueprint_gate": {
            "sharpe_above_0_8":   passed_sharpe,
            "positive_alpha":     positive_alpha,
            "passed":             passed_sharpe and positive_alpha,
        },
        "notes":                result.notes + m.notes,
    }


def format_backtest_summary(result: BacktestResult) -> str:
    """
    Human-readable summary for Orchestrator / logging.
    Keeps numbers pre-formatted so LLMs don't need to compute.
    """
    m   = result.metrics
    rpt = build_backtest_report(result)
    gate_status = "✅ PASSED" if rpt["blueprint_gate"]["passed"] else "❌ FAILED"

    return (
        f"══════════════════════════════════════════\n"
        f"BACKTEST REPORT — {result.strategy_name}\n"
        f"Ticker: {result.ticker} | Period: {rpt['period']}\n"
        f"══════════════════════════════════════════\n"
        f"Blueprint Gate:    {gate_status}\n"
        f"  Sharpe ≥ 0.8:    {'✅' if rpt['blueprint_gate']['sharpe_above_0_8'] else '❌'} ({m.sharpe_ratio:.3f})\n"
        f"  Positive Alpha:  {'✅' if rpt['blueprint_gate']['positive_alpha'] else '❌'} ({m.alpha:.4f} pa)\n"
        f"\nPerformance:\n"
        f"  CAGR:          {m.cagr_pct*100:.1f}%\n"
        f"  Total Return:  {m.total_return_pct*100:.1f}%\n"
        f"  Sharpe:        {m.sharpe_ratio:.3f}\n"
        f"  Sortino:       {m.sortino_ratio:.3f}\n"
        f"  Calmar:        {m.calmar_ratio:.3f}\n"
        f"  Max Drawdown:  {m.max_drawdown_pct*100:.1f}%\n"
        f"  Win Rate:      {m.win_rate*100:.1f}%\n"
        f"  Beta:          {m.beta:.3f}\n"
        f"\nTrade Details:\n"
        f"  Trades:        {result.n_trades}\n"
        f"  Days:          {result.n_days}\n"
        f"  Commission:    ₹{result.commission_paid:,.0f}\n"
        f"  Final Equity:  ₹{result.final_equity:,.0f}\n"
        + (f"\nNotes:\n" + "\n".join(f"  • {n}" for n in rpt["notes"])
           if rpt["notes"] else "")
        + f"\n══════════════════════════════════════════"
    )
