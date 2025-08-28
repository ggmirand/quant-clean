from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional, Tuple
import time, math, random
import numpy as np
import pandas as pd

from ..utils import providers as P
from ..utils.math import rsi14, ema

# Optional Yahoo fallback
try:
    import yfinance as yf
    HAVE_YF = True
except Exception:
    HAVE_YF = False

router = APIRouter()

# ---------------- cache (5 minutes) ----------------
_TTL = 300.0
_prices: Dict[Tuple[str,int], Tuple[float,float]] = {}
_hist: Dict[Tuple[str,int], Tuple[pd.Series,float]] = {}

def _now(): return time.time()

def _get_cached_price(sym:str, days:int)->Optional[float]:
    k=(sym.upper(),days); v=_prices.get(k)
    if not v: return None
    px,ts=v
    return px if (_now()-ts)<_TTL else None

def _put_cached_price(sym:str,days:int,px:float):
    _prices[(sym.upper(),days)] = (float(px), _now())

def _get_cached_hist(sym:str, days:int)->Optional[pd.Series]:
    k=(sym.upper(),days); v=_hist.get(k)
    if not v: return None
    s,ts=v
    return s if (_now()-ts)<_TTL else None

def _put_cached_hist(sym:str, days:int, s:pd.Series):
    _hist[(sym.upper(),days)] = (s.copy(), _now())

# -------------- providers with fallback -----------
def _hist_closes(sym:str, days:int)->Optional[pd.Series]:
    s = _get_cached_hist(sym, days)
    if s is not None and len(s): return s

    # 1) Stooq via providers
    try:
        s = P.hist_close_series(sym, days)
        if s is not None and len(s):
            _put_cached_hist(sym, days, s)
            _put_cached_price(sym, days, float(s.iloc[-1]))
            return s
    except Exception:
        pass

    # 2) Yahoo fallback
    if HAVE_YF:
        try:
            t = yf.Ticker(sym)
            period = "max" if days>365 else f"{days}d"
            df = t.history(period=period, auto_adjust=False)
            if not df.empty and "Close" in df.columns:
                s = df["Close"].dropna().sort_index().tail(days)
                if len(s):
                    _put_cached_hist(sym, days, s)
                    _put_cached_price(sym, days, float(s.iloc[-1]))
                    return s
        except Exception:
            pass

    return None

def _last_price(sym:str, days:int=30)->Optional[float]:
    px = _get_cached_price(sym, days)
    if px is not None: return px
    s = _hist_closes(sym, max(days,10))
    if s is not None and len(s):
        px = float(s.iloc[-1]); _put_cached_price(sym, days, px); return px
    return None

def _pct_change(sym:str, days:int=5)->Optional[float]:
    s=_hist_closes(sym, max(30,days+1))
    if s is None or len(s)<(days+1): return None
    a=float(s.iloc[-1]); b=float(s.iloc[-1-days])
    if b<=0: return None
    return a/b-1.0

# ------------ Sector ETF proxies -------------------
SECTOR_ETFS = {
    "Energy": "XLE", "Consumer Disc.": "XLY", "Materials": "XLB",
    "Technology": "XLK", "Financials": "XLF", "Industrials": "XLI",
    "Comm. Services": "XLC", "Real Estate": "XLRE", "Healthcare": "XLV",
    "Utilities": "XLU", "Consumer Staples": "XLP",
}

# A small, representative per-sector universe (kept modest to reduce rate limits)
SECTOR_UNIVERSE = {
    "XLK": ["AAPL","MSFT","NVDA","AVGO","META","ADBE","ORCL"],
    "XLY": ["AMZN","HD","TSLA","MCD","NKE","SBUX"],
    "XLF": ["JPM","BAC","WFC","GS","MS","BLK"],
    "XLE": ["XOM","CVX","COP","SLB","EOG","PSX"],
    "XLP": ["PG","KO","PEP","COST","WMT","MDLZ"],
    "XLI": ["UNP","CAT","GE","HON","BA","DE"],
    "XLB": ["LIN","APD","SHW","FCX","NEM"],
    "XLV": ["UNH","LLY","JNJ","PFE","MRK","ABBV"],
    "XLU": ["NEE","DUK","SO","EXC","AEP"],
    "XLRE":["AMT","PLD","CCI","EQIX","SPG"],
    "XLC": ["GOOGL","GOOG","META","TMUS","NFLX"],
}

# ------------------ Endpoints ----------------------

@router.get("/sectors")
def sectors()->Dict[str,Any]:
    rows, notes = [], []
    for name,etf in SECTOR_ETFS.items():
        try:
            chg=_pct_change(etf,days=5)
            if chg is None: notes.append(f"{etf}: no data"); continue
            rows.append({"sector":name,"symbol":etf,"change_5d":round(chg*100,2)})
            time.sleep(0.02)
        except Exception:
            notes.append(f"{etf}: provider error")
    rows.sort(key=lambda r: r["change_5d"], reverse=True)
    return {"sectors":rows, "note":"; ".join(notes) if notes else None, "as_of": pd.Timestamp.utcnow().isoformat()}

def _row_features(sym:str, days:int=180)->Optional[Dict[str,Any]]:
    s=_hist_closes(sym, days)
    if s is None or len(s)<50: return None
    price=float(s.iloc[-1])
    ema12=float(ema(s,12).iloc[-1]); ema26=float(ema(s,26).iloc[-1])
    rsi=float(rsi14(s) or 50.0)
    mom5=float(price/float(s.iloc[-6]) -1.0) if len(s)>6 else 0.0
    score=(0.4 if ema12>ema26 else 0.0)+(0.3 if mom5>0 else 0.0)+0.3*max(0.0,1.0-abs(rsi-50)/50)
    return {
        "symbol":sym,"price":round(price,2),
        "ema_short":round(ema12,2),"ema_long":round(ema26,2),
        "rsi":round(rsi,1),"mom_5d":round(mom5,4),
        "score":float(score),
        "closes":[round(float(x),2) for x in s.tail(days).tolist()],
    }

def _explain_row(row:Dict[str,Any])->str:
    price=row["price"]; rsi=row["rsi"]; ema_s=row["ema_short"]; ema_l=row["ema_long"]; mom=row["mom_5d"]
    trend="uptrend" if ema_s>ema_l else "downtrend"
    rsi_hint="healthy (near 50)" if 45<=rsi<=55 else ("strong" if rsi>60 else ("weak" if rsi<40 else "mixed"))
    mom_pct=f"{mom*100:.1f}%"
    return (f"Price ≈ ${price:.2f}. The short-term average is {'above' if ema_s>ema_l else 'below'} the long-term average "
            f"(that’s a {trend}). 5-day momentum ≈ {mom_pct}. RSI looks {rsi_hint}. Overall score {row.get('score',0):.2f} (higher is stronger).")

@router.get("/scan")
def scan(symbols:str=Query(...,description="Comma-separated tickers"),
         include_history:int=Query(1,ge=0,le=1),
         history_days:int=Query(180,ge=60,le=400))->Dict[str,Any]:
    results, notes = [], []
    tickers=[t.strip().upper() for t in symbols.split(",") if t.strip()]
    if not tickers: return {"results":[],"note":"no tickers provided"}
    for t in tickers:
        try:
            row=_row_features(t,history_days)
            if not row: notes.append(f"{t}: no history"); continue
            if include_history==0: row.pop("closes",None)
            row["explain"]=_explain_row(row)
            results.append(row); time.sleep(0.02)
        except Exception as e:
            notes.append(f"{t}: data error")
    results.sort(key=lambda r:r.get("score",0.0), reverse=True)
    return {"results":results,"note":"; ".join(notes) if notes else None}

# ---------- sector drilldown: top constituents ----------
@router.get("/sector/top")
def sector_top(sector_symbol:str=Query(...,description="e.g., XLK"),
               limit:int=Query(8,ge=1,le=20))->Dict[str,Any]:
    universe = SECTOR_UNIVERSE.get(sector_symbol.upper(), [])
    if not universe: return {"symbols":[],"note":"unknown sector"}
    out=[]
    for t in universe:
        row=_row_features(t,180)
        if row: 
            row["explain"]=_explain_row(row)
            out.append(row)
        time.sleep(0.02)
    out.sort(key=lambda r:r.get("score",0.0), reverse=True)
    return {"symbols": out[:limit], "as_of": pd.Timestamp.utcnow().isoformat()}

# ---------- single stock summary with probability ----------
def _prob_up_20d_from_hist(s:pd.Series, samples:int=2000)->Dict[str,Any]:
    # bootstrap 20 daily returns from last 180d
    cls=s.dropna().astype(float)
    if len(cls)<60: return {"prob_up_20d": None, "exp_move_1sigma": None}
    rets=np.diff(np.log(cls))/1.0
    if len(rets)<40: return {"prob_up_20d": None, "exp_move_1sigma": None}
    rng=np.random.default_rng(42)
    n=20
    sims = rng.choice(rets, size=(samples, n), replace=True).sum(axis=1)
    prob_up=float((sims>0).mean())
    sigma=float(np.std(rets)*math.sqrt(n))  # ~1-sigma log-return in 20d
    return {"prob_up_20d": prob_up, "exp_move_1sigma": sigma}

@router.get("/stock_summary")
def stock_summary(symbol:str=Query(...))->Dict[str,Any]:
    symbol=symbol.upper().strip()
    s=_hist_closes(symbol, 220)
    if s is None or len(s)<50:
        return {"symbol":symbol,"note":"not enough history"}
    row=_row_features(symbol,180)
    prob=_prob_up_20d_from_hist(s, samples=4000)
    row["prob_up_20d"]=prob["prob_up_20d"]
    row["exp_move_1sigma"]=prob["exp_move_1sigma"]
    row["explain"]=_explain_row(row)+(
        f" Based on recent swings, the chance of being higher in ~20 trading days is ~{(row['prob_up_20d']*100):.0f}%."
        if row.get("prob_up_20d") is not None else " We could not compute a 20-day probability due to limited data."
    )
    return {"summary":row, "as_of": pd.Timestamp.utcnow().isoformat()}
