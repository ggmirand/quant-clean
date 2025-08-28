from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import market, screener, options

app = FastAPI(title="Quant Clean API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health(): return {"ok": True}

app.include_router(market.router,   prefix="/api/market",   tags=["market"])
app.include_router(screener.router, prefix="/api/screener", tags=["screener"])
app.include_router(options.router,  prefix="/api/options",  tags=["options"])
