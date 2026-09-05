#!/usr/bin/env python3
"""Small, transparent grid-search optimizer for Strategy E V7.
The optimizer runs the same backtester repeatedly; it does not invent a new strategy.
"""
import argparse,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def run_once(base,extra,output_root,index):
    out=Path(output_root);out.mkdir(parents=True,exist_ok=True)
    summary=out/f'summary_{index}.json';trades=out/f'trades_{index}.csv'
    cmd=[sys.executable,'backtest/backtest_strategy_e.py','--signals',base[0],'--data-dir',base[1],'--output',str(trades),'--summary',str(summary)]
    if base[2]:cmd += ['--market-data-file',base[2]]
    for k,v in extra.items():cmd += [f'--{k.replace("_","-")}',str(v)]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
    return json.loads(summary.read_text())

def main():
    p=argparse.ArgumentParser();p.add_argument('--signals',required=True);p.add_argument('--data-dir',required=True);p.add_argument('--market-data-file',default='');p.add_argument('--output-dir',default='backtest_results/optimizer')
    p.add_argument('--score-grid',default='60,70');p.add_argument('--trade2-score-grid',default='70,80');p.add_argument('--max-risk-grid',default='1.5,2.0');p.add_argument('--be-r-grid',default='0.7,0.9');p.add_argument('--trail-lock-grid',default='0.5,0.75');p.add_argument('--trail-distance-grid',default='0.75,1.0');p.add_argument('--basket-distance-grid',default='750,1000');p.add_argument('--windows-grid',default='09:15-11:00,13:00-14:45|09:20-11:30,13:00-14:45');p.add_argument('--top',type=int,default=20)
    a=p.parse_args();
    grids={
      'score_threshold':[float(x) for x in a.score_grid.split(',')], 'trade2_score_threshold':[float(x) for x in a.trade2_score_grid.split(',')], 'max_risk_pct':[float(x) for x in a.max_risk_grid.split(',')],
      'break_even_r':[float(x) for x in a.be_r_grid.split(',')], 'trailing_lock_r':[float(x) for x in a.trail_lock_grid.split(',')], 'trailing_distance_r':[float(x) for x in a.trail_distance_grid.split(',')], 'basket_trailing_distance':[float(x) for x in a.basket_distance_grid.split(',')], 'time_windows':a.windows_grid.split('|')}
    # Keep search bounded by sampling all scalar dimensions but require no more than 3^7*2 = 4374 runs by default.
    results=[];base=(a.signals,a.data_dir,a.market_data_file);i=0
    for score in grids['score_threshold']:
      for t2 in grids['trade2_score_threshold']:
       if t2<score:continue
       for mr in grids['max_risk_pct']:
        for be in grids['break_even_r']:
         for tl in grids['trailing_lock_r']:
          for td in grids['trailing_distance_r']:
           for bd in grids['basket_trailing_distance']:
            for tw in grids['time_windows']:
             i+=1;cfg={'score_threshold':score,'trade2_score_threshold':t2,'max_risk_pct':mr,'break_even_r':be,'trailing_lock_r':tl,'trailing_distance_r':td,'basket_trailing_distance':bd,'time_windows':tw}
             sm=run_once(base,cfg,a.output_dir,i);results.append({'config':cfg,'net_pnl':sm['net_pnl'],'profit_factor':sm['profit_factor'] or 0,'max_drawdown':sm['max_drawdown'],'win_rate_pct':sm['win_rate_pct'],'trades':sm['trades'],'expectancy':sm['expectancy']})
             if i%50==0:print('completed',i)
    results.sort(key=lambda r:(r['profit_factor'],r['net_pnl'],r['max_drawdown']),reverse=True)
    out=Path(a.output_dir)/'optimization_ranked.json';out.write_text(json.dumps(results[:a.top],indent=2),encoding='utf-8');print('RUNS',i);print('TOP RESULTS');print(json.dumps(results[:a.top],indent=2));print('OUTPUT',out.resolve())
if __name__=='__main__':main()
