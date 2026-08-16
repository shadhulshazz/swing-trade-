"""
bot_poll.py — Telegram polling bot.

Reads the latest Telegram messages, finds /scan commands sent in the last
10 minutes that haven't been replied to yet, runs the scan, and replies.

Run by GitHub Actions every 5 minutes (bot.yml).
"""

import os
import sys
import logging
import requests
import time

import data
import indicators
import scoring
import risk
import alert as alert_module
import sheet_log
from watchlist import WATCHLIST

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bot_poll")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
CAPITAL   = float(os.environ.get("TRADING_CAPITAL") or "40000")
RISK_PCT  = float(os.environ.get("RISK_PCT_PER_TRADE") or "1.0")

BASE_URL  = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── How far back to look for commands (seconds) ──────────────────────────────
LOOKBACK_SECS = 6 * 60   # 6 minutes — covers the 5-min cron gap with slack


def send_message(chat_id: str, text: str) -> None:
    try:
        requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as exc:
        logger.error("sendMessage failed: %s", exc)


def get_updates() -> list:
    """Fetch the last 50 updates from Telegram."""
    try:
        resp = requests.get(
            f"{BASE_URL}/getUpdates",
            params={"limit": 50, "timeout": 0},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("result", [])
    except Exception as exc:
        logger.error("getUpdates failed: %s", exc)
        return []


def acknowledge_updates(last_update_id: int) -> None:
    """Tell Telegram we've processed up to this update_id so it won't repeat."""
    try:
        requests.get(
            f"{BASE_URL}/getUpdates",
            params={"offset": last_update_id + 1, "limit": 1, "timeout": 0},
            timeout=10,
        )
    except Exception as exc:
        logger.error("acknowledge_updates failed: %s", exc)


def scan_single_ticker(ticker: str, chat_id: str) -> None:
    """Run a full scan on one ticker and send the result to Telegram."""
    logger.info("Scanning %s", ticker)
    send_message(chat_id, f"⏳ Scanning {ticker.replace('.NS','')}... please wait.")

    df = data.fetch(ticker)
    if df is None:
        send_message(chat_id, f"❌ Could not fetch data for {ticker.replace('.NS','')}. Check if the ticker is valid (NSE listed).")
        return

    price = data.latest_price(df)
    try:
        ind = indicators.compute(df)
    except Exception as exc:
        send_message(chat_id, f"❌ Indicator error for {ticker}: {exc}")
        return

    result = scoring.score_ticker(ind)
    setup = risk.calculate(
        price=price, atr=ind["atr"], capital=CAPITAL,
        risk_pct=RISK_PCT, min_rr=0.0,
    )
    if setup is None or not setup.is_valid:
        from risk import TradeSetup
        setup = TradeSetup(price, price - ind["atr"], price + ind["atr"], 1, 0, 1.0, ind["atr"])

    alert_module.send_alert(
        ticker=ticker, score=result.score, reasons=result.reasons,
        entry=setup.entry, stop_loss=setup.stop_loss, target=setup.target,
        qty=setup.qty, risk_reward=setup.risk_reward, atr=setup.atr,
        capital=CAPITAL,
    )
    try:
        sheet_log.log_trade(
            ticker=ticker, score=result.score, entry=setup.entry,
            stop_loss=setup.stop_loss, target=setup.target,
            qty=setup.qty, risk_reward=setup.risk_reward, reasons=result.reasons,
        )
    except Exception as exc:
        logger.warning("Sheet log failed: %s", exc)


def scan_full_watchlist(chat_id: str) -> None:
    """Run scan on all watchlist tickers."""
    send_message(chat_id, f"⏳ Scanning full watchlist ({len(WATCHLIST)} tickers)... results coming.")
    alerted = 0
    skipped = 0
    SCORE_THRESHOLD = int(os.environ.get("SCORE_THRESHOLD") or "5")
    MIN_RR = float(os.environ.get("MIN_RISK_REWARD") or "2.0")

    for ticker in WATCHLIST:
        df = data.fetch(ticker)
        if df is None:
            skipped += 1
            continue
        price = data.latest_price(df)
        try:
            ind = indicators.compute(df)
        except Exception:
            skipped += 1
            continue
        result = scoring.score_ticker(ind)
        if result.score < SCORE_THRESHOLD:
            continue
        setup = risk.calculate(price=price, atr=ind["atr"], capital=CAPITAL, risk_pct=RISK_PCT, min_rr=MIN_RR)
        if setup is None or not setup.is_valid:
            continue
        alert_module.send_alert(
            ticker=ticker, score=result.score, reasons=result.reasons,
            entry=setup.entry, stop_loss=setup.stop_loss, target=setup.target,
            qty=setup.qty, risk_reward=setup.risk_reward, atr=setup.atr,
            capital=CAPITAL,
        )
        try:
            sheet_log.log_trade(ticker=ticker, score=result.score, entry=setup.entry,
                stop_loss=setup.stop_loss, target=setup.target,
                qty=setup.qty, risk_reward=setup.risk_reward, reasons=result.reasons)
        except Exception:
            pass
        alerted += 1

    alert_module.send_summary(total=len(WATCHLIST), alerted=alerted, skipped=skipped)


def main():
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        sys.exit(1)

    now = int(time.time())
    cutoff = now - LOOKBACK_SECS

    updates = get_updates()
    if not updates:
        logger.info("No updates from Telegram.")
        return

    last_update_id = updates[-1]["update_id"]
    found_command = False

    # Process updates newest-first, pick only the most recent /scan command
    for update in reversed(updates):
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            continue
        msg_time = msg.get("date", 0)
        text = (msg.get("text") or "").strip()

        # Only process /scan commands sent within the lookback window
        if msg_time < cutoff:
            break
        if not text.lower().startswith("/scan"):
            continue

        ticker_raw = text[5:].strip().upper()
        chat_id = str(msg["chat"]["id"])

        logger.info("Found command: '%s' at ts=%d", text, msg_time)

        if ticker_raw:
            ticker = ticker_raw if ticker_raw.endswith(".NS") else ticker_raw + ".NS"
            scan_single_ticker(ticker, chat_id)
        else:
            scan_full_watchlist(chat_id)

        found_command = True
        break  # Only process the single most recent command

    if not found_command:
        logger.info("No new /scan commands in the last %d seconds.", LOOKBACK_SECS)

    # Always acknowledge — clears the retry queue
    acknowledge_updates(last_update_id)
    logger.info("Done. Acknowledged up to update_id=%d", last_update_id)


if __name__ == "__main__":
    main()
