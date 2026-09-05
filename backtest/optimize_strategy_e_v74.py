#!/usr/bin/env python3
"""V7.4 entry optimizer: compares delayed entry modes without changing the exit model."""
import argparse,json,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--signals',required=True);p.add_argument('--data-dir',required=True);p.add_argument('--one-minute-dir',default='');p.add_argument('--market-data-file',default='');p.add_argument('--output-dir',default='backtest_results/optimizer_v74');p.add_argument('--modes',default='PULLBACK_BOS,CONTINUATION_BOS,ADAPTIVE');p.add_argument('--score-grid',default='55,60,65,70');p.add_argument('--wait-grid',default='15,20');p.add_argument('--fib-ema-tolerance-grid',default='0.20,0.25,0.40');p.add_argument('--zone-tolerance-grid',default='0.10,0.15,0.25');p.add_argument('--top',type=int,default=20);a=p.parse_args()
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);results=[];i=0
    for mode in [x.strip() for x in a.modes.split(',') if x.strip()]:
      for score in [float(x) for x in a.score_grid.split(',')]:
       for wait in [int(x) for x in a.wait_grid.split(',')]:
        for et in [float(x) for x in a.fib_ema_tolerance_grid.split(',')]:
         for zt in [float(x) for x in a.zone_tolerance_grid.split(',')]:
          i+=1;summary=out/f'summary_{i}.json';trades=out/f'trades_{i}.csv'
          cmd=[sys.executable,'backtest/backtest_strategy_e_v74.py','--signals',a.signals,'--data-dir',a.data_dir,'--one-minute-dir',a.one_minute_dir,'--entry-mode',mode,'--score-threshold',str(score),'--wait-minutes',str(wait),'--fib-ema-tolerance-pct',str(et),'--zone-tolerance-pct',str(zt),'--output',str(trades),'--summary',str(summary)]
          if a.market_data_file:cmd += ['--market-data-file',a.market_data_file]
          subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
          sm=json.loads(summary.read_text());results.append({'config':{'entry_mode':mode,'score_threshold':score,'wait_minutes':wait,'fib_ema_tolerance_pct':et,'zone_tolerance_pct':zt},'net_pnl':sm['net_pnl'],'profit_factor':sm['profit_factor'] or 0,'max_drawdown':sm['max_drawdown'],'win_rate_pct':sm['win_rate_pct'],'trades':sm['trades'],'expectancy':sm['expectancy'],'prepared_candidates':sm['prepared_candidates']})
    results.sort(key=lambda r:(r['profit_factor'],r['net_pnl'],-abs(r['max_drawdown'])),reverse=True);ranked=out/'optimization_ranked.json';ranked.write_text(json.dumps(results[:a.top],indent=2));print('RUNS',i);print('TOP RESULTS');print(json.dumps(results[:a.top],indent=2));print('OUTPUT',ranked.resolve())
if __name__=='__main__':main()
