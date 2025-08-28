from fastapi import APIRouter
import datetime as dt, time
from typing import Dict, Any, Optional
from ..utils import providers as P

router = APIRouter()

SECTOR_ETF_MAP = {
    "Materials": "XLB","Energy": "XLE","Technology": "XLK","Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP","Health Care": "XLV","Industrials": "XLI","Financials": "XLF",
    "Utilities": "XLU","Communication Services": "XLC","Real Estate": "XLRE",
}

def sector_change_percent(ticker: str) -> Optional[float]:
    try:
        s = P.hist_close_series(ticker, 5)
        if s is None or len(s)<2: return None
        return float((s.iloc[-1]/s.iloc[-2]-1.0)*100.0)
    except Exception:
        return None

@router.get("/sectors")
def sectors() -> Dict[str, Any]:
    out={}
    for name,etf in SECTOR_ETF_MAP.items():
        chg = sector_change_percent(etf)
        if chg is not None: out[name]=f"{chg:.2f}%"
        time.sleep(0.02)
    return {
        "Rank A: Real-Time Performance": out,
        "note": None if out else "sector data temporarily unavailable (provider rate-limit/offline)",
        "as_of": dt.datetime.utcnow().isoformat(timespec="seconds")+"Z"
    }

@router.get("/top-gainers")
def top_gainers():
    try:
        rows = P.yahoo_day_gainers(24)[:12]
        return {"top_gainers": rows}
    except Exception as e:
        return {"top_gainers": [], "note": f"unavailable: {type(e).__name__}"}
