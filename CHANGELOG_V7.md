# Strategy E V7.1

## Universe and OHLC architecture
- Core universe is the official Nifty MidSmallcap 400 constituent set.
- Any valid NSE symbol arriving from Chartink is dynamically auto-enrolled, even outside the core 400.
- Incremental 5-minute OHLC cache: first run downloads 90 days by default; later runs append only missing/overlapping candles with de-duplication and atomic file replacement.
- Historical data acquisition is outside the Chartink webhook/order path.
- `python run.py sync-universe` refreshes the core 400 list.
- `python run.py update-ohlc --symbols-file data/feature_universe.txt` maintains the cache.

## Safety / trading logic
- Strategy E V6.6/V7 entry, trailing-stop, basket-trailing and live-gate behavior retained.
- Feature gate remains SHADOW by default until cache readiness and latency are proven operationally.

### V7.1.1 hotfix
- Added `KiteBroker.historical_data()` read-only wrapper required by incremental 5-minute OHLC and historical backtest downloaders.
- No order APIs were added or changed.
