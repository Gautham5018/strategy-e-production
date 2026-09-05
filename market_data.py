import threading,time
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
from kiteconnect import KiteTicker
from config import SETTINGS
from logging_setup import logger

IST=ZoneInfo("Asia/Kolkata")

class MarketData:
    def __init__(self,broker,runtime=None):
        self.broker=broker; self.runtime=runtime; self.kws=None; self.prices={}; self.timestamps={}; self.lock=threading.RLock(); self.connected=False; self.started=False; self.bars_1m=defaultdict(list); self.current_bar={}
    def start(self):
        if self.started:return
        self.started=True; self.kws=KiteTicker(SETTINGS.kite_api_key,self.broker.access_token)
        self.kws.on_connect=self._on_connect; self.kws.on_ticks=self._on_ticks; self.kws.on_close=self._on_close; self.kws.on_error=self._on_error
        threading.Thread(target=self._run,daemon=True,name="kite-ticker").start()
    def stop(self):
        self.started=False
        try:
            if self.kws:self.kws.close()
        except Exception:pass
        self._set_connected(False)
    def _run(self):
        try:self.kws.connect(threaded=True)
        except Exception as exc:logger.exception("KITE TICKER connect failed: %s",exc);self._set_connected(False)
        while self.started:time.sleep(1)
    def _set_connected(self,v):
        self.connected=v
        if self.runtime:self.runtime.update(market_data_connected=v)
    def _on_connect(self,ws,response):self._set_connected(True);self._resubscribe_open_positions();self._resubscribe_pending()
    def _pending_tokens(self):
        try:return [int(x.get('instrument_token')) for x in self.broker.state_pending_entries() if x.get('instrument_token')]
        except Exception:return []
    def _resubscribe_open_positions(self):
        try:tokens=[int(p['instrument_token']) for p in self.broker.state_positions() if p.get('instrument_token')]
        except Exception:tokens=[]
        self._subscribe(tokens)
    def _resubscribe_pending(self):self._subscribe(self._pending_tokens())
    def _subscribe(self,tokens):
        if tokens and self.connected:
            self.kws.subscribe(tokens);self.kws.set_mode(self.kws.MODE_LTP,tokens)
    def subscribe(self,token):self._subscribe([int(token)])
    def _on_ticks(self,ws,ticks):
        now=datetime.now(IST).replace(tzinfo=None)
        with self.lock:
            for t in ticks:
                token=int(t['instrument_token']); price=float(t['last_price']); self.prices[token]=price; self.timestamps[token]=now
                bucket=now.replace(second=0,microsecond=0); key=(token,bucket)
                bar=self.current_bar.get(key)
                if bar is None:
                    bar={'ts':bucket,'open':price,'high':price,'low':price,'close':price,'volume':0.0};self.current_bar[key]=bar;self.bars_1m[token].append(bar);self.bars_1m[token]=self.bars_1m[token][-120:]
                else:
                    bar['high']=max(bar['high'],price);bar['low']=min(bar['low'],price);bar['close']=price
    def _on_close(self,ws,code,reason):logger.warning('KITE TICKER closed code=%s reason=%s',code,reason);self._set_connected(False)
    def _on_error(self,ws,code,reason):logger.error('KITE TICKER error code=%s reason=%s',code,reason);self._set_connected(False)
    def get(self,token):
        with self.lock:return self.prices.get(int(token)),self.timestamps.get(int(token))
    def fresh(self,token,max_age):
        p,ts=self.get(token); return p if p is not None and ts is not None and (datetime.now()-ts).total_seconds()<=max_age else None
    def get_1m(self,token,limit=60,closed_only=True):
        with self.lock:
            rows=[dict(x) for x in self.bars_1m.get(int(token),[])]
        if closed_only:
            current_minute=datetime.now(IST).replace(tzinfo=None,second=0,microsecond=0)
            rows=[x for x in rows if x["ts"] < current_minute]
        return rows[-limit:]
