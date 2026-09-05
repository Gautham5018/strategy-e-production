from config import SETTINGS

class Reconciler:
    def __init__(self,broker,store): self.broker=broker; self.store=store
    def reconcile(self):
        broker_positions=self.broker.positions().get("net",[])
        broker_mis={}
        for p in broker_positions:
            if p.get("exchange")==SETTINGS.exchange and p.get("product")==SETTINGS.product:
                q=int(p.get("quantity") or 0)
                if q: broker_mis[p["tradingsymbol"]]=q
        internal=self.store.positions(); problems=[]
        for symbol,p in internal.items():
            expected=int(p.get("remaining_quantity",0)); actual=int(broker_mis.get(symbol,0))
            if expected!=actual: problems.append({"symbol":symbol,"expected":expected,"actual":actual,"type":"POSITION_MISMATCH"})
        for symbol,actual in broker_mis.items():
            if symbol not in internal: problems.append({"symbol":symbol,"expected":0,"actual":actual,"type":"UNKNOWN_BROKER_POSITION"})
        return problems
