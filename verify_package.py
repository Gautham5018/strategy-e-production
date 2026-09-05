#!/usr/bin/env python3
"""Offline package verification. Never places orders or requires a running app."""
from __future__ import annotations
import ast
import compileall
import importlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
CORE = [
    "app", "config", "entry_engine", "execution", "feature_cache", "feature_engine",
    "kite_client", "live_feature_gate", "market_data", "monitor", "models",
    "risk_manager", "state_store", "webhook", "backtest.incremental_ohlc",
    "backtest.incremental_ohlc_1m", "backtest.backtest_strategy_e_v74",
]


def main() -> int:
    print("=" * 70)
    print("STRATEGY E V7.4 PACKAGE VERIFICATION")
    print("ROOT:", ROOT)
    print("=" * 70)
    ok = compileall.compile_dir(str(ROOT), quiet=1, maxlevels=10)
    print("PASS | Python compileall" if ok else "FAIL | Python compileall")
    if not ok:
        return 1
    for mod in CORE:
        try:
            importlib.import_module(mod)
            print("PASS | import |", mod)
        except Exception as exc:
            print("FAIL | import |", mod, "|", exc)
            return 1
    for file in ROOT.rglob("*.py"):
        try:
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except Exception as exc:
            print("FAIL | syntax |", file, "|", exc)
            return 1
    print("PASS | AST syntax scan")
    for cmd in ([sys.executable, "run.py", "--help"], [sys.executable, "run.py", "cache-health", "--help"], [sys.executable, "run.py", "update-ohlc", "--help"], [sys.executable, "run.py", "update-ohlc-1m", "--help"], [sys.executable, "run.py", "backtest", "--help"], [sys.executable, "run.py", "optimize", "--help"]):
        # run.py intentionally uses a custom usage line for --help; a non-zero
        # result is acceptable only if the command printed usage successfully.
        r = subprocess.run(cmd, capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip()
        if "Usage:" not in out and "usage:" not in out:
            print("FAIL | CLI help |", " ".join(cmd), "|", out[:300])
            return 1
        print("PASS | CLI |", " ".join(cmd[2:]))
    print("PASS | No live order was placed")
    print("PACKAGE VERIFICATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
