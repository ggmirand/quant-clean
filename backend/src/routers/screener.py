from fastapi import APIRouter, Query
import time
from typing import Dict, Any, List
from ..utils import providers as P
from ..utils.math import rsi14, ema

router = APIRouter()

@router.get("/scan")
def scan(
    symbols: str = Query(...),
    min_volume: int = Query(0, ge=0),
    include_history: int = Query(1),
    history_days: int = Query(180, ge=30, le=400),
) -> Dict[str, Any]:
    results=[]; notes=[]
    tickers = [x.strip().upper() for x in symbols.split(",") if x.strip()]
    if not tickers: return {"results": [], "note": "no tickers provided"}

    for t in tickers:
        try:
            close = P.hist_close_series(t, history_days)
            if close is None or close.empty:
                notes.append(f"{t}: no history"); continue
            price = float(close.iloc[-1])
            ema12 = ema(close, 12).iloc[-1]; ema26 = ema(close, 26).iloc[-1]
            rsi = rsi14(close) or 50.0
            mom_5d = float(price / float(close.iloc[-6]) - 1.0) if len(close) > 6 else 0.0
            score = (0.4 if ema12>ema26 else 0.0) + (0.3 if mom_5d>0 else 0.0) + 0.3*max(0.0,1.0-abs(rsi-50)/50)
            row = {
                "symbol": t, "price": price, "volume": 0,
                "ema_short": float(ema12), "ema_long": float(ema26),
                "rsi": float(rsi), "mom_5d": float(mom_5d),
                "volume_rank_pct": 0.5, "score": float(score),
            }
            if include_history:
                row["closes"] = [round(float(x), 2) for x in close.tail(history_days).tolist()]
                row["volumes"] = []
            results.append(row)
            time.sleep(0.02)
        except Exception as e:
            notes.append(f"{t}: data error ({type(e).__name__})")
            continue

    results.sort(key=lambda r: r.get("score",0.0), reverse=True)
    note = "; ".join(notes) if notes else None
    return {"results": results, "note": note}
