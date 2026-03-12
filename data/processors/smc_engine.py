"""
SMC Engine — Pure Python Smart Money Concepts
Replaces: smartmoneyconcepts==0.0.26 (removed — numba==0.58.1 incompatible with numpy>=2.4)
Zero external deps beyond numpy + pandas.
Implements: BOS, CHoCH, Order Blocks, Fair Value Gaps, Swing HL
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd

@dataclass
class SwingPoint:
    index: int
    timestamp: pd.Timestamp
    price: float
    kind: str  # "HIGH" | "LOW"

@dataclass
class StructureEvent:
    index: int
    timestamp: pd.Timestamp
    price: float
    event_type: str   # "BOS" | "CHoCH"
    direction: str    # "BULLISH" | "BEARISH"
    broken_swing: float

@dataclass
class OrderBlock:
    start_index: int
    end_index: int
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    top: float
    bottom: float
    ob_type: str      # "BULLISH" | "BEARISH"
    mitigated: bool = False

@dataclass
class FairValueGap:
    index: int
    timestamp: pd.Timestamp
    top: float
    bottom: float
    fvg_type: str     # "BULLISH" | "BEARISH"
    filled: bool = False
    fill_pct: float = 0.0

@dataclass
class SMCResult:
    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows:  list[SwingPoint] = field(default_factory=list)
    structure_events: list[StructureEvent] = field(default_factory=list)
    order_blocks: list[OrderBlock] = field(default_factory=list)
    fair_value_gaps: list[FairValueGap] = field(default_factory=list)
    current_bias: str = "NEUTRAL"
    nearest_ob_above: Optional[OrderBlock] = None
    nearest_ob_below: Optional[OrderBlock] = None
    nearest_fvg_above: Optional[FairValueGap] = None
    nearest_fvg_below: Optional[FairValueGap] = None

class SMCEngine:
    def __init__(self, swing_length: int = 5):
        self.swing_length = swing_length

    def _find_swing_highs(self, high, timestamps):
        n, swings = self.swing_length, []
        for i in range(n, len(high) - n):
            window = high[i - n: i + n + 1]
            if high[i] == window.max() and list(window).count(high[i]) == 1:
                swings.append(SwingPoint(i, timestamps[i], float(high[i]), "HIGH"))
        return swings

    def _find_swing_lows(self, low, timestamps):
        n, swings = self.swing_length, []
        for i in range(n, len(low) - n):
            window = low[i - n: i + n + 1]
            if low[i] == window.min() and list(window).count(low[i]) == 1:
                swings.append(SwingPoint(i, timestamps[i], float(low[i]), "LOW"))
        return swings

    def _find_structure_events(self, close, high, low, timestamps, sh, sl):
        events, bias = [], "NEUTRAL"
        last_sh = last_sl = None
        shi = sli = 0
        for i in range(len(close)):
            while shi < len(sh) and sh[shi].index <= i:
                last_sh = sh[shi]; shi += 1
            while sli < len(sl) and sl[sli].index <= i:
                last_sl = sl[sli]; sli += 1
            c = float(close[i])
            if last_sh and c > last_sh.price:
                et = "CHoCH" if bias == "BEARISH" else "BOS"
                events.append(StructureEvent(i, timestamps[i], c, et, "BULLISH", last_sh.price))
                bias = "BULLISH"; last_sh = None
            elif last_sl and c < last_sl.price:
                et = "CHoCH" if bias == "BULLISH" else "BOS"
                events.append(StructureEvent(i, timestamps[i], c, et, "BEARISH", last_sl.price))
                bias = "BEARISH"; last_sl = None
        return events, bias

    def _find_order_blocks(self, open_, high, low, close, timestamps, events):
        obs = []
        for ev in events:
            if ev.index < 2: continue
            if ev.direction == "BULLISH":
                for j in range(ev.index - 1, max(ev.index - 10, 0), -1):
                    if close[j] < open_[j]:
                        obs.append(OrderBlock(j, ev.index, timestamps[j], timestamps[ev.index],
                                              float(high[j]), float(low[j]), "BULLISH")); break
            else:
                for j in range(ev.index - 1, max(ev.index - 10, 0), -1):
                    if close[j] > open_[j]:
                        obs.append(OrderBlock(j, ev.index, timestamps[j], timestamps[ev.index],
                                              float(high[j]), float(low[j]), "BEARISH")); break
        cp = float(close[-1])
        for ob in obs:
            ob.mitigated = (ob.ob_type == "BULLISH" and cp <= ob.top) or \
                           (ob.ob_type == "BEARISH" and cp >= ob.bottom)
        return obs

    def _find_fvg(self, high, low, timestamps):
        fvgs = []
        for i in range(1, len(high) - 1):
            if high[i - 1] < low[i + 1]:
                fvgs.append(FairValueGap(i, timestamps[i], float(low[i+1]), float(high[i-1]), "BULLISH"))
            elif low[i - 1] > high[i + 1]:
                fvgs.append(FairValueGap(i, timestamps[i], float(low[i-1]), float(high[i+1]), "BEARISH"))
        cl, ch = float(low[-1]), float(high[-1])
        for f in fvgs:
            span = max(f.top - f.bottom, 0.001)
            if f.fvg_type == "BULLISH" and cl <= f.top:
                f.fill_pct = min((min(ch, f.top) - f.bottom) / span, 1.0) * 100
                f.filled = f.fill_pct >= 100.0
            elif f.fvg_type == "BEARISH" and ch >= f.bottom:
                f.fill_pct = min((f.top - max(cl, f.bottom)) / span, 1.0) * 100
                f.filled = f.fill_pct >= 100.0
        return fvgs

    def analyze(self, df: pd.DataFrame) -> SMCResult:
        df = df.copy(); df.columns = df.columns.str.lower()
        for c in ("open","high","low","close"):
            if c not in df.columns: raise ValueError(f"Missing column: {c}")
        min_rows = 2 * self.swing_length + 3
        if len(df) < min_rows: raise ValueError(f"Need >={min_rows} rows, got {len(df)}")
        o = df["open"].values.astype(np.float64)
        h = df["high"].values.astype(np.float64)
        l = df["low"].values.astype(np.float64)
        c = df["close"].values.astype(np.float64)
        ts = df.index; cp = float(c[-1])
        sh = self._find_swing_highs(h, ts)
        sl = self._find_swing_lows(l, ts)
        events, bias = self._find_structure_events(c, h, l, ts, sh, sl)
        obs  = self._find_order_blocks(o, h, l, c, ts, events)
        fvgs = self._find_fvg(h, l, ts)
        a_bull_ob = [x for x in obs  if x.ob_type == "BULLISH" and not x.mitigated]
        a_bear_ob = [x for x in obs  if x.ob_type == "BEARISH" and not x.mitigated]
        a_bull_fv = [x for x in fvgs if x.fvg_type == "BULLISH" and not x.filled]
        a_bear_fv = [x for x in fvgs if x.fvg_type == "BEARISH" and not x.filled]
        obs_above = [x for x in a_bear_ob if x.bottom > cp]
        obs_below = [x for x in a_bull_ob if x.top < cp]
        fvg_above = [x for x in a_bear_fv if x.bottom > cp]
        fvg_below = [x for x in a_bull_fv if x.top < cp]
        return SMCResult(
            swing_highs=sh, swing_lows=sl, structure_events=events,
            order_blocks=obs, fair_value_gaps=fvgs, current_bias=bias,
            nearest_ob_above=min(obs_above, key=lambda x: x.bottom, default=None),
            nearest_ob_below=max(obs_below, key=lambda x: x.top,    default=None),
            nearest_fvg_above=min(fvg_above, key=lambda x: x.bottom, default=None),
            nearest_fvg_below=max(fvg_below, key=lambda x: x.top,    default=None),
        )

    def to_agent_summary(self, result: SMCResult, current_price: float) -> str:
        lines = [
            f"SMC Analysis (Pure Python — numpy {np.__version__}):",
            f"  Bias:        {result.current_bias}",
            f"  Swing Highs: {len(result.swing_highs)}",
            f"  Swing Lows:  {len(result.swing_lows)}",
            f"  BOS:  {sum(1 for e in result.structure_events if e.event_type=='BOS')}",
            f"  CHoCH:{sum(1 for e in result.structure_events if e.event_type=='CHoCH')}",
            f"  OBs:  {len(result.order_blocks)} ({sum(1 for o in result.order_blocks if not o.mitigated)} active)",
            f"  FVGs: {len(result.fair_value_gaps)} ({sum(1 for f in result.fair_value_gaps if not f.filled)} unfilled)",
        ]
        if result.nearest_ob_above:
            ob = result.nearest_ob_above
            lines.append(f"  Bearish OB (resistance): ₹{ob.bottom:.2f}–₹{ob.top:.2f} (+{((ob.bottom-current_price)/current_price)*100:.1f}%)")
        if result.nearest_ob_below:
            ob = result.nearest_ob_below
            lines.append(f"  Bullish OB (support):    ₹{ob.bottom:.2f}–₹{ob.top:.2f} (-{((current_price-ob.top)/current_price)*100:.1f}%)")
        return "\n".join(lines)

def analyze_smc(df: pd.DataFrame, swing_length: int = 5) -> SMCResult:
    return SMCEngine(swing_length=swing_length).analyze(df)
