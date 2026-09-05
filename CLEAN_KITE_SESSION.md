# Clean Kite Session Setup

This package fixes the previous environment-loading ambiguity. Every Kite helper explicitly reads:
`<package>/strategy_e_production_v1/.env`.

## Start clean
```bash
cd /Users/gauthamk/Desktop/algo/chatbot/strategy_e_production_v6_clean_kite_session/strategy_e_production_v1
source /Users/gauthamk/Desktop/algo/chatbot/.venv/bin/activate
./clean_start.sh
```

The script preserves the existing `.env` and makes a timestamped backup. It only unsets Kite variables in the current shell; it does not delete credentials.

## Generate today's Kite session
```bash
python kite_session.py
```
Open the printed login URL, complete Zerodha login/2FA, copy the fresh `request_token` from the redirect, and paste it at the prompt.

The helper uses the API key + API secret from the package `.env`, calls `generate_session`, verifies `profile()` immediately, and writes the new `KITE_ACCESS_TOKEN` into the same `.env`.

## Verify before app
```bash
python kite_readonly_check.py
```
Expected: Profile, NSE instrument, LTP, Positions and Order book PASS.

## Run regression suite
```bash
python run_all_tests.py
```

## Start server
```bash
uvicorn app:app --host 127.0.0.1 --port 8081
```

Then from another terminal:
```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8081/readiness
curl http://127.0.0.1:8081/live-gate
```

For the first live trade, `/live-gate` must be allowed only after all configured gates pass.

## Safety
Never paste API key, API secret, access token, request token, Chartink token, or admin token into chat.
No live order is placed by `kite_session.py` or `kite_readonly_check.py`.
