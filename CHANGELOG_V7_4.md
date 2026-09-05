# Strategy E V7.4

## Delayed entry engine
- Chartink 5-minute signal is a setup, not an immediate buy.
- Primary method: previous 5-minute candle 0.50-0.618 retracement + EMA9 proximity + closed 1-minute LL/LH/LL/LH sequence + close above latest LH.
- Optional adaptive continuation breakout fallback.
- Default confirmation window: 20 minutes.
- Entry risk is calculated from the confirmed structure stop and checked at actual entry.
- Live path never downloads historical data in the webhook. Missing history is warmed asynchronously.

## Data
- Added incremental 1-minute OHLC cache using Kite `minute` interval.
- 5-minute cache remains incremental/shared.

## Backtest
- `run.py backtest` now invokes the V7.4 event-driven entry backtester.
- V7.4 backtest requires a 1-minute cache directory in addition to 5-minute data.

- Optimizer now compares delayed-entry modes and entry timing/tolerance parameters.
