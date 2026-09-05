# Strategy E Production V7.4.1

Strategy E is an NSE equity MIS long-only system fed by Chartink webhooks and executed through Zerodha Kite Connect. V7.4 adds delayed 1-minute structure confirmation, shared incremental OHLC caches, feature/risk scoring, and an integrated 5-minute + 1-minute backtest/optimizer.

## V7 additions

Kite session is handled by the existing token/session helper. The app remains local-only by default; expose the Chartink webhook through a Cloudflare HTTPS tunnel or another controlled HTTPS proxy. The readiness and live-gate checks are fail-closed, and the FIRST LIVE template keeps live order arming off.


- Fast pre-trade structural/risk gate: candle-width, entry-to-stop risk and time window.
- Feature score 0-100: EMA alignment, VWAP, relative volume, ADX, ATR%, momentum and candle close location.
- Market regime check using cached NIFTY 50 5-minute bars.
- Higher score threshold for trade #2.
- Break-even/profit-lock before/around 1R.
- Risk-based quantity sizing capped by the existing ₹35,000/position x 5 MIS allocation.
- Daily realized profit lock and loss lock.
- Consecutive-loss circuit breaker.
- Individual trailing stop after the 1R partial.
- ₹4,500 basket activation followed by a trailing basket stop.
- Signal intelligence JSONL store with score, reasons and calculation latency.

## Signal latency architecture

**The live webhook path does not download historical OHLC.** Heavy OHLC acquisition is deliberately separated from signal handling.

The live feature gate reads only an in-memory/local pre-warmed cache. If feature data is not ready:

- `FEATURE_GATE_MODE=SHADOW` (default in FIRST_LIVE_TRADE.env): advanced score is calculated when available but does not block a signal. The fast structural/risk gate still runs.
- `FEATURE_GATE_MODE=ENFORCE`: missing feature cache blocks the trade, which is appropriate only after the feature cache has been operationally proven.
- `FEATURE_GATE_MODE=OFF`: disables advanced feature scoring.

The webhook logs total processing time (`processing_ms`) and feature calculation time (`feature_calc_ms`). CPU-side feature calculations are deterministic and intended to be sub-millisecond to low-millisecond on a normal desktop; the network-bound portion is avoided for historical OHLC.

## OHLC workflow

Before market, pre-warm the symbols in the shared universe into the shared 5-minute feature cache:

```powershell
python run.py prewarm-features --initial-history-days 90
```

The pre-warmer uses Kite historical candles and is read-only: it does not place orders. It runs outside the webhook path. Zerodha documents a 3 requests/second historical-candle limit, so downloading everything at signal time would be a poor architecture. citeturn401345search0turn401345search3

Keep the universe limited to symbols your Chartink screener can actually emit. For live ENFORCE mode, make sure the universe is already cached before the opening bell.

## Backtest

The V7.4 backtester uses 5-minute signal candles plus 1-minute delayed-entry confirmation and models:

- max 2 open positions / max 2 entries per day
- 50% at 1R and remaining 3R target
- break-even/profit-lock
- individual trailing stop
- market-regime and feature-score filters
- EOD flattening

Example:

```powershell
python run.py backtest `
  --signals ".\\data\\chartink_csv\\Backtest Intraday Claude Strategy.csv" `
  --data-dir ".\\data\\backtest_ohlc" `
  --market-data-file ".\\data\\backtest_ohlc\\NIFTY 50_20260801_20260831_5minute.csv" `
  --debug
```

Run the parameter optimizer after the baseline backtest:

```powershell
python run.py optimize `
  --signals ".\\data\\chartink_csv\\Backtest Intraday Claude Strategy.csv" `
  --data-dir ".\\data\\backtest_ohlc" `
  --market-data-file ".\\data\\backtest_ohlc\\NIFTY 50_20260801_20260831_5minute.csv"
```

Optimization should be judged on profit factor, expectancy, drawdown and out-of-sample performance, not win rate alone.

## Important operational rule

Do not turn `FEATURE_GATE_MODE=ENFORCE` or `LIVE_ORDERS_ARMED=true` merely because a backtest looks good. First run the application in PAPER/shadow mode and verify that the live decision latency, feature-cache readiness and order lifecycle behave as expected.

## V7.2 shared runtime architecture

Builds are disposable; credentials and trading data are persistent. New builds use the same shared directories by default on macOS:

- `~/Desktop/algo/kite_credentials/.env`
- `~/Desktop/algo/kite_credentials/.kite_access_token`
- `~/Desktop/algo/strategy_e_shared_data/universe`
- `~/Desktop/algo/strategy_e_shared_data/live_feature_cache`
- `~/Desktop/algo/strategy_e_shared_data/backtest_ohlc`
- `~/Desktop/algo/strategy_e_shared_data/state`
- `~/Desktop/algo/strategy_e_shared_data/logs`

One-time migration from an existing build:

```bash
python run.py setup-shared --source-env "$HOME/Desktop/algo/chatbot/<old-build>/.env"
python run.py setup-shared --migrate-package-data "$HOME/Desktop/algo/chatbot/<old-build>/data"
```

Daily session refresh, when required by Zerodha:

```bash
python run.py kite-login
```

Read-only session verification:

```bash
python run.py session-status
python kite_readonly_check.py
```


## V7.3 production workflow
The shared runtime is persistent across builds. Chartink symbols outside the 400-stock core are auto-enrolled when valid in NSE/Kite and warmed asynchronously. The webhook never waits for a 90-day OHLC download. `python run.py enroll-file FILE` is available for bulk historical recovery.

## V7.3 additions

- `run.py backtest` and `run.py optimize` correctly strip their subcommand before invoking argparse-based modules.
- `run.py enroll-file FILE` validates a batch of Chartink symbols against the NSE/Kite instrument table and enrolls only valid instruments.
- Chartink webhooks validate symbols against the preloaded NSE instruments table, auto-enroll valid symbols, and asynchronously warm their 5-minute OHLC cache. The webhook never waits for a 90-day historical download.
- NSE instruments are preloaded once at startup to avoid a first-signal instruments API call.
- `run.py cache-health` reports universe/cache coverage before a backtest.
- `run.py momentum-rank` creates a transparent local momentum ranking for the prepared universe. The ranking is informational/prioritization only and is not a trading whitelist.
- Backtest automatically uses `NIFTY 50_5minute.csv` beside the supplied data directory when `--market-data-file` is omitted.
- Realized P&L accounting is updated for asynchronously completed manual exits.

## Verification

Before paper/live operation, run:

```bash
python run.py verify
python run_all_tests.py
python production_check.py
python kite_readonly_check.py
python run.py kite-history-test --symbol RELIANCE --interval 5minute --from "2026-09-02T09:15:00" --to "2026-09-02T09:30:00"
```

`verify` is offline and never places orders. The Kite checks are read-only.

## macOS quick start

```bash
source .venv/bin/activate
python run.py session-status
python kite_readonly_check.py
python run.py sync-universe
python run.py update-ohlc --symbols-file "$HOME/Desktop/algo/strategy_e_shared_data/universe/feature_universe.txt" --output-dir "$HOME/Desktop/algo/strategy_e_shared_data/live_feature_cache" --initial-history-days 90
python run.py cache-health --universe "$HOME/Desktop/algo/strategy_e_shared_data/universe/feature_universe.txt" --cache-dir "$HOME/Desktop/algo/strategy_e_shared_data/live_feature_cache"
python run.py momentum-rank --universe "$HOME/Desktop/algo/strategy_e_shared_data/universe/feature_universe.txt" --cache-dir "$HOME/Desktop/algo/strategy_e_shared_data/live_feature_cache" --output-dir "$HOME/Desktop/algo/strategy_e_shared_data/universe" --market-file "$HOME/Desktop/algo/strategy_e_shared_data/live_feature_cache/NIFTY 50_5minute.csv" --top 150
```

Keep `LIVE_ORDERS_ARMED=false` until paper/shadow validation is complete.

## V7.4 delayed entry
Chartink 5-minute signals are setup alerts; production default does not buy immediately. The primary entry waits for the previous 5-minute candle 0.50-0.618 retracement zone with EMA9 proximity, then a confirmed 1-minute LL/LH/LL/LH structure followed by a closed 1-minute close above the latest lower-high. A 20-minute expiry prevents stale entries. Optional adaptive continuation is available.

## 1-minute data
Use `python run.py update-ohlc-1m` to maintain the incremental one-minute cache used for backtesting. The 1-minute cache is stored separately from the 5-minute feature cache so the live feature loader cannot accidentally ingest 1-minute bars. Live confirmation uses in-memory 1-minute bars aggregated from KiteTicker; it does not download historical OHLC from the webhook path.

## Kite historical-data smoke test
This is the quickest way to verify the exact shared-session path used by the OHLC downloader, without placing an order:

```bash
python run.py kite-history-test --symbol RELIANCE --interval 5minute \n  --from "2026-09-02T09:15:00" --to "2026-09-02T09:30:00"
```

A successful result prints `HISTORICAL PASS` and the candle count.
