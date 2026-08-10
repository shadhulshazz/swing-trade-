"""
data.py - Fetches OHLCV data from Yahoo Finance via yfinance.
Fails gracefully: returns None if the ticker is bad or Yahoo is flaky.
"""

import yfinance as yf
import pandas as pd
import logging

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 120


def fetch(ticker: str):
    try:
        df = yf.download(
            ticker,
            period=f"{LOOKBACK_DAYS}d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            timeout=15,
        )
    except Exception as exc:
        logger.warning("yfinance download failed for %s: %s", ticker, exc)
        return None

    if df is None or df.empty:
        logger.warning("Empty data returned for %s", ticker)
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    required_cols = {"Open", "High", "Low", "Close", "Volume"}
    if not required_cols.issubset(df.columns):
        logger.warning("Missing columns for %s: %s", ticker, df.columns.tolist())
        return None

    df = df[list(required_cols)].copy()
    df.dropna(subset=["Close"], inplace=True)

    if len(df) < 60:
        logger.warning("Insufficient rows (%d) for %s", len(df), ticker)
        return None

    return df


def latest_price(df: pd.DataFrame) -> float:
    return float(df["Close"].iloc[-1])
