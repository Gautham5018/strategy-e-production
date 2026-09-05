# Strategy E V7.4 Backtesting

The V7.4 backtest reproduces the delayed-entry decision path: a Chartink 5-minute setup is followed by 1-minute confirmation. It is read-only and never places broker orders.

## Data

The engine requires:
- 5-minute OHLCV for the signaled symbol.
- 1-minute OHLCV for delayed-entry confirmation and post-entry exits.
- Optional NIFTY 50 5-minute context for the feature/regime score.

Maintain the caches with:

```bash
python run.py update-ohlc --symbols-file "$HOME/Desktop/algo/strategy_e_shared_data/universe/feature_universe.txt" --output-dir "$HOME/Desktop/algo/strategy_e_shared_data/live_feature_cache" --initial-history-days 90
python run.py update-ohlc-1m --symbols-file "$HOME/Desktop/algo/strategy_e_shared_data/universe/feature_universe.txt" --output-dir "$HOME/Desktop/algo/strategy_e_shared_data/live_1m_cache" --initial-history-days 60
```

The 1-minute cache is deliberately separate from the 5-minute feature cache.

## V7.4 entry

- Chartink 5-minute signal creates a pending setup; it is not an immediate buy.
- Primary `PULLBACK_BOS`: previous 5-minute 0.50-0.618 retracement zone + EMA9 proximity, then confirmed 1-minute lower-high/lower-low structure and a close above the latest lower-high.
- `CONTINUATION_BOS` and `ADAPTIVE` are available for research/optimization.
- Default confirmation window is 20 minutes.
- Entry stop/risk is calculated only after confirmation.

## V7.4 exit model

- 50% at 1R.
- Remaining 50% at 3R.
- Break-even/profit-lock and trailing stop are configurable.
- 90-minute / 0.20% stagnation rule applies after the partial exit.
- EOD fallback exits at the final available 1-minute close when no earlier exit occurs.

The V7.4 backtest intentionally does not claim exact intrabar equivalence for live tick-triggered exits, basket locks, or daily circuit-breakers unless those are explicitly added to the backtest model.

## Example

```bash
python run.py backtest \
  --signals "$HOME/path/to/chartink_signals.csv" \
  --data-dir "$HOME/Desktop/algo/strategy_e_shared_data/live_feature_cache" \
  --one-minute-dir "$HOME/Desktop/algo/strategy_e_shared_data/live_1m_cache"
```

## Optimizer

```bash
python run.py optimize \
  --signals "$HOME/path/to/chartink_signals.csv" \
  --data-dir "$HOME/Desktop/algo/strategy_e_shared_data/live_feature_cache" \
  --one-minute-dir "$HOME/Desktop/algo/strategy_e_shared_data/live_1m_cache"
```

Judge configurations using profit factor, expectancy, drawdown, trade count, and out-of-sample stability—not win rate alone.
