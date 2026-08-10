"""
alert.py - Sends formatted trade alerts to Telegram.
Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment variables.
"""

from __future__ import annotations
import os
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _env():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    return token, chat_id


def _stars(score: int) -> str:
    filled = min(max(score, 0), 10)
    return "*" * filled + "." * (10 - filled)


def send_alert(
    ticker: str,
    score: int,
    reasons: list,
    entry: float,
    stop_loss: float,
    target: float,
    qty: int,
    risk_reward: float,
    atr: float,
    capital: float,
) -> bool:
    """Build and send a Telegram alert message. Returns True if sent."""
    token, chat_id = _env()
    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set - alert skipped.")
        return False

    symbol = ticker.replace(".NS", "")
    rr_emoji = "STRONG" if risk_reward >= 3.0 else "GOOD" if risk_reward >= 2.0 else "OK"
    reasons_text = "\n".join(f"  {r}" for r in reasons[:8])

    message = (
        f"SWING TRADE ALERT\n"
        f"====================\n"
        f"Stock: {symbol} (NSE)\n"
        f"Score: {score}/10  [{_stars(score)}]\n\n"
        f"Trade Levels:\n"
        f"  Entry     : Rs {entry:,.2f}\n"
        f"  Stop Loss : Rs {stop_loss:,.2f}\n"
        f"  Target    : Rs {target:,.2f}\n"
        f"  Qty       : {qty} shares\n"
        f"  ATR(14)   : Rs {atr:,.2f}\n\n"
        f"Risk:Reward = 1:{risk_reward:.1f}  [{rr_emoji}]\n"
        f"  Capital at risk: Rs {capital * 0.01:,.0f} (1% rule)\n\n"
        f"Why this stock?\n"
        f"{reasons_text}\n\n"
        f"NOTE: Decision-support only - not a trade order.\n"
        f"===================="
    )

    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram alert sent for %s", ticker)
        return True
    except requests.RequestException as exc:
        logger.error("Failed to send Telegram alert for %s: %s", ticker, exc)
        return False


def send_summary(total: int, alerted: int, skipped: int) -> None:
    """Send a brief end-of-scan summary message."""
    token, chat_id = _env()
    if not token or not chat_id:
        return

    message = (
        f"Scan Complete\n"
        f"  Tickers scanned : {total}\n"
        f"  Alerts fired    : {alerted}\n"
        f"  Skipped (data)  : {skipped}\n"
        f"  No-signal       : {total - alerted - skipped}"
    )

    url = TELEGRAM_API.format(token=token)
    try:
        requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning("Summary message failed: %s", exc)
