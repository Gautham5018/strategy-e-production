"""Fast live signal gate.

No historical-data API calls are made here. Advanced features are evaluated only
from a pre-warmed in-memory/local cache. When cache is unavailable, the default
FAST_BASELINE mode preserves signal latency rather than blocking on OHLC download.
"""
from dataclasses import dataclass
from feature_engine import score_trade
from config import SETTINGS

@dataclass
class GateResult:
    passed: bool
    mode: str
    score: float = 0.0
    grade: str = 'NA'
    reason: str = ''
    snapshot: dict = None

class LiveFeatureGate:
    def __init__(self, cache=None):
        self.cache=cache
    def evaluate(self, signal, entry_price, trade_number=1, market_bars=None):
        mode=SETTINGS.feature_gate_mode.upper()
        # Always-fast structural/risk gate first.
        risk=max(float(entry_price)-float(signal.signal_low),0.0)
        risk_pct=(risk/max(float(entry_price),1e-9))*100.0
        if risk<=0:return GateResult(False,mode,reason='INVALID_RISK')
        if risk_pct>SETTINGS.max_entry_risk_pct:return GateResult(False,mode,reason='ENTRY_RISK_OVER_LIMIT')
        bars=self.cache.get(signal.symbol) if self.cache else []
        if self.cache is not None:
            bars.append({'ts':signal.signal_time,'open':signal.signal_open,'high':signal.signal_high,'low':signal.signal_low,'close':signal.signal_close,'volume':0.0})
            bars=sorted({b['ts']:b for b in bars}.values(),key=lambda x:x['ts'])[-max(SETTINGS.feature_min_bars,60):]
        snap=None
        if len(bars)>=SETTINGS.feature_min_bars:
            snap=score_trade(symbol=signal.symbol,signal_time=signal.signal_time,signal_open=signal.signal_open,signal_high=signal.signal_high,
                             signal_low=signal.signal_low,signal_close=signal.signal_close,entry_price=entry_price,bars=bars,market_bars=market_bars,
                             max_risk_pct=SETTINGS.max_entry_risk_pct,min_adx=SETTINGS.feature_min_adx,min_relative_volume=SETTINGS.feature_min_relative_volume,
                             min_atr_pct=SETTINGS.feature_min_atr_pct,max_atr_pct=SETTINGS.feature_max_atr_pct,score_threshold=SETTINGS.feature_score_threshold,
                             market_filter=SETTINGS.market_regime_filter)
        if snap is None:
            if mode=='ENFORCE': return GateResult(False,mode,reason='FEATURE_CACHE_NOT_READY')
            return GateResult(True,mode,reason='FAST_BASELINE_FALLBACK')
        threshold=SETTINGS.feature_trade2_score_threshold if trade_number>=2 else SETTINGS.feature_score_threshold
        passed=snap.score>=threshold and snap.market_regime_ok and snap.time_window_ok and snap.risk_ok
        if mode=='SHADOW': passed=True
        return GateResult(passed,mode,float(snap.score),snap.grade,';'.join(snap.reasons),snap.to_dict())
