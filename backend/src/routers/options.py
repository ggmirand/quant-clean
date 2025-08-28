from fastapi import APIRouter, Query
import datetime as dt, os, time
from typing import List, Dict, Optional, Any
import requests

from ..utils import providers as P
from ..utils.math import (
    call_delta, put_delta, call_price, put_price,
    mc_option_samples_from_hist, ema, rsi14
)

router = APIRouter()
R = requests.Session()
R.headers.update({"User-Agent": "Mozilla/5.0 (QuantClean/1.0)", "Accept": "application/json"})
TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")  # optional

# -------- helpers --------------------------------------------------------------
def _retry(fn, attempts=2, sleep_sec=0.35):
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(sleep_sec)
    if last: raise last
    return None

def _third_fridays(n=6):
    out=[]; today = dt.date.today(); y,m=today.year,today.month
    for _ in range(n+2):
        first = dt.date(y,m,1); dow = first.weekday()
        first_fri = 4 - dow if dow<=4 else 11 - dow
        third = first + dt.timedelta(days=first_fri + 14)
        if third > today: out.append(third)
        m += 1
        if m>12: y+=1; m=1
    return out[:n]

def _trend_score(symbol: str):
    # robust history with retry
    s = None
    try:
        s = _retry(lambda: P.hist_close_series(symbol, 200), attempts=2)
    except Exception:
        s = None

    if s is None or len(s) < 50:
        return {"trend":"neutral","score":0.0,"notes":["Not enough history"], "rsi": None, "close": s}

    ema20 = float(ema(s,20).iloc[-1])
    ema50 = float(ema(s,50).iloc[-1])
    ret10 = float((s.iloc[-1]/s.iloc[-11] - 1.0)) if len(s) > 11 else 0.0
    rsi_val = float(rsi14(s) or 50.0)
    score = (0.4 if ema20>ema50 else 0.0) + (0.3 if ret10>0 else 0.0) + 0.3*max(0.0,1.0-abs(rsi_val-50)/50)
    trend = "up" if score >= 0.55 else ("down" if score <= 0.35 else "neutral")
    return {"trend":trend, "score":float(score), "notes":[
        "EMA20 > EMA50" if ema20>ema50 else "EMA20 ≤ EMA50",
        f"10-day momentum: {ret10*100:.1f}%",
        f"RSI(14): {rsi_val:.1f}"
    ], "rsi": rsi_val, "close": s}

def _last_price(symbol: str) -> Optional[float]:
    try:
        return _retry(lambda: P.last_price(symbol), attempts=2)
    except Exception:
        return None

def _construct_candidates_no_chain(S: float, T_days: int, prefer: str, buying_power: float):
    if S is None or S <= 0 or T_days <= 0: return []
    r=0.0; sigma=0.35
    if prefer=="up":
        Ks=[S*0.95,S*1.0,S*1.05]; is_call=True
    elif prefer=="down":
        Ks=[S*1.05,S*1.0,S*0.95]; is_call=False
    else:
        Ks=[S*0.95,S,S*1.05]; is_call=True
    out=[]; T=T_days/365.0
    for K in Ks:
        if is_call:
            prem = call_price(S,K,T,r,sigma); delta = call_delta(S,K,T,r,sigma); be=K+prem; typ="CALL"
        else:
            prem = put_price(S,K,T,r,sigma);  delta = put_delta(S,K,T,r,sigma);  be=K-prem; typ="PUT"
        if prem*100 > buying_power: continue
        out.append({"expiry": (dt.date.today()+dt.timedelta(days=T_days)).isoformat(),
                    "type": typ, "strike": round(K,2), "mid_price": round(prem,2),
                    "iv": sigma, "delta": round(delta,3), "breakeven": round(be,2),
                    "oi": 0, "volume": 0, "chance_profit": None, "dte": T_days})
    return out[:3]

def _confidence_score(c):
    score=0; premium=c.get("mid_price",0) or 0
    if c.get("delta") is not None and 0.1 <= abs(c["delta"]) <= 0.6: score += 35
    if premium*100 <= 300: score += 25
    elif premium*100 <= 800: score += 12
    if c.get("oi",0)>=50 or c.get("volume",0)>=10: score += 15
    return min(100,score)

def _tradier_chain(symbol: str, expiry: str) -> Dict[str, List[dict]]:
    url = "https://api.tradier.com/v1/markets/options/chains"
    r = R.get(url, params={"symbol": symbol, "expiration": expiry, "greeks": "false"},
              headers={"Authorization": f"Bearer {TRADIER_TOKEN}", "Accept": "application/json"}, timeout=6)
    r.raise_for_status()
    j = r.json()
    opts = (((j or {}).get("options") or {}).get("option")) or []
    calls, puts = [], []
    for o in opts:
        try:
            row = {
                "strike": float(o.get("strike")),
                "bid": float(o.get("bid") or 0.0),
                "ask": float(o.get("ask") or 0.0),
                "lastPrice": float(o.get("last") or 0.0),
                "openInterest": int(o.get("open_interest") or 0),
                "volume": int(o.get("volume") or 0),
                "impliedVolatility": float((o.get("greeks") or {}).get("mid_iv") or 0.0),
                "type": "CALL" if str(o.get("option_type")).lower()=="call" else "PUT"
            }
            (calls if row["type"]=="CALL" else puts).append(row)
        except Exception:
            continue
    return {"calls": calls, "puts": puts}

def _pick_candidates(symbol: str, buying_power: float, prefer: str, S: Optional[float]) -> List[Dict[str, Any]]:
    expiries = [e for e in (lambda xs=[21,28,35,42]: [dt.date.today()+dt.timedelta(days=d) for d in xs])()
                if 21<= (e-dt.date.today()).days <=45]
    candidates=[]
    if TRADIER_TOKEN:
        for e in expiries[:2]:
            try:
                book = _tradier_chain(symbol, e.isoformat())
                for side,rows in (("CALL",book["calls"]),("PUT",book["puts"])):
                    is_call = side == "CALL"
                    for r in rows:
                        K=float(r["strike"])
                        bid=float(r["bid"]); ask=float(r["ask"]); last=float(r["lastPrice"])
                        mid=(bid+ask)/2.0 if (bid>0 or ask>0) else last
                        if mid<=0 or mid*100>buying_power: continue
                        dte=(e-dt.date.today()).days; T=dte/365.0; rr=0.0
                        iv = float(r.get("impliedVolatility") or 0.35)
                        delta = call_delta(S,K,T,rr, max(0.2,iv)) if is_call else (call_delta(S,K,T,rr, max(0.2,iv)) - 1.0)
                        be = (K+mid) if is_call else (K-mid)
                        candidates.append({"expiry": e.isoformat(), "type": side,
                                           "strike": round(K,2), "mid_price": round(mid,2), "iv": iv,
                                           "delta": round(delta,3), "breakeven": round(be,2),
                                           "oi": int(r.get("openInterest") or 0), "volume": int(r.get("volume") or 0),
                                           "chance_profit": None, "dte": dte})
            except Exception:
                continue
    else:
        # model-only, resilient path (no external options API)
        candidates = _construct_candidates_no_chain(S or 0.0, 35, prefer, buying_power)
    return candidates

def idea_for_symbol(symbol: str, buying_power: float) -> Dict[str, Any]:
    symbol = symbol.upper().strip()

    # robust price + trend
    S = _last_price(symbol) or 0.0
    trend = _trend_score(symbol)
    prefer = trend["trend"]

    # build candidates
    try:
        candidates = _pick_candidates(symbol, buying_power, prefer, S)
    except Exception as e:
        return {
            "symbol": symbol,
            "under_price": S,
            "picked_window": None,
            "suggestions": [],
            "explanation": "Provider temporarily unavailable. Try again in a minute.",
            "thought_process": trend["notes"],
            "note": f"provider error: {type(e).__name__}"
        }

    if not candidates:
        return {
            "symbol": symbol,
            "under_price": S,
            "picked_window": None,
            "suggestions": [],
            "explanation": "No affordable contracts found right now.",
            "thought_process": trend["notes"],
            "note": "no candidates (rate-limit or insufficient buying power)"
        }

    # rank + add confidence
    for c in candidates:
        c["conf"] = _confidence_score(c)
        c["delta_diff"] = abs(abs(c.get("delta") or 0.0) - 0.30)
    candidates.sort(key=lambda x: (x["delta_diff"], -x["conf"], x["mid_price"]))
    best = candidates[:3]

    # simulation (robust)
    close = trend["close"]; sims=[]
    for c in best:
        try:
            sim = mc_option_samples_from_hist(symbol, S, c["strike"], c["mid_price"], c["dte"], c["type"], close) if close is not None else None
        except Exception:
            sim = None
        sims.append(sim)

    return {
        "symbol": symbol,
        "under_price": S,
        "picked_window": None,
        "suggestions": best,
        "sim": sims[0] if sims else None,  # send one summary sim for UI
        "explanation": "We target ~0.30 delta near-month, fit your buying power, and align with the trend.",
        "thought_process": trend["notes"],
        "note": None
    }

WATCHLIST = ["AAPL","MSFT","NVDA","TSLA","AMZN","META","GOOGL","AMD","NFLX","AVGO"]

@router.get("/idea")
def idea(symbol: str = Query(...), buying_power: float = Query(...)):
    """
    Single-symbol option idea, resilient to provider errors.
    """
    try:
        return idea_for_symbol(symbol, buying_power)
    except Exception as e:
        return {
            "symbol": symbol.upper(),
            "under_price": P.last_price(symbol) or 0.0,
            "picked_window": None,
            "suggestions": [],
            "sim": None,
            "explanation": "Provider temporarily unavailable. Try again shortly.",
            "thought_process": [],
            "note": f"provider error: {type(e).__name__}"
        }

@router.get("/market-ideas")
def market_ideas(buying_power: float = Query(...), limit: int = Query(3, ge=1, le=10)):
    scored=[]
    for t in WATCHLIST:
        try:
            s = idea_for_symbol(t, buying_power)
            if s.get("suggestions"):
                best = s["suggestions"][0]
                scored.append({"symbol": t, "under_price": s["under_price"],
                               "suggestion": best, "confidence": best.get("conf",0),
                               "explanation": s["explanation"], "thought_process": s["thought_process"]})
        except Exception:
            continue
        time.sleep(0.05)
    scored.sort(key=lambda x: -x.get("confidence",0))
    return {"ideas": scored[:limit]}
