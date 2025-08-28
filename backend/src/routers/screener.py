from fastapi import APIRouter, Query
import time
from typing import Dict, Any, List, Optional
from ..utils import providers as P
from ..utils.math import rsi14, ema

router = APIRouter()

# --- small helper with retry/fallback ----------------------------------------
def _safe_hist(symbol: str, days: int, attempts: int = 2) -> Optional[list]:
    """
    Try to fetch close history for `symbol` with a couple of attempts.
    Returns a list[float] (closes) or None.
    """
    last_err = None
    for i in range(attempts):
        try:
            s = P.hist_close_series(symbol, days)
            if s is not None and len(s):
                return [float(x) for x in s.tail(days).tolist()]
        except Exception as e:
            last_err = e
        # tiny backoff before retry
        time.sleep(0.35)
    return None

@router.get("/scan")
def scan(
    symbols: str = Query(..., description="Comma-separated tickers"),
    min_volume: int = Query(0, ge=0),
    include_history: int = Query(1, description="Include closes/volumes arrays"),
    history_days: int = Query(180, ge=30, le=400),
) -> Dict[str, Any]:
    """
    Lightweight screener using EMA/RSI/momentum. Robust to provider hiccups.
    """
    results: List[Dict[str, Any]] = []
    notes: List[str] = []

    tickers = [x.strip().upper() for x in symbols.split(",") if x.strip()]
    if not tickers:
        return {"results": [], "note": "no tickers provided"}

    for t in tickers:
        try:
            closes = _safe_hist(t, history_days, attempts=2)
            if not closes:
                notes.append(f"{t}: no history (provider temporarily unavailable)")
                continue

            price = float(closes[-1])
            # pandas-free quick EMA calc when possible
            # but we still call our utility EMA for consistency
            import pandas as pd
            s = pd.Series(closes)
            ema12 = float(ema(s, 12).iloc[-1])
            ema26 = float(ema(s, 26).iloc[-1])
            rsi = float(rsi14(s) or 50.0)
            mom_5d = float(price / float(closes[-6]) - 1.0) if len(closes) > 6 else 0.0

            score = (0.4 if ema12 > ema26 else 0.0) \
                  + (0.3 if mom_5d > 0 else 0.0) \
                  + 0.3 * max(0.0, 1.0 - abs(rsi - 50) / 50)

            row: Dict[str, Any] = {
                "symbol": t,
                "price": price,
                "volume": 0,
                "ema_short": ema12,
                "ema_long": ema26,
                "rsi": rsi,
                "mom_5d": mom_5d,
                "volume_rank_pct": 0.5,
                "score": float(score),
            }
            if include_history:
                row["closes"] = [round(x, 2) for x in closes]
                row["volumes"] = []  # no reliable free intraday vol here

            results.append(row)
            time.sleep(0.05)  # be gentle with providers
        except Exception as e:
            notes.append(f"{t}: data error ({type(e).__name__})")
            continue

    results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
    note = "; ".join(notes) if notes else None
    # Give a helpful top-level note if everything failed
    if not results and not note:
        note = "data provider temporarily unavailable (rate-limit or no internet)"
    return {"results": results, "note": note}
