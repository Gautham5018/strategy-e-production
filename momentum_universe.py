#!/usr/bin/env python3
"""Rank the prepared universe by medium-term momentum without restricting Chartink signals.
Read-only over local OHLC cache; no order APIs and no network calls.
"""
import argparse,csv,json
from pathlib import Path
from datetime import datetime

def load(path):
    rows=[]
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            try:
                t=datetime.fromisoformat(str(r['date']).replace('Z','+00:00'))
                if t.tzinfo:t=t.astimezone().replace(tzinfo=None)
                rows.append((t,float(r['close']),float(r.get('volume',0) or 0)))
            except Exception: pass
    rows.sort()
    return rows

def ret(rows,n):
    if len(rows)<=n or rows[-n-1][1]<=0:return None
    return rows[-1][1]/rows[-n-1][1]-1.0

def rank(universe_file,cache_dir,output_dir,top_n=150,market_file=''):
    syms=[]
    for line in Path(universe_file).read_text(encoding='utf-8').splitlines():
        x=line.strip().upper()
        if x and not x.startswith('#') and x not in syms:syms.append(x)
    market=load(market_file) if market_file and Path(market_file).exists() else []
    market20=ret(market,20*75) if market else None  # roughly 20 sessions of 75 five-minute bars
    out=[]
    for s in syms:
        f=Path(cache_dir)/f'{s}_5minute.csv'
        if not f.exists():continue
        rows=load(f)
        if len(rows)<100:continue
        r5=ret(rows,5*75);r20=ret(rows,20*75);r60=ret(rows,60*75)
        # Approximate relative volume using the latest bar vs recent median volume.
        vols=[v for _,_,v in rows[-20:] if v>0]
        rv=(rows[-1][2]/(sum(vols[:-1])/max(1,len(vols)-1))) if len(vols)>1 and sum(vols[:-1])>0 else None
        ema20=sum(x[1] for x in rows[-20:])/20 if len(rows)>=20 else rows[-1][1]
        trend=rows[-1][1]/ema20-1 if ema20 else 0
        rel=(r20-market20) if market20 is not None and r20 is not None else None
        components=[r for r in (r5,r20,r60,trend,rel) if r is not None]
        if not components:continue
        # Transparent normalized score: returns/trend/relative strength, capped to a sensible 0-100 range.
        raw=50 + 220*sum(components)/len(components) + (5*max(0,min((rv or 1)-1,2)))
        score=max(0,min(100,raw))
        out.append({'symbol':s,'momentum_score':round(score,2),'return_5d_pct':round(r5*100,2) if r5 is not None else None,'return_20d_pct':round(r20*100,2) if r20 is not None else None,'return_60d_pct':round(r60*100,2) if r60 is not None else None,'relative_strength_20d_pct':round(rel*100,2) if rel is not None else None,'volume_ratio':round(rv,2) if rv is not None else None})
    out.sort(key=lambda x:(x['momentum_score'],x.get('return_20d_pct') or -999),reverse=True)
    od=Path(output_dir);od.mkdir(parents=True,exist_ok=True)
    csv_path=od/'momentum_rank.csv';txt_path=od/'momentum_top_symbols.txt'
    with csv_path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]) if out else ['symbol','momentum_score']);w.writeheader();w.writerows(out)
    txt_path.write_text('# Auto-generated momentum ranking; NOT a trading whitelist.\n'+'\n'.join(x['symbol'] for x in out[:top_n])+'\n',encoding='utf-8')
    summary={'universe':len(syms),'ranked':len(out),'top_n':min(top_n,len(out)),'csv':str(csv_path),'top_symbols':str(txt_path),'market_return_20d_pct':round(market20*100,2) if market20 is not None else None}
    (od/'momentum_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--universe',required=True);p.add_argument('--cache-dir',required=True);p.add_argument('--output-dir',required=True);p.add_argument('--market-file',default='');p.add_argument('--top',type=int,default=150);a=p.parse_args();print(json.dumps(rank(a.universe,a.cache_dir,a.output_dir,a.top,a.market_file),indent=2))
if __name__=='__main__':main()
