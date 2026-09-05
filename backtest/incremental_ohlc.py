#!/usr/bin/env python3
"""Incremental, append-only 5-minute OHLCV cache for Strategy E.

Initial run: download INITIAL_HISTORY_DAYS (default 90).
Later runs: inspect the existing file and request only missing dates/candles.
No order APIs are used.
"""
import argparse, csv, json, logging, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from config import DATA_DIR, SETTINGS

INTERVAL = "5minute"
IST = ZoneInfo("Asia/Kolkata")


def _parse_ts(v):
    x = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if x.tzinfo:
        x = x.astimezone(IST).replace(tzinfo=None)
    return x


def _read_rows(path):
    rows = {}
    if not path.exists():
        return rows
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                ts = _parse_ts(r["date"])
                rows[ts] = (ts, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r.get("volume", 0) or 0))
            except Exception:
                continue
    return rows


def _write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        for r in sorted(rows.values(), key=lambda x: x[0]):
            w.writerow([r[0].strftime("%Y-%m-%d %H:%M:%S"), *r[1:]])
    tmp.replace(path)


def _last_complete_end(now=None):
    now = now or datetime.now(IST)
    local = now.replace(tzinfo=None, second=0, microsecond=0)
    bucket = (local.minute // 5) * 5
    return local.replace(minute=bucket) - timedelta(minutes=5)


def _chunks(a, b, n=30):
    while a <= b:
        e = min(b, a + timedelta(days=n - 1))
        yield a, e
        a = e + timedelta(days=1)


def _fetch(broker, token, start, end, delay=.4):
    out = {}
    for no, (a, b) in enumerate(_chunks(start.date(), end.date()), 1):
        fd = max(start, datetime(a.year, a.month, a.day, 9, 15))
        td = min(end, datetime(b.year, b.month, b.day, 15, 30))
        if fd > td:
            continue
        last = None
        for attempt in range(1, 4):
            try:
                logging.info("pull chunk=%s %s..%s", no, fd, td)
                for r in broker.historical_data(token, fd, td, INTERVAL):
                    ts = r["date"]
                    if getattr(ts, "tzinfo", None):
                        ts = ts.astimezone(IST).replace(tzinfo=None)
                    out[ts] = (ts, r["open"], r["high"], r["low"], r["close"], r.get("volume", 0))
                last = None
                break
            except Exception as exc:
                last = exc
                logging.warning("history attempt=%s failed: %s", attempt, exc)
                time.sleep(attempt * 1.5)
        if last:
            raise RuntimeError(str(last))
        time.sleep(delay)
    return out


def update_symbol(broker, symbol, outdir, initial_history_days=90, chunk_days=30, delay=.4):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{symbol.upper()}_5minute.csv"
    rows = _read_rows(path)
    token = int(broker.instrument(symbol)["instrument_token"])
    now_end = _last_complete_end()
    if rows:
        last_ts = max(rows)
        # Include the last candle's date in the fetch so corrections are picked up and dedup handles overlap.
        start = max(last_ts - timedelta(minutes=5), datetime(2000, 1, 1))
        mode = "APPEND"
    else:
        start = now_end - timedelta(days=max(1, initial_history_days))
        mode = "INITIAL"
    if start > now_end:
        return {"symbol": symbol, "mode": mode, "rows": len(rows), "downloaded": 0, "file": str(path), "instrument_token": token, "last_candle": max(rows).isoformat() if rows else None}
    got = _fetch(broker, token, start, now_end, delay=delay)
    rows.update(got)
    _write_rows(path, rows)
    last = max(rows) if rows else None
    return {"symbol": symbol, "mode": mode, "rows": len(rows), "downloaded": len(got), "file": str(path), "instrument_token": token, "last_candle": last.isoformat() if last else None}


def symbols_from_file(path):
    out=[]
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            s=line.strip().upper()
            if s and not s.startswith("#") and s not in out: out.append(s)
    return out


def main():
    p=argparse.ArgumentParser(description="Incremental Strategy E 5-minute OHLC cache")
    p.add_argument("--symbols", default="")
    p.add_argument("--symbols-file", default="")
    p.add_argument("--output-dir", default=str(SETTINGS.feature_cache_dir))
    p.add_argument("--initial-history-days", type=int, default=90)
    p.add_argument("--delay", type=float, default=.4)
    a=p.parse_args()
    syms=[]
    if a.symbols: syms.extend(x.strip().upper() for x in a.symbols.split(",") if x.strip())
    if a.symbols_file: syms.extend(symbols_from_file(a.symbols_file))
    syms=list(dict.fromkeys(syms))
    if not syms: raise SystemExit("No symbols provided")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | incremental5m | %(message)s")
    print(f"Strategy E incremental 5m cache | symbols={len(syms)} | read-only")
    from kite_client import KiteBroker
    broker=KiteBroker(); results=[]; failed=[]
    for sym in syms:
        try:
            r=update_symbol(broker,sym,a.output_dir,a.initial_history_days,delay=a.delay)
            results.append(r); print(f"PASS | {sym:15s} mode={r['mode']:7s} added={r['downloaded']:6d} total={r['rows']:7d}")
        except Exception as exc:
            failed.append({"symbol":sym,"error":str(exc)}); print(f"FAIL | {sym:15s} {exc}")
    summary={"symbols_requested":len(syms),"completed":len(results),"failed":len(failed),"interval":INTERVAL,"initial_history_days":a.initial_history_days,"files":results,"failed_symbols":failed}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"incremental_update_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
    if failed: raise SystemExit(2)

if __name__=='__main__': main()
