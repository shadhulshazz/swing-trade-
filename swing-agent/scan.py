import os
from watchlist import TICKERS, INDEX_TICKER
from data import get_data
from indicators import add_indicators, support_resistance, fib_levels
from scoring import score_stock
from risk import risk_plan
from alert import send_telegram
from sheet_log import log_to_sheet

# --- Config ---
SCORE_THRESHOLD = 5       # out of 6 — raise/lower to tune signal frequency
MIN_RISK_REWARD = 2.0
CAPITAL = float(os.environ.get("TRADING_CAPITAL", "100000"))
RISK_PCT = float(os.environ.get("RISK_PCT_PER_TRADE", "1.0"))


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")

    # Broad market trend filter
    market_df = add_indicators(get_data(INDEX_TICKER))
    if market_df.empty or "SMA50" not in market_df.columns:
        print("[scan] Could not determine market trend, defaulting to neutral/up")
        market_up = True
    else:
        latest_idx = market_df.iloc[-1]
        market_up = bool(latest_idx["Close"] > latest_idx["SMA50"])

    alerts_sent = 0

    for ticker in TICKERS:
        raw = get_data(ticker)
        if raw.empty:
            continue

        df = add_indicators(raw)
        score, max_score, reasons = score_stock(df, market_up)

        print(f"{ticker}: score {score}/{max_score} — {reasons}")

        if score < SCORE_THRESHOLD:
            continue

        plan = risk_plan(df.iloc[-1], capital=CAPITAL, risk_pct=RISK_PCT)
        if plan["risk_reward"] < MIN_RISK_REWARD or plan["position_size"] <= 0:
            continue

        support, resistance = support_resistance(df)
        fibs = fib_levels(support, resistance)

        msg = (
            f"*{ticker}* — Swing Buy Candidate ({score}/{max_score})\n"
            f"Entry: {plan['entry']}  SL: {plan['stop_loss']}  Target: {plan['target']}\n"
            f"R:R {plan['risk_reward']}  Qty: {plan['position_size']} "
            f"(capital ₹{CAPITAL:,.0f}, risk {RISK_PCT}%)\n"
            f"Support/Resistance: {support:.2f} / {resistance:.2f}\n"
            f"Fib 61.8%: {fibs['61.8%']}\n"
            f"Why: {', '.join(reasons)}"
        )

        send_telegram(token, chat_id, msg)
        log_to_sheet([
            ticker, score, plan["entry"], plan["stop_loss"], plan["target"],
            plan["position_size"], plan["risk_reward"], "; ".join(reasons),
        ])
        alerts_sent += 1

    print(f"[scan] Done. {alerts_sent} alert(s) sent.")


if __name__ == "__main__":
    main()
