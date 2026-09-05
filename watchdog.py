
"""Local macOS watchdog for Strategy E.

Safety properties:
- Never enables live trading.
- Never places/modifies/cancels orders.
- Checks application health over localhost.
- Restarts the application only after repeated health failures.
"""
import os, signal, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PORT=int(os.getenv("PORT","8081"))
HEALTH_URL=f"http://127.0.0.1:{PORT}/health"
APP=[sys.executable, str(ROOT/"app.py")]
CHECK_SECONDS=int(os.getenv("WATCHDOG_INTERVAL_SECONDS","10"))
FAIL_THRESHOLD=int(os.getenv("WATCHDOG_FAIL_THRESHOLD","3"))

def healthy():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as r:
            return 200 <= r.status < 300
    except Exception:
        return False

def main():
    # Explicit safety gate: watchdog is never a trading switch.
    if os.getenv("LIVE_ORDERS_ARMED","false").lower()=="true":
        print("REFUSING TO RUN: watchdog cannot be used with LIVE_ORDERS_ARMED=true")
        return 2

    proc=None
    failures=0
    try:
        while True:
            if proc is None or proc.poll() is not None:
                proc=subprocess.Popen(APP, cwd=str(ROOT), env=os.environ.copy())
                failures=0
                time.sleep(3)

            if healthy():
                failures=0
            else:
                failures += 1
                print(f"health failure {failures}/{FAIL_THRESHOLD}", flush=True)
                if failures >= FAIL_THRESHOLD:
                    try: proc.terminate()
                    except Exception: pass
                    try: proc.wait(timeout=10)
                    except Exception:
                        try: proc.kill()
                        except Exception: pass
                    proc=None
                    failures=0
            time.sleep(CHECK_SECONDS)
    except KeyboardInterrupt:
        if proc and proc.poll() is None:
            proc.terminate()
        return 0

if __name__=="__main__":
    raise SystemExit(main())
