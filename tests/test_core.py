
from datetime import datetime
from models import Signal
from config import SETTINGS

s=Signal("TEST",datetime(2026,8,24,9,15),100,101,99,100)
assert abs(s.signal_candle_pct-2.0202020202)<1e-6
risk=100-s.signal_low
assert risk==1
assert 100+risk==101
assert 100+2*risk==102
assert SETTINGS.max_open_positions==2
assert SETTINGS.total_capital==70000
assert SETTINGS.trade_capital_per_position==35000
print("CORE TESTS PASS")
