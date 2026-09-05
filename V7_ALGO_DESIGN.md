# Strategy E V7 algorithm design

## Live decision path

Chartink webhook -> fast structural validation -> one LTP lookup for valid symbols -> feature gate from local cache -> MARKET order.

The webhook path deliberately does **not** call Kite historical_data. This prevents a slow network request from sitting between the signal and the order.

### Fast gate
- trading window
- max daily entries
- max open positions
- duplicate stock
- first-signal cutoff
- signal candle width
- entry-to-stop risk percentage
- daily realized P&L locks
- consecutive-loss lock

### Cached feature score
The score is computed over cached 5-minute bars already present in memory/local disk:
- EMA 9/20 trend alignment
- VWAP relationship
- relative volume
- ADX 14
- ATR percentage
- 3-bar momentum
- candle close location
- entry risk percentage
- NIFTY 50 regime
- time-of-day window

No feature should cause an API request during webhook processing.

## Profit protection
- 50% exit at 1R
- break-even/profit-lock around 0.8R
- remaining 50% gets a ratcheting trail after the partial
- final target remains 3R
- basket activates at ₹4,500 and trails the combined P&L
- daily profit lock prevents new entries after ₹6,000 realized
- daily loss lock prevents continued trading after -₹7,000 realized/open combined guard
- two consecutive losses lock new entries

## Sizing
The original ₹35,000 per-position allocation remains the hard notional cap. Risk-based sizing is implemented as an optional lower cap and is disabled in the first-live template. Turn it on only after backtesting confirms that lower quantity on wide-stop trades improves expectancy/drawdown.

## Backtest / optimizer
The backtester uses 5-minute OHLCV and next-candle-open entries. The optimizer varies the thresholds and protection parameters. The portfolio basket is still a conservative approximation when only candle closes are available because live execution uses tick/LTP timing.

Use chronological train/test or walk-forward splits before promoting a parameter set to live. Avoid selecting a model solely by highest win rate.
