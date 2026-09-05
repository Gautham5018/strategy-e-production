# Strategy E V7.3

## Production hardening
- Shared credentials/data remain build-independent.
- `run.py backtest` and `run.py optimize` now correctly pass subcommand arguments.
- Added `run.py enroll-file FILE` with read-only NSE/Kite validation.
- Chartink webhook auto-validates valid NSE symbols, enrolls them dynamically, and starts asynchronous OHLC warm-up without blocking the signal/order path.
- NSE instrument list is preloaded at application startup so first-signal symbol resolution is local/fast.
- Backtest auto-discovers `NIFTY 50_5minute.csv` beside the supplied data directory when `--market-data-file` is omitted.
- Unknown signal stocks never trigger a full historical download inside the webhook request.

## Live safety
- Advanced feature gate remains configurable. Use `SHADOW` while validating data completeness; use `ENFORCE` only after paper validation.
- Live orders remain explicitly gated.
