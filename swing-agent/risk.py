def risk_plan(latest, capital: float, risk_pct: float = 1.0):
    """ATR-based entry/stop/target and position sizing."""
    entry = float(latest["Close"])
    atr = float(latest["ATR"])

    stop_loss = entry - 1.5 * atr
    target = entry + 3 * atr  # ~1:2 reward:risk by construction

    risk_per_share = entry - stop_loss
    risk_amount = capital * (risk_pct / 100)
    position_size = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
    rr_ratio = (target - entry) / risk_per_share if risk_per_share > 0 else 0

    return {
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "target": round(target, 2),
        "position_size": position_size,
        "risk_reward": round(rr_ratio, 2),
    }
