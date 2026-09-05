from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv,re

IST=ZoneInfo("Asia/Kolkata")

def _sym(path):
    m=re.match(r'^(.+?)_\d{8}_\d{8}_5minute$',path.stem,re.I)
    return (m.group(1) if m else path.stem.split('_')[0]).upper()

def load_dir(folder, cache):
    folder=Path(folder);loaded=0
    for f in folder.glob('*.csv'):
        rows=[]
        try:
            with f.open(newline='',encoding='utf-8-sig') as h:
                for r in csv.DictReader(h):
                    try:
                        ts=datetime.fromisoformat(str(r['date']).replace('Z','+00:00'))
                        if getattr(ts,'tzinfo',None):ts=ts.astimezone(IST).replace(tzinfo=None)
                        rows.append({'ts':ts,'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close']),'volume':float(r.get('volume',0) or 0)})
                    except Exception: pass
            if rows: cache.put(_sym(f),rows); loaded+=1
        except Exception: pass
    return loaded
