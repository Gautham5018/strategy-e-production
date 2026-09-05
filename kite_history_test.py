#!/usr/bin/env python3
"""Read-only historical-candle smoke test for the live shared Kite session."""
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from kiteconnect import KiteConnect
from config import SETTINGS
from env_loader import load_env, ENV_FILE
from shared_paths import KITE_ACCESS_TOKEN_FILE

IST = ZoneInfo("Asia/Kolkata")


def _parse_dt(value: str) -> datetime:
    x = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if x.tzinfo:
        x = x.astimezone(IST).replace(tzinfo=None)
    return x


def main():
    p = argparse.ArgumentParser(description="Read-only Kite historical_data smoke test")
    p.add_argument("--symbol", default="RELIANCE")
    p.add_argument("--from", dest="from_dt", default="")
    p.add_argument("--to", dest="to_dt", default="")
    p.add_argument("--interval", choices=["minute", "5minute", "15minute", "30minute", "60minute", "day"], default="5minute")
    a = p.parse_args()
    env = load_env()
    api = (env.get("KITE_API_KEY") or "").strip()
    token = KITE_ACCESS_TOKEN_FILE.read_text(encoding="utf-8").strip() if KITE_ACCESS_TOKEN_FILE.exists() else ""
    if not token:
        token = (env.get("KITE_ACCESS_TOKEN") or "").strip()
    if not api:
        raise SystemExit("KITE_API_KEY missing")
    if not token:
        raise SystemExit(f"Kite access token missing: {KITE_ACCESS_TOKEN_FILE}")
    end = _parse_dt(a.to_dt) if a.to_dt else (datetime.now(IST).replace(tzinfo=None, second=0, microsecond=0) - timedelta(minutes=5))
    start = _parse_dt(a.from_dt) if a.from_dt else end - timedelta(minutes=15)
    kite = KiteConnect(api_key=api)
    kite.set_access_token(token)
    rows = kite.instruments(SETTINGS.exchange)
    wanted = a.symbol.strip().upper()
    ins = next((r for r in rows if r.get("tradingsymbol", "").upper() == wanted), None)
    if not ins:
        raise SystemExit(f"NSE instrument not found: {wanted}")
    data = kite.historical_data(int(ins["instrument_token"]), start, end, a.interval)
    print("ENV:", ENV_FILE)
    print("SYMBOL:", wanted)
    print("TOKEN:", ins["instrument_token"])
    print("FROM:", start.isoformat())
    print("TO:", end.isoformat())
    print("INTERVAL:", a.interval)
    print("HISTORICAL PASS")
    print("CANDLES:", len(data))
    for row in data[:3]:
        print(row)


if __name__ == "__main__":
    main()
