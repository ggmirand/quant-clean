from fastapi import APIRouter, Query
import datetime as dt, time, os
from typing import Dict, Any, List, Optional
from ..utils import providers as P
from ..utils.math import (call_delta, put_delta, call_price, put_price,
                          mc_option_samples_from_hist, ema, rsi14)

router = APIRouter()

def _trend(symbol: str):
    s = P.hist_close_series(symbol, 200)
    if s is None or len(s)<50:
        return {"trend":"neutral","score":0.0,"notes":["Not enough history"], "close":s}
    ema20=float(ema(s,20).iloc[-1]); ema50=float(ema(s,50).iloc[-1])
    ret10=float((s.iloc[-1]/s.iloc[-11]-1.0)) if len(s)>11 else 0.0
    rsi = float(rsi14(s) or 50.0)
    score=(0.4 if ema20>ema50 else 0.0)+(0.3 if ret10>0 else 0.0)+0.3*max(0.0,1.0-abs(rsi-50)/50)
    tr="up" if score>=0.55 else ("down" if score<=0.35 else "neutral")
    return {"trend":tr,"score":float(score),"notes":[
        "EMA20 > EMA50" if ema20>ema50 else "EMA20 ≤ EMA50",
        f"10-day momentum: {ret10*100:.1f}%",
        f"RSI(14): {rsi:.1f}"
    ],"close":s}

def _model_candidates(S: float, prefer: str, buying_power: float, T_days=35):
    if not (S and S>0): return []
    r=0.0; iv=0.35; T=T_days/365.0
    if prefer=="up": Ks=[S*0.95,S,S*1.05]; is_call=True
    elif prefer=="down": Ks=[S*1.05,S,S*0.95]; is_call=False
    else: Ks=[S*0.95,S,S*1.05]; is_call=True
    out=[]
    for K in Ks:
        if is_call:
            prem=call_price(S,K,T,r,iv); delta=call_delta(S,K,T,r,iv); be=K+prem; typ="CALL"
        else:
            prem=put_price(S,K,T,r,iv);  delta=put_delta(S,K,T,r,iv);  be=K-prem; typ="PUT"
        if prem*100>buying_power: continue
        out.append({"expiry":(dt.date.today()+dt.timedelta(days=T_days)).isoformat(),
                    "type":typ,"strike":round(K,2),"mid_price":round(prem,2),
                    "iv":iv,"delta":round(delta,3),"breakeven":round(be,2),
                    "oi":0,"volume":0,"chance_profit":None,"dte":T_days})
    return out[:3]

def _conf(c):
    score=0; prem=c.get("mid_price",0) or 0.0
    if c.get("delta") is not None and 0.1<=abs(c["delta"])<=0.6: score+=35
    if prem*100<=300: score+=25
    elif prem*100<=800: score+=12
    if c.get("oi",0)>=50 or c.get("volume",0)>=10: score+=15
    return min(100,score)

@router.get("/idea")
def idea(symbol: str = Query(...), buying_power: float = Query(...)) -> Dict[str, Any]:
    symbol=symbol.upper().strip()
    S = P.last_price(symbol) or 0.0
    tr = _trend(symbol)
    prefer = tr["trend"]
    cands = _model_candidates(S, prefer, buying_power)
    if not cands:
        return {"symbol":symbol,"under_price":S,"picked_window":None,"suggestions":[],
                "sim":None,"explanation":"No affordable contracts right now.","thought_process":tr["notes"],
                "note":"provider or affordability"}
    for c in cands:
        c["conf"]=_conf(c); c["delta_diff"]=abs(abs(c.get("delta") or 0.0)-0.30)
    cands.sort(key=lambda x:(x["delta_diff"], -x["conf"], x["mid_price"]))
    best=cands[:3]
    # one light simulation
    close = tr["close"]; sim=None
    try:
        if close is not None and len(close)>40:
            sim = mc_option_samples_from_hist(symbol, S, best[0]["strike"], best[0]["mid_price"], best[0]["dte"], best[0]["type"], close)
    except Exception: sim=None
    return {"symbol":symbol,"under_price":S,"picked_window":None,"suggestions":best,"sim":sim,
            "explanation":"We target ~0.30 delta near-month, fit your buying power, and align with trend.",
            "thought_process":tr["notes"],"note":None}

WATCHLIST=["AAPL","MSFT","NVDA","TSLA","AMZN","META","GOOGL","AMD","NFLX","AVGO"]

@router.get("/market-ideas")
def market_ideas(buying_power: float = Query(...), limit: int = Query(3, ge=1, le=10)):
    scored=[]
    for t in WATCHLIST:
        try:
            s=idea(t, buying_power)  # reuse same logic
            if s.get("suggestions"):
                best=s["suggestions"][0]
                scored.append({"symbol":t,"under_price":s["under_price"],
                               "suggestion":best,"confidence":best.get("conf",0),
                               "explanation":s["explanation"],"thought_process":s["thought_process"]})
        except Exception:
            pass
        time.sleep(0.03)
    scored.sort(key=lambda x:-x.get("confidence",0))
    return {"ideas":scored[:limit]}
