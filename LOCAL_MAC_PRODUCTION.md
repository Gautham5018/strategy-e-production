# Local Mac production hardening

## Safety
Keep these values until the final live gate:

```env
MODE=PAPER
TRADING_ENABLED=false
ALLOW_LIVE_ORDERS=false
LIVE_ORDERS_ARMED=false
```

The watchdog refuses to run if `LIVE_ORDERS_ARMED=true`.

## Launchd
1. Ensure the project virtualenv exists at `.venv`.
2. Review `deploy/com.strategyE.trading.plist.template`.
3. Run:
   `bash deploy/install_mac_launchd.sh`
4. Check:
   `launchctl print gui/$(id -u)/com.strategyE.trading`
5. Logs:
   `logs/launchd.out.log`
   `logs/launchd.err.log`
6. Stop:
   `bash deploy/uninstall_mac_launchd.sh`

## Sleep prevention
For a trading session, keep the Mac awake and connected to power.
A launchd service does not make a sleeping Mac trade-capable.

## Watchdog
Run PAPER watchdog manually first:
`python watchdog.py`

It monitors `GET /health` and restarts the app after repeated failures.
It has no order API calls and cannot arm live trading.

## Public webhook tunnel
Keep the public webhook tunnel separate from the trading process. If the tunnel dies, existing positions
must still be handled by the trading engine/reconciliation loop. Do not make ngrok
the source of truth for broker positions.

## Final live prerequisites
- Confirm the Mac's current public IPv4 matches the static IP registered with Kite.
- Do not rely on a changing Wi-Fi/public IP.
- Keep `MARKET_PROTECTION` non-zero for API market orders.
- Test a controlled live order only after all production gates pass.
