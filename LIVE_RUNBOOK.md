# Strategy E Live Runbook — Local Mac

Project path:
`/Users/gauthamk/Desktop/LIVE/strategy_e_production_v6`

## Every trading day

### 1. Enter the project
```bash
cd /Users/gauthamk/Desktop/LIVE/strategy_e_production_v6
source .venv/bin/activate
```

### 2. Remove stale shell Kite variables
```bash
unset KITE_API_KEY KITE_API_SECRET KITE_ACCESS_TOKEN
```

### 3. Generate today's Kite session
```bash
python kite_session.py
```

### 4. Verify Kite read-only access
```bash
python kite_readonly_check.py
```

### 5. Run production preflight and full tests
```bash
python production_check.py
python run_all_tests.py
```

### 6. Start Strategy E
```bash
python run.py
```

### 7. Verify health/readiness/gate
```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8081/readiness
curl http://127.0.0.1:8081/live-gate
```

For LIVE trading, require:
- `/readiness` -> `ready: true`
- `/live-gate` -> `allowed: true`

### 8. Start the public webhook tunnel
```bash
cloudflared tunnel --url http://127.0.0.1:8081
```

Chartink webhook format:
```text
https://<public-host>/chartink/webhook/<CHARTINK_WEBHOOK_TOKEN>
```

### 9. Monitor logs
```bash
tail -f logs/strategy_e.log
```

### 10. First-live qualification
Use `MAX_ENTRIES_PER_DAY=1` initially.
Do not proceed when readiness is false, reconciliation is not clean, or Kite authentication fails.

### 11. After trading
Confirm:
- no open Strategy E positions remain;
- Kite positions are flat for the Strategy E symbols;
- reconciliation is clean;
- logs show final square-off/reconciliation.

## Locking the Mac
The display can be locked. The Mac must not sleep during market hours.

## Emergency
Do not assume stopping the Python process closes broker positions. Verify Kite positions/order book first. Use `KILL_SWITCH=true` in `.env` to block future entries, then reconcile/flatten any open broker position through the controlled process.
