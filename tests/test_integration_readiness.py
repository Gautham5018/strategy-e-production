
import os, sys, json, tempfile, unittest
from datetime import datetime, time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import Signal
from state_store import StateStore
from risk_manager import RiskManager
from execution import ExecutionEngine


class FakeBroker:
    def __init__(self):
        self.orders=[]
        self._id=0
        self.prices={"TEST":100.0,"TEST2":200.0,"TEST3":300.0}
        self.instruments_data={
            s: {"instrument_token":i,"tradingsymbol":s,"exchange":"NSE","lot_size":1}
            for s,i in [("TEST",111),("TEST2",222),("TEST3",333)]
        }

    def instrument(self,s): return self.instruments_data[s]
    def ltp(self,s): return self.prices[s]
    def ltp_many(self,ss): return {s:self.ltp(s) for s in ss}

    def _order(self,s,side,q):
        self._id+=1
        oid=f"INT{self._id}"
        self.orders.append({
            "order_id":oid,"symbol":s,"side":side,"quantity":q,
            "filled_quantity":q,"average_price":self.ltp(s),"status":"COMPLETE"
        })
        return oid

    def place_market_buy(self,s,q): return self._order(s,"BUY",q)
    def place_market_sell(self,s,q): return self._order(s,"SELL",q)
    def completed_fill(self,oid):
        x=next(x for x in self.orders if x["order_id"]==oid)
        return x["filled_quantity"],x["average_price"],x["status"]


class IntegrationReadiness(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=StateStore(os.path.join(self.tmp.name,"state.json"))
        self.broker=FakeBroker()

        import risk_manager
        from config import SETTINGS
        from dataclasses import replace
        self.old_settings=risk_manager.SETTINGS
        risk_manager.SETTINGS=replace(
            SETTINGS, mode="PAPER", trading_enabled=True,
            allow_live_orders=False, kill_switch=False,
            max_open_positions=2, max_entries_per_day=2,
            delayed_entry_enabled=False,
            trade_capital_per_position=35000.0,
            total_capital=70000.0
        )
        self.risk=RiskManager(self.store,self.broker)
        self.engine=ExecutionEngine(self.broker,self.store,self.risk)

    def tearDown(self):
        import risk_manager
        risk_manager.SETTINGS=self.old_settings
        self.tmp.cleanup()

    def signal(self,s="TEST",t=time(9,15),low=99,high=100):
        return Signal(
            symbol=s,
            signal_time=datetime.combine(datetime(2026,8,24),t),
            signal_open=99.5,signal_high=high,
            signal_low=low,signal_close=99.8
        )

    def test_01_chartink_like_signal_end_to_end(self):
        result=self.engine.process_signal(self.signal())
        self.assertTrue(result["accepted"],result)
        self.assertIn("TEST",self.store.positions())
        p=self.store.positions()["TEST"]
        self.assertEqual(p["entry_quantity"],1750)
        self.assertEqual(p["partial_quantity"],875)
        self.assertEqual(p["final_quantity"],875)

    def test_02_second_position_then_third_rejected(self):
        self.assertTrue(self.engine.process_signal(self.signal("TEST"))["accepted"])
        self.assertTrue(self.engine.process_signal(self.signal("TEST2"))["accepted"])
        r=self.engine.process_signal(self.signal("TEST3"))
        self.assertFalse(r["accepted"])
        self.assertEqual(r["reason"],"MAX_ENTRIES_PER_DAY")

    def test_03_duplicate_same_stock_rejected(self):
        self.assertTrue(self.engine.process_signal(self.signal("TEST"))["accepted"])
        r=self.engine.process_signal(self.signal("TEST"))
        self.assertFalse(r["accepted"])

    def test_04_partial_then_final_exit_lifecycle(self):
        self.engine.process_signal(self.signal())
        p=self.store.positions()["TEST"]
        self.assertEqual(p["remaining_quantity"],1750)

        self.engine.exit_partial(p)
        p=self.store.positions()["TEST"]
        self.assertEqual(p["partial_filled"],875)
        self.assertEqual(p["remaining_quantity"],875)

        self.engine.exit_final(p)
        self.assertNotIn("TEST",self.store.positions())

    def test_05_fixed_allocation_across_two_positions(self):
        a=self.engine.process_signal(self.signal("TEST"))
        b=self.engine.process_signal(self.signal("TEST2"))
        self.assertEqual(self.store.positions()["TEST"]["entry_quantity"],1750)
        self.assertEqual(self.store.positions()["TEST2"]["entry_quantity"],875)
        self.assertEqual(self.store.positions()["TEST"]["partial_quantity"],875)
        self.assertEqual(self.store.positions()["TEST2"]["partial_quantity"],437)

    def test_06_restart_state_persists(self):
        self.engine.process_signal(self.signal())
        self.assertIn("TEST",self.store.positions())

        store2=StateStore(self.store.path)
        self.assertIn("TEST",store2.positions())
        self.assertEqual(store2.positions()["TEST"]["remaining_quantity"],1750)

    def test_07_order_count_is_exact(self):
        self.engine.process_signal(self.signal())
        # PAPER mode deliberately does not send broker orders.
        self.assertEqual(len(self.broker.orders),0)
        p=self.store.positions()["TEST"]
        self.engine.exit_partial(p)
        self.assertEqual(len(self.broker.orders),0)
        self.engine.exit_final(self.store.positions()["TEST"])
        self.assertEqual(len(self.broker.orders),0)

    def test_08_no_compounding_after_profit(self):
        self.engine.process_signal(self.signal())
        self.engine.exit_final(self.store.positions()["TEST"])
        # New signal still receives fixed 35k allocation.
        r=self.engine.process_signal(self.signal("TEST2"))
        self.assertTrue(r["accepted"],r)
        self.assertEqual(self.store.positions()["TEST2"]["entry_quantity"],875)

    def test_09_live_gate_stays_closed(self):
        import risk_manager
        from dataclasses import replace
        old=risk_manager.SETTINGS
        risk_manager.SETTINGS=replace(old,mode="LIVE",trading_enabled=True,
                                      allow_live_orders=False,kill_switch=False)
        try:
            r=self.engine.process_signal(self.signal())
            self.assertFalse(r["accepted"])
            self.assertEqual(r["reason"],"LIVE_ORDERS_NOT_ARMED")
        finally:
            risk_manager.SETTINGS=old

    def test_10_invalid_signal_does_not_place_order(self):
        r=self.engine.process_signal(self.signal(low=90,high=100))
        self.assertFalse(r["accepted"])
        self.assertEqual(len(self.broker.orders),0)

    def test_11_outside_window_does_not_place_order(self):
        r=self.engine.process_signal(self.signal(t=time(9,14)))
        self.assertFalse(r["accepted"])
        self.assertEqual(len(self.broker.orders),0)

    def test_12_webhook_idempotency_primitive(self):
        key="webhook:TEST:2026-08-24T09:15:00"
        self.assertFalse(self.store.processed(key))
        self.store.mark_processed(key)
        self.assertTrue(self.store.processed(key))

if __name__=="__main__":
    unittest.main(verbosity=2)
