"""
scoring.py - Converts raw indicator values into a conviction score.
"""

from __future__ import annotations
from dataclasses import dataclass, field


DEFAULT_SCORE_THRESHOLD = 5


@dataclass
class ScoreResult:
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def add(self, points: int, reason: str) -> None:
        self.score += points
        self.reasons.append(f"[+{points}] {reason}")

    def sub(self, points: int, reason: str) -> None:
        self.score -= points
        self.reasons.append(f"[-{points}] {reason}")


def score_ticker(ind: dict) -> ScoreResult:
    """Score a ticker based on its indicator dict."""
    r = ScoreResult()

    # Trend
    if ind["above_50ma"]:
        r.add(1, "Price above 50-day SMA (uptrend)")
    else:
        r.sub(1, "Price below 50-day SMA (weak trend)")

    if ind["above_200ma"]:
        r.add(1, "Price above 200-day SMA (long-term bull)")
    else:
        r.sub(1, "Price below 200-day SMA (bear territory)")

    if ind["above_50ma"] and ind["above_200ma"]:
        r.add(1, "Golden-zone: price above both 50 & 200 MA")

    # Momentum RSI
    rsi = ind["rsi"]
    if 50 <= rsi <= 70:
        r.add(2, f"RSI {rsi:.1f} in bullish-momentum zone (50-70)")
    elif 40 <= rsi < 50:
        r.add(1, f"RSI {rsi:.1f} recovering - watch for breakout above 50")
    elif rsi > 70:
        r.sub(1, f"RSI {rsi:.1f} overbought - chasing risk")
    elif rsi < 35:
        r.sub(2, f"RSI {rsi:.1f} oversold - avoid longs until stabilises")

    # MACD
    if ind["macd_cross"] == 1:
        r.add(2, "Fresh MACD bullish crossover (today)")
    elif ind["macd_above_signal"] and ind["macd_cross"] == 0:
        r.add(1, "MACD above signal line (continued bull momentum)")
    elif ind["macd_cross"] == -1:
        r.sub(2, "Fresh MACD bearish crossover - skip")
    elif not ind["macd_above_signal"]:
        r.sub(1, "MACD below signal line (bearish)")

    # Volume
    vr = ind["volume_ratio"]
    if vr >= 2.0:
        r.add(2, f"Volume surge {vr:.1f}x average - strong institutional interest")
    elif vr >= 1.5:
        r.add(1, f"Above-average volume {vr:.1f}x - confirming move")
    elif vr < 0.7:
        r.sub(1, f"Low volume {vr:.1f}x - lack of conviction")

    # 52-week high
    if ind["near_52w_high"]:
        r.add(1, "Within 10% of 52-week high - breakout candidate")

    # Bollinger Band squeeze
    if ind["bb_squeeze"]:
        r.add(1, "Bollinger Band squeeze - volatility contraction (coiled)")

    if ind["bb_position"] < 0.25:
        r.add(1, f"Price near lower Bollinger Band ({ind['bb_position']:.2f}) - oversold within trend")

    # Price momentum
    if 1.0 <= ind["price_change_1d"] <= 4.0:
        r.add(1, f"Healthy 1-day gain +{ind['price_change_1d']:.1f}% (not extended)")
    elif ind["price_change_1d"] > 5.0:
        r.sub(1, f"Gap-up +{ind['price_change_1d']:.1f}% - chasing risk after big move")
    elif ind["price_change_1d"] < -3.0:
        r.sub(1, f"Sharp 1-day drop {ind['price_change_1d']:.1f}% - avoid")

    if ind["price_change_5d"] >= 5.0:
        r.add(1, f"Strong 5-day momentum +{ind['price_change_5d']:.1f}%")
    elif ind["price_change_5d"] < -5.0:
        r.sub(1, f"Weak 5-day performance {ind['price_change_5d']:.1f}%")

    return r
