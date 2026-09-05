#!/usr/bin/env python3
"""Create/migrate Strategy E build-independent secrets and data directories."""
import argparse, shutil
from pathlib import Path
from env_loader import ROOT, SECRETS_DIR, SHARED_ENV_FILE, DATA_DIR, load_env
from shared_paths import ensure_dirs


def migrate_env(source: Path | None):
    ensure_dirs()
    if SHARED_ENV_FILE.exists():
        return "EXISTS", SHARED_ENV_FILE
    src = source or (ROOT / ".env")
    if src.exists():
        shutil.copy2(src, SHARED_ENV_FILE)
        try: SHARED_ENV_FILE.chmod(0o600)
        except OSError: pass
        return "COPIED", SHARED_ENV_FILE
    return "MISSING", SHARED_ENV_FILE


def migrate_data(source: Path | None):
    ensure_dirs()
    if not source or not source.exists():
        return {"copied":0,"source":str(source) if source else None}
    copied=0
    # Preserve the package's existing relative data layout under the shared root.
    for src_name, dst_name in (("live_feature_cache","live_feature_cache"),("backtest_ohlc","backtest_ohlc"),("universe","universe"),("feature_universe.txt","universe/feature_universe.txt"),("chartink_csv","chartink_csv"),("state","state"),("logs","logs")):
        src=source/src_name; dst=DATA_DIR/dst_name
        if not src.exists(): continue
        if src.is_dir():
            dst.parent.mkdir(parents=True,exist_ok=True)
            for item in src.rglob("*"):
                if item.is_file():
                    rel=item.relative_to(src); out=dst/rel; out.parent.mkdir(parents=True,exist_ok=True)
                    if not out.exists(): shutil.copy2(item,out); copied+=1
        else:
            dst.parent.mkdir(parents=True,exist_ok=True)
            if not dst.exists(): shutil.copy2(src,dst); copied+=1
    return {"copied":copied,"source":str(source),"destination":str(DATA_DIR)}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--source-env",default=""); ap.add_argument("--migrate-package-data",default="")
    a=ap.parse_args(); ensure_dirs()
    status,path=migrate_env(Path(a.source_env).expanduser() if a.source_env else None)
    data=migrate_data(Path(a.migrate_package_data).expanduser() if a.migrate_package_data else None)
    print("Strategy E shared runtime setup")
    print("SECRETS_DIR:",SECRETS_DIR)
    print("SHARED_ENV:",path,"status=",status)
    print("DATA_DIR:",DATA_DIR)
    print("DATA_MIGRATION:",data)
    if status=="MISSING": print("ACTION: create the shared .env once with KITE_API_KEY, KITE_API_SECRET, and your Strategy E settings.")

if __name__=="__main__": main()
