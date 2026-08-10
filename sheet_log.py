"""
sheet_log.py — Appends trade-alert rows to the SwingTradeLog Google Sheet.

Authentication uses a Service Account JSON key, which is stored as a
GitHub Actions secret (GOOGLE_SHEETS_CREDS) and passed in as an env var.

Sheet columns (Row 1 headers — must match exactly):
    Timestamp | Ticker | Score | Entry | StopLoss | Target | Qty | RiskReward | Reasons
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

# Column order — must match the header row in your Google Sheet
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


def _get_client() -> gspread.Client | None:
    """Authenticate with Google Sheets using the service account JSON."""
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDS")
    if not creds_json:
        logger.warning("GOOGLE_SHEETS_CREDS not set — Google Sheets logging disabled.")
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
    reasons: list[str],
) -> bool:
    """
    Append one row to the SwingTradeLog sheet.

    Returns True on success, False on any failure.
    """
    client = _get_client()
    if client is None:
        return False

    try:
        sheet = client.open(SHEET_NAME).sheet1
    except gspread.SpreadsheetNotFound:
        logger.error(
            "Spreadsheet '%s' not found. Check the name and sharing settings.", SHEET_NAME
        )
        return False
    except Exception as exc:
        logger.error("Cannot open spreadsheet: %s", exc)
        return False

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reasons_str = " | ".join(r.strip() for r in reasons[:6])  # keep it concise

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

    # Validate column count matches
    assert len(row) == len(COLUMNS), f"Row length {len(row)} != header length {len(COLUMNS)}"

    try:
        sheet.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Logged %s to Google Sheets", ticker)
        return True
    except Exception as exc:
        logger.error("Failed to append row to sheet: %s", exc)
        return False


def ensure_headers() -> None:
    """
    Check if row 1 of the sheet has the expected headers.
    If the sheet is empty, writes the headers automatically.
    """
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
            logger.warning(
                "Sheet headers don't match expected. Expected: %s  Got: %s",
                COLUMNS,
                existing,
            )
    except Exception as exc:
        logger.warning("Could not verify sheet headers: %s", exc)
