from fastapi import APIRouter, Query
from typing import Dict, Any, Optional, List
import time
import datetime as dt
import pandas as pd

from ..utils import providers as P
from ..utils.math import (
    call_price, put_price,
    call_delta, put_delta,
    ema, rsi14, mc_option_samples_from_hist,
)

# Optional Yahoo fallback for last price/history
try:
    import yfinance as yf
    HAVE_YF = True
except Exception:
    HAVE_YF = False

router = APIRouter()

# ---------- small cache (price/history) -------------
_PRICE_CACHE: Dict[str, float] = {}
_HIST_CACHE: Dict[str, pd.Series] = {}
_TS: Dict[str, float] = {}
_TTL = 300.0

def _now() -> float:
    return time.time()

def _get_hist(symbol: str, days: int = 200) -> Optional[pd.Series]:
    key = f"{symbol.upper()}:{days}"
    if key in _HIST_CACHE and (_now() - _TS.get(key, 0.0)) < _TTL:
        return _HIST_CACHE[key]

    # Stooq first
    s = None
    try:
        s = P.hist_close_series(symbol, days)
    except Exception:
        s = None

    # Yahoo fallback
    if (s is None or len(s) == 0) and HAVE_YF:
        try:
            t = yf.Ticker(symbol)
            period = "max" if days > 365 else f"{days}d"
            df = t.history(period=period)
            if not df.empty:
                s = df["Close"].dropna().sort_index().tail(days)
        except Exception:
            s = None

    if s is not None and len(s) > 0:
        _HIST_CACHE[key] = s
        _TS[key] = _now()
        _PRICE_CACHE[symbol.upper()] = float(s.iloc[-1])
        return s
    return None

def _last_price(symbol: str) -> Optional[float]:
    key = symbol.upper()
    if key in _PRICE_CACHE and (_now() - _TS.get(key, 0.0)) < _TTL:
        return _PRICE_CACHE[key]
    s = _get_hist(symbol, 30)
    return float(s.iloc[-1]) if s is not None and len(s) else None

def _trend(symbol: str) -> Dict[str, Any]:
    s = _get_hist(symbol, 200)
    if s is None or len(s) < 50:
        return {
            "trend": "neutral",
            "score": 0.0,
            "notes": ["Not enough recent history"],
            "close_series": s,
        }
    ema20 = float(ema(s, 20).iloc[-1])
    ema50 = float(ema(s, 50).iloc[-1])
    ret10 = float((s.iloc[-1] / s.iloc[-11] - 1.0)) if len(s) > 11 else 0.0
    rsi_val = float(rsi14(s) or 50.0)
    score = (
        (0.4 if ema20 > ema50 else 0.0) +
        (0.3 if ret10 > 0 else 0.0) +
        0.3 * max(0.0, 1.0 - abs(rsi_val - 50) / 50)
    )
    trend = "up" if score >= 0.55 else ("down" if score <= 0.35 else "neutral")
    return {
        "trend": trend,
        "score": float(score),
        "notes": [
            "EMA20 > EMA50" if ema20 > ema50 else "EMA20 ≤ EMA50",
            f"10-day momentum: {ret10 * 100:.1f}%",
            f"RSI(14): {rsi_val:.1f}",
        ],
        "close_series": s,
    }

def _model_candidates(S: float, prefer: str, buying_power: float, T_days: int = 35) -> List[Dict[str, Any]]:
    """No external chains: create 1–3 affordable contracts with Black–Scholes pricing."""
    if S is None or S <= 0:
        return []
    r = 0.0
    iv = 0.35
    T = T_days / 365.0

    if prefer == "up":
        Ks = [S * 0.95, S * 1.00, S * 1.05]; is_call = True
    elif prefer == "down":
        Ks = [S * 1.05, S * 1.00, S * 0.95]; is_call = False
    else:
        Ks = [S * 0.95, S * 1.00, S * 1.05]; is_call = True

    out: List[Dict[str, Any]] = []
    for K in Ks:
        if is_call:
            prem = call_price(S, K, T, r, iv); delta = call_delta(S, K, T, r, iv); be = K + prem; typ = "CALL"
        else:
            prem = put_price(S, K, T, r, iv);  delta = put_delta(S, K, T, r, iv);  be = K - prem; typ = "PUT"
        cost = prem * 100.0
        if cost > buying_power:
            continue
        out.append({
            "type": typ,
            "strike": round(K, 2),
            "mid_price": round(prem, 2),
            "breakeven": round(be, 2),
            "iv": iv,
            "delta": round(delta, 3),
            "dte": T_days,
            "expiry": (dt.date.today() + dt.timedelta(days=T_days)).isoformat(),
            "oi": 0,
            "volume": 0,
        })
    return out[:3]

def _confidence(c: Dict[str, Any]) -> int:
    score = 0
    d = abs(c.get("delta") or 0.0)
    cost = (c.get("mid_price") or 0.0) * 100.0
    if 0.1 <= d <= 0.6: score += 40
    if cost <= 300: score += 25
    elif cost <= 800: score += 12
    return min(100, score)

def _explain_choice(symbol: str, S: float, c: Dict[str, Any], trend_notes: List[str]) -> str:
    """
    8th-grade summary:
    - What we’re buying (call/put), strike, expiry
    - Cost & breakeven
    - Why (trend + delta≈0.30 targeting)
    """
    typ = c.get("type")
    strike = c.get("strike")
    expiry = c.get("expiry")
    cost = (c.get("mid_price") or 0.0) * 100.0
    be = c.get("breakeven")
    delta = c.get("delta")
    dir_txt = "go up" if typ == "CALL" else "go down"

    notes = "; ".join(trend_notes[:2]) if trend_notes else ""
    return (
        f"We suggest a {typ} for {symbol}. Strike ≈ ${strike:.2f}, expiry {expiry}. "
        f"Estimated cost ≈ ${cost:.0f} per contract. Breakeven ≈ ${be:.2f}. "
        f"Delta ≈ {delta:.2f}, which means the option moves ~{abs(delta)*100:.0f}% of the stock’s move. "
        f"This pick lines up with the recent trend ({notes}). If the stock does {dir_txt}, this option can benefit. "
        f"Only risk what you can afford—options can go to $0."
    )

@router.get("/idea")
def idea(symbol: str = Query(...), buying_power: float = Query(...)) -> Dict[str, Any]:
    symbol = symbol.upper().strip()
    S = _last_price(symbol) or 0.0
    tr = _trend(symbol)
    prefer = tr["trend"]

    if S <= 0.0:
        return {
            "symbol": symbol,
            "under_price": 0.0,
            "picked_window": None,
            "suggestions": [],
            "sim": None,
            "explanation": "Couldn’t fetch a recent price. Please try again in a minute.",
            "thought_process": tr["notes"],
            "note": "provider temporarily unavailable",
        }

    cands = _model_candidates(S, prefer, buying_power)
    if not cands:
        return {
            "symbol": symbol,
            "under_price": S,
            "picked_window": None,
            "suggestions": [],
            "sim": None,
            "explanation": "No affordable contracts matched your buying power right now.",
            "thought_process": tr["notes"],
            "note": None,
        }

    # rank: target delta ~0.30, then confidence, then cheaper first
    for c in cands:
        c["conf"] = _confidence(c)
        c["delta_diff"] = abs(abs(c.get("delta") or 0.0) - 0.30)
    cands.sort(key=lambda x: (x["delta_diff"], -x["conf"], x["mid_price"]))
    best = cands[:3]

    # one light simulation for the first pick
    sim = None
    try:
        s = tr.get("close_series")
        if s is not None and len(s) > 40:
            b0 = best[0]
            sim = mc_option_samples_from_hist(symbol, S, b0["strike"], b0["mid_price"], b0["dte"], b0["type"], s)
    except Exception:
        sim = None

    explanation = _explain_choice(symbol, S, best[0], tr["notes"])
    return {
        "symbol": symbol,
        "under_price": S,
        "picked_window": {"dte": best[0]["dte"]},
        "suggestions": best,
        "sim": sim,
        "explanation": explanation,
        "thought_process": tr["notes"],
        "note": None,
    }
