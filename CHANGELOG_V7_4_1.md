# Strategy E V7.4.1 Fixed Build

This build preserves the V7.4 trading behavior and fixes packaging/runtime inconsistencies found during verification.

## Fixed
- Shared credential environment is authoritative when the shared `.env` exists; a stale package-local `.env` can no longer silently override it.
- Shared token file remains the first-choice access token source.
- Added a read-only `kite-history-test` CLI for the exact historical-data path.
- Added an offline `verify` CLI for compile/import/CLI verification.
- Fixed `update-ohlc-1m --help` parser failure.
- Separated 1-minute OHLC cache from the 5-minute feature cache (`live_1m_cache`) to prevent cross-interval cache contamination.
- Live delayed-entry confirmation now consumes closed 1-minute bars only.
- Standardized IST handling in live 1-minute market-data timestamps and feature-cache loading.
- Fixed V7.4 backtest one-minute file loading (the previous code passed a `Path` where candle rows were expected).
- Added the missing `--stop-buffer-pct` backtest argument.
- Added EOD fallback exit to the V7.4 backtest.
- Aligned V7.4 backtest defaults with the live configuration for score threshold, risk sizing, and break-even trigger.
- Corrected current documentation/template references from 2R to the V7.4 3R final target and removed misleading package-local cache paths.
- Added regression tests for the separate 1-minute cache, 3R target, and incremental 5-minute downloader.

## Verification performed
- Python compileall: PASS
- AST syntax scan: PASS
- Production/core module imports: PASS with dependency smoke stub
- CLI help checks: PASS
- Full regression suite: 124 tests, 124 PASS
- Synthetic V7.4 delayed-entry backtest: PASS
- No live order was placed during verification

Live broker historical-data authentication was separately confirmed on the user's Mac with the shared credentials: `HISTORICAL PASS`, 3 candles returned.
