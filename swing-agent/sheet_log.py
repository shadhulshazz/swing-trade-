import json
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_NAME = "SwingTradeLog"  # must match the Google Sheet's name exactly


def log_to_sheet(row: list):
    """Appends a row. Silently skips if credentials aren't configured (won't crash the scan)."""
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDS")
    if not creds_json:
        print("[sheet_log] GOOGLE_SHEETS_CREDS not set, skipping log.")
        return
    try:
        creds_dict = json.loads(creds_json)
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp] + row)
    except Exception as e:
        print(f"[sheet_log] Failed to log: {e}")
