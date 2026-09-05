from config import SETTINGS
from live_feature_gate import LiveFeatureGate
from models import Signal

class RiskManager:
    def __init__(self, store, broker, feature_gate=None):
        self.store=store; self.broker=broker; self.feature_gate=feature_gate

    def validate_signal(self, signal: Signal, reference_price=None, trade_number=None):
        s=SETTINGS; now=signal.signal_time; day=now.date().isoformat()
        if s.kill_switch or not s.trading_enabled:return False,"TRADING_DISABLED"
        if s.mode=="LIVE" and not s.allow_live_orders:return False,"LIVE_ORDERS_NOT_ARMED"
        if now.time()<s.trading_start or now.time()>s.trading_end:return False,"OUTSIDE_TRADING_WINDOW"
        entries=self.store.entry_count(day)
        if entries>=s.max_entries_per_day:return False,"MAX_ENTRIES_PER_DAY"
        if len(self.store.positions())+len(self.store.pending_entries())>=s.max_open_positions:return False,"MAX_OPEN_POSITIONS"
        if signal.signal_candle_pct>s.max_signal_candle_pct:return False,"SIGNAL_CANDLE_OVER_LIMIT"
        if signal.signal_low<=0 or signal.signal_high<signal.signal_low:return False,"INVALID_SIGNAL_OHLC"
        if signal.symbol in self.store.positions():return False,"SYMBOL_ALREADY_OPEN"
        if now.time()>s.first_signal_cutoff and entries==0:return False,"FIRST_SIGNAL_CUTOFF"
        if self.store.consecutive_losses()>=s.max_consecutive_losses:return False,"CONSECUTIVE_LOSS_LOCK"
        if s.daily_profit_lock_enabled and self.store.daily_realized_pnl(day)>=s.daily_profit_lock_inr:return False,"DAILY_PROFIT_LOCK"
        if s.daily_loss_limit_enabled and self.store.daily_realized_pnl(day)<=-s.daily_loss_limit_inr:return False,"DAILY_LOSS_LOCK"
        if reference_price is not None:
            risk=max(float(reference_price)-float(signal.signal_low),0.0)
            if risk<=0:return False,"REFERENCE_PRICE_AT_OR_BELOW_SIGNAL_LOW"
            if (risk/float(reference_price))*100.0>s.max_entry_risk_pct:return False,"ENTRY_RISK_OVER_LIMIT"
        return True,"OK"

    def feature_check(self, signal, entry_price, trade_number=1, market_bars=None):
        if SETTINGS.feature_gate_mode=="OFF" or not self.feature_gate:return True,"FEATURE_GATE_OFF",None
        g=self.feature_gate.evaluate(signal,entry_price,trade_number=trade_number,market_bars=market_bars)
        return g.passed, (g.reason or ("FEATURE_SCORE_%s"%g.score)), g.snapshot

    def quantity(self, entry_price, signal_low=None):
        s=SETTINGS
        cap_qty=int((s.trade_capital_per_position*s.mis_leverage)//entry_price)
        if not s.risk_based_sizing_enabled or signal_low is None:return cap_qty
        risk=max(float(entry_price)-float(signal_low),0.0)
        if risk<=0:return 0
        risk_qty=int(s.risk_per_trade_inr//risk)
        return min(cap_qty,risk_qty)
