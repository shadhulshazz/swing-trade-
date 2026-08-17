"""
scanner_today.py - Handles the /scan today (NIFTY 500) massive scan.
Fetches NIFTY 500, bulk downloads data, screens using indicators/scoring,
and alerts the top 3-5 setups to Telegram.
"""

import os
import logging
import time
import pandas as pd
import yfinance as yf

import indicators
import scoring
import risk
import alert
import sheet_log

logger = logging.getLogger("scanner_today")

CAPITAL = float(os.environ.get("TRADING_CAPITAL") or "40000")
RISK_PCT = float(os.environ.get("RISK_PCT_PER_TRADE") or "1.0")

# Pre-defined fallback in case niftyindices.com blocks the GitHub Action
FALLBACK_NIFTY = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "ITC.NS",
    "SBIN.NS", "BHARTIARTL.NS", "LT.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", 
    "AXISBANK.NS", "KOTAKBANK.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS",
    "TATAMOTORS.NS", "NTPC.NS", "ULTRACEMCO.NS", "POWERGRID.NS", "ONGC.NS",
    "BAJAJFINSV.NS", "NESTLEIND.NS", "JSWSTEEL.NS", "M&M.NS", "HCLTECH.NS",
    "ADANIENT.NS", "ADANIPORTS.NS", "TATASTEEL.NS", "HINDALCO.NS", "GRASIM.NS",
    "WIPRO.NS", "TECHM.NS", "SBILIFE.NS", "HDFCLIFE.NS", "INDUSINDBK.NS",
    "DIVISLAB.NS", "DRREDDY.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "HEROMOTOCO.NS",
    "APOLLOHOSP.NS", "CIPLA.NS", "TATACONSUM.NS", "COALINDIA.NS", "BRITANNIA.NS",
    "UPL.NS", "BPCL.NS", "HAL.NS", "BEL.NS", "BHEL.NS", "SUZLON.NS",
    "RVNL.NS", "IRFC.NS", "ZOMATO.NS", "PAYTM.NS", "JIOFIN.NS"
]

def get_nifty500() -> list:
    """Fetch NIFTY 500 tickers directly from NSE indices CSV."""
    url = 'https://niftyindices.com/IndexConstituent/ind_nifty500list.csv'
    try:
        df = pd.read_csv(url, storage_options={'User-Agent': 'Mozilla/5.0'})
        tickers = [sym + ".NS" for sym in df['Symbol'].tolist()]
        logger.info("Successfully fetched %d tickers from NIFTY 500 index.", len(tickers))
        return tickers
    except Exception as exc:
        logger.warning("Failed to fetch NIFTY 500 list: %s. Using fallback list.", exc)
        return FALLBACK_NIFTY

def format_telegram_message(ticker: str, score: int, setup: risk.TradeSetup, ind: dict, company_name: str) -> str:
    rr_emoji = "🔥 STRONG" if setup.risk_reward >= 3.0 else "⭐ GOOD" if setup.risk_reward >= 2.0 else "✅ OK"
    
    rsi = ind['rsi']
    vol_ratio = ind['volume_ratio']
    trend_desc = "Above 50 & 200 EMA" if ind['above_50ma'] and ind['above_200ma'] else "Mixed Trend"
    macd_desc = "Bullish Cross" if ind['macd_cross'] == 1 else "Positive" if ind['macd_above_signal'] else "Negative"

    return (
        f"🏆 <b>TOP SWING TRADE TODAY</b>\n"
        f"<b>{ticker.replace('.NS', '')}</b> {f'({company_name})' if company_name else ''}\n"
        f"Confidence Score: <b>{score}/10</b>\n\n"
        f"📈 <b>Trade Setup:</b>\n"
        f"• Entry     : Rs {setup.entry:,.2f}\n"
        f"• Target    : Rs {setup.target:,.2f}  [R:R 1:{setup.risk_reward:.1f}] {rr_emoji}\n"
        f"• Stop Loss : Rs {setup.stop_loss:,.2f}  (ATR: {setup.atr:.1f})\n"
        f"• Quantity  : {setup.qty} shares\n"
        f"• Capital Risk: Rs {setup.risk_amount:,.0f} ({RISK_PCT}%)\n\n"
        f"📊 <b>Why? (Technicals):</b>\n"
        f"• Trend   : {trend_desc}\n"
        f"• Momentum: RSI {rsi:.1f} | MACD {macd_desc}\n"
        f"• Volume  : {vol_ratio:.1f}x Daily Average"
    )

def run_today_scan():
    logger.info("Starting Massive NIFTY 500 Scanner (/scan today)")
    tickers = get_nifty500()
    
    # 1. Bulk Download (Super Fast)
    logger.info("Bulk downloading daily data for %d tickers...", len(tickers))
    start_time = time.time()
    
    # Using threads=True speeds up yfinance downloads considerably
    raw_data = yf.download(tickers, period="200d", group_by="ticker", threads=True, progress=False)
    logger.info("Download completed in %.2fs", time.time() - start_time)

    candidates = []
    
    # 2. Vectorized Processing & Scoring
    for ticker in tickers:
        try:
            # yfinance returns different structures if 1 vs multiple tickers
            if len(tickers) == 1:
                df = raw_data.dropna()
            else:
                if ticker not in raw_data.columns.levels[0]:
                    continue
                df = raw_data[ticker].dropna()
            
            if len(df) < 50:
                continue
                
            # Rename columns to remove MultiIndex artifacts if any
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                
            price = df["Close"].iloc[-1]
            if price < 10:  # Skip absolute pennies
                continue
                
            ind = indicators.compute(df)
            result = scoring.score_ticker(ind)
            
            # Stage 1 Filter: We only want stocks that score very highly (>= 7)
            # and have good volume (at least 1.2x average)
            if result.score >= 7 and ind["volume_ratio"] >= 1.2:
                setup = risk.calculate(
                    price=price,
                    atr=ind["atr"],
                    capital=CAPITAL,
                    risk_pct=RISK_PCT,
                    min_rr=2.0,  # Strict R:R for top picks
                )
                
                if setup and setup.is_valid:
                    candidates.append({
                        "ticker": ticker,
                        "score": result.score,
                        "setup": setup,
                        "ind": ind,
                        "reasons": result.reasons
                    })
        except Exception as e:
            # Skip on any error (delisted, missing data, computation error)
            continue

    logger.info("Stage 1 & 2 complete. Found %d strong candidates.", len(candidates))
    
    if not candidates:
        logger.info("No stocks passed the strict /scan today criteria.")
        alert._env = alert._env  # dummy to ensure we can use it
        token, chat_id = alert._env()
        if token and chat_id:
            import requests
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": "✅ Scan complete.\n\nNo exceptional swing setups found today in the NIFTY 500 based on strict technical criteria. Cash is a position!"}
            )
        return

    # Sort candidates by Score (desc), then Volume Ratio (desc)
    candidates.sort(key=lambda x: (x["score"], x["ind"]["volume_ratio"]), reverse=True)
    
    # Take top 3
    top_candidates = candidates[:3]
    logger.info("Top %d candidates selected.", len(top_candidates))
    
    # 3. Fetch Fundamentals (Stage 4) & Alert
    token, chat_id = alert._env()
    if not token or not chat_id:
        logger.error("No Telegram creds found.")
        return

    import requests

    for pick in top_candidates:
        ticker = pick["ticker"]
        logger.info("Fetching info for %s...", ticker)
        company_name = ""
        try:
            # Fetching fundamentals for just 3 stocks is fast
            info = yf.Ticker(ticker).info
            company_name = info.get("shortName") or info.get("longName", "")
        except:
            pass
            
        msg_text = format_telegram_message(
            ticker=ticker,
            score=pick["score"],
            setup=pick["setup"],
            ind=pick["ind"],
            company_name=company_name
        )
        
        # Send Alert
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg_text, "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=10,
            )
            # Log to Google Sheet
            sheet_log.ensure_headers()
            sheet_log.log_trade(
                ticker=ticker,
                score=pick["score"],
                entry=pick["setup"].entry,
                stop_loss=pick["setup"].stop_loss,
                target=pick["setup"].target,
                qty=pick["setup"].qty,
                risk_reward=pick["setup"].risk_reward,
                reasons=pick["reasons"],
            )
        except Exception as e:
            logger.error("Failed to send/log top pick %s: %s", ticker, e)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    run_today_scan()
