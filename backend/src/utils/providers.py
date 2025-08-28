import io, time
from typing import Optional, List, Dict
import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:
    yf = None

UA = "Mozilla/5.0 (compatible; QuantClean/1.0)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "application/json"})

def stooq_hist_daily(symbol: str, days: int = 365) -> Optional[pd.DataFrame]:
    try:
        sym = symbol.lower()
        if not sym.endswith(".us"): sym += ".us"
        url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
        r = S.get(url, timeout=5); r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        if df.empty: return None
        df["Date"] = pd.to_datetime(df["Date"])
        return df.sort_values("Date").tail(max(60, days))
    except Exception:
        return None

def hist_close_series(symbol: str, days: int = 365) -> Optional[pd.Series]:
    if yf is not None:
        try:
            h = yf.Ticker(symbol).history(period=f"{max(60,days)}d", interval="1d")
            if h is not None and not h.empty and "Close" in h:
                return h["Close"].dropna()
        except Exception:
            pass
    df = stooq_hist_daily(symbol, days)
    if df is None or df.empty: return None
    return df.set_index("Date")["Close"].dropna()

def last_price(symbol: str) -> Optional[float]:
    if yf is not None:
        try:
            info = yf.Ticker(symbol).fast_info
            for k in ("last_price","regularMarketPrice","regular_market_price"):
                v = info.get(k)
                if v is not None: return float(v)
        except Exception: pass
    s = hist_close_series(symbol, 10)
    return float(s.iloc[-1]) if s is not None and len(s) else None

def yahoo_day_gainers(count=24) -> List[Dict]:
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    j = S.get(url, params={"count": str(count), "scrIds": "day_gainers"}, timeout=6)
    j.raise_for_status()
    j = j.json()
    quotes = (((j or {}).get("finance") or {}).get("result") or [{}])[0].get("quotes") or []
    rows=[]
    for q in quotes:
        sym = q.get("symbol")
        if not sym or "." in sym: continue
        try:
            price = float(q.get("regularMarketPrice"))
            chg   = float(q.get("regularMarketChangePercent"))
        except Exception:
            continue
        rows.append({"ticker":sym,"price":price,"change_percentage":f"{chg:.2f}%","name":q.get("shortName") or q.get("longName") or sym})
    return rows
