#!/usr/bin/env python3
"""Read-only Kite qualification. No order API is used."""
from datetime import datetime
from kiteconnect import KiteConnect
from env_loader import load_env, ENV_FILE, SHARED_ENV_FILE
from shared_paths import KITE_ACCESS_TOKEN_FILE
from config import SETTINGS


def fail(msg):
    print(f"FAIL | {msg}")
    raise SystemExit(1)


def main():
    env = load_env()
    api = (env.get("KITE_API_KEY") or "").strip()
    token = ""
    if KITE_ACCESS_TOKEN_FILE.exists():
        token = KITE_ACCESS_TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        token = (env.get("KITE_ACCESS_TOKEN") or "").strip()
    print("=" * 70)
    print("STRATEGY E KITE READ-ONLY QUALIFICATION")
    print("Time       :", datetime.now().isoformat(timespec="seconds"))
    print("ENV_FILE   :", ENV_FILE)
    print("Shared env :", SHARED_ENV_FILE)
    print("Token file :", KITE_ACCESS_TOKEN_FILE)
    print("Orders     : DISABLED BY DESIGN")
    print()
    if not api:
        fail("KITE_API_KEY missing")
    if not token:
        fail("Kite access token missing; run `python run.py kite-login`")
    kite = KiteConnect(api_key=api)
    kite.set_access_token(token)
    try:
        profile = kite.profile()
        print(f"PASS | Profile        | {profile.get('user_name','UNKNOWN')} ({profile.get('user_id','')})")
        rows = kite.instruments(SETTINGS.exchange)
        rel = next((r for r in rows if r.get("tradingsymbol") == "RELIANCE"), None)
        if not rel:
            fail("NSE instrument RELIANCE not found")
        print(f"PASS | NSE instrument | RELIANCE token={rel['instrument_token']}")
        ltp = kite.ltp([f"{SETTINGS.exchange}:RELIANCE"])
        print(f"PASS | LTP            | {ltp[f'{SETTINGS.exchange}:RELIANCE']['last_price']}")
        pos = kite.positions()
        print(f"PASS | Positions       | net={len(pos.get('net', []))} day={len(pos.get('day', []))}")
        orders = kite.orders()
        print(f"PASS | Order book      | rows={len(orders)} (read-only query)")
    except Exception as exc:
        fail(f"Kite API check failed: {exc}")
    print("READ-ONLY KITE QUALIFICATION: PASS")


if __name__ == "__main__":
    main()
