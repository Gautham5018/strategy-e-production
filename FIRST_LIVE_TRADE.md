# Controlled First Live Trade

This package is configured for a **single live entry only**.

## Risk limits

- Total capital: ₹70,000
- Normal Strategy E slot: ₹35,000
- Maximum open positions: 2 (architecture requirement)
- **Maximum entries today: 1**
- MIS
- NSE
- 50% at 1R
- 50% at 1R; remaining 50% at 3R
- Signal candle <= 8%
- First signal cutoff: 09:35
- Trading window: 09:15–15:00

Because `MAX_ENTRIES_PER_DAY=1`, after the first accepted live entry,
no second entry can be accepted that day even if the first trade exits.

## Before enabling

1. Confirm the Mac's current public IP is the IP already registered in Kite.
2. Confirm `kite_readonly_check.py` passes.
3. Confirm `python run_all_tests.py` passes.
4. Confirm `production_check.py` passes.
5. Confirm `/health`, `/readiness`, and `/live-gate` work.
6. Start with no open broker positions.
7. Confirm the strategy receives the intended Chartink signal.
8. Keep the first live test to ONE entry only.

## Apply configuration

Do not replace your existing `.env` blindly because it contains secrets.

Merge the values from:

`FIRST_LIVE_TRADE.env`

into your existing `.env`, preserving your existing:
- KITE_API_KEY
- KITE_API_SECRET
- KITE_ACCESS_TOKEN
- CHARTINK_WEBHOOK_TOKEN
- ADMIN_TOKEN

Then restart the application so the new environment is loaded.

## Verify the gate before a signal

```bash
curl http://127.0.0.1:8081/live-gate
```

It must report:

```json
{"allowed": true, "reasons": []}
```

If it reports anything else, **do not trade**.

## First-trade procedure

1. Start `python run.py`.
2. Start the configured public webhook tunnel (Cloudflare Tunnel is recommended).
3. Confirm Chartink webhook URL.
4. Confirm `/live-gate` is allowed.
5. Let ONE valid Chartink signal arrive.
6. Verify the order in Kite.
7. Verify completed quantity and average fill.
8. Verify local position state.
9. Verify broker/local reconciliation is CLEAN.
10. Allow Strategy E to manage 1R/3R exits.
11. Verify final broker quantity is zero.
12. Verify local position is removed.
13. Verify reconciliation is CLEAN.
14. Immediately disable live trading after the qualification.

## Stop conditions

Do not continue if:
- order remains OPEN beyond the configured timeout;
- completed fill quantity differs from requested quantity unexpectedly;
- average fill price is missing/invalid;
- local state and Kite positions disagree;
- reconciliation is not CLEAN;
- LTP is stale;
- unexpected second entry is attempted;
- any emergency/kill condition occurs.

## Emergency kill

Set:

```bash
export KILL_SWITCH=true
```

and restart the application if required.

Do not assume stopping Python flattens a broker position. Always verify Kite
positions/order book and reconcile.

## Important

This is a controlled qualification, not a guarantee of profitability.
A market order can fill at a different price from the signal/reference price,
and slippage can change the realized R multiple.
