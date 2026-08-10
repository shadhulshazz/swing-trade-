# Swing Trade Agent — Complete Setup From Zero

Stack: **GitHub Actions (free scheduler) → Python → Telegram (free alerts) → Google Sheets (free logging)**.
No servers, no n8n, no paid tier of anything. Total build time: ~30–45 min.

---

## 1. Create the Telegram bot (5 min)

1. Open Telegram, search **@BotFather**, start a chat.
2. Send `/newbot`, give it a name and a username (must end in `bot`, e.g. `myswingagent_bot`).
3. BotFather replies with a **token** like `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxx`. Save it — this is `TELEGRAM_BOT_TOKEN`.
4. Send your new bot any message (e.g. "hi") so it registers a chat with you.
5. In a browser, visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   Find `"chat":{"id": 123456789, ...}` in the response — that number is `TELEGRAM_CHAT_ID`.

---

## 2. Create the Google Sheet + service account (10 min)

1. Go to [Google Sheets](https://sheets.google.com), create a new sheet named exactly **`SwingTradeLog`**.
   In row 1 add headers: `Timestamp | Ticker | Score | Entry | StopLoss | Target | Qty | RiskReward | Reasons`.
2. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a new project (any name).
3. Enable **Google Sheets API** and **Google Drive API** for that project (search each in the top search bar → Enable).
4. Go to **APIs & Services → Credentials → Create Credentials → Service Account**. Name it anything, finish creation.
5. Open the new service account → **Keys** tab → **Add Key → Create new key → JSON**. This downloads a `.json` file — this whole file's contents become `GOOGLE_SHEETS_CREDS`.
6. Open that JSON file, copy the `client_email` field (looks like `xxx@xxx.iam.gserviceaccount.com`).
7. Go back to your `SwingTradeLog` Google Sheet → **Share** → paste that service account email → give it **Editor** access.

---

## 3. Create the GitHub repo (5 min)

1. Create a new repo on GitHub, e.g. `swing-agent` (private is fine — free either way).
2. Upload all the files from this project:
   - `scan.py`, `data.py`, `indicators.py`, `scoring.py`, `risk.py`, `alert.py`, `sheet_log.py`
   - `watchlist.py`
   - `requirements.txt`
   - `.github/workflows/scan.yml`
3. Edit `watchlist.py` to your actual stock list before pushing (NSE tickers, format `SYMBOL.NS`).

---

## 4. Add secrets and variables (5 min)

In the repo: **Settings → Secrets and variables → Actions**

**Secrets** (Secrets tab → New repository secret):
| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from Step 1 |
| `TELEGRAM_CHAT_ID` | from Step 1 |
| `GOOGLE_SHEETS_CREDS` | paste the ENTIRE contents of the JSON key file from Step 2 |

**Variables** (Variables tab → New repository variable — optional, has sane defaults if skipped):
| Name | Value |
|---|---|
| `TRADING_CAPITAL` | e.g. `100000` |
| `RISK_PCT_PER_TRADE` | e.g. `1.0` |

---

## 5. Test it manually (2 min)

1. Go to the **Actions** tab in your repo.
2. Click the `swing-scan` workflow → **Run workflow** button (this is the `workflow_dispatch` trigger) → Run.
3. Watch the run logs. You should see each ticker's score printed.
4. If any stock crosses the threshold, check your Telegram — you should get a message within seconds of the run finishing. Check the Google Sheet for a new row too.

If nothing fires, that's normal — it only alerts when a stock actually clears the score + risk/reward bar. Lower `SCORE_THRESHOLD` in `scan.py` temporarily to `3` if you want to force a test alert, then put it back.

---

## 6. Let it run

Once the manual test works, do nothing else — the cron in `scan.yml` fires automatically every 30 minutes during NSE market hours (9:00–15:45 IST, Mon–Fri), converted to UTC in the workflow. No server to keep on, no laptop needed.

---

## 7. Tuning knobs (once you have data)

- `SCORE_THRESHOLD` in `scan.py` — raise for fewer/higher-conviction alerts, lower for more.
- `MIN_RISK_REWARD` — the minimum acceptable reward:risk before it'll alert.
- Indicator weights in `scoring.py` — after a few weeks of logged outcomes in your Sheet, you'll see which conditions actually predicted winners; adjust the `score +=` weighting accordingly.
- Add earnings/news filtering later by checking a free calendar source before scoring a ticker that has earnings in the next 2 trading days (skip or flag it — earnings volatility breaks technical setups).

---

## Notes

- **yfinance is unofficial** — if Yahoo changes their API it can break; the `data.py` module fails gracefully (returns empty, script skips that ticker) rather than crashing the whole run.
- **This is a personal decision-support tool, not a broker connection** — it does not place trades. You still execute manually based on the alert.
- **GitHub Actions free tier**: unlimited minutes on public repos; 2,000 min/month on private repos, which this easily fits (each run is under a minute).
