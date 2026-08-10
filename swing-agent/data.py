import yfinance as yf
import pandas as pd


def get_data(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data for a ticker. Returns empty DataFrame on failure."""
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df.empty:
            return df
        # yfinance sometimes returns MultiIndex columns for single tickers
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"[data] Failed to fetch {ticker}: {e}")
        return pd.DataFrame()
