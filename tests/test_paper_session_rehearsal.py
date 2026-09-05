
import os, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from models import Signal
from state_store import StateStore
from risk_manager import RiskManager
from execution import ExecutionEngine
import webhook
import config

class FakeBroker:
    def __init__(self):
        self.prices={"TEST":100.0,"TEST2":200.0}
        self.instruments_data={
            "TEST":{"instrument_token":111,"tradingsymbol":"TEST","exchange":"NSE"},
            "TEST2":{"instrument_token":222,"tradingsymbol":"TEST2","exchange":"NSE"},
        }
        self.market_data=None

    def instrument(self,s): return self.instruments_data[s]
    def ltp(self,s): return self.prices[s]
    def ltp_many(self,ss): return {s:self.ltp(s) for s in ss}

class Processor:
    def __init__(self,store,execution):
        self.store=store
        self.execution=execution

class PaperSessionRehearsal(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=StateStore(os.path.join(self.tmp.name,"state.json"))
        self.broker=FakeBroker()

        import risk_manager
        old=risk_manager.SETTINGS
        self.old_settings=old
        risk_manager.SETTINGS=replace(
            config.SETTINGS,
            mode="PAPER",
            trading_enabled=True,
            allow_live_orders=False,
            kill_switch=False,
            chartink_webhook_token="TESTTOKEN",
            max_open_positions=2,
            max_entries_per_day=2,
            delayed_entry_enabled=False,
            trade_capital_per_position=35000.0,
            total_capital=70000.0,
            max_signal_candle_pct=8.0,
            trading_start=__import__("datetime").time(9,15),
            trading_end=__import__("datetime").time(15,0),
            first_signal_cutoff=__import__("datetime").time(9,35),
            final_r_multiple=2.0,
        )
        self.risk=risk_manager.RiskManager(self.store,self.broker)
        self.execution=ExecutionEngine(self.broker,self.store,self.risk)
        self.processor=Processor(self.store,self.execution)

        # Make webhook candle timestamp deterministic for this rehearsal.
        self.old_latest=webhook._latest_completed_candle_time
        webhook._latest_completed_candle_time=lambda now: datetime(2026,8,24,9,15)
        self.old_processor=webhook.PROCESSOR
        self.old_webhook_settings=webhook.SETTINGS
        webhook.PROCESSOR=self.processor
        webhook.SETTINGS=replace(
            config.SETTINGS,
            chartink_webhook_token="TESTTOKEN",
            mode="PAPER",
            trading_enabled=True,
            allow_live_orders=False,
            kill_switch=False,
            max_open_positions=2,
            max_entries_per_day=2,
            delayed_entry_enabled=False,
            trade_capital_per_position=35000.0,
            max_signal_candle_pct=8.0,
            final_r_multiple=2.0,
        )

        app=FastAPI()
        app.include_router(webhook.router)
        self.client=TestClient(app)

    def tearDown(self):
        import risk_manager
        risk_manager.SETTINGS=self.old_settings
        webhook._latest_completed_candle_time=self.old_latest
        webhook.PROCESSOR=self.old_processor
        webhook.SETTINGS=self.old_webhook_settings
        self.tmp.cleanup()

    def payload(self, symbols=("TEST","TEST2")):
        cols=[]
        for s in symbols:
            px=100 if s=="TEST" else 200
            cols.append({"symbol":s,"open":px-0.5,"high":px+1.0,
                         "low":px-1.0,"close":px-0.2})
        return {"columns":cols}

    def test_01_chartink_webhook_accepts_two_signals(self):
        r=self.client.post("/chartink/webhook/TESTTOKEN",json=self.payload())
        self.assertEqual(r.status_code,200,r.text)
        body=r.json()
        self.assertTrue(body["accepted_for_processing"])
        self.assertEqual(len(body["results"]),2)
        self.assertTrue(all(x["accepted"] for x in body["results"]))
        self.assertEqual(len(self.store.positions()),2)

    def test_02_duplicate_webhook_is_idempotent(self):
        first=self.client.post("/chartink/webhook/TESTTOKEN",json=self.payload())
        self.assertEqual(first.status_code,200)
        second=self.client.post("/chartink/webhook/TESTTOKEN",json=self.payload())
        self.assertTrue(second.json()["duplicate"])
        self.assertEqual(len(self.store.positions()),2)

    def test_03_invalid_webhook_token_rejected(self):
        r=self.client.post("/chartink/webhook/BADTOKEN",json=self.payload())
        self.assertEqual(r.status_code,404)
        self.assertEqual(len(self.store.positions()),0)

    def test_04_invalid_candle_is_rejected_without_order(self):
        payload={"columns":[{"symbol":"TEST","open":90,"high":100,"low":90,"close":99}]}
        r=self.client.post("/chartink/webhook/TESTTOKEN",json=payload)
        self.assertEqual(r.status_code,200)
        self.assertFalse(r.json()["results"][0]["accepted"])
        self.assertEqual(len(self.store.positions()),0)

    def test_05_paper_1r_then_2r_lifecycle(self):
        r=self.client.post("/chartink/webhook/TESTTOKEN",
                           json=self.payload(("TEST",)))
        self.assertTrue(r.json()["results"][0]["accepted"])
        p=self.store.positions()["TEST"]
        self.assertEqual(p["entry_quantity"],1750)
        self.assertEqual(p["partial_quantity"],875)
        self.assertEqual(p["final_quantity"],875)

        # Simulate price reaching 1R.
        self.broker.prices["TEST"]=101.0
        self.execution.exit_partial(p)
        p=self.store.positions()["TEST"]
        self.assertEqual(p["partial_filled"],875)
        self.assertEqual(p["remaining_quantity"],875)

        # Simulate price reaching 2R.
        self.broker.prices["TEST"]=102.0
        self.execution.exit_final(p)
        self.assertNotIn("TEST",self.store.positions())

    def test_06_restart_recovery_keeps_open_position(self):
        self.client.post("/chartink/webhook/TESTTOKEN",
                         json=self.payload(("TEST",)))
        before=self.store.positions()["TEST"]
        store2=StateStore(self.store.path)
        after=store2.positions()["TEST"]
        self.assertEqual(after["remaining_quantity"],before["remaining_quantity"])
        self.assertEqual(after["entry_order_id"],before["entry_order_id"])

    def test_07_third_signal_rejected_after_two_entries(self):
        self.client.post("/chartink/webhook/TESTTOKEN",
                         json=self.payload())
        # New webhook, different payload so it is not a duplicate.
        r=self.client.post("/chartink/webhook/TESTTOKEN",
                           json={"columns":[{"symbol":"TEST","open":99,
                           "high":101,"low":98.5,"close":100}]})
        self.assertEqual(r.status_code,200)
        self.assertFalse(r.json()["results"][0]["accepted"])

if __name__=="__main__":
    unittest.main(verbosity=2)
