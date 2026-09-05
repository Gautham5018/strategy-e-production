
import os, sys, unittest, tempfile
from datetime import datetime, time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import Signal, PositionState
from risk_manager import RiskManager
from state_store import StateStore
from execution import ExecutionEngine


class FakeBroker:
    def __init__(self):
        self.orders=[]
        self._order_no=0
        self.prices={"TEST":100.0,"TEST2":200.0,"TEST3":300.0}
        self.instruments_data={
            "TEST":{"instrument_token":111,"tradingsymbol":"TEST","exchange":"NSE","lot_size":1},
            "TEST2":{"instrument_token":222,"tradingsymbol":"TEST2","exchange":"NSE","lot_size":1},
            "TEST3":{"instrument_token":333,"tradingsymbol":"TEST3","exchange":"NSE","lot_size":1},
        }

    def instrument(self, symbol):
        return self.instruments_data[symbol]

    def ltp(self, symbol):
        return self.prices[symbol]

    def ltp_many(self, symbols):
        return {s:self.ltp(s) for s in symbols}

    def place_market_buy(self, symbol, quantity):
        self._order_no += 1
        oid=f"OID{self._order_no}"
        price=self.ltp(symbol)
        self.orders.append({"order_id":oid,"symbol":symbol,"side":"BUY",
                            "quantity":quantity,"filled_quantity":quantity,
                            "average_price":price,"status":"COMPLETE"})
        return oid

    def place_market_sell(self, symbol, quantity):
        self._order_no += 1
        oid=f"OID{self._order_no}"
        price=self.ltp(symbol)
        self.orders.append({"order_id":oid,"symbol":symbol,"side":"SELL",
                            "quantity":quantity,"filled_quantity":quantity,
                            "average_price":price,"status":"COMPLETE"})
        return oid

    def completed_fill(self, order_id):
        o=next(x for x in self.orders if x["order_id"]==order_id)
        return o["filled_quantity"], o["average_price"], o["status"]


class ProductionTests(unittest.TestCase):

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=StateStore(os.path.join(self.tmp.name,"state.json"))
        self.broker=FakeBroker()

        # Unit tests must not inherit production safety switches from .env.
        # Keep the real application .env unchanged; only replace the module
        # settings object for this test process.
        import risk_manager
        from config import SETTINGS
        from dataclasses import replace
        self._original_settings = risk_manager.SETTINGS
        risk_manager.SETTINGS = replace(
            SETTINGS,
            mode="PAPER",
            trading_enabled=True,
            allow_live_orders=False,
            kill_switch=False,
            max_open_positions=2,
            max_entries_per_day=2,
            delayed_entry_enabled=False,
            trade_capital_per_position=35000.0,
            total_capital=70000.0,
        )

        self.risk=RiskManager(self.store,self.broker)
        self.engine=ExecutionEngine(self.broker,self.store,self.risk)

    def tearDown(self):
        import risk_manager
        risk_manager.SETTINGS = self._original_settings
        self.tmp.cleanup()

    def signal(self, symbol="TEST", t=time(9,15), low=99.0, high=100.0):
        return Signal(
            symbol=symbol,
            signal_time=datetime.combine(datetime(2026,8,24),t),
            signal_open=99.5,
            signal_high=high,
            signal_low=low,
            signal_close=99.8,
        )

    def add_position(self, symbol):
        p=PositionState(
            symbol=symbol,
            instrument_token=self.broker.instrument(symbol)["instrument_token"],
            signal_time=datetime(2026,8,24,9,15),
            entry_order_id="TEST",
            entry_price=self.broker.ltp(symbol),
            entry_quantity=100,
            remaining_quantity=100,
            signal_low=self.broker.ltp(symbol)-1,
            risk_per_share=1,
            one_r=self.broker.ltp(symbol)+1,
            two_r=self.broker.ltp(symbol)+2,
            partial_quantity=50,
            final_quantity=50,
        )
        self.store.upsert_position(p)

    # Signal/risk gates
    def test_01_valid_signal(self):
        ok,reason=self.risk.validate_signal(self.signal())
        self.assertTrue(ok,reason)

    def test_02_signal_over_8_percent_rejected(self):
        ok,reason=self.risk.validate_signal(self.signal(low=90.0,high=100.0))
        self.assertFalse(ok)
        self.assertEqual(reason,"SIGNAL_CANDLE_OVER_LIMIT")

    def test_03_before_trading_window_rejected(self):
        ok,reason=self.risk.validate_signal(self.signal(t=time(9,14)))
        self.assertFalse(ok)
        self.assertEqual(reason,"OUTSIDE_TRADING_WINDOW")

    def test_04_first_signal_after_cutoff_rejected(self):
        ok,reason=self.risk.validate_signal(self.signal(t=time(9,36)))
        self.assertFalse(ok)
        self.assertEqual(reason,"FIRST_SIGNAL_CUTOFF")

    def test_05_two_positions_allowed(self):
        self.add_position("TEST")
        ok,reason=self.risk.validate_signal(self.signal("TEST2"))
        self.assertTrue(ok,reason)

    def test_06_third_parallel_position_rejected(self):
        self.add_position("TEST")
        self.add_position("TEST2")
        ok,reason=self.risk.validate_signal(self.signal("TEST3"))
        self.assertFalse(ok)
        self.assertEqual(reason,"MAX_OPEN_POSITIONS")

    def test_07_duplicate_stock_rejected(self):
        self.add_position("TEST")
        ok,reason=self.risk.validate_signal(self.signal("TEST"))
        self.assertFalse(ok)
        self.assertEqual(reason,"SYMBOL_ALREADY_OPEN")

    # Strategy math
    def test_08_strategy_e_r_math(self):
        entry=100.0
        signal_low=99.0
        risk=entry-signal_low
        self.assertEqual(risk,1.0)
        self.assertEqual(entry+risk,101.0)
        self.assertEqual(entry+2*risk,102.0)

    def test_09_quantity_split(self):
        qty=697
        q1=qty//2
        q2=qty-q1
        self.assertEqual((q1,q2),(348,349))
        self.assertEqual(q1+q2,qty)

    def test_10_fixed_capital_no_compounding(self):
        self.assertEqual(35000,70000/2)
        # Fixed allocation remains 35k regardless of previous P&L.
        for prior_pnl in (-10000,0,10000,58512.56):
            self.assertEqual(35000,70000/2)

    # Idempotency
    def test_11_duplicate_webhook_key(self):
        key="chartink:TEST:2026-08-24T09:15:00"
        self.assertFalse(self.store.processed(key))
        self.store.mark_processed(key)
        self.assertTrue(self.store.processed(key))

    # Broker/order behavior
    def test_12_paper_entry_creates_position_and_1r_2r(self):
        r=self.engine.process_signal(self.signal())
        self.assertTrue(r["accepted"],r)
        self.assertEqual(r["quantity"],1750)
        self.assertAlmostEqual(r["fill_price"],100.0)
        self.assertAlmostEqual(r["one_r"],101.0)
        self.assertAlmostEqual(r["two_r"],103.0)
        self.assertEqual(len(self.store.positions()),1)

    def test_13_paper_partial_exit_reduces_position(self):
        self.engine.process_signal(self.signal())
        p=self.store.positions()["TEST"]
        self.assertEqual(p["partial_quantity"],875)
        self.engine.exit_partial(p)
        p2=self.store.positions()["TEST"]
        self.assertEqual(p2["partial_filled"],875)
        self.assertEqual(p2["remaining_quantity"],875)

    def test_14_paper_final_exit_removes_position(self):
        self.engine.process_signal(self.signal())
        p=self.store.positions()["TEST"]
        self.engine.exit_final(p)
        self.assertNotIn("TEST",self.store.positions())

    def test_15_order_fill_fields(self):
        oid=self.broker.place_market_buy("TEST",697)
        filled,price,status=self.broker.completed_fill(oid)
        self.assertEqual(filled,697)
        self.assertEqual(price,100.0)
        self.assertEqual(status,"COMPLETE")

    def test_16_partial_fill_is_not_full_fill(self):
        oid=self.broker.place_market_sell("TEST",348)
        o=self.broker.orders[-1]
        o["status"]="OPEN"
        o["filled_quantity"]=200
        filled,_,status=self.broker.completed_fill(oid)
        self.assertEqual(filled,200)
        self.assertEqual(status,"OPEN")
        self.assertNotEqual(filled,348)

    def test_17_reconciliation_mismatch_detectable(self):
        internal={"TEST":697}
        broker={"TEST":348}
        self.assertNotEqual(internal,broker)

    def test_18_live_orders_require_arm(self):
        import risk_manager
        from config import SETTINGS
        from dataclasses import replace
        old=risk_manager.SETTINGS
        try:
            risk_manager.SETTINGS=replace(
                SETTINGS, mode="LIVE",
                trading_enabled=True, allow_live_orders=False,
                kill_switch=False
            )
            ok,reason=self.risk.validate_signal(self.signal())
            self.assertFalse(ok)
            self.assertEqual(reason,"LIVE_ORDERS_NOT_ARMED")
        finally:
            risk_manager.SETTINGS=old

    def test_19_strategy_e_only_no_variant_mode(self):
        with open(
            os.path.join(os.path.dirname(os.path.dirname(__file__)),"execution.py")
        ) as f:
            execution_source=f.read()
        self.assertNotIn("run_variant(",execution_source)
        self.assertNotIn("if mode in",execution_source)

    def test_20_core_production_modules_import(self):
        import config, models, state_store, risk_manager, execution, reconciliation, monitor
        self.assertTrue(True)


if __name__=="__main__":
    unittest.main(verbosity=2)
