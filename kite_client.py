import time
from pathlib import Path
from kiteconnect import KiteConnect
from config import SETTINGS, ROOT
from logging_setup import logger

class KiteBroker:
    def __init__(self, state_store=None):
        self.state_store=state_store
        self.kite=KiteConnect(api_key=SETTINGS.kite_api_key)
        token=""
        p=Path(SETTINGS.kite_access_token_file)
        if p.exists():
            token=p.read_text(encoding="utf-8").strip()
        if not token:
            token=SETTINGS.kite_access_token
        if not token: raise RuntimeError("KITE_ACCESS_TOKEN missing; run `python run.py kite-login` or configure the shared token file")
        self.kite.set_access_token(token); self.access_token=token; self._instruments=None
        # Do not call the profile endpoint during broker construction.
        # Historical-data downloads only need the authenticated client and
        # instruments/historical APIs. Calling profile here created an
        # unnecessary network dependency and could abort OHLC prewarming
        # on transient TLS/API connection resets. Profile is lazy and is
        # still checked by readiness/reconciliation when required.
        self._last_profile = None
        logger.info("KITE BROKER initialized (profile deferred)")

    def profile(self):
        last = None
        for attempt in range(1, 4):
            try:
                self._last_profile=self.kite.profile(); return self._last_profile
            except Exception as exc:
                last = exc
                if attempt < 3:
                    logger.warning("KITE profile attempt=%s failed: %s; retrying", attempt, exc)
                    time.sleep(attempt * 1.5)
        raise last

    def instruments(self):
        if self._instruments is None:
            last = None
            for attempt in range(1, 4):
                try:
                    rows=self.kite.instruments(SETTINGS.exchange); self._instruments={r["tradingsymbol"].upper():r for r in rows}; break
                except Exception as exc:
                    last = exc
                    if attempt < 3:
                        logger.warning("KITE instruments attempt=%s failed: %s; retrying", attempt, exc)
                        time.sleep(attempt * 1.5)
            else:
                raise last
        return self._instruments

    def instrument(self,symbol):
        row=self.instruments().get(symbol.upper())
        if not row: raise ValueError(f"NSE instrument not found: {symbol}")
        return row

    def historical_data(self, instrument_token, from_date, to_date, interval="5minute", continuous=False, oi=False):
        """Read-only wrapper around KiteConnect historical_data."""
        return self.kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=interval,
            continuous=continuous,
            oi=oi,
        )

    def state_pending_entries(self):
        return list(self.state_store.pending_entries().values()) if getattr(self, "state_store", None) else []

    def ltp(self,symbol):
        key=f"{SETTINGS.exchange}:{symbol}"; data=self.kite.ltp([key]); return float(data[key]["last_price"])
    def ltp_many(self,symbols):
        keys=[f"{SETTINGS.exchange}:{s}" for s in symbols]
        if not keys: return {}
        data=self.kite.ltp(keys); return {s:float(data[f"{SETTINGS.exchange}:{s}"]["last_price"]) for s in symbols}
    def positions(self): return self.kite.positions()
    def state_positions(self): return list(self.state_store.positions().values()) if self.state_store else []
    def orders(self): return self.kite.orders()

    def place_market_buy(self,symbol,quantity):
        return self.kite.place_order(variety=self.kite.VARIETY_REGULAR,exchange=SETTINGS.exchange,tradingsymbol=symbol,transaction_type=self.kite.TRANSACTION_TYPE_BUY,quantity=int(quantity),product=self.kite.PRODUCT_MIS,order_type=self.kite.ORDER_TYPE_MARKET,validity=self.kite.VALIDITY_DAY,tag="STRAT_E",market_protection=SETTINGS.market_protection)
    def place_market_sell(self,symbol,quantity):
        return self.kite.place_order(variety=self.kite.VARIETY_REGULAR,exchange=SETTINGS.exchange,tradingsymbol=symbol,transaction_type=self.kite.TRANSACTION_TYPE_SELL,quantity=int(quantity),product=self.kite.PRODUCT_MIS,order_type=self.kite.ORDER_TYPE_MARKET,validity=self.kite.VALIDITY_DAY,tag="STRAT_E",market_protection=SETTINGS.market_protection)
    def cancel_order(self,order_id):
        logger.warning("CANCEL order_id=%s",order_id)
        return self.kite.cancel_order(variety=self.kite.VARIETY_REGULAR,order_id=order_id)
    def order_snapshot(self,order_id):
        for o in self.orders():
            if str(o.get("order_id"))==str(order_id): return o
        return None
    def wait_for_order(self,order_id,timeout=None,cancel_on_timeout=True):
        timeout=SETTINGS.order_timeout_seconds if timeout is None else timeout; deadline=time.time()+timeout; last=None
        while time.time()<deadline:
            last=self.order_snapshot(order_id)
            if last and last.get("status") in {"COMPLETE","REJECTED","CANCELLED"}: return last
            time.sleep(0.75)
        if cancel_on_timeout and last and last.get("status") not in {None,"COMPLETE","REJECTED","CANCELLED"}:
            try:self.cancel_order(order_id)
            except Exception as exc: logger.exception("Order cancellation failed order=%s: %s",order_id,exc)
            time.sleep(0.75)
            last=self.order_snapshot(order_id) or last
        return last
    def finalize_entry(self,order_id,requested_quantity):
        snap=self.wait_for_order(order_id,cancel_on_timeout=True)
        if not snap: raise RuntimeError(f"Entry order not found: {order_id}")
        filled=int(snap.get("filled_quantity") or 0); price=float(snap.get("average_price") or 0); status=str(snap.get("status") or "")
        if status!="COMPLETE":
            raise RuntimeError(f"Entry order {order_id} did not complete: status={status} filled={filled}/{requested_quantity}")
        if filled<=0 or price<=0: raise RuntimeError(f"Entry order {order_id} has no valid fill")
        return filled,price,snap
    def completed_fill(self,order_id):
        o=self.wait_for_order(order_id)
        if not o: raise RuntimeError(f"Order not found: {order_id}")
        if o.get("status")!="COMPLETE": raise RuntimeError(f"Order {order_id} status={o.get('status')}; cancel/timeout path completed")
        qty=int(o.get("filled_quantity") or 0); price=float(o.get("average_price") or 0)
        if qty<=0 or price<=0: raise RuntimeError(f"Order {order_id} has no valid complete fill")
        return qty,price,o
