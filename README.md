# Quant Clean

Minimal, robust trading assistant (no Docker):
- Market Highlights: sector performance via SPDR ETFs + verified top gainers
- Quick Screener: RSI/EMA/momentum with simple charts
- Options — My Ticker: 1–3 contract ideas from buying power + payoff + simple simulation + 8th-grade summary
- Options — Market Ideas: scan a watchlist for top suggestions
- Dark, Robinhood-ish UI
- Provider hardening: yfinance with Stooq EOD fallback; optional Tradier token for real chains

## Run locally

### API
```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
