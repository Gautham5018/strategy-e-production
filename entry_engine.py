"""Strategy E V7.4 pullback + 1-minute market-structure entry engine.

A Chartink 5-minute signal creates a pending setup; it is NOT an immediate order.
Primary entry: previous 5-minute candle 0.50-0.618 retracement + EMA9 proximity,
then a closed 1-minute LL/LH/LL/LH sequence followed by a close above the latest LH.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


def ema(values, period=9):
    vals=[float(v) for v in values if v is not None]
    if not vals:return None
    a=2/(period+1); e=vals[0]
    for v in vals[1:]: e=a*v+(1-a)*e
    return e


def _pivots(bars, left=1, right=1):
    highs=[]; lows=[]
    for i in range(left,len(bars)-right):
        h=bars[i]['high']; l=bars[i]['low']
        if all(h>=bars[j]['high'] for j in range(i-left,i+right+1) if j!=i): highs.append((i,h))
        if all(l<=bars[j]['low'] for j in range(i-left,i+right+1) if j!=i): lows.append((i,l))
    return highs,lows


def fib_zone(previous_bar):
    high=float(previous_bar['high']); low=float(previous_bar['low']); rng=high-low
    return high-0.50*rng, high-0.618*rng


def ema9_value(bars):
    closes=[b['close'] for b in sorted(bars,key=lambda x:x['ts'])]
    return ema(closes[-60:],9) if closes else None


def build_setup(signal_time, previous_bar, signal_bar, five_min_bars, *, ema_tolerance_pct=0.25, wait_minutes=20):
    z50,z618=fib_zone(previous_bar)
    zone_low=min(z50,z618); zone_high=max(z50,z618)
    e9=ema9_value(five_min_bars)
    ema_near=e9 is not None and zone_low*(1-ema_tolerance_pct/100)<=e9<=zone_high*(1+ema_tolerance_pct/100)
    return {
        'signal_time':signal_time.isoformat(),
        'signal_high':float(signal_bar['high']), 'signal_low':float(signal_bar['low']),
        'previous_high':float(previous_bar['high']), 'previous_low':float(previous_bar['low']),
        'fib_50':float(z50), 'fib_618':float(z618), 'fib_zone_low':float(zone_low), 'fib_zone_high':float(zone_high),
        'ema9':float(e9) if e9 is not None else None,
        'ema9_near_fib':bool(ema_near),
        'expires_at':(signal_time+timedelta(minutes=wait_minutes)).isoformat(),
        'status':'PENDING', 'method':None,
    }


def _in_zone(price, lo, hi, tol_pct=0.15):
    pad=max(abs(price)*tol_pct/100, 0.0)
    return lo-pad <= price <= hi+pad


def _structure_state(one_min_bars):
    bars=sorted(one_min_bars,key=lambda x:x['ts'])
    if len(bars)<7:return None
    highs,lows=_pivots(bars[-30:],1,1)
    if len(highs)<2 or len(lows)<2:return None
    # Use the most recent two confirmed highs/lows to classify the pullback structure.
    highs=highs[-3:]; lows=lows[-3:]
    # Need alternating descending lows and highs after the signal, then BOS over the latest LH.
    if len(highs)<2 or len(lows)<2:return None
    lh1=highs[-2][1]; lh2=highs[-1][1]
    ll1=lows[-2][1]; ll2=lows[-1][1]
    return {'lh1':lh1,'lh2':lh2,'ll1':ll1,'ll2':ll2,'lh_lower':lh2<lh1,'ll_lower':ll2<ll1}


def confirm_pullback_bos(setup, one_min_bars, *, zone_tolerance_pct=0.15):
    bars=sorted(one_min_bars,key=lambda x:x['ts'])
    if not bars:return None
    try: expires=datetime.fromisoformat(setup['expires_at'])
    except Exception: expires=None
    for b in bars:
        if expires and b['ts']>expires: break
        if b['ts']<=datetime.fromisoformat(setup['signal_time']): continue
        if not _in_zone(float(b['low']),float(setup['fib_zone_low']),float(setup['fib_zone_high']),zone_tolerance_pct):
            continue
        idx=bars.index(b)
        recent=bars[max(0,idx-8):idx+1]
        st=_structure_state(recent)
        if not st or not (st['lh_lower'] and st['ll_lower']): continue
        if float(b['close'])>float(st['lh2']):
            swing_low=min(x['low'] for x in recent[-5:])
            return {'entry_price':float(b['close']), 'entry_time':b['ts'].isoformat(), 'structure_lh':float(st['lh2']), 'structure_low':float(swing_low), 'method':'FIB_EMA_1M_BOS'}
    return None


def confirm_continuation_bos(setup, one_min_bars):
    bars=sorted(one_min_bars,key=lambda x:x['ts'])
    if len(bars)<5:return None
    try: expires=datetime.fromisoformat(setup['expires_at'])
    except Exception: expires=None
    signal_high=float(setup['signal_high'])
    for i in range(2,len(bars)):
        b=bars[i]
        if b['ts']<=datetime.fromisoformat(setup['signal_time']): continue
        if expires and b['ts']>expires: break
        r=bars[max(0,i-4):i]
        if len(r)<3:continue
        hi=max(x['high'] for x in r); lo=min(x['low'] for x in r)
        tight=(hi-lo)/max(lo,1e-9)*100<=0.8
        if tight and b['close']>max(hi,signal_high):
            return {'entry_price':float(b['close']),'entry_time':b['ts'].isoformat(),'structure_lh':float(hi),'structure_low':float(lo),'method':'CONTINUATION_BOS'}
    return None


def confirmation(setup, one_min_bars, *, mode='PULLBACK_BOS', allow_continuation=True, zone_tolerance_pct=0.15):
    if setup.get('ema9') is not None and not setup.get('ema9_near_fib',False) and mode=='PULLBACK_BOS':
        return None
    if mode in {'PULLBACK_BOS','ADAPTIVE'}:
        r=confirm_pullback_bos(setup,one_min_bars,zone_tolerance_pct=zone_tolerance_pct)
        if r:return r
    if allow_continuation and mode in {'CONTINUATION_BOS','ADAPTIVE'}:
        return confirm_continuation_bos(setup,one_min_bars)
    return None
