# Strategy E V6.6

## Basket Profit Target -> Trailing
- ₹4,500 is now the basket trailing activation level when 2 positions are open.
- The system no longer exits both positions immediately at ₹4,500.
- At activation the basket stop protects ₹4,500.
- Basket peak P&L is tracked and the stop ratchets upward at a configurable ₹1,000 default distance.
- Basket trailing state is persisted in `state/state.json` to survive app restarts.
- Basket exit reason is `PORTFOLIO_TRAILING_STOP`.
- Integrated 5-minute backtester models the same activation/trailing logic conservatively on common 5-minute closes.

## Safety
- Live basket trailing is software/LTP driven, not an exchange-resident stop order.
- Validate in paper trading before enabling live orders.
