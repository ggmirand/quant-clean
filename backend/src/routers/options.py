from fastapi import APIRouter, Query
from typing import Dict, Any, Optional, List
import time, datetime as dt, math
import numpy as np
import pandas as pd

from ..utils import providers as P
from ..utils.math import (
    call_price, put_price, call_delta, put_delta,
    ema, rsi14,
)

try:
    import yfinance as yf
    HAVE_YF=True
except Exception:
    HAVE_YF=False

router = APIRouter()

# small caches
_PRICE: Dict[str,float] = {}
_HIST: Dict[str,pd.Series] = {}
_TS: Dict[str,float] = {}
_TTL=300.0

def _now(): return time.time()

def _hist(sym:str, days:int=240)->Optional[pd.Series]:
    key=f"{sym.upper()}:{days}"
    if key in _HIST and (_now()-_TS.get(key,0))<_TTL: return _HIST[key]
    s=None
    try: s=P.hist_close_series(sym,days)
    except Exception: s=None
    if (s is None or len(s)==0) and HAVE_YF:
        try:
            t=yf.Ticker(sym); period="max" if days>365 else f"{days}d"
            df=t.history(period=period)
            if not df.empty: s=df["Close"].dropna().sort_index().tail(days)
        except Exception: s=None
    if s is not None and len(s):
        _HIST[key]=s; _TS[key]=_now(); _PRICE[sym.upper()]=float(s.iloc[-1]); return s
    return None

def _price(sym:str)->Optional[float]:
    key=sym.upper()
    if key in _PRICE and (_now()-_TS.get(f"{key}:240",0))<_TTL: return _PRICE[key]
    s=_hist(sym,60); 
    return float(s.iloc[-1]) if s is not None and len(s) else None

def _trend(sym:str)->Dict[str,Any]:
    s=_hist(sym,200)
    if s is None or len(s)<50:
        return {"trend":"neutral","score":0.0,"notes":["Not enough data"],"series":s}
    ema20=float(ema(s,20).iloc[-1]); ema50=float(ema(s,50).iloc[-1])
    ret10=float(s.iloc[-1]/s.iloc[-11]-1.0) if len(s)>11 else 0.0
    rsi=float(rsi14(s) or 50.0)
    score=(0.4 if ema20>ema50 else 0.0)+(0.3 if ret10>0 else 0.0)+0.3*max(0.0,1.0-abs(rsi-50)/50)
    trend="up" if score>=0.55 else ("down" if score<=0.35 else "neutral")
    return {"trend":trend,"score":float(score),"notes":[("EMA20>EMA50" if ema20>ema50 else "EMA20≤EMA50"),
            f"10-day momentum {ret10*100:.1f}%", f"RSI {rsi:.1f}"],"series":s}

def _third_friday(year:int, month:int)->dt.date:
    d=dt.date(year, month, 1)
    # weekday: Mon=0..Sun=6; we find the 3rd Friday (weekday=4)
    first_friday = 1 + ((4 - d.weekday()) % 7)
    return dt.date(year, month, first_friday + 14)

def _pick_expiry(days_min:int=21, days_max:int=60)->dt.date:
    today=dt.date.today()
    # try next two third-Fridays within window
    months=[today.month, (today.month%12)+1, (today.month+1)%12+1]
    candidates=[]
    for m_offset in range(0,4):
        y = today.year + ((today.month-1 + m_offset)//12)
        m = (today.month-1 + m_offset)%12 + 1
        candidates.append(_third_friday(y,m))
    valid=[d for d in candidates if days_min <= (d-today).days <= days_max]
    if valid: return min(valid, key=lambda d:(d-today).days)
    # fallback: nearest Friday ~35d from now
    guess=today+dt.timedelta(days=35)
    while guess.weekday()!=4: guess+=dt.timedelta(days=1)
    return guess

def _bs_candidates(S:float, prefer:str, bp:float)->List[Dict[str,Any]]:
    if not S or S<=0: return []
    r=0.0; iv=0.35
    expiry=_pick_expiry()
    dte=(expiry - dt.date.today()).days
    T=dte/365.0
    if prefer=="up": Ks=[S*0.95, S*1.00, S*1.05]; is_call=True
    elif prefer=="down": Ks=[S*1.05, S*1.00, S*0.95]; is_call=False
    else: Ks=[S*0.95,S*1.00,S*1.05]; is_call=True
    out=[]
    for K in Ks:
        if is_call:
            prem=call_price(S,K,T,r,iv); delta=call_delta(S,K,T,r,iv); be=K+prem; typ="CALL"
        else:
            prem=put_price(S,K,T,r,iv);  delta=put_delta(S,K,T,r,iv);  be=K-prem; typ="PUT"
        cost=prem*100.0
        if cost>bp: continue
        out.append({"type":typ,"strike":round(K,2),"mid_price":round(prem,2),"breakeven":round(be,2),
                    "iv":iv,"delta":round(delta,3),"dte":dte,"expiry":expiry.isoformat(),"oi":0,"volume":0})
    return out[:3]

def _prob_profit_mc(S:float, c:Dict[str,Any], series:pd.Series, sims:int=8000)->float:
    """Probability( P/L > 0 ) using bootstrap daily log returns, horizon = DTE."""
    if series is None or len(series)<80: return None
    rets=np.diff(np.log(series.values))
    if len(rets)<40: return None
    rng=np.random.default_rng(123)
    n=c.get("dte",30)
    typ=c.get("type"); K=c.get("strike"); prem=c.get("mid_price",0.0)
    # simulate end prices
    paths=rng.choice(rets, size=(sims, n), replace=True).sum(axis=1)
    S_end = S * np.exp(paths)
    if typ=="CALL":
        payoff=np.maximum(S_end-K, 0.0)
    else:
        payoff=np.maximum(K-S_end, 0.0)
    pnl = payoff - prem
    return float((pnl>0).mean())

def _explain_choice(sym:str, S:float, c:Dict[str,Any], trend_notes:List[str], pop:Optional[float])->str:
    typ=c["type"]; K=c["strike"]; exp=c["expiry"]; prem=c["mid_price"]; be=c["breakeven"]
    delta=c["delta"]; conf=c.get("conf",0)
    dir_txt="go up" if typ=="CALL" else "go down"
    base=(f"We suggest a {typ} on {sym}. Strike ≈ ${K:.2f}, expiry {exp}. Cost ≈ ${prem*100:.0f} per contract. "
          f"Breakeven ≈ ${be:.2f}. Delta ≈ {delta:.2f} (moves about {abs(delta)*100:.0f}% of the stock). "
          f"This aligns with the recent trend ({'; '.join(trend_notes[:2])}). ")
    prob = f"Based on recent swings, the chance this trade finishes profitable is ~{pop*100:.0f}%." if pop is not None else ""
    risk = " Options can lose all value — only risk what you can afford."
    return base + prob + risk

@router.get("/idea")
def idea(symbol:str=Query(...), buying_power:float=Query(...))->Dict[str,Any]:
    sym=symbol.upper().strip()
    S=_price(sym) or 0.0
    trend=_trend(sym)
    prefer=trend["trend"]
    if S<=0:
        return {"symbol":sym,"under_price":0.0,"picked_window":None,"suggestions":[],
                "sim":None,"explanation":"Couldn’t fetch a recent price. Try again shortly.","thought_process":trend["notes"],"note":"provider temporarily unavailable"}
    cands=_bs_candidates(S, prefer, buying_power)
    if not cands:
        return {"symbol":sym,"under_price":S,"picked_window":None,"suggestions":[],
                "sim":None,"explanation":"No affordable contracts met the filters.","thought_process":trend["notes"],"note":None}
    # rank by delta closeness to 0.30, then confidence, then cheaper first
    for c in cands:
        c["conf"]=min(100, (60-abs(abs(c["delta"])-0.30)*100) + (20 if (c["mid_price"]*100)<=400 else 0))
        c["delta_diff"]=abs(abs(c["delta"])-0.30)
    cands.sort(key=lambda x:(x["delta_diff"], -x["conf"], x["mid_price"]))
    best=cands[:3]

    # probability of profit for the first candidate
    series=trend.get("series")
    pop=_prob_profit_mc(S, best[0], series) if series is not None else None

    explanation=_explain_choice(sym, S, best[0], trend["notes"], pop)
    return {
        "symbol": sym,
        "under_price": S,
        "picked_window": {"dte": best[0]["dte"]},
        "suggestions": best,
        "sim": {"prob_profit": pop} if pop is not None else None,
        "explanation": explanation,
        "thought_process": trend["notes"],
        "note": None
    }
