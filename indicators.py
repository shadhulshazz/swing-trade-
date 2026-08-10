"""
indicators.py — Computes all technical indicators used by the scorer.

All functions accept a pd.DataFrame (OHLCV) and return a dict of named values
so scoring.py never needs to import ta or numpy directly.
"""

import numpy as np
import pandas as pd

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False


# ── helpers ────────────────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


# ── public API ──────────────────────────────────────────────────────────────

def compute(df: pd.DataFrame) -> dict:
    """
    Compute all indicators from OHLCV DataFrame.

    Returns
    -------
    dict with keys:
        close           – last closing price
        volume_ratio    – today's vol / 20-day avg vol
        rsi             – 14-day RSI (last value)
        macd_cross      – +1 bullish cross, -1 bearish cross, 0 no cross
        above_50ma      – bool: close > 50-day SMA
        above_200ma     – bool: close > 200-day SMA
        near_52w_high   – bool: close within 10 % of 52-week high
        bb_squeeze      – bool: Bollinger Band width < 20-period median width
        atr             – last ATR(14) value (absolute ₹)
        atr_pct         – ATR / close × 100 (relative %)
        price_change_1d – 1-day % change
        price_change_5d – 5-day % change
    """
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    n = len(close)

    result: dict = {}

    # --- Price ---
    result["close"] = float(close.iloc[-1])
    result["price_change_1d"] = float(
        (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100
    ) if n >= 2 else 0.0
    result["price_change_5d"] = float(
        (close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100
    ) if n >= 6 else 0.0

    # --- Volume ---
    vol_ma20 = volume.rolling(20).mean().iloc[-1]
    result["volume_ratio"] = float(volume.iloc[-1] / vol_ma20) if vol_ma20 > 0 else 0.0

    # --- Moving averages ---
    ma50 = _sma(close, 50)
    ma200 = _sma(close, 200)
    result["above_50ma"] = bool(close.iloc[-1] > ma50.iloc[-1]) if not np.isnan(ma50.iloc[-1]) else False
    result["above_200ma"] = bool(close.iloc[-1] > ma200.iloc[-1]) if not np.isnan(ma200.iloc[-1]) else False

    # --- RSI ---
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    result["rsi"] = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

    # --- MACD ---
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd_line = ema12 - ema26
    signal_line = _ema(macd_line, 9)
    # Cross detection: today crossed above/below
    prev_diff = macd_line.iloc[-2] - signal_line.iloc[-2]
    curr_diff = macd_line.iloc[-1] - signal_line.iloc[-1]
    if prev_diff < 0 and curr_diff >= 0:
        result["macd_cross"] = 1   # bullish
    elif prev_diff > 0 and curr_diff <= 0:
        result["macd_cross"] = -1  # bearish
    else:
        result["macd_cross"] = 0

    result["macd_above_signal"] = bool(curr_diff > 0)

    # --- 52-week high proximity ---
    high_52w = high.rolling(252, min_periods=50).max().iloc[-1]
    result["near_52w_high"] = bool(close.iloc[-1] >= 0.90 * high_52w)
    result["high_52w"] = float(high_52w)

    # --- Bollinger Band squeeze ---
    bb_ma = _sma(close, 20)
    bb_std = close.rolling(20).std()
    bb_width = (2 * bb_std) / bb_ma  # normalised width
    median_bw = bb_width.rolling(100, min_periods=20).median().iloc[-1]
    result["bb_squeeze"] = bool(bb_width.iloc[-1] < median_bw) if not np.isnan(median_bw) else False
    result["bb_upper"] = float(bb_ma.iloc[-1] + 2 * bb_std.iloc[-1])
    result["bb_lower"] = float(bb_ma.iloc[-1] - 2 * bb_std.iloc[-1])
    result["bb_mid"] = float(bb_ma.iloc[-1])

    # Close relative to Bollinger Bands (0 = at lower, 1 = at upper)
    bb_range = result["bb_upper"] - result["bb_lower"]
    result["bb_position"] = float(
        (close.iloc[-1] - result["bb_lower"]) / bb_range
    ) if bb_range > 0 else 0.5

    # --- ATR ---
    atr_series = _atr(df, 14)
    result["atr"] = float(atr_series.iloc[-1]) if not np.isnan(atr_series.iloc[-1]) else 0.0
    result["atr_pct"] = float(result["atr"] / result["close"] * 100) if result["close"] > 0 else 0.0

    # --- Support / Resistance (simple pivot) ---
    pivot = (high.iloc[-2] + low.iloc[-2] + close.iloc[-2]) / 3
    r1 = 2 * pivot - low.iloc[-2]
    s1 = 2 * pivot - high.iloc[-2]
    result["pivot"] = float(pivot)
    result["r1"] = float(r1)
    result["s1"] = float(s1)

    return result
