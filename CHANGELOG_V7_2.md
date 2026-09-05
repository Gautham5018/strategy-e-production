# Strategy E V7.2

## Build-independent runtime architecture

- Persistent Kite credentials moved to a shared directory outside the application build.
- Daily access token stored in a separate 600-permission token file.
- Package-local `.env` remains backward compatible but is no longer required for new builds.
- Added `python run.py setup-shared` for one-time migration of an existing `.env` and existing data.
- Added `python run.py kite-login` and `python run.py session-status` using the shared credential store.
- Token file is authoritative when present, preventing a stale `KITE_ACCESS_TOKEN` value in an older `.env` from overriding the current session.

## Persistent shared data

- Universe, live 5-minute feature cache, backtest OHLC, state and logs can live outside the replaceable build.
- Incremental OHLC defaults to the shared cache and continues to append/deduplicate missing candles.
- Backtest historical downloads default to shared `backtest_ohlc` storage.

## Safety

- `kite-login`, `kite_readonly_check.py`, and setup commands contain no order APIs.
- Live gates remain explicit and independent.
- No production secrets are included in the ZIP.


### V7.2.1 hotfix
- Deferred the Kite `profile()` call during `KiteBroker` construction so read-only OHLC prewarming does not depend on an unnecessary profile request.
- Added short retry/backoff handling for profile and NSE instruments API calls to tolerate transient connection resets.
- No order semantics or live-entry rules changed.
