from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock

@dataclass
class RuntimeState:
    startup_complete: bool=False
    broker_ok: bool=False
    market_data_connected: bool=False
    reconciliation: list=field(default_factory=list)
    last_reconciliation_at: str=""
    last_error: str=""
    lock: RLock=field(default_factory=RLock, repr=False)

    def update(self, **kwargs):
        with self.lock:
            for k,v in kwargs.items(): setattr(self,k,v)

    def snapshot(self):
        with self.lock:
            return {
                "startup_complete":self.startup_complete,
                "broker_ok":self.broker_ok,
                "market_data_connected":self.market_data_connected,
                "reconciliation":list(self.reconciliation),
                "last_reconciliation_at":self.last_reconciliation_at,
                "last_error":self.last_error,
            }

    def ready(self, require_market_data=True):
        with self.lock:
            return (self.startup_complete and self.broker_ok and not self.reconciliation and
                    (self.market_data_connected if require_market_data else True))
