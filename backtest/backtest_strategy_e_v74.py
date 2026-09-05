#!/usr/bin/env python3
"""Strategy E V7.4 delayed-entry backtest: 5m signal + 1m confirmation."""
import argparse,csv,json,re,sys
from pathlib import Path
from datetime import datetime,time,timedelta
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_engine import score_trade
from entry_engine import build_setup,confirmation

def dt(s):
    s=str(s or '').strip()
    for f in ('%d-%m-%Y %I:%M %p','%d-%m-%Y %H:%M','%Y-%m-%d %H:%M:%S%z','%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M%z','%Y-%m-%d %H:%M'):
        try:
            x=datetime.strptime(s,f);return x.astimezone().replace(tzinfo=None) if x.tzinfo else x
        except:pass
    try:
        x=datetime.fromisoformat(s.replace('Z','+00:00'));return x.astimezone().replace(tzinfo=None) if x.tzinfo else x
    except:return None

def read_csv(path, one_min=False):
    out=[]
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            t=dt(r.get('date') or r.get('Date') or r.get('timestamp'))
            if not t:continue
            try:out.append({'ts':t,'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close']),'volume':float(r.get('volume',0) or 0)})
            except:pass
    return sorted(out,key=lambda x:x['ts'])

def index_files(folder,suffix):
    out={}
    for f in Path(folder).glob(f'*_{suffix}.csv'):
        stem=f.stem
        m=re.match(r'^(.+?)_\d{8}_\d{8}_'+re.escape(suffix)+r'$',stem,re.I)
        sym=m.group(1).upper() if m else stem.rsplit('_',1)[0].upper();out[sym]=f
    return out

def one_trade(entry,stop,bs,final_r,be_on,be_r,be_lock,trail_on,trail_lock,trail_dist,time_stop,stag_pct,charge,slip,qty):
    risk=entry-stop
    if risk<=0:return None
    one=entry+risk;target=entry+final_r*risk;q1=qty//2;q2=qty-q1
    partial=None;pi=None;exitp=None;ei=None;reason=None;peak=0;be_stop=None
    for i,b in enumerate(bs):
        if b['low']<=stop and partial is None:exitp=stop;ei=i;reason='STOP';break
        if partial is None:
            if be_on and b['high']>=entry+be_r*risk:be_stop=max(stop,entry+be_lock*risk)
            if be_stop is not None and b['low']<=be_stop:exitp=be_stop;ei=i;reason='BREAK_EVEN_PROFIT_LOCK';break
            if b['high']>=one:
                partial=one;pi=i;peak=b['high'];be_stop=max(be_stop or stop,entry+be_lock*risk)
                if b['high']>=target:exitp=target;ei=i;reason='TARGET';break
        else:
            peak=max(peak,b['high'])
            if trail_on:
                tr=max(entry+trail_lock*risk,peak-trail_dist*risk,stop)
                if b['low']<=tr:exitp=tr;ei=i;reason='TRAILING_STOP';break
            if b['high']>=target:exitp=target;ei=i;reason='TARGET';break
            elapsed=(b['ts']-bs[pi]['ts']).total_seconds()/60
            if elapsed>=time_stop and peak < partial*(1+stag_pct/100):exitp=partial;ei=i;reason='TIME_STAGNATION';break
    if exitp is None and bs:
        last=bs[-1]
        exitp=float(last['close']); ei=len(bs)-1; reason='EOD_FLATTEN'
    if exitp is None:return None
    gross=(exitp-entry)*qty if partial is None else (partial-entry)*q1+(exitp-entry)*q2
    turn=entry*qty+(exitp*qty if partial is None else partial*q1+exitp*q2)
    costs=turn*slip/100+charge
    return {'entry':entry,'stop':stop,'qty':qty,'one_r':one,'final_target':target,'partial_exit':partial,'partial_qty':q1,'final_exit':exitp,'gross_pnl':gross,'costs':costs,'net_pnl':gross-costs,'entry_time':bs[0]['ts'],'exit_time':bs[ei]['ts'],'holding_min':(bs[ei]['ts']-bs[0]['ts']).total_seconds()/60,'reason':reason}

def run_mode(args,mode):
    sigs=[]
    with Path(args.signals).open(newline='',encoding='utf-8-sig') as f:
        for n,r in enumerate(csv.DictReader(f),2):
            s=(r.get('Symbol') or r.get('symbol') or r.get('Tradingsymbol') or '').strip().upper();t=dt(r.get('Date') or r.get('date') or r.get('timestamp') or r.get('Timestamp'))
            if s and t:sigs.append({'row':n,'symbol':s,'signal_time':t})
    from config import SETTINGS
    one_minute_dir=args.one_minute_dir or SETTINGS.one_minute_cache_dir
    five=index_files(args.data_dir,'5minute');one=index_files(one_minute_dir,'1minute');market=read_csv(args.market_data_file) if args.market_data_file else None
    trades=[];reject=defaultdict(int);prepared=[]
    for s in sigs:
        if s['symbol'] not in five or s['symbol'] not in one:reject['CACHE_MISSING']+=1;continue
        bs=read_csv(five[s['symbol']]);mb=market or []
        si=min(range(len(bs)),key=lambda i:abs((bs[i]['ts']-s['signal_time']).total_seconds())) if bs else None
        if si is None or abs((bs[si]['ts']-s['signal_time']).total_seconds())>90:reject['SIGNAL_CANDLE_NOT_FOUND']+=1;continue
        if si<1:reject['PREVIOUS_CANDLE_MISSING']+=1;continue
        signal_bar=bs[si];prev=bs[si-1]
        if signal_bar['ts'].time()>datetime.strptime(args.first_signal_cutoff,'%H:%M').time() and len([x for x in prepared if x.get('entry')])==0:reject['FIRST_SIGNAL_CUTOFF']+=1;continue
        # Setup score uses signal close with risk score de-emphasized; actual entry risk is validated after confirmation.
        snap=score_trade(symbol=s['symbol'],signal_time=signal_bar['ts'],signal_open=signal_bar['open'],signal_high=signal_bar['high'],signal_low=signal_bar['low'],signal_close=signal_bar['close'],entry_price=signal_bar['close'],bars=bs[:si+1],market_bars=mb,max_risk_pct=999,min_adx=args.min_adx,min_relative_volume=args.min_relative_volume,min_atr_pct=args.min_atr_pct,max_atr_pct=args.max_atr_pct,score_threshold=args.score_threshold,start=datetime.strptime(args.trading_start,'%H:%M').time(),end=datetime.strptime(args.trading_end,'%H:%M').time(),allow_windows=None,market_filter=args.market_filter)
        if not (snap.score>=args.score_threshold and snap.market_regime_ok and snap.time_window_ok):reject['FEATURE_REJECT']+=1;continue
        setup=build_setup(signal_bar['ts'],prev,signal_bar,bs[:si+1],ema_tolerance_pct=args.fib_ema_tolerance_pct,wait_minutes=args.wait_minutes)
        one_bars=read_csv(one[s['symbol']], one_min=True)
        post=[b for b in one_bars if b['ts']>signal_bar['ts'] and b['ts']<=signal_bar['ts']+timedelta(minutes=args.wait_minutes)]
        conf=confirmation(setup,post,mode=mode,allow_continuation=args.allow_continuation,zone_tolerance_pct=args.zone_tolerance_pct)
        if not conf:reject[f'NO_ENTRY_{mode}']+=1;continue
        entry=conf['entry_price'];stop=min(float(entry),max(float(signal_bar['low']),float(conf['structure_low']))-args.stop_buffer_pct/100*entry)
        if stop>=entry:reject['INVALID_ENTRY_STOP']+=1;continue
        riskpct=(entry-stop)/entry*100
        if riskpct>args.max_risk_pct:reject['ENTRY_RISK_OVER_LIMIT']+=1;continue
        qty=int((args.capital*args.leverage)//entry)
        if args.risk_sizing:qty=min(qty,int(args.risk_per_trade_inr//(entry-stop)))
        if qty<2:reject['QUANTITY_LT_2']+=1;continue
        exitbars=[b for b in one_bars if b['ts']>=datetime.fromisoformat(conf['entry_time']) and b['ts'].date()==signal_bar['ts'].date()]
        tr=one_trade(entry,stop,exitbars,args.final_r,args.break_even,args.break_even_r,args.break_even_lock_r,args.trailing_stop,args.trailing_lock_r,args.trailing_distance_r,args.time_stop,args.stagnation_pct,args.fixed_charge,args.slippage_pct,qty)
        if not tr:reject['NO_EXIT_DATA']+=1;continue
        tr.update({'symbol':s['symbol'],'signal_time':signal_bar['ts'],'entry_method':conf['method'],'fib_50':setup['fib_50'],'fib_618':setup['fib_618'],'ema9':setup['ema9'],'score':snap.score,'grade':snap.grade,'signal_low':signal_bar['low']})
        prepared.append(tr)
    # portfolio capacity: accept earliest entries while allowing at most 2 overlaps and max 2 entries/day.
    day_counts=defaultdict(int);accepted=[]
    for tr in sorted(prepared,key=lambda x:x['entry_time']):
        d=tr['entry_time'].date();over=sum(1 for a in accepted if a['entry_time']<=tr['entry_time']<a['exit_time'])
        if day_counts[d]>=args.max_entries:continue
        if over>=args.max_open:continue
        accepted.append(tr);day_counts[d]+=1
    gross=sum(x['gross_pnl'] for x in accepted);cost=sum(x['costs'] for x in accepted);net=sum(x['net_pnl'] for x in accepted)
    wins=sum(x['net_pnl']>0 for x in accepted);loss=sum(x['net_pnl']<=0 for x in accepted);pf=(sum(x['net_pnl'] for x in accepted if x['net_pnl']>0)/abs(sum(x['net_pnl'] for x in accepted if x['net_pnl']<0))) if any(x['net_pnl']<0 for x in accepted) else None
    eq=0;peak=0;dd=0
    for x in sorted(accepted,key=lambda z:z['exit_time']):eq+=x['net_pnl'];peak=max(peak,eq);dd=min(dd,eq-peak)
    return {'mode':mode,'signals_seen':len(sigs),'prepared_candidates':len(prepared),'trades':len(accepted),'wins':wins,'losses':loss,'win_rate_pct':round(wins/len(accepted)*100,2) if accepted else 0,'net_pnl':net,'gross_profit':sum(max(0,x['net_pnl']) for x in accepted),'gross_loss':sum(min(0,x['net_pnl']) for x in accepted),'profit_factor':pf,'expectancy':net/len(accepted) if accepted else 0,'max_drawdown':dd,'avg_holding_min':sum(x['holding_min'] for x in accepted)/len(accepted) if accepted else 0,'rejects':dict(reject),'trades_data':accepted}

def main():
    p=argparse.ArgumentParser();p.add_argument('--signals',required=True);p.add_argument('--data-dir',required=True);p.add_argument('--one-minute-dir',default='');p.add_argument('--market-data-file',default='');p.add_argument('--output',default='backtest_results/strategy_e_v74_trades.csv');p.add_argument('--summary',default='backtest_results/strategy_e_v74_summary.json');p.add_argument('--capital',type=float,default=35000);p.add_argument('--leverage',type=float,default=5);p.add_argument('--max-open',type=int,default=2);p.add_argument('--max-entries',type=int,default=2);p.add_argument('--final-r',type=float,default=3);p.add_argument('--trading-start',default='09:15');p.add_argument('--trading-end',default='15:00');p.add_argument('--first-signal-cutoff',default='09:35');p.add_argument('--max-risk-pct',type=float,default=2);p.add_argument('--score-threshold',type=float,default=65);p.add_argument('--market-filter',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--min-adx',type=float,default=18);p.add_argument('--min-relative-volume',type=float,default=1);p.add_argument('--min-atr-pct',type=float,default=.2);p.add_argument('--max-atr-pct',type=float,default=4);p.add_argument('--fib-ema-tolerance-pct',type=float,default=.25);p.add_argument('--zone-tolerance-pct',type=float,default=.15);p.add_argument('--stop-buffer-pct',type=float,default=.15);p.add_argument('--wait-minutes',type=int,default=20);p.add_argument('--allow-continuation',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--risk-sizing',action=argparse.BooleanOptionalAction,default=False);p.add_argument('--risk-per-trade-inr',type=float,default=1750);p.add_argument('--break-even',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--break-even-r',type=float,default=.8);p.add_argument('--break-even-lock-r',type=float,default=0);p.add_argument('--time-stop',type=int,default=90);p.add_argument('--stagnation-pct',type=float,default=.2);p.add_argument('--trailing-stop',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--trailing-lock-r',type=float,default=.5);p.add_argument('--trailing-distance-r',type=float,default=1);p.add_argument('--fixed-charge',type=float,default=40);p.add_argument('--slippage-pct',type=float,default=.02);p.add_argument('--entry-mode',choices=['PULLBACK_BOS','CONTINUATION_BOS','ADAPTIVE'],default='PULLBACK_BOS');p.add_argument('--debug',action='store_true');a=p.parse_args()
    r=run_mode(a,a.entry_mode);tr=Path(a.output);tr.parent.mkdir(parents=True,exist_ok=True)
    if r['trades_data']:
        keys=['symbol','signal_time','entry_time','exit_time','entry_method','entry','stop','qty','fib_50','fib_618','ema9','score','grade','partial_exit','final_exit','reason','gross_pnl','costs','net_pnl']
        with tr.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
            for x in r['trades_data']:w.writerow({k:x.get(k) for k in keys})
    clean={k:v for k,v in r.items() if k!='trades_data'};Path(a.summary).parent.mkdir(parents=True,exist_ok=True);Path(a.summary).write_text(json.dumps(clean,indent=2,default=str))
    print(json.dumps(clean,indent=2));print('TRADES:',tr.resolve(),'SUMMARY:',Path(a.summary).resolve())
if __name__=='__main__':main()
