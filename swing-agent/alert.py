import requests


def send_telegram(token: str, chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[alert] Telegram send failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[alert] Telegram send error: {e}")
