# Strategy E V6.3 Manual Control

## Browser interface
Start the application with `python run.py start`, then open `http://127.0.0.1:8081/`.
Enter `ADMIN_TOKEN` in the page to enable Reconcile, Exit and Flatten All.

Manual exit is isolated per symbol. The position is marked `manual_exit_pending` so the automatic monitor will not submit another exit for the same position. The application continues running. Pending manual exits are monitored and reconciled; rejected/cancelled manual exits are returned to normal management.

## CLI interface
The same `run.py` entry point handles operational commands:

```bash
python run.py start
python run.py status
python run.py readiness
python run.py gate
python run.py positions
python run.py reconcile
python run.py exit TBZ --confirm
python run.py exit TBZ --confirm --reason "Operator requested exit"
python run.py flatten --confirm
python run.py kill
```

`exit` and `flatten` are intentionally protected by `--confirm`.

## Current production candidate
- Initial stop: signal candle low
- 50% exit: 1R
- Remaining target: 3R
- Post-partial stagnation: 90 minutes
- Stagnation threshold: 0.20% progress beyond the partial exit price
- End-of-day flatten: 15:00

Environment:
```env
FINAL_R_MULTIPLE=3.0
POST_PARTIAL_TIME_STOP_MINUTES=90
POST_PARTIAL_STAGNATION_PCT=0.20
```
