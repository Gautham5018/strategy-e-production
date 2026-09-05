#!/usr/bin/env python3
"""Read-only Kite historical 5-minute OHLCV downloader for Strategy E backtesting."""
import argparse,csv,json,logging,time
from datetime import datetime,timedelta
from pathlib import Path
from kite_client import KiteBroker
from config import DATA_DIR, SETTINGS
INTERVAL="5minute"

def parse_dt(s):
    s=str(s or '').strip()
    for f in ('%d-%m-%Y %I:%M %p','%d-%m-%Y %H:%M','%Y-%m-%d %H:%M:%S%z','%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M%z','%Y-%m-%d %H:%M'):
        try:
            x=datetime.strptime(s,f); return x.astimezone().replace(tzinfo=None) if x.tzinfo else x
        except Exception: pass
    try:
        x=datetime.fromisoformat(s.replace('Z','+00:00')); return x.astimezone().replace(tzinfo=None) if x.tzinfo else x
    except Exception:return None

def parse_date(s): return datetime.strptime(s,'%Y-%m-%d').date()
def symbols(path):
    out=set()
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            s=(r.get('Symbol') or r.get('symbol') or r.get('Tradingsymbol') or r.get('tradingsymbol') or '').strip().upper()
            if s:out.add(s)
    return sorted(out)
def dates(path):
    a=[]
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            x=parse_dt(r.get('Date') or r.get('date') or r.get('timestamp') or r.get('Timestamp'))
            if x:a.append(x.date())
    return (min(a),max(a)) if a else (None,None)
def chunks(a,b,n=30):
    while a<=b:
        e=min(b,a+timedelta(days=n-1));yield a,e;a=e+timedelta(days=1)
def pull(broker,sym,start,end,outdir,chunk_days,delay):
    token=int(broker.instrument(sym)['instrument_token']); rows={}
    for no,(a,b) in enumerate(chunks(start,end,chunk_days),1):
        fd=datetime(a.year,a.month,a.day,9,15);td=datetime(b.year,b.month,b.day,15,30)
        last=None
        for attempt in range(1,4):
            try:
                logging.info('%s chunk %s %s..%s',sym,no,a,b)
                for r in broker.historical_data(token,fd,td,INTERVAL):
                    ts=r['date'];
                    if getattr(ts,'tzinfo',None):ts=ts.astimezone().replace(tzinfo=None)
                    rows[ts]=(ts,r['open'],r['high'],r['low'],r['close'],r.get('volume',0))
                last=None;break
            except Exception as exc:
                last=exc;logging.warning('%s chunk %s attempt %s failed: %s',sym,no,attempt,exc);time.sleep(attempt*1.5)
        if last:raise RuntimeError(f'{sym}: {last}')
        time.sleep(delay)
    outdir.mkdir(parents=True,exist_ok=True);f=outdir/f'{sym}_{start:%Y%m%d}_{end:%Y%m%d}_5minute.csv'
    with f.open('w',newline='',encoding='utf-8') as h:
        w=csv.writer(h);w.writerow(['date','open','high','low','close','volume'])
        for r in sorted(rows.values()):w.writerow([r[0].strftime('%Y-%m-%d %H:%M:%S'),*r[1:]])
    return f,len(rows),token

def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--signals');g.add_argument('--symbols')
    p.add_argument('--from',dest='start');p.add_argument('--to',dest='end');p.add_argument('--output-dir',default=str(DATA_DIR/'backtest_ohlc'));p.add_argument('--chunk-days',type=int,default=30);p.add_argument('--delay',type=float,default=.4);p.add_argument('--dry-run',action='store_true')
    a=p.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | history5m | %(message)s')
    if a.signals:
        sp=Path(a.signals)
        if not sp.exists():raise SystemExit(f'Signals file not found: {sp}')
        syms=symbols(sp);s,e=dates(sp)
    else:syms=sorted({x.strip().upper() for x in a.symbols.split(',') if x.strip()});s=e=None
    start=parse_date(a.start) if a.start else s;end=parse_date(a.end) if a.end else e
    if not syms or not start or not end or start>end:raise SystemExit('Valid symbols/date range required')
    print(f'Strategy E 5-minute historical pull | symbols={len(syms)} | {start}..{end} | orders=DISABLED')
    if a.dry_run:return [print('WOULD DOWNLOAD',x) for x in syms]
    broker=KiteBroker();done=[];failed=[]
    for sym in syms:
        try:f,n,t=pull(broker,sym,start,end,Path(a.output_dir),a.chunk_days,a.delay);print(f'PASS | {sym:15s} rows={n:6d} file={f.name}');done.append({'symbol':sym,'rows':n,'file':str(f),'instrument_token':t})
        except Exception as exc:print(f'FAIL | {sym:15s} {exc}');failed.append({'symbol':sym,'error':str(exc)})
    summary={'symbols_requested':len(syms),'completed':len(done),'failed':len(failed),'from':str(start),'to':str(end),'interval':INTERVAL,'files':done,'failed_symbols':failed}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/'download_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2));
    if failed:raise SystemExit(2)
if __name__=='__main__':main()
