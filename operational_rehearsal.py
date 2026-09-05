
"""Controlled PAPER operational rehearsal.

This never enables live trading and never calls broker order APIs.
It validates the local runtime components that will be used during a session.
"""
import os, sys, json, time, urllib.request
from pathlib import Path
from config import DATA_DIR
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
IST=ZoneInfo("Asia/Kolkata")
PORT=int(os.getenv("PORT","8081"))
HEALTH=f"http://127.0.0.1:{PORT}/health"

def check(label, fn):
    try:
        value=fn()
        print(f"PASS | {label} | {value}")
        return True
    except Exception as e:
        print(f"FAIL | {label} | {e}")
        return False

def main():
    print("="*72)
    print("STRATEGY E V3 LOCAL MAC OPERATIONAL REHEARSAL")
    print("="*72)
    print("TIME:",datetime.now(IST).isoformat())
    print("MODE:",os.getenv("MODE","PAPER"))
    print("LIVE_ORDERS_ARMED:",os.getenv("LIVE_ORDERS_ARMED","false"))
    print("TRADING_ENABLED:",os.getenv("TRADING_ENABLED","false"))
    print()

    # Hard safety gates.
    if os.getenv("MODE","PAPER").upper()=="LIVE":
        raise SystemExit("FAIL | MODE must remain PAPER for operational rehearsal")
    if os.getenv("LIVE_ORDERS_ARMED","false").lower()=="true":
        raise SystemExit("FAIL | LIVE_ORDERS_ARMED must remain false")
    if os.getenv("ALLOW_LIVE_ORDERS","false").lower()=="true":
        raise SystemExit("FAIL | ALLOW_LIVE_ORDERS must remain false")

    results=[]
    results.append(check("IST clock",lambda: datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z")))

    def health():
        with urllib.request.urlopen(HEALTH,timeout=3) as r:
            if r.status != 200: raise RuntimeError(f"HTTP {r.status}")
            return "HTTP 200"
    results.append(check("Application health",health))

    def state():
        p=DATA_DIR/"state"
        p.mkdir(exist_ok=True)
        return f"{p} writable={os.access(p,os.W_OK)}"
    results.append(check("State directory",state))

    def logs():
        p=DATA_DIR/"logs"
        p.mkdir(exist_ok=True)
        test=p/".rehearsal_write_test"
        test.write_text("ok")
        test.unlink()
        return "writable"
    results.append(check("Log directory",logs))

    if not all(results):
        raise SystemExit(1)

    print()
    print("="*72)
    print("OPERATIONAL REHEARSAL PRECHECK: PASS")
    print("NO LIVE ORDER WAS PLACED")
    print("="*72)

if __name__=="__main__":
    main()
