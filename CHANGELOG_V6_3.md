# Strategy E V6.3

- Production exit policy updated to 50% at 1R, remaining 50% at 3R.
- Added 90-minute post-partial stagnation exit with configurable 0.20% progress threshold.
- Added per-symbol manual exit API.
- Added manual flatten-all API.
- Added browser control console at `/`.
- Added unified CLI control through `run.py`.
- Manual exit gets a dedicated live-exit gate so emergency exits are not blocked by the normal entry kill switch.
- Manual exits are serialized per symbol and marked `manual_exit_pending` so the automatic monitor does not duplicate an exit.
- Added pending manual-exit reconciliation and recovery.
- Secured admin position endpoint with `X-Admin-Token`.
- Added V6.3 manual-control tests.
