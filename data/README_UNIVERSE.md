# Strategy E universe + OHLC cache

The authoritative production universe lives outside the build under:

`~/Desktop/algo/strategy_e_shared_data/universe/feature_universe.txt`

Core universe: official Nifty MidSmallcap 400 plus NIFTY 50. Dynamic universe: any valid NSE symbol emitted by Chartink is auto-enrolled without restricting the signal to the core 400.

The live 5-minute cache lives under:

`~/Desktop/algo/strategy_e_shared_data/live_feature_cache`

The first download builds the configured history. Later updates are incremental and append only missing/overlapping candles with deduplication. Historical acquisition is never performed synchronously in the Chartink webhook.


## Shared cache layout
- 5-minute feature cache: `~/Desktop/algo/strategy_e_shared_data/live_feature_cache`
- 1-minute delayed-entry/backtest cache: `~/Desktop/algo/strategy_e_shared_data/live_1m_cache`
The 1-minute cache is intentionally separate from the 5-minute feature cache.
