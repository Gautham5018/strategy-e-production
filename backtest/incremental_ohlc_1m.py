#!/usr/bin/env python3
"""Incremental append-only 1-minute OHLCV cache for V7.4 entry confirmation."""
import argparse,csv,json,logging,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from config import SETTINGS
INTERVAL='minute'; IST=ZoneInfo('Asia/Kolkata')

def _parse(v):
    x=datetime.fromisoformat(str(v).replace('Z','+00:00'))
    return x.astimezone(IST).replace(tzinfo=None) if x.tzinfo else x

def _read(p):
    d={}
    if not p.exists():return d
    with p.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            try:
                ts=_parse(r['date']);d[ts]=(ts,float(r['open']),float(r['high']),float(r['low']),float(r['close']),float(r.get('volume',0) or 0))
            except Exception:pass
    return d

def _write(p,d):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['date','open','high','low','close','volume'])
        for r in sorted(d.values(),key=lambda x:x[0]):w.writerow([r[0].strftime('%Y-%m-%d %H:%M:%S'),*r[1:]])
    tmp.replace(p)

def _end(now=None):
    now=now or datetime.now(IST);x=now.replace(tzinfo=None,second=0,microsecond=0);return x-timedelta(minutes=1)

def _chunks(a,b,n=30):
    while a<=b:
        e=min(b,a+timedelta(days=n-1));yield a,e;a=e+timedelta(days=1)

def _fetch(broker,token,start,end,delay=.5):
    out={}
    for no,(a,b) in enumerate(_chunks(start.date(),end.date()),1):
        fd=max(start,datetime(a.year,a.month,a.day,9,15));td=min(end,datetime(b.year,b.month,b.day,15,30))
        if fd>td:continue
        err=None
        for attempt in range(1,4):
            try:
                logging.info('pull 1m chunk=%s %s..%s',no,fd,td)
                for r in broker.historical_data(token,fd,td,INTERVAL):
                    ts=r['date']; ts=ts.astimezone(IST).replace(tzinfo=None) if getattr(ts,'tzinfo',None) else ts
                    out[ts]=(ts,r['open'],r['high'],r['low'],r['close'],r.get('volume',0))
                err=None;break
            except Exception as exc:
                err=exc;logging.warning('1m history attempt=%s failed: %s',attempt,exc);time.sleep(attempt*1.5)
        if err:raise RuntimeError(str(err))
        time.sleep(delay)
    return out

def update_symbol(broker,symbol,outdir,initial_history_days=60,delay=.5):
    outdir=Path(outdir);p=outdir/f'{symbol.upper()}_1minute.csv';rows=_read(p);end=_end()
    if rows:start=max(rows)-timedelta(minutes=1);mode='APPEND'
    else:start=end-timedelta(days=max(1,initial_history_days));mode='INITIAL'
    token=int(broker.instrument(symbol)['instrument_token'])
    if start>end:return {'symbol':symbol,'mode':mode,'rows':len(rows),'downloaded':0,'file':str(p),'last_candle':max(rows).isoformat() if rows else None}
    got=_fetch(broker,token,start,end,delay);rows.update(got);_write(p,rows)
    return {'symbol':symbol,'mode':mode,'rows':len(rows),'downloaded':len(got),'file':str(p),'last_candle':max(rows).isoformat() if rows else None}

def symbols_from_file(path):
    out=[]
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        s=line.strip().upper()
        if s and not s.startswith('#') and s not in out:out.append(s)
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--symbols',default='');p.add_argument('--symbols-file',default='');p.add_argument('--output-dir',default=str(SETTINGS.one_minute_cache_dir));p.add_argument('--initial-history-days',type=int,default=60);p.add_argument('--delay',type=float,default=.5);a=p.parse_args()
    syms=[]
    if a.symbols:syms += [x.strip().upper() for x in a.symbols.split(',') if x.strip()]
    if a.symbols_file:syms += symbols_from_file(a.symbols_file)
    syms=list(dict.fromkeys(syms))
    if not syms:raise SystemExit('No symbols provided')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | incremental1m | %(message)s')
    from kite_client import KiteBroker
    broker=KiteBroker();done=[];failed=[]
    for s in syms:
        try:r=update_symbol(broker,s,a.output_dir,a.initial_history_days,a.delay);done.append(r);print(f"PASS | {s:15s} mode={r['mode']:7s} added={r['downloaded']:6d} total={r['rows']:8d}")
        except Exception as exc:failed.append({'symbol':s,'error':str(exc)});print(f'FAIL | {s:15s} {exc}')
    summary={'symbols_requested':len(syms),'completed':len(done),'failed':len(failed),'interval':INTERVAL,'initial_history_days':a.initial_history_days,'files':done,'failed_symbols':failed}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/'incremental_1m_update_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    if failed:raise SystemExit(2)
if __name__=='__main__':main()
