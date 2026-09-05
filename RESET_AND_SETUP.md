# Strategy E V7.2 — Shared Runtime Setup

V7.2 separates the replaceable application build from persistent Kite credentials, access-token state, OHLC cache, universe and runtime state.

Default shared locations on macOS:

```text
~/Desktop/algo/kite_credentials/
    .env                 # API credentials + Strategy E runtime settings
    .kite_access_token   # daily access token, mode 600

~/Desktop/algo/strategy_e_shared_data/
    universe/
    live_feature_cache/
    backtest_ohlc/
    state/
    logs/
```

A package-local `.env` remains supported for backward compatibility, but new builds do not require one.

## One-time setup

If you already have a working older Strategy E `.env`, migrate it once:

```bash
python run.py setup-shared --source-env "$HOME/Desktop/algo/chatbot/<old-strategy-folder>/.env"
```

If the shared `.env` already exists, it is preserved.

You can also migrate existing data once:

```bash
python run.py setup-shared \
  --migrate-package-data "$HOME/Desktop/algo/chatbot/<old-strategy-folder>/data"
```

## Daily Kite session

Use:

```bash
python run.py kite-login
```

The generated access token is stored in the shared token file. Future builds reuse it automatically until Zerodha requires a fresh session.

Check the session without placing orders:

```bash
python run.py session-status
python kite_readonly_check.py
```

## New build behavior

Extracting V7.3/V7.4/etc. should not require copying credentials, recreating `.env`, or redownloading the existing OHLC cache. Point every build at the same shared directories, or keep the defaults above.
