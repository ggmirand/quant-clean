import io
from typing import Optional, List, Dict
import pandas as pd
import requests

UA = "Mozilla/5.0 (compatible; QuantClean/1.1; +https://example.com)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "text/csv,application/json"})

def stooq_hist_daily(symbol: str, days: int = 365) -> Optional[pd.DataFrame]:
    """
    Daily OHLC from Stooq (free). US tickers require `.us` suffix.
    Returns last `days` rows sorted by date ascending.
    """
    try:
        sym = symbol.lower()
        if not sym.endswith(".us"):
            sym += ".us"
        url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
        r = S.get(url, timeout=6)
        r.raise_for_status()
        # Stooq returns plain CSV text
        df = pd.read_csv(io.StringIO(r.text))
        if df is None or df.empty or "Date" not in df or "Close" not in df:
            return None
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        return df.tail(max(60, days))
    except Exception:
        return None

def hist_close_series(symbol: str, days: int = 365) -> Optional[pd.Series]:
    """
    Returns pd.Series of Close (Date index) from Stooq.
    """
    df = stooq_hist_daily(symbol, days)
    if df is None or df.empty:
        return None
    return df.set_index("Date")["Close"].dropna()

def last_price(symbol: str) -> Optional[float]:
    s = hist_close_series(symbol, 10)
    if s is None or len(s) == 0:
        return None
    return float(s.iloc[-1])

def yahoo_day_gainers(count=24) -> List[Dict]:
    """
    Keep using Yahoo's predefined screener for 'Top gainers' because it’s simple JSON.
    If this call fails, the caller should handle and show a friendly note.
    """
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    r = S.get(url, params={"count": str(count), "scrIds": "day_gainers"}, timeout=6)
    r.raise_for_status()
    j = r.json()
    quotes = (((j or {}).get("finance") or {}).get("result") or [{}])[0].get("quotes") or []
    out = []
    for q in quotes:
        sym = q.get("symbol")
        if not sym or "." in sym:  # skip non-common tickers
            continue
        try:
            price = float(q.get("regularMarketPrice"))
            chg = float(q.get("regularMarketChangePercent"))
        except Exception:
            continue
        out.append({
            "ticker": sym,
            "price": price,
            "change_percentage": f"{chg:.2f}%",
            "name": q.get("shortName") or q.get("longName") or sym
        })
    return out
