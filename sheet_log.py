"""
sheet_log.py - Appends trade-alert rows to the SwingTradeLog Google Sheet.
Authentication uses a Service Account JSON key stored as GOOGLE_SHEETS_CREDS env var.

Sheet headers (Row 1): Timestamp | Ticker | Score | Entry | StopLoss | Target | Qty | RiskReward | Reasons
"""

from __future__ import annotations
import os
import json
import logging
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SHEET_NAME = "SwingTradeLog"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COLUMNS = [
    "Timestamp",
    "Ticker",
    "Score",
    "Entry",
    "StopLoss",
    "Target",
    "Qty",
    "RiskReward",
    "Reasons",
]


def _get_client():
    """Authenticate with Google Sheets using the service account JSON."""
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDS")
    if not creds_json:
        logger.warning("GOOGLE_SHEETS_CREDS not set - Google Sheets logging disabled.")
        return None
    try:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as exc:
        logger.error("Failed to authenticate with Google Sheets: %s", exc)
        return None


def log_trade(
    ticker: str,
    score: int,
    entry: float,
    stop_loss: float,
    target: float,
    qty: int,
    risk_reward: float,
    reasons: list,
) -> bool:
    """Append one row to the SwingTradeLog sheet. Returns True on success."""
    client = _get_client()
    if client is None:
        return False

    try:
        sheet = client.open(SHEET_NAME).sheet1
    except gspread.SpreadsheetNotFound:
        logger.error("Spreadsheet '%s' not found. Check the name and sharing settings.", SHEET_NAME)
        return False
    except Exception as exc:
        logger.error("Cannot open spreadsheet: %s", exc)
        return False

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reasons_str = " | ".join(r.strip() for r in reasons[:6])

    row = [
        timestamp,
        ticker.replace(".NS", ""),
        score,
        entry,
        stop_loss,
        target,
        qty,
        risk_reward,
        reasons_str,
    ]

    try:
        sheet.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Logged %s to Google Sheets", ticker)
        return True
    except Exception as exc:
        logger.error("Failed to append row to sheet: %s", exc)
        return False


def ensure_headers() -> None:
    """Check/create headers in row 1 if the sheet is empty."""
    client = _get_client()
    if client is None:
        return

    try:
        sheet = client.open(SHEET_NAME).sheet1
        existing = sheet.row_values(1)
        if not existing:
            sheet.append_row(COLUMNS)
            logger.info("Headers written to empty sheet.")
        elif existing != COLUMNS:
            logger.warning("Sheet headers do not match expected. Expected: %s  Got: %s", COLUMNS, existing)
    except Exception as exc:
        logger.warning("Could not verify sheet headers: %s", exc)
