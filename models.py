from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Signal:
    symbol: str
    signal_time: datetime
    signal_open: float
    signal_high: float
    signal_low: float
    signal_close: float
    source: str = "chartink"
    webhook_id: str = ""

    @property
    def signal_candle_pct(self) -> float:
        if self.signal_low <= 0:
            return 999.0
        return (self.signal_high - self.signal_low) / self.signal_low * 100.0

@dataclass
class PositionState:
    symbol: str
    instrument_token: int
    signal_time: datetime
    entry_order_id: str
    entry_price: float
    entry_quantity: int
    remaining_quantity: int
    signal_low: float
    risk_per_share: float
    one_r: float
    two_r: float
    partial_quantity: int
    final_quantity: int
    partial_exit_order_id: Optional[str] = None
    final_exit_order_id: Optional[str] = None
    partial_filled: int = 0
    final_filled: int = 0
    status: str = "OPEN"
    opened_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    partial_exit_filled_at: Optional[str] = None
    partial_exit_price: Optional[float] = None
    max_price_since_partial: Optional[float] = None
    manual_exit_pending: bool = False
    manual_exit_order_id: Optional[str] = None
    manual_exit_requested: int = 0
    manual_exit_filled: int = 0
    manual_exit_reason: Optional[str] = None
    realized_pnl: float = 0.0
    trailing_stop_price: Optional[float] = None
    trailing_stop_active: bool = False
    portfolio_profit_target_triggered: bool = False
    feature_score: Optional[float] = None
    feature_grade: Optional[str] = None
    entry_risk_pct: Optional[float] = None
    break_even_stop_price: Optional[float] = None
    initial_stop_price: Optional[float] = None
    entry_method: Optional[str] = None
    entry_confirmation_time: Optional[str] = None
    fib_50: Optional[float] = None
    fib_618: Optional[float] = None
    break_even_active: bool = False

    def to_dict(self):
        return self.__dict__.copy()
