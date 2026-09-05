"""Build-independent local production session status. Read-only."""
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from env_loader import load_env, ENV_FILE, SECRETS_DIR, SHARED_ENV_FILE
from shared_paths import KITE_ACCESS_TOKEN_FILE

def main():
    env=load_env()
    print("STRATEGY E SESSION STATUS")
    print("Selected ENV_FILE:", ENV_FILE)
    print("Shared secrets dir:", SECRETS_DIR)
    print("Shared credentials file:", SHARED_ENV_FILE)
    print("Shared access token file:", KITE_ACCESS_TOKEN_FILE)
    print("IST:", datetime.now(ZoneInfo("Asia/Kolkata")).isoformat())
    for k in (
        "MODE","PORT","BIND_HOST","TRADING_START","TRADING_END","FIRST_SIGNAL_CUTOFF",
        "MAX_OPEN_POSITIONS","MAX_ENTRIES_PER_DAY","TOTAL_CAPITAL",
        "TRADE_CAPITAL_PER_POSITION","PARTIAL_R_FRACTION","FINAL_R_MULTIPLE",
        "MIS_LEVERAGE","TRADING_ENABLED","ALLOW_LIVE_ORDERS","LIVE_ORDERS_ARMED",
        "KILL_SWITCH","STARTUP_RECONCILE_REQUIRED"
    ):
        print(f"{k}={os.getenv(k,env.get(k,'<unset>'))}")
    api=(os.getenv("KITE_API_KEY") or env.get("KITE_API_KEY") or "").strip()
    token=(os.getenv("KITE_ACCESS_TOKEN") or env.get("KITE_ACCESS_TOKEN") or "").strip()
    print("KITE_API_KEY_PRESENT=", bool(api))
    print("KITE_ACCESS_TOKEN_ENV_PRESENT=", bool(token))
    print("KITE_ACCESS_TOKEN_FILE_PRESENT=", KITE_ACCESS_TOKEN_FILE.exists())
    print("ORDER PLACEMENT: requires all explicit live gates and healthy readiness.")

if __name__=="__main__": main()
