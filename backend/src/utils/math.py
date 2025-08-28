import math
import numpy as np
import pandas as pd

SQRT_2 = math.sqrt(2.0)
def norm_cdf(x: float) -> float: return 0.5 * (1.0 + math.erf(x / SQRT_2))

def bs_d1(S, K, T, r, sigma):
    if S <= 0 or K <= 0 or sigma <= 0 or T <= 0: return float("nan")
    return (math.log(S/K) + (r + 0.5*sigma*sigma)*T) / (sigma*math.sqrt(T))

def call_price(S,K,T,r,sigma):
    d1 = bs_d1(S,K,T,r,sigma); d2 = d1 - sigma*math.sqrt(T)
    return S*norm_cdf(d1) - K*math.exp(-r*T)*norm_cdf(d2)

def put_price(S,K,T,r,sigma):
    d1 = bs_d1(S,K,T,r,sigma); d2 = d1 - sigma*math.sqrt(T)
    return K*math.exp(-r*T)*norm_cdf(-d2) - S*norm_cdf(-d1)

def call_delta(S,K,T,r,sigma): return norm_cdf(bs_d1(S,K,T,r,sigma))
def put_delta(S,K,T,r,sigma):  return call_delta(S,K,T,r,sigma) - 1.0

def rsi14(close: pd.Series) -> float | None:
    s = close.dropna()
    if len(s) < 20: return None
    d = s.diff().dropna()
    up = d.clip(lower=0.0); down = -d.clip(upper=0.0)
    roll_up = up.ewm(alpha=1/14, adjust=False).mean()
    roll_down = down.ewm(alpha=1/14, adjust=False).mean()
    rs = (roll_up/roll_down).replace([np.inf,-np.inf], 0.0).fillna(0.0)
    rsi = 100 - (100/(1+rs))
    return float(rsi.iloc[-1])

def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()

def mc_option_samples_from_hist(symbol: str, S: float, K: float, premium: float, T_days: int, otype: str, close: pd.Series, n_paths=800):
    if S<=0 or K<=0 or T_days<=0 or close is None or len(close)<40: return None
    lr = np.log(close / close.shift(1)).dropna().values
    mu, sig = float(np.mean(lr)), float(np.std(lr))
    T = float(T_days)
    Z = np.random.normal(0,1,size=n_paths)
    ST = S*np.exp((mu-0.5*sig**2)*T + sig*np.sqrt(T)*Z)
    payoff = (np.maximum(ST-K,0.0)-premium) if otype.upper()=="CALL" else (np.maximum(K-ST,0.0)-premium)
    p5,p50,p95 = np.percentile(payoff, [5,50,95])
    prob_profit=float((payoff>0).mean())
    return {"pl_p5": float(p5), "pl_p50": float(p50), "pl_p95": float(p95), "prob_profit": prob_profit}
