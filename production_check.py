"""Safe production infrastructure preflight; never places orders."""
import ast,compileall
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from env_loader import load_env,ENV_FILE,SECRETS_DIR,DATA_DIR
from config import SETTINGS,validate_settings

ROOT=Path(__file__).resolve().parent
FORBIDDEN={"place_order","modify_order","cancel_order","exit_order"}

def fail(msg): print(f"FAIL | {msg}"); raise SystemExit(1)

def main():
    print("="*70); print("STRATEGY E V7.4 PRODUCTION PREFLIGHT"); print("="*70)
    print("PASS | Project root |",ROOT); print("PASS | ENV_FILE     |",ENV_FILE); print("PASS | Shared secrets|",SECRETS_DIR); print("PASS | Shared data   |",DATA_DIR); print("PASS | IST clock    |",datetime.now(ZoneInfo("Asia/Kolkata")).isoformat())
    errors=validate_settings()
    if errors and SETTINGS.mode=="PAPER": print("WARN | Settings:",errors)
    if SETTINGS.mode=="LIVE" and errors: fail("LIVE settings invalid: "+"; ".join(errors))
    for p in ROOT.rglob("*.py"):
        try: ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
        except Exception as e: fail(f"Syntax error {p}: {e}")
    print("PASS | Python syntax")
    for fname in ("production_check.py","kite_readonly_check.py","kite_session.py"):
        tree=ast.parse((ROOT/fname).read_text(encoding="utf-8")); attrs={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        if attrs & FORBIDDEN: fail(f"Unsafe order API in {fname}: {attrs & FORBIDDEN}")
    print("PASS | Read-only/session scripts contain no order API")
    required=["app.py","execution.py","risk_manager.py","state_store.py","reconciliation.py","monitor.py","market_data.py","webhook.py","runtime_state.py","logging_setup.py"]
    missing=[x for x in required if not (ROOT/x).exists()]
    if missing: fail("Missing core files: "+", ".join(missing))
    print("PASS | Core production modules present")
    print("="*70); print("PRODUCTION PREFLIGHT: PASS"); print("NO LIVE ORDER WAS PLACED"); print("="*70)
if __name__=="__main__": main()
