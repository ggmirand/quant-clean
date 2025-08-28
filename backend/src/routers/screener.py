from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional, Tuple
import time
import math

import pandas as pd

from ..utils import providers as P
from ..utils.math import rsi14, ema

# Optional Yahoo fallback without exploding the app if unavailable
try:
    import yfinance as yf
    HAVE_YF = True
except Exception:
    HAVE_YF = False

router = APIRouter()

# -------------------- tiny in-memory cache (5 min) ----------------------------
_CACHE: Dict[Tuple[str, int], Tuple[float, float]] = {}    # (symbol, horizon_days) -> (last_price, ts)
_HIST_CACHE: Dict[Tuple[str, int], Tuple[pd.Series, float]] = {}  # (symbol, days) -> (series, ts)
_TTL = 300.0  # seconds

def _now() -> float:
    return time.time()

def _cache_get_price(symbol: str, days: int) -> Optional[float]:
    key = (symbol.upper(), days)
    v = _CACHE.get(key)
    if not v: return None
    price, ts = v
    return price if (_now() - ts) < _TTL else None

def _cache_put_price(symbol: str, days: int, price: float) -> None:
    _CACHE[(symbol.upper(), days)] = (float(price), _now())

def _cache_get_hist(symbol: str, days: int) -> Optional[pd.Series]:
    key = (symbol.upper(), days)
    v = _HIST_CACHE.get(key)
    if not v: return None
    s, ts = v
    return s if (_now() - ts) < _TTL else None

def _cache_put_hist(symbol: str, days: int, s: pd.Series) -> None:
    _HIST_CACHE[(symbol.upper(), days)] = (s.copy(), _now())


# ---------------------- data access with fallback -----------------------------
def _hist_closes(symbol: str, days: int) -> Optional[pd.Series]:
    """Try Stooq (providers.py), then Yahoo (yfinance) if needed. Cache for 5 minutes."""
    # cache first
    s = _cache_get_hist(symbol, days)
    if s is not None:
        return s

    # 1) Stooq via providers
    try:
        s = P.hist_close_series(symbol, days)
        if s is not None and len(s) > 0:
            _cache_put_hist(symbol, days, s)
            _cache_put_price(symbol, days, float(s.iloc[-1]))
            return s
    except Exception:
        pass

    # 2) Yahoo fallback
    if HAVE_YF:
        try:
            yf_sym = yf.Ticker(symbol)
            # if days > 365, ask for max then tail
            period = "max" if days > 365 else f"{days}d"
            df = yf_sym.history(period=period, auto_adjust=False)
            if not df.empty and "Close" in df.columns:
                s = df["Close"]
                s.index = pd.to_datetime(s.index)
                s = s.dropna().sort_index().tail(days)
                if len(s) > 0:
                    _cache_put_hist(symbol, days, s)
                    _cache_put_price(symbol, days, float(s.iloc[-1]))
                    return s
        except Exception:
            pass

    return None


def _last_price(symbol: str, days: int = 30) -> Optional[float]:
    # cache?
    cp = _cache_get_price(symbol, days)
    if cp is not None:
        return cp

    s = _hist_closes(symbol, max(days, 10))
    if s is not None and len(s):
        px = float(s.iloc[-1])
        _cache_put_price(symbol, days, px)
        return px
    return None


# ---------------------- sector “performance” (ETF proxy) ----------------------
# We’ll compute simple % change for well-known sector ETFs, with YF fallback.
_SECTOR_ETFS = {
    "Technology": "XLK", "Healthcare": "XLV", "Financials": "XLF",
    "Energy": "XLE", "Consumer Disc.": "XLY", "Consumer Staples": "XLP",
    "Industrials": "XLI", "Materials": "XLB", "Utilities": "XLU",
    "Real Estate": "XLRE", "Comm. Services": "XLC",
}

def _pct_change(symbol: str, days: int = 5) -> Optional[float]:
    s = _hist_closes(symbol, max(30, days + 1))
    if s is None or len(s) < (days + 1):
        return None
    a, b = float(s.iloc[-1]), float(s.iloc[-1 - days])
    if b <= 0: return None
    return (a / b) - 1.0


@router.get("/sectors")
def sectors() -> Dict[str, Any]:
    rows = []
    notes = []
    for name, etf in _SECTOR_ETFS.items():
        try:
            chg = _pct_change(etf, days=5)
            if chg is None:
                notes.append(f"{etf}: no data")
                continue
            rows.append({"sector": name, "symbol": etf, "change_5d": round(chg * 100.0, 2)})
            time.sleep(0.03)
        except Exception:
            notes.append(f"{etf}: provider error")
            continue

    rows.sort(key=lambda r: r["change_5d"], reverse=True)
    as_of = pd.Timestamp.utcnow().isoformat()
    if not rows:
        return {"sectors": [], "note": "provider temporarily unavailable", "as_of": as_of}
    return {"sectors": rows, "note": "; ".join(notes) if notes else None, "as_of": as_of}


# ------------------------------ screener /scan --------------------------------
def _explain_row(row: Dict[str, Any]) -> str:
    """Simple, 8th-grade explanation for a stock’s metrics."""
    price = row.get("price")
    rsi = row.get("rsi")
    ema_s = row.get("ema_short")
    ema_l = row.get("ema_long")
    mom = row.get("mom_5d")

    trend = "uptrend" if ema_s > ema_l else "downtrend"
    rsi_hint = (
        "healthy (near 50)" if rsi and 45 <= rsi <= 55 else
        "strong" if rsi and rsi > 60 else
        "weak" if rsi and rsi < 40 else "mixed"
    )
    mom_pct = f"{mom * 100:.1f}%" if mom is not None else "0%"
    return (
        f"Price ≈ ${price:.2f}. Short-term average is {'above' if ema_s > ema_l else 'below'} "
        f"the long-term average → {trend}. 5-day momentum ≈ {mom_pct}. RSI looks {rsi_hint}. "
        f"Together, this gets a score of {row.get('score', 0):.2f} (higher is stronger)."
    )

@router.get("/scan")
def scan(
    symbols: str = Query(..., description="Comma-separated tickers, e.g. AAPL,MSFT,NVDA"),
    include_history: int = Query(1, ge=0, le=1),
    history_days: int = Query(180, ge=60, le=400),
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    notes: List[str] = []

    tickers = [t.strip().upper() for t in symbols.split(",") if t.strip()]
    if not tickers:
        return {"results": [], "note": "no tickers provided"}

    for t in tickers:
        try:
            s = _hist_closes(t, history_days)
            if s is None or len(s) < 50:
                notes.append(f"{t}: no history (provider)")
                continue

            price = float(s.iloc[-1])
            s_list = s.tail(history_days)
            ema12 = float(ema(s_list, 12).iloc[-1])
            ema26 = float(ema(s_list, 26).iloc[-1])
            rsi_val = float(rsi14(s_list) or 50.0)
            mom_5d = float(price / float(s_list.iloc[-6]) - 1.0) if len(s_list) > 6 else 0.0

            # Simple composite (0..1+)
            score = (
                (0.4 if ema12 > ema26 else 0.0)
                + (0.3 if mom_5d > 0 else 0.0)
                + 0.3 * max(0.0, 1.0 - abs(rsi_val - 50) / 50)
            )

            row: Dict[str, Any] = {
                "symbol": t,
                "price": round(price, 2),
                "ema_short": round(ema12, 2),
                "ema_long": round(ema26, 2),
                "rsi": round(rsi_val, 1),
                "mom_5d": round(mom_5d, 4),
                "score": float(score),
            }
            if include_history:
                row["closes"] = [round(float(x), 2) for x in s_list.tolist()]

            row["explain"] = _explain_row(row)
            results.append(row)
            time.sleep(0.03)
        except Exception as e:
            notes.append(f"{t}: data error ({type(e).__name__})")

    results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
    top_note = "; ".join(notes) if notes else None
    if not results and not top_note:
        top_note = "provider temporarily unavailable"
    return {"results": results, "note": top_note}
