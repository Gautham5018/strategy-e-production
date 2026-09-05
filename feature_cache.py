"""In-memory feature-bar cache. No historical API calls occur in the webhook path."""
from threading import RLock
from datetime import datetime, timedelta

class FeatureBarCache:
    def __init__(self,max_bars=300):
        self.max_bars=max_bars;self._data={};self._lock=RLock()
    def put(self,symbol,bars):
        rows=sorted(list(bars),key=lambda x:x['ts'])[-self.max_bars:]
        with self._lock:self._data[symbol.upper()]=rows
    def append(self,symbol,bar):
        with self._lock:
            rows=self._data.setdefault(symbol.upper(),[])
            if rows and rows[-1]['ts']==bar['ts']:rows[-1]=bar
            else:rows.append(bar)
            self._data[symbol.upper()]=rows[-self.max_bars:]
    def get(self,symbol):
        with self._lock:return list(self._data.get(symbol.upper(),[]))
    def age_seconds(self,symbol,now=None):
        rows=self.get(symbol); now=now or datetime.now()
        if not rows:return None
        return max(0,(now-rows[-1]['ts']).total_seconds())
    def ready(self,symbol,min_bars=30):return len(self.get(symbol))>=min_bars
