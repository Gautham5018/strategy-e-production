# Strategy E V6.5

- Added post-1R trailing stop with upward-only ratchet.
- Added ₹4,500 two-position basket profit lock.
- Added configurable open-basket loss guard.
- Added realized P&L tracking on position exit fills for basket calculations.
- Added 5-minute Kite historical downloader to the production package.
- Added production-equivalent 5-minute Strategy E backtest with CSV/JSON/HTML reporting.
- Added `run.py pull-5m` and `run.py backtest` commands.
- Backtest uses next 5-minute open and conservative no-lookahead trailing logic.
- Manual exit remains independent from automatic strategy exits.
