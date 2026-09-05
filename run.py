#!/usr/bin/env python3
import json,sys,urllib.parse,urllib.request,urllib.error
from datetime import datetime

def call(path,method="GET",body=None,token=None):
    data=json.dumps(body).encode() if body is not None else None; headers={"Content-Type":"application/json"}
    if token:headers["X-Admin-Token"]=token
    req=urllib.request.Request("http://127.0.0.1:8081"+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=15) as r:return r.status,json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:d=json.loads(e.read().decode())
        except:d={"detail":str(e)}
        return e.code,d

def start():
    import uvicorn
    from config import SETTINGS
    uvicorn.run("app:app",host=SETTINGS.bind_host,port=SETTINGS.port,reload=False)

def main():
    args=sys.argv[1:]
    if not args or args[0]=="start":return start()
    if args[0] in {"status","health","readiness","gate","positions"}:
        path={"status":"/health","health":"/health","readiness":"/readiness","gate":"/live-gate","positions":"/admin/positions"}[args[0]]
        if args[0]=="positions":
            from env_loader import load_env
            token=load_env().get("ADMIN_TOKEN","")
            print(json.dumps(call(path,token=token)[1],indent=2,default=str))
        else:
            print(json.dumps(call(path)[1],indent=2,default=str))
        return
    if args[0] == "verify":
        from verify_package import main as verify_main
        raise SystemExit(verify_main())
    if args[0] == "setup-shared":
        from setup_shared import main as setup_main
        old=sys.argv[:];sys.argv=[sys.argv[0]]+args[1:]
        try: setup_main()
        finally: sys.argv=old
        return
    if args[0] == "kite-history-test":
        from kite_history_test import main as history_main
        old=sys.argv[:];sys.argv=[sys.argv[0]]+args[1:]
        try: history_main()
        finally: sys.argv=old
        return
    if args[0] in {"kite-login", "session-status"}:
        if args[0] == "kite-login":
            from kite_session import main as session_main
            session_main()
        else:
            from session_status import main as status_main
            status_main()
        return
    if args[0] == "sync-universe":
        from universe_manager import main as universe_main
        old=sys.argv[:]; sys.argv=[sys.argv[0],"sync"]
        try: universe_main()
        finally: sys.argv=old
        return
    if args[0] == "enroll-symbol":
        from universe_manager import enroll, validate_symbol
        if len(args)<2: raise SystemExit("Usage: python run.py enroll-symbol SYMBOL")
        symbol=args[1].upper()
        ok,reason=validate_symbol(symbol)
        if not ok: raise SystemExit(f"Cannot enroll {symbol}: {reason}")
        enroll(symbol); print("ENROLLED", symbol); return
    if args[0] == "enroll-file":
        from universe_manager import enroll_file
        if len(args)<2: raise SystemExit("Usage: python run.py enroll-file FILE")
        print(json.dumps(enroll_file(args[1]),indent=2)); return
    if args[0] == "momentum-rank":
        from momentum_universe import main as momentum_main
        old=sys.argv[:];sys.argv=[sys.argv[0]]+args[1:]
        try: momentum_main()
        finally: sys.argv=old
        return
    if args[0] == "cache-health":
        from backtest.cache_health import main as health_main
        old=sys.argv[:];sys.argv=[sys.argv[0]]+args[1:]
        try: health_main()
        finally: sys.argv=old
        return
    if args[0] == "update-ohlc-1m":
        from backtest.incremental_ohlc_1m import main as incremental_main
        old=sys.argv[:];sys.argv=[sys.argv[0]]+args[1:]
        try: incremental_main()
        finally: sys.argv=old
        return
    if args[0] == "update-ohlc":
        from backtest.incremental_ohlc import main as incremental_main
        old=sys.argv[:]; sys.argv=[sys.argv[0]]+args[1:]
        try: incremental_main()
        finally: sys.argv=old
        return
    if args[0] == "prewarm-features":
        from backtest.incremental_ohlc import main as pull_main
        from config import SETTINGS
        if not __import__("pathlib").Path(SETTINGS.feature_universe_file).exists():
            raise SystemExit(f"Feature universe not found: {SETTINGS.feature_universe_file}")
        import argparse as _ap
        q=_ap.ArgumentParser(add_help=False);q.add_argument("--initial-history-days",type=int,default=90);known,rest=q.parse_known_args(args[1:])
        argv0=sys.argv[:];sys.argv=[sys.argv[0],"--symbols-file",SETTINGS.feature_universe_file,"--output-dir",SETTINGS.feature_cache_dir,"--initial-history-days",str(known.initial_history_days)]
        try:pull_main()
        finally:sys.argv=argv0
        return
    if args[0] == "pull-5m":
        from backtest.historical_5m import main as pull_main
        pull_main(); return
    if args[0] == "backtest":
        from backtest.backtest_strategy_e_v74 import main as backtest_main
        old=sys.argv[:]; sys.argv=[sys.argv[0]]+args[1:]
        try: backtest_main()
        finally: sys.argv=old
        return
    if args[0] == "optimize":
        from backtest.optimize_strategy_e_v74 import main as optimize_main
        old=sys.argv[:]; sys.argv=[sys.argv[0]]+args[1:]
        try: optimize_main()
        finally: sys.argv=old
        return
    from env_loader import load_env
    token=load_env().get("ADMIN_TOKEN","")
    if args[0]=="reconcile": path="/admin/reconcile";body=None
    elif args[0]=="exit" and len(args)>=2:
        if "--confirm" not in args: raise SystemExit("Refusing manual exit without --confirm")
        reason="CLI_MANUAL_EXIT"
        if "--reason" in args:
            i=args.index("--reason")
            if i+1<len(args):reason=args[i+1]
        path="/admin/exit/"+urllib.parse.quote(args[1].upper());body={"reason":reason}
    elif args[0]=="flatten":
        if "--confirm" not in args:raise SystemExit("Refusing flatten without --confirm")
        path="/admin/flatten";body={"reason":"CLI_MANUAL_FLATTEN_ALL"}
    elif args[0]=="kill":path="/admin/kill-switch";body=None
    else:raise SystemExit("Usage: python run.py [start|status|readiness|gate|positions|verify|setup-shared|kite-history-test|kite-login|session-status|sync-universe|enroll-symbol SYMBOL|enroll-file FILE|momentum-rank|cache-health|update-ohlc|update-ohlc-1m|prewarm-features|pull-5m|backtest|optimize|reconcile|exit SYMBOL --confirm|flatten --confirm|kill]")
    print(json.dumps(call(path,"POST",body,token)[1],indent=2,default=str))

if __name__=="__main__":main()
