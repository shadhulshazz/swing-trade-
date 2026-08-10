"""
risk.py - Position sizing and trade level calculation.
Uses ATR-based stop loss and a configurable risk-reward ratio.
"""

from __future__ import annotations
from dataclasses import dataclass
import math


DEFAULT_CAPITAL = 100_000
DEFAULT_RISK_PCT = 1.0
DEFAULT_ATR_STOP_MULT = 1.5
DEFAULT_MIN_RISK_REWARD = 2.0
DEFAULT_TARGET_MULT = 3.0


@dataclass
class TradeSetup:
    entry: float
    stop_loss: float
    target: float
    qty: int
    risk_amount: float
    risk_reward: float
    atr: float

    @property
    def is_valid(self) -> bool:
        return self.qty > 0 and self.risk_reward >= 1.0


def calculate(
    price: float,
    atr: float,
    capital: float = DEFAULT_CAPITAL,
    risk_pct: float = DEFAULT_RISK_PCT,
    atr_stop_mult: float = DEFAULT_ATR_STOP_MULT,
    target_mult: float = DEFAULT_TARGET_MULT,
    min_rr: float = DEFAULT_MIN_RISK_REWARD,
):
    """
    Compute ATR-based trade setup.
    Returns None if setup is not viable.
    """
    if atr <= 0 or price <= 0:
        return None

    stop_distance = atr_stop_mult * atr
    target_distance = target_mult * atr

    stop_loss = round(price - stop_distance, 2)
    target = round(price + target_distance, 2)

    if stop_loss <= 0:
        return None

    risk_reward = round(target_distance / stop_distance, 2)

    if risk_reward < min_rr:
        return None

    risk_amount = capital * (risk_pct / 100)
    qty = math.floor(risk_amount / stop_distance)

    if qty < 1:
        return None

    return TradeSetup(
        entry=round(price, 2),
        stop_loss=stop_loss,
        target=target,
        qty=qty,
        risk_amount=round(risk_amount, 2),
        risk_reward=risk_reward,
        atr=round(atr, 2),
    )
