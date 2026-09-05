#!/usr/bin/env python3
"""Strategy E V7 5-minute backtester with feature scoring and portfolio risk controls."""
import argparse,csv,json,re,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,time
from collections import defaultdict,Counter
from feature_engine import score_trade


def dt(s):
    s=str(s or '').strip()
    for f in ('%d-%m-%Y %I:%M %p','%d-%m-%Y %H:%M','%Y-%m-%d %H:%M:%S%z','%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M%z','%Y-%m-%d %H:%M'):
        try:
            x=datetime.strptime(s,f); return x.astimezone().replace(tzinfo=None) if x.tzinfo else x
        except: pass
    try:
        x=datetime.fromisoformat(s.replace('Z','+00:00')); return x.astimezone().replace(tzinfo=None) if x.tzinfo else x
    except: return None


def sigs(path):
    out=[]
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        for n,r in enumerate(csv.DictReader(f),2):
            s=(r.get('Symbol') or r.get('symbol') or r.get('Tradingsymbol') or '').strip().upper(); t=dt(r.get('Date') or r.get('date') or r.get('timestamp') or r.get('Timestamp'))
            if s and t: out.append({'row':n,'symbol':s,'signal_time':t})
    return out


def sym(f):
    stem=Path(f).stem
    m=re.match(r'^(.+?)_\d{8}_\d{8}_5minute$',stem,re.I)
    return m.group(1).upper() if m else stem.split('_')[0].upper()


def load_index(folder):
    x=defaultdict(list)
    for f in Path(folder).glob('*.csv'): x[sym(f)].append(f)
    return x


def bars(path):
    out=[]
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            t=dt(r.get('date') or r.get('Date') or r.get('timestamp'))
            if not t: continue
            try: out.append({'ts':t,'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close']),'volume':float(r.get('volume',0) or 0)})
            except: pass
    return sorted(out,key=lambda x:x['ts'])


def find_bar(bs,ts,tol=60):
    if not bs:return None
    i=min(range(len(bs)),key=lambda j:abs((bs[j]['ts']-ts).total_seconds()))
    return i if abs((bs[i]['ts']-ts).total_seconds())<=tol else None


def windows(s):
    out=[]
    for x in str(s or '').split(','):
        if '-' not in x:continue
        a,b=x.strip().split('-',1)
        out.append((datetime.strptime(a,'%H:%M').time(),datetime.strptime(b,'%H:%M').time()))
    return out


def one_trade(c,bs,capital,lev,final_r,time_stop,stag_pct,trail_on,trail_lock,trail_dist,charge,slip,be_on,be_r,be_lock_r,risk_size_on,risk_inr):
    si=c['signal_idx']; ei=si+1
    if ei>=len(bs): return None
    entry=bs[ei]['open']; signal_low=bs[si]['low']; risk=max(entry-signal_low,0.0)
    if risk<=0:return {'status':'REJECTED','reason':'INVALID_RISK'}
    cap_qty=int(capital*lev//entry)
    risk_qty=int(risk_inr//risk) if risk_size_on else cap_qty
    qty=min(cap_qty,risk_qty)
    if qty<2:return {'status':'REJECTED','reason':'QUANTITY_LT_2_AFTER_RISK_SIZING'}
    q1=qty//2;q2=qty-q1;one=entry+risk;target=entry+final_r*risk
    partial_i=None;partial=None;exit_price=None;exit_i=None;reason=None;peak=0.0;be_stop=None
    for j in range(ei,len(bs)):
        b=bs[j]
        if b['ts'].date()!=bs[si]['ts'].date():break
        # Before 1R, break-even/profit-lock can arm; this is checked before the partial trigger.
        if partial is None and be_on and b['high']>=entry+be_r*risk:
            be_stop=max(signal_low,entry+be_lock_r*risk)
        if partial is None:
            if be_stop is not None and b['low']<=be_stop:
                exit_price=be_stop;exit_i=j;reason='BREAK_EVEN_PROFIT_LOCK';break
            if b['low']<=signal_low:
                exit_price=signal_low;exit_i=j;reason='STOP';break
            if b['high']>=one:
                partial=one;partial_i=j;peak=b['high'];be_stop=max(be_stop or signal_low,entry+be_lock_r*risk)
                if b['high']>=target:
                    exit_price=target;exit_i=j;reason='TARGET';break
        else:
            if trail_on:
                floor=max(entry+trail_lock*risk, be_stop or signal_low)
                trailing=max(floor,peak-trail_dist*risk)
                if b['low']<=trailing:
                    exit_price=trailing;exit_i=j;reason='TRAILING_STOP';break
            if b['low']<=signal_low:
                exit_price=signal_low;exit_i=j;reason='STOP_AFTER_PARTIAL';break
            if b['high']>=target:
                exit_price=target;exit_i=j;reason='TARGET';break
            elapsed=(b['ts']-bs[partial_i]['ts']).total_seconds()/60
            if elapsed>=time_stop and peak<partial*(1+stag_pct/100):
                exit_price=partial;exit_i=j;reason='TIME_STAGNATION';break
            peak=max(peak,b['high'])
        if j+1>=len(bs) or bs[j+1]['ts'].date()!=b['ts'].date() or bs[j+1]['ts'].time()>time(15,0):
            exit_price=b['close'];exit_i=j;reason='EOD_FLATTEN';break
    if exit_price is None:return None
    if partial is None:gross=(exit_price-entry)*qty;turn=entry*qty+exit_price*qty
    else:gross=(partial-entry)*q1+(exit_price-entry)*q2;turn=entry*qty+partial*q1+exit_price*q2
    net=gross-turn*slip/100-charge
    return {'status':'TRADE','reason':reason,'entry':entry,'qty':qty,'buy_value':entry*qty,'margin':entry*qty/lev,'signal_low':signal_low,'risk':risk,'one_r':one,'final_target':target,'partial_exit':partial,'partial_time':(bs[partial_i]['ts'] if partial_i is not None else None),'partial_qty':q1,'remaining_qty_at_partial':q2,'final_exit':exit_price,'gross_pnl':gross,'costs':turn*slip/100+charge,'net_pnl':net,'entry_time':bs[ei]['ts'],'exit_time':bs[exit_i]['ts'],'holding_min':(bs[exit_i]['ts']-bs[ei]['ts']).total_seconds()/60,'peak_after_partial':peak}


def basket_adjust(trades,cache,target=4500.0,trailing_on=True,trailing_distance=1000.0,slip=0.02,charge=40.0):
    trades=sorted(trades,key=lambda x:(x['entry_time'],x['symbol']))
    for i,a in enumerate(trades):
        for b in trades[i+1:]:
            if a['symbol']==b['symbol']:continue
            start=max(a['entry_time'],b['entry_time']);end=min(a['exit_time'],b['exit_time'])
            if start>=end:continue
            amap={x['ts']:x['close'] for x in cache[a['bars_file']] if start<=x['ts']<=end}; bmap={x['ts']:x['close'] for x in cache[b['bars_file']] if start<=x['ts']<=end}
            armed=False;peak=0.0
            for ts in sorted(set(amap)&set(bmap)):
                total=0.0;per=[]
                for x,px in ((a,amap[ts]),(b,bmap[ts])):
                    qty=int(x['qty']);q1=int(x['partial_qty']);q2=int(x['remaining_qty_at_partial']);pp=x.get('partial_exit');pt=x.get('partial_time')
                    pnl=(pp-x['entry'])*q1+(px-x['entry'])*q2 if pp is not None and pt is not None and pt<=ts else (px-x['entry'])*qty
                    total+=pnl;per.append((x,px))
                if not armed and total>=target:armed=True;peak=total
                if armed:
                    peak=max(peak,total);stop=max(target,peak-trailing_distance) if trailing_on else target
                    if total<=stop:
                        for x,px in per:
                            qty=int(x['qty']);q1=int(x['partial_qty']);q2=int(x['remaining_qty_at_partial']);pp=x.get('partial_exit');pt=x.get('partial_time')
                            gross=(pp-x['entry'])*q1+(px-x['entry'])*q2 if pp is not None and pt is not None and pt<=ts else (px-x['entry'])*qty
                            turnover=x['entry']*qty+(pp*q1 if pp is not None and pt is not None and pt<=ts else 0)+px*(q2 if pp is not None and pt is not None and pt<=ts else qty)
                            x['final_exit']=px;x['exit_time']=ts;x['reason']='PORTFOLIO_PROFIT_TARGET_TRAILING_STOP';x['gross_pnl']=gross;x['costs']=turnover*slip/100+charge;x['net_pnl']=gross-x['costs'];x['portfolio_target_pnl']=target;x['portfolio_peak_pnl']=peak;x['portfolio_trailing_stop_pnl']=stop
                        return trades
    return trades



def rank_key(row):
    """
    Point-in-time ranking only.
    Higher feature score is preferred, followed by stronger ADX,
    relative volume, and lower risk.
    """
    return (
        float(row.get('feature_score') or 0),
        float(row.get('adx14') or 0),
        float(row.get('relative_volume') or 0),
        -float(row.get('risk_pct') or 999),
    )

def main():
    p=argparse.ArgumentParser(description='Strategy E V7 5-minute backtest')
    p.add_argument('--signals',required=True);p.add_argument('--data-dir',required=True);p.add_argument('--market-data-file',default='');p.add_argument('--output',default='backtest_results/strategy_e_v7_trades.csv');p.add_argument('--summary',default='backtest_results/strategy_e_v7_summary.json')
    p.add_argument('--capital',type=float,default=35000);p.add_argument('--leverage',type=float,default=5);p.add_argument('--max-open',type=int,default=2);p.add_argument('--max-entries',type=int,default=2);p.add_argument('--final-r',type=float,default=3.0);p.add_argument('--trading-start',default='09:15');p.add_argument('--trading-end',default='15:00');p.add_argument('--first-signal-cutoff',default='09:35');p.add_argument('--max-signal-candle-pct',type=float,default=8.0)
    p.add_argument('--max-risk-pct',type=float,default=2.0);p.add_argument('--score-threshold',type=float,default=65);p.add_argument('--trade2-score-threshold',type=float,default=75);p.add_argument('--market-filter',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--min-adx',type=float,default=18);p.add_argument('--min-relative-volume',type=float,default=1.0);p.add_argument('--min-atr-pct',type=float,default=.20);p.add_argument('--max-atr-pct',type=float,default=4.0);p.add_argument('--time-windows',default='09:20-11:30,13:00-14:45');p.add_argument('--second-trade-min-score',type=float,default=75);p.add_argument('--second-trade-open-loss-limit',type=float,default=-1500)
    p.add_argument('--risk-sizing',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--risk-per-trade-inr',type=float,default=1750);p.add_argument('--break-even',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--break-even-r',type=float,default=.80);p.add_argument('--break-even-lock-r',type=float,default=0.0)
    p.add_argument('--time-stop',type=int,default=90);p.add_argument('--stagnation-pct',type=float,default=.20);p.add_argument('--trailing-stop',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--trailing-lock-r',type=float,default=.50);p.add_argument('--trailing-distance-r',type=float,default=1.0);p.add_argument('--basket-target',type=float,default=4500);p.add_argument('--basket-trailing',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--basket-trailing-distance',type=float,default=1000);p.add_argument('--daily-loss-limit',type=float,default=7000);p.add_argument('--daily-profit-lock',type=float,default=6000);p.add_argument('--max-consecutive-losses',type=int,default=2);p.add_argument('--slippage-pct',type=float,default=.02);p.add_argument('--fixed-charge',type=float,default=40);p.add_argument('--debug',action='store_true')
    a=p.parse_args();signals=sigs(a.signals);idx=load_index(a.data_dir);cache={};decisions=[];candidates=[]
    start=time.fromisoformat(a.trading_start);end=time.fromisoformat(a.trading_end);cut=time.fromisoformat(a.first_signal_cutoff);tw=windows(a.time_windows)
    market=[]
    market_path=Path(a.market_data_file) if a.market_data_file else Path(a.data_dir)/'NIFTY 50_5minute.csv'
    if market_path.exists(): market=bars(market_path)
    # Signal quality feature calculation is CPU-only over local bars. No API calls occur in the loop.
    for s in signals:
        f=(idx.get(s['symbol']) or [None])[0]
        if not f: decisions.append({**s,'status':'REJECTED','reason':'CACHE_MISSING'});continue
        key=str(f);cache.setdefault(key,bars(f));bs=cache[key];si=find_bar(bs,s['signal_time'])
        if si is None: decisions.append({**s,'status':'REJECTED','reason':'SIGNAL_CANDLE_NOT_FOUND'});continue
        b=bs[si];rng=(b['high']-b['low'])/max(b['low'],1e-9)*100
        if b['ts'].time()<start or b['ts'].time()>end: decisions.append({**s,'status':'REJECTED','reason':'OUTSIDE_TRADING_WINDOW','signal_range_pct':rng});continue
        if a.max_signal_candle_pct>=0 and rng>a.max_signal_candle_pct: decisions.append({**s,'status':'REJECTED','reason':'SIGNAL_CANDLE_OVER_LIMIT','signal_range_pct':rng});continue
        candidates.append({**s,'signal_idx':si,'bars_file':key,'signal_range_pct':rng})
    candidates.sort(key=lambda x:(x['signal_time'],x['symbol'],x['row']))
    day_count=defaultdict(int);active=[];closed_by_day=defaultdict(list);day_net=defaultdict(float);day_consecutive=defaultdict(int)
    # Point-in-time ranked selection.
    # Signals with the same timestamp compete using only information
    # available at that timestamp.
    from itertools import groupby

    candidates.sort(key=lambda x:(x['signal_time'],x['symbol'],x['row']))

    day_count=defaultdict(int)
    active=[]
    closed_by_day=defaultdict(list)
    day_net=defaultdict(float)
    day_consecutive=defaultdict(int)

    for ts, group_iter in groupby(candidates, key=lambda x:x['signal_time']):
        group=list(group_iter)
        day=ts.date()

        # Release trades which have already exited before this timestamp.
        still_active=[]
        for x in active:
            if x['exit_time']<=ts:
                exit_day=x['exit_time'].date()
                day_net[exit_day]+=x['net_pnl']
                day_consecutive[exit_day]=(
                    day_consecutive[exit_day]+1
                    if x['net_pnl']<0 else 0
                )
                closed_by_day[exit_day].append(x)
            else:
                still_active.append(x)
        active=still_active

        # Daily protection rules.
        if day_net[day]>=a.daily_profit_lock:
            for c in group:
                decisions.append({
                    **c,'status':'REJECTED','reason':'DAILY_PROFIT_LOCK'
                })
            continue

        if day_net[day]<=-a.daily_loss_limit:
            for c in group:
                decisions.append({
                    **c,'status':'REJECTED','reason':'DAILY_LOSS_LOCK'
                })
            continue

        if day_consecutive[day]>=a.max_consecutive_losses:
            for c in group:
                decisions.append({
                    **c,'status':'REJECTED','reason':'CONSECUTIVE_LOSS_LOCK'
                })
            continue

        # Preserve first-signal cutoff.
        if ts.time()>cut and day_count[day]==0:
            for c in group:
                decisions.append({
                    **c,'status':'REJECTED','reason':'FIRST_SIGNAL_CUTOFF'
                })
            continue

        available_entries=max(0,a.max_entries-day_count[day])
        available_open=max(0,a.max_open-len(active))
        available_slots=min(available_entries,available_open)

        if available_slots<=0:
            reason=(
                'MAX_ENTRIES_PER_DAY'
                if available_entries<=0
                else 'MAX_OPEN_POSITIONS'
            )
            for c in group:
                decisions.append({
                    **c,'status':'REJECTED','reason':reason
                })
            continue

        # Current open basket P&L.
        open_loss=0.0
        if active:
            for x in active:
                xb=cache[x['bars_file']]
                xi=find_bar(xb,ts)
                if xi is not None:
                    open_loss+=(xb[xi]['close']-x['entry'])*x['qty']

        # ---------------------------------------------------------------
        # PHASE 1:
        # Evaluate every candidate using the first-trade threshold.
        # This creates the complete point-in-time candidate pool.
        # ---------------------------------------------------------------
        evaluated=[]

        for c in group:
            bs=cache[c['bars_file']]
            signal_bar=bs[c['signal_idx']]

            entry_preview=(
                bs[c['signal_idx']+1]['open']
                if c['signal_idx']+1<len(bs)
                else signal_bar['close']
            )

            snap=score_trade(
                symbol=c['symbol'],
                signal_time=ts,
                signal_open=signal_bar['open'],
                signal_high=signal_bar['high'],
                signal_low=signal_bar['low'],
                signal_close=signal_bar['close'],
                entry_price=entry_preview,
                bars=bs[:c['signal_idx']+1],
                market_bars=[m for m in market if m['ts']<=ts],
                max_risk_pct=a.max_risk_pct,
                min_adx=a.min_adx,
                min_relative_volume=a.min_relative_volume,
                min_atr_pct=a.min_atr_pct,
                max_atr_pct=a.max_atr_pct,
                score_threshold=a.score_threshold,
                start=start,
                end=end,
                allow_windows=tw,
                market_filter=a.market_filter
            )

            row={
                **c,
                'feature_score':snap.score,
                'feature_grade':snap.grade,
                'risk_pct':snap.risk_pct,
                'atr_pct':snap.atr_pct,
                'adx14':snap.adx14,
                'relative_volume':snap.relative_volume,
                'vwap':snap.vwap,
                'market_regime_ok':snap.market_regime_ok,
                'time_window_ok':snap.time_window_ok,
                'feature_reasons':'|'.join(snap.reasons),
                'trade_threshold':a.score_threshold,
                'open_positions_pnl_at_signal':open_loss
            }

            feature_pass=bool(
                snap.score>=a.score_threshold
                and snap.market_regime_ok
                and snap.time_window_ok
                and snap.risk_ok
            )

            if not feature_pass:
                reason='FEATURE_REJECT:'+'|'.join(
                    snap.reasons or ('SCORE_BELOW_THRESHOLD',)
                )
                decisions.append({
                    **row,
                    'status':'REJECTED',
                    'reason':reason
                })
                continue

            if day_count[day]>=1 and open_loss<=a.second_trade_open_loss_limit:
                decisions.append({
                    **row,
                    'status':'REJECTED',
                    'reason':'SECOND_TRADE_OPEN_LOSS_GUARD'
                })
                continue

            evaluated.append(row)

        if not evaluated:
            continue

        # ---------------------------------------------------------------
        # PHASE 2:
        # Rank all point-in-time candidates.
        # ---------------------------------------------------------------
        evaluated.sort(key=rank_key,reverse=True)

        selected_rows=[]

        # ---------------------------------------------------------------
        # PHASE 3:
        # Select FIRST trade using the normal threshold.
        # ---------------------------------------------------------------
        first_trade=None

        if day_count[day]<a.max_entries and len(active)<a.max_open:
            if evaluated:
                first_trade=evaluated[0]
                selected_rows.append(first_trade)

        # ---------------------------------------------------------------
        # PHASE 4:
        # Select SECOND trade independently.
        #
        # The second trade MUST:
        #   - be different from the first trade
        #   - satisfy the stricter second-trade score
        #   - respect the open-loss guard
        # ---------------------------------------------------------------
        if (
            available_slots>=2
            and first_trade is not None
            and day_count[day]+1<a.max_entries
            and len(active)+1<a.max_open
        ):
            second_trade=None

            for candidate in evaluated[1:]:
                if candidate['feature_score'] < a.trade2_score_threshold:
                    continue

                candidate['trade_threshold']=a.trade2_score_threshold
                second_trade=candidate
                break

            if second_trade is not None:
                selected_rows.append(second_trade)

        # ---------------------------------------------------------------
        # PHASE 5:
        # Execute selected trades.
        # ---------------------------------------------------------------
        selected_symbols=set()

        for row in selected_rows:
            if row['symbol'] in selected_symbols:
                continue

            if day_count[day]>=a.max_entries:
                break

            if len(active)>=a.max_open:
                break

            c=row
            bs=cache[c['bars_file']]

            tr=one_trade(
                c,
                bs,
                a.capital,
                a.leverage,
                a.final_r,
                a.time_stop,
                a.stagnation_pct,
                a.trailing_stop,
                a.trailing_lock_r,
                a.trailing_distance_r,
                a.fixed_charge,
                a.slippage_pct,
                a.break_even,
                a.break_even_r,
                a.break_even_lock_r,
                a.risk_sizing,
                a.risk_per_trade_inr
            )

            if not tr:
                decisions.append({
                    **row,
                    'status':'REJECTED',
                    'reason':'TRADE_SIMULATION_FAILED'
                })
                continue

            row.update(tr)

            if tr['status']!='TRADE':
                decisions.append(row)
                continue

            row['signal_time']=c['signal_time']
            row['symbol']=c['symbol']
            row['remaining_qty']=tr['qty']

            decisions.append(row)
            active.append(row)
            selected_symbols.add(row['symbol'])
            day_count[day]+=1

        # Mark other qualifying candidates as losing the point-in-time ranking.
        selected_symbol_set=set(selected_symbols)

        for row in evaluated:
            if row['symbol'] not in selected_symbol_set:
                # It was already recorded if it failed a feature/guard.
                # Only record candidates that remained eligible but weren't selected.
                decisions.append({
                    **row,
                    'status':'REJECTED',
                    'reason':'RANKED_SLOT_NOT_SELECTED'
                })

    trades=[r for r in decisions if r.get('status')=='TRADE']
    trades=basket_adjust(trades,cache,a.basket_target,a.basket_trailing,a.basket_trailing_distance,a.slippage_pct,a.fixed_charge)
    pnl=[x['net_pnl'] for x in trades];wins=[x for x in pnl if x>0];loss=[x for x in pnl if x<0]
    eq=peak=dd=0
    for x in pnl:eq+=x;peak=max(peak,eq);dd=min(dd,eq-peak)
    summary={'strategy':'Strategy E V7','timeframe':'5minute','signals_seen':len(signals),'candidate_signals':len(candidates),'trades':len(trades),'rejected':len(decisions)-len(trades),'wins':len(wins),'losses':len(loss),'win_rate_pct':100*len(wins)/len(trades) if trades else 0,'net_pnl':sum(pnl),'gross_profit':sum(wins),'gross_loss':sum(loss),'profit_factor':sum(wins)/(-sum(loss)) if loss else None,'expectancy':sum(pnl)/len(trades) if trades else 0,'max_drawdown':dd,'avg_holding_min':sum(x['holding_min'] for x in trades)/len(trades) if trades else 0,'exit_reasons':dict(Counter(x['reason'] for x in trades)),'rejection_reasons':dict(Counter(x.get('reason') for x in decisions if x.get('status')!='TRADE')),'configuration':{**vars(a),'market_data_file_resolved':str(market_path) if market_path.exists() else ''}}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);fields=[];seen=set()
    for r in decisions:
        for k in r:
            if k not in seen:seen.add(k);fields.append(k)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(decisions)
    Path(a.summary).write_text(json.dumps(summary,indent=2,default=str),encoding='utf-8')
    html=out.with_suffix('.html');html.write_text('<html><head><meta charset="utf-8"><title>Strategy E V7 Backtest</title></head><body><h1>Strategy E V7 Backtest</h1><pre>'+json.dumps(summary,indent=2,default=str)+'</pre></body></html>',encoding='utf-8')
    if a.debug: print('CACHE FILES INDEXED:',sum(len(v) for v in idx.values()),'CACHE SYMBOLS:',len(idx),'SIGNALS:',len(signals),'CANDIDATES:',len(candidates))
    print(json.dumps(summary,indent=2,default=str));print('TRADES:',out.resolve());print('SUMMARY:',Path(a.summary).resolve());print('HTML:',html.resolve())
if __name__=='__main__':main()
