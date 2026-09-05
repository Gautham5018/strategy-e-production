
# Strategy E V4 — Paper Session Rehearsal

This phase validates the complete local request-to-position lifecycle without
placing a real Kite order.

## Safety
Keep:
- `MODE=PAPER`
- `TRADING_ENABLED=false` for the actual production `.env`
- `ALLOW_LIVE_ORDERS=false`
- `LIVE_ORDERS_ARMED=false`

The automated rehearsal uses an isolated PAPER configuration and a fake broker.

## Automated test
```bash
python run_all_tests.py
```

The suite includes:
- Chartink webhook authentication
- Chartink payload parsing
- two simultaneous positions
- duplicate webhook idempotency
- invalid candle rejection
- Strategy E 50% at 1R + 50% at 2R
- state persistence/restart recovery
- third-entry rejection

## Operational Mac rehearsal
1. Start the application in PAPER mode.
2. Confirm `/health` returns `200`.
3. Confirm `/readiness` is healthy.
4. Keep the public webhook tunnel running only when testing webhook delivery.
5. Send a controlled Chartink webhook.
6. Confirm the application accepts the signal.
7. Confirm the position appears in local state.
8. Simulate/observe 1R and verify 50% exit.
9. Simulate/observe 2R and verify remaining 50% exit.
10. Restart the application with an open position.
11. Confirm state recovery and reconciliation.
12. Do not enable live orders.

## Important
Do not test a real live order in this phase. The next phase is a dedicated
LIVE ORDER qualification with a very small controlled quantity and explicit
kill/flatten checks.
