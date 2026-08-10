import pandas as pd


def score_stock(df: pd.DataFrame, market_trend_up: bool):
    """Rules-based scoring. Returns (score, max_possible_score, reasons list)."""
    if df.empty or len(df) < 50:
        return 0, 6, ["Insufficient data"]

    latest = df.iloc[-1]
    score = 0
    reasons = []

    required = ["SMA50", "EMA20", "RSI", "MACD_12_26_9", "MACDs_12_26_9", "Volume", "ATR"]
    if any(pd.isna(latest.get(col)) for col in required):
        return 0, 6, ["Missing indicator values (not enough history yet)"]

    # Trend
    if latest["Close"] > latest["SMA50"]:
        score += 1
        reasons.append("Price above SMA50 (uptrend)")
    if latest["EMA20"] > latest["SMA50"]:
        score += 1
        reasons.append("EMA20 above SMA50")

    # Momentum
    if 40 < latest["RSI"] < 65:
        score += 1
        reasons.append(f"RSI healthy ({latest['RSI']:.1f})")
    elif latest["RSI"] < 30:
        score += 1
        reasons.append(f"RSI oversold, bounce candidate ({latest['RSI']:.1f})")

    if latest["MACD_12_26_9"] > latest["MACDs_12_26_9"]:
        score += 1
        reasons.append("MACD bullish crossover")

    # Volume confirmation
    avg_vol = df["Volume"].tail(20).mean()
    if avg_vol > 0 and latest["Volume"] > avg_vol * 1.3:
        score += 1
        reasons.append("Volume surge confirms move")

    # Broad market filter
    if market_trend_up:
        score += 1
        reasons.append("Nifty in uptrend (tailwind)")
    else:
        score -= 1
        reasons.append("Nifty weak (headwind)")

    return score, 6, reasons
