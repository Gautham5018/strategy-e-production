
# Final LIVE Qualification — Strategy E

## Current strategy contract

- Strategy: E only
- Capital: ₹70,000
- Two parallel positions maximum
- ₹35,000 allocation per position
- No compounding
- MIS
- NSE
- 50% quantity exits at 1R
- Remaining 50% exits at 3R
- New entries only within configured window
- First-entry cutoff 09:35
- Maximum signal candle 8%
- Static Kite IP already configured

## Independent live gate

Live broker order APIs are blocked unless ALL conditions are true:

1. `MODE=LIVE`
2. `TRADING_ENABLED=true`
3. `ALLOW_LIVE_ORDERS=true`
4. `LIVE_ORDERS_ARMED=true`
5. `KILL_SWITCH=false`
6. `LIVE_TRADING_ACK=I_UNDERSTAND_LIVE_TRADING_RISK`
7. `KITE_STATIC_IP_VERIFIED=true`
8. `PRODUCTION_ENVIRONMENT=LOCAL_MAC`

A single missing condition blocks the broker order call.

## Recommended first live qualification

Do NOT use the full ₹35,000 allocation for the first live qualification.

Use the smallest broker-valid quantity and a controlled symbol, then verify:

- entry order ID
- exchange/tradingsymbol
- requested quantity
- completed fill quantity
- average fill price
- order status
- local state
- Kite positions
- reconciliation
- exit order
- completed exit fill
- final position = zero

Only after this succeeds should normal Strategy E allocation be enabled.

## Before arming

Run:

```bash
python run_all_tests.py
python production_check.py
python kite_readonly_check.py
python session_status.py
```

Then:

```bash
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8081/readiness
curl http://127.0.0.1:8081/live-gate
```

The live gate must remain blocked until the explicit qualification window.

## Emergency controls

Keep these immediately available:

```bash
export KILL_SWITCH=true
```

and use the application's reconciliation/admin controls to verify broker state.

Do not rely on terminating the Python process as an emergency flatten mechanism;
process termination must not be considered proof that the broker position is flat.

## Go/No-Go

GO only when:
- Kite authentication succeeds from the Mac
- registered public IP is confirmed
- readiness is healthy
- reconciliation is clean
- live gate explicitly reports allowed
- the first controlled order is fully reconciled
- the resulting broker position is zero

Otherwise NO-GO.
