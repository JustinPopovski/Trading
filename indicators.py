"""
indicators.py
-------------
Core trading indicator logic:
  - MACD (12/26/9)
  - 200-day Simple Moving Average
  - Support & Resistance levels (pivot-based)
  - Signal generation combining all three
"""

import numpy as np
import pandas as pd


# ── MACD ──────────────────────────────────────────────────────────────────────

def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Return DataFrame with MACD line, signal line, and histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }, index=close.index)


# ── 200-day MA ────────────────────────────────────────────────────────────────

def compute_ma200(close: pd.Series) -> pd.Series:
    """Return the 200-day simple moving average."""
    return close.rolling(window=200, min_periods=1).mean().rename("ma200")


# ── Support & Resistance ──────────────────────────────────────────────────────

def compute_support_resistance(
    df: pd.DataFrame,
    window: int = 20,
    num_levels: int = 5,
    tolerance: float = 0.015,
) -> dict:
    """
    Detect support and resistance levels using rolling pivot highs/lows.

    Returns
    -------
    dict with keys:
        'support'    – list of price levels (float)
        'resistance' – list of price levels (float)
    """
    highs = df["High"]
    lows  = df["Low"]

    pivot_highs = _find_pivots(highs, window, is_high=True)
    pivot_lows  = _find_pivots(lows,  window, is_high=False)

    resistance = _cluster_levels(pivot_highs, tolerance, num_levels)
    support    = _cluster_levels(pivot_lows,  tolerance, num_levels)

    return {"support": support, "resistance": resistance}


def _find_pivots(series: pd.Series, window: int, is_high: bool) -> list:
    pivots = []
    arr = series.values
    for i in range(window, len(arr) - window):
        segment = arr[i - window : i + window + 1]
        val = arr[i]
        if is_high and val == segment.max():
            pivots.append(float(val))
        elif not is_high and val == segment.min():
            pivots.append(float(val))
    return pivots


def _cluster_levels(levels: list, tolerance: float, num_levels: int) -> list:
    """Merge nearby levels into clusters and return the strongest ones."""
    if not levels:
        return []
    levels_sorted = sorted(levels)
    clusters = []
    current = [levels_sorted[0]]
    for price in levels_sorted[1:]:
        if (price - current[-1]) / current[-1] <= tolerance:
            current.append(price)
        else:
            clusters.append(current)
            current = [price]
    clusters.append(current)
    # Sort by cluster size (most-tested level first), then take top N
    clusters.sort(key=len, reverse=True)
    return [round(float(np.mean(c)), 4) for c in clusters[:num_levels]]


# ── Signal Generation ─────────────────────────────────────────────────────────

def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add signal columns to the OHLCV dataframe.

    Columns added
    -------------
    ma200        – 200-day SMA
    macd         – MACD line
    macd_signal  – MACD signal line
    macd_hist    – MACD histogram
    signal       – 'BUY', 'SELL', or 'HOLD'
    signal_score – integer strength (-3 … +3)
    """
    close = df["Close"]

    # 200 MA
    df["ma200"] = compute_ma200(close)

    # MACD
    macd_df = compute_macd(close)
    df["macd"]        = macd_df["macd"]
    df["macd_signal"] = macd_df["signal"]
    df["macd_hist"]   = macd_df["histogram"]

    # S/R levels (scalar — stored as metadata, not per-row)
    sr = compute_support_resistance(df)

    # Score (+1 per bullish condition, -1 per bearish)
    score = pd.Series(0, index=df.index)

    # 1. Price above/below 200 MA
    score += np.where(close > df["ma200"],  1, -1)

    # 2. MACD line above/below signal
    score += np.where(df["macd"] > df["macd_signal"],  1, -1)

    # 3. MACD histogram positive/negative
    score += np.where(df["macd_hist"] > 0,  1, -1)

    df["signal_score"] = score

    # Map score to label
    def _label(s):
        if s >= 2:
            return "BUY"
        elif s <= -2:
            return "SELL"
        return "HOLD"

    df["signal"] = df["signal_score"].apply(_label)
    df["sr_support"]    = str(sr["support"])
    df["sr_resistance"] = str(sr["resistance"])

    return df, sr
