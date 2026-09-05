import json
from pathlib import Path
from threading import RLock
from models import PositionState
from config import DATA_DIR

class StateStore:
    def __init__(self, path=None):
        self.path=Path(path) if path else DATA_DIR/"state"/"state.json"
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=RLock()

    def load(self):
        with self.lock:
            if not self.path.exists(): return {"positions":{},"processed_webhooks":[],"daily_entries":{},"portfolio":{},"pending_entries":{}}
            try: return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc: raise RuntimeError(f"State file is corrupt: {self.path}: {exc}") from exc

    def save(self,data):
        with self.lock:
            tmp=self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data,default=str,indent=2),encoding="utf-8")
            tmp.replace(self.path)

    def positions(self): return self.load().get("positions",{})
    def upsert_position(self,p:PositionState):
        data=self.load(); data.setdefault("positions",{})[p.symbol]=p.to_dict(); self.save(data)
    def upsert_position_dict(self,p:dict):
        data=self.load(); data.setdefault("positions",{})[p["symbol"]]=p; self.save(data)
    def remove_position(self,symbol):
        data=self.load(); data.setdefault("positions",{}).pop(symbol,None); self.save(data)
    def processed(self,key): return key in self.load().get("processed_webhooks",[])
    def mark_processed(self,key):
        data=self.load(); arr=data.setdefault("processed_webhooks",[]);
        if key not in arr: arr.append(key)
        data["processed_webhooks"]=arr[-2000:]; self.save(data)
    def entry_count(self,day): return int(self.load().get("daily_entries",{}).get(day,0))
    def increment_entry(self,day):
        data=self.load(); d=data.setdefault("daily_entries",{}); d[day]=int(d.get(day,0))+1; self.save(data)
    def daily_realized_pnl(self, day):
        return float(self.load().get("daily_realized_pnl",{}).get(day,0.0))
    def add_daily_realized_pnl(self, day, amount):
        data=self.load(); d=data.setdefault("daily_realized_pnl",{}); d[day]=float(d.get(day,0.0))+float(amount); self.save(data)
    def consecutive_losses(self):
        return int(self.load().get("risk_meta",{}).get("consecutive_losses",0))
    def record_closed_trade(self, day, pnl):
        data=self.load(); d=data.setdefault("daily_realized_pnl",{}); d[day]=float(d.get(day,0.0))+float(pnl)
        meta=data.setdefault("risk_meta",{}); meta["consecutive_losses"]=(int(meta.get("consecutive_losses",0))+1) if float(pnl)<0 else 0
        self.save(data)
    def append_signal_intelligence(self, row):
        path=self.path.parent/"trade_intelligence.jsonl"
        with path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(row,default=str,separators=(",",":"))+"\n")
    def pending_entries(self): return self.load().get("pending_entries",{})
    def upsert_pending_entry(self, symbol, data):
        state=self.load(); state.setdefault("pending_entries",{})[symbol.upper()]=data; self.save(state)
    def remove_pending_entry(self, symbol):
        state=self.load(); state.setdefault("pending_entries",{}).pop(symbol.upper(),None); self.save(state)
    def portfolio_state(self):
        return self.load().get("portfolio",{})
    def update_portfolio_state(self, **kwargs):
        data=self.load(); portfolio=data.setdefault("portfolio",{}); portfolio.update(kwargs); self.save(data)
