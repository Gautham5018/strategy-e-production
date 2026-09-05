"""Fast, deterministic feature scoring for Strategy E.

Live path uses already-cached 5-minute bars only. It NEVER calls Kite historical data.
Backtests can pass historical bars directly.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, time
from math import sqrt
from typing import Optional


def _ema(vals, period):
    if not vals:
        return None
    a = 2.0 / (period + 1.0)
    e = float(vals[0])
    for x in vals[1:]:
        e = a * float(x) + (1.0 - a) * e
    return e


def _atr(bars, period=14):
    if len(bars) < 2:
        return None
    trs=[]
    prev=bars[0]['close']
    for b in bars[1:]:
        trs.append(max(b['high']-b['low'], abs(b['high']-prev), abs(b['low']-prev)))
        prev=b['close']
    if len(trs) < period:
        return sum(trs)/len(trs) if trs else None
    return sum(trs[-period:])/period


def _adx(bars, period=14):
    if len(bars) < 3:
        return None
    trs=[]; plus=[]; minus=[]
    for i in range(1,len(bars)):
        b=bars[i]; p=bars[i-1]
        up=b['high']-p['high']; down=p['low']-b['low']
        tr=max(b['high']-b['low'],abs(b['high']-p['close']),abs(b['low']-p['close']))
        trs.append(tr); plus.append(up if up>down and up>0 else 0.0); minus.append(down if down>up and down>0 else 0.0)
    n=min(period,len(trs))
    if n<2:return None
    tr=sum(trs[-n:])/n or 1e-9
    p=sum(plus[-n:])/n
    m=sum(minus[-n:])/n
    pdi=100*p/tr; mdi=100*m/tr
    dx=100*abs(pdi-mdi)/max(pdi+mdi,1e-9)
    return dx


def _vwap(bars):
    pv=0.0; vol=0.0
    for b in bars:
        v=max(float(b.get('volume',0) or 0),0.0)
        typical=(b['high']+b['low']+b['close'])/3.0
        pv+=typical*v; vol+=v
    return pv/vol if vol>0 else None


def _relative_volume(bars, lookback=20):
    vols=[float(b.get('volume',0) or 0) for b in bars]
    if len(vols)<2 or sum(vols[-lookback-1:-1])<=0:return None
    base=sum(vols[-lookback-1:-1])/min(lookback,max(1,len(vols)-1))
    return vols[-1]/base if base>0 else None


def _find_ts(bars, ts):
    if not bars:return None
    exact=[b for b in bars if b['ts']==ts]
    if exact:return exact[-1]
    return min(bars,key=lambda b:abs((b['ts']-ts).total_seconds()))

@dataclass(frozen=True)
class FeatureSnapshot:
    symbol: str
    ts: datetime
    entry_price: float
    risk_pct: float
    candle_range_pct: float
    close_location: float
    ema9: Optional[float]
    ema20: Optional[float]
    atr14: Optional[float]
    atr_pct: Optional[float]
    adx14: Optional[float]
    vwap: Optional[float]
    relative_volume: Optional[float]
    momentum_3: Optional[float]
    momentum_20: Optional[float]
    score: float
    grade: str
    market_regime_ok: bool
    time_window_ok: bool
    risk_ok: bool
    reasons: tuple

    def to_dict(self):
        d=asdict(self);d['ts']=self.ts.isoformat();d['reasons']=list(self.reasons);return d


def score_trade(*, symbol, signal_time, signal_open, signal_high, signal_low, signal_close, entry_price, bars, market_bars=None,
                max_risk_pct=2.0, min_adx=18.0, min_relative_volume=1.0, min_atr_pct=0.20, max_atr_pct=4.0,
                score_threshold=65.0, start=time(9,15), end=time(15,0), allow_windows=None,
                market_filter=True):
    # bars must already contain data through the signal candle. This function is CPU-only.
    b=list(sorted(bars,key=lambda x:x['ts']))
    last=b[-1] if b else {'open':signal_open,'high':signal_high,'low':signal_low,'close':signal_close,'volume':0,'ts':signal_time}
    close=float(signal_close); low=float(signal_low); high=float(signal_high)
    risk=max(float(entry_price)-low,0.0)
    risk_pct=(risk/max(float(entry_price),1e-9))*100.0
    rng_pct=(high-low)/max(low,1e-9)*100.0
    close_loc=(close-low)/max(high-low,1e-9)
    closes=[x['close'] for x in b]
    ema9=_ema(closes[-60:],9) if closes else None
    ema20=_ema(closes[-100:],20) if closes else None
    atr=_atr(b[-100:],14)
    atr_pct=(atr/close*100.0) if atr is not None and close>0 else None
    adx=_adx(b[-100:],14)
    vwap=_vwap([x for x in b if x['ts'].date()==signal_time.date()])
    rv=_relative_volume(b[-40:],20)
    mom3=(close/closes[-4]-1.0)*100 if len(closes)>=4 and closes[-4]>0 else None
    bars_per_session=75
    mom20=(close/closes[-(20*bars_per_session+1)]-1.0)*100 if len(closes)>(20*bars_per_session) and closes[-(20*bars_per_session+1)]>0 else None

    reasons=[]; score=0.0
    if risk_pct<=max_risk_pct: score+=15
    else: reasons.append('RISK_OVER_LIMIT')
    if close_loc>=0.70: score+=10
    elif close_loc>=0.55: score+=5
    else: reasons.append('WEAK_CLOSE_LOCATION')
    if ema9 is not None and ema20 is not None and close>=ema9>=ema20: score+=15
    elif ema20 is not None and close>=ema20: score+=8
    else: reasons.append('EMA_NOT_ALIGNED')
    if vwap is not None and close>=vwap: score+=15
    else: reasons.append('BELOW_VWAP')
    if rv is not None and rv>=min_relative_volume: score+=10
    else: reasons.append('LOW_RELATIVE_VOLUME')
    if adx is not None and adx>=min_adx: score+=10
    else: reasons.append('LOW_ADX')
    if atr_pct is not None and min_atr_pct<=atr_pct<=max_atr_pct: score+=10
    else: reasons.append('ATR_OUT_OF_RANGE')
    if mom3 is not None and mom3>0: score+=5
    else: reasons.append('MOMENTUM_NOT_POSITIVE')
    if mom20 is not None and mom20>0: score+=5
    else: reasons.append('MEDIUM_TERM_MOMENTUM_NOT_POSITIVE')
    if rng_pct<=8.0: score+=5
    else: reasons.append('CANDLE_TOO_WIDE')

    time_ok=start<=signal_time.time()<=end
    if allow_windows:
        time_ok=False
        for a,z in allow_windows:
            if a<=signal_time.time()<=z: time_ok=True;break
    if not time_ok: reasons.append('TIME_WINDOW_BLOCK')

    market_ok=True
    if market_filter:
        if not market_bars or len(market_bars)<10:
            market_ok=False;reasons.append('MARKET_CONTEXT_UNAVAILABLE')
        else:
            mc=[x['close'] for x in sorted(market_bars,key=lambda x:x['ts'])]
            me9=_ema(mc[-60:],9);me20=_ema(mc[-100:],20);madx=_adx(sorted(market_bars,key=lambda x:x['ts'])[-100:],14)
            market_ok=bool(me9 is not None and me20 is not None and mc[-1]>=me20 and me9>=me20 and (madx is None or madx>=min_adx))
            if not market_ok:reasons.append('MARKET_REGIME_NOT_BULLISH')

    grade='A+' if score>=85 else ('A' if score>=75 else ('B' if score>=65 else 'C'))
    risk_ok=risk>0 and risk_pct<=max_risk_pct
    passed=score>=score_threshold and market_ok and time_ok and risk_ok
    if not passed and not reasons: reasons.append('SCORE_BELOW_THRESHOLD')
    return FeatureSnapshot(symbol=symbol,ts=signal_time,entry_price=float(entry_price),risk_pct=risk_pct,candle_range_pct=rng_pct,close_location=close_loc,
                           ema9=ema9,ema20=ema20,atr14=atr,atr_pct=atr_pct,adx14=adx,vwap=vwap,relative_volume=rv,momentum_3=mom3,momentum_20=mom20,
                           score=min(score,100.0),grade=grade,market_regime_ok=bool(market_ok),time_window_ok=bool(time_ok),risk_ok=bool(risk_ok),reasons=tuple(reasons))
