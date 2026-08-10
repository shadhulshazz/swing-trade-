import pandas as pd
import pandas_ta as ta


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 50:
        return df

    df = df.copy()
    df["SMA20"] = ta.sma(df["Close"], length=20)
    df["SMA50"] = ta.sma(df["Close"], length=50)
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["RSI"] = ta.rsi(df["Close"], length=14)

    macd = ta.macd(df["Close"])
    if macd is not None:
        df = df.join(macd)

    stoch = ta.stoch(df["High"], df["Low"], df["Close"])
    if stoch is not None:
        df = df.join(stoch)

    bb = ta.bbands(df["Close"], length=20)
    if bb is not None:
        df = df.join(bb)

    df["ATR"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    return df


def support_resistance(df: pd.DataFrame, lookback: int = 20):
    recent = df.tail(lookback)
    resistance = float(recent["High"].max())
    support = float(recent["Low"].min())
    return support, resistance


def fib_levels(support: float, resistance: float) -> dict:
    diff = resistance - support
    return {
        "38.2%": round(resistance - 0.382 * diff, 2),
        "50%": round(resistance - 0.5 * diff, 2),
        "61.8%": round(resistance - 0.618 * diff, 2),
    }
