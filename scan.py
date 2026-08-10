"""
scan.py — Orchestrator. Called by GitHub Actions every 30 min during NSE hours.

Environment variables (set as GitHub Secrets / Variables):
    TELEGRAM_BOT_TOKEN    – Telegram bot token
    TELEGRAM_CHAT_ID      – Your Telegram chat ID
    GOOGLE_SHEETS_CREDS   – Full JSON contents of the service account key
    TRADING_CAPITAL       – Total capital in ₹ (default: 100000)
    RISK_PCT_PER_TRADE    – % to risk per trade   (default: 1.0)
    SCORE_THRESHOLD       – Min score to alert     (default: 5)
    MIN_RISK_REWARD       – Min acceptable R:R     (default: 2.0)
"""

import os
import sys
import logging
from datetime import datetime, timezone

import pytz

import data
import indicators
import scoring
import risk
import alert
import sheet_log
from watchlist import WATCHLIST

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scan")

# ── Config from env ────────────────────────────────────────────────────────
CAPITAL = float(os.environ.get("TRADING_CAPITAL") or "100000")
RISK_PCT        = float(os.environ.get("RISK_PCT_PER_TRADE") or "1.0")
SCORE_THRESHOLD = int(os.environ.get("SCORE_THRESHOLD") or "5")
MIN_RR          = float(os.environ.get("MIN_RISK_REWARD") or "2.0")

IST = pytz.timezone("Asia/Kolkata")


def is_market_open() -> bool:
    """
    Return True if the current IST time falls within NSE trading hours.
    The GitHub Actions cron is already constrained to these windows,
    but a double-check never hurts (e.g. manual dispatch outside hours).
    """
    now_ist = datetime.now(IST)
    # Skip weekends
    if now_ist.weekday() >= 5:
        return False
    market_open  = now_ist.replace(hour=9,  minute=0,  second=0, microsecond=0)
    market_close = now_ist.replace(hour=15, minute=45, second=0, microsecond=0)
    return market_open <= now_ist <= market_close


def run_scan() -> None:
    logger.info("=" * 60)
    logger.info("Swing Trade Scanner starting")
    logger.info("Capital: ₹%.0f  |  Risk: %.1f%%  |  Min score: %d  |  Min R:R: %.1f",
                CAPITAL, RISK_PCT, SCORE_THRESHOLD, MIN_RR)
    logger.info("Watchlist: %d tickers", len(WATCHLIST))
    logger.info("=" * 60)

    if not is_market_open():
        logger.info("Market is closed right now — scan aborted. "
                    "(Run with --force to override.)")
        if "--force" not in sys.argv:
            return

    # Ensure Google Sheet has headers before we start writing
    sheet_log.ensure_headers()

    total   = len(WATCHLIST)
    alerted = 0
    skipped = 0

    for ticker in WATCHLIST:
        logger.info("── %s", ticker)

        # 1. Fetch data
        df = data.fetch(ticker)
        if df is None:
            logger.warning("  Skipped — no data")
            skipped += 1
            continue

        price = data.latest_price(df)

        # 2. Compute indicators
        try:
            ind = indicators.compute(df)
        except Exception as exc:
            logger.error("  Indicator error: %s", exc)
            skipped += 1
            continue

        # 3. Score
        result = scoring.score_ticker(ind)
        logger.info("  Score: %d  |  Price: ₹%.2f  |  RSI: %.1f  |  Vol×: %.1f",
                    result.score, price, ind["rsi"], ind["volume_ratio"])

        if result.score < SCORE_THRESHOLD:
            logger.info("  Below threshold (%d < %d) — skip", result.score, SCORE_THRESHOLD)
            continue

        # 4. Risk calculation
        setup = risk.calculate(
            price=price,
            atr=ind["atr"],
            capital=CAPITAL,
            risk_pct=RISK_PCT,
            min_rr=MIN_RR,
        )

        if setup is None or not setup.is_valid:
            logger.info("  Trade setup invalid (ATR=%.2f, R:R failed) — skip", ind["atr"])
            continue

        logger.info(
            "  ALERT  Entry=₹%.2f  SL=₹%.2f  Target=₹%.2f  Qty=%d  R:R=%.1f",
            setup.entry, setup.stop_loss, setup.target, setup.qty, setup.risk_reward,
        )

        # 5. Send Telegram alert
        sent = alert.send_alert(
            ticker=ticker,
            score=result.score,
            reasons=result.reasons,
            entry=setup.entry,
            stop_loss=setup.stop_loss,
            target=setup.target,
            qty=setup.qty,
            risk_reward=setup.risk_reward,
            atr=setup.atr,
            capital=CAPITAL,
        )

        # 6. Log to Google Sheet
        sheet_log.log_trade(
            ticker=ticker,
            score=result.score,
            entry=setup.entry,
            stop_loss=setup.stop_loss,
            target=setup.target,
            qty=setup.qty,
            risk_reward=setup.risk_reward,
            reasons=result.reasons,
        )

        if sent:
            alerted += 1

    logger.info("=" * 60)
    logger.info("Scan complete — %d/%d alerted, %d skipped", alerted, total, skipped)

    # Send summary to Telegram
    alert.send_summary(total=total, alerted=alerted, skipped=skipped)


if __name__ == "__main__":
    run_scan()
