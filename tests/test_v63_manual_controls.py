import unittest
from pathlib import Path
import tempfile
from models import PositionState
from state_store import StateStore

class FakeBroker:
    def __init__(self): self.prices={"TEST":100.0}; self.sells=[]
    def ltp(self,s): return self.prices[s]
    def instrument(self,s): return {"instrument_token":1}
    def place_market_sell(self,s,q): self.sells.append((s,q)); return "MANUAL-1"
    def wait_for_order(self,oid,cancel_on_timeout=False): return {"order_id":oid,"status":"COMPLETE","filled_quantity":self.sells[-1][1],"average_price":99.5}
    def order_snapshot(self,oid): return None
    def cancel_order(self,oid): return None

class FakeRisk:
    def validate_signal(self,*a): return True,"OK"

class ManualControlTests(unittest.TestCase):
    def test_manual_exit_removes_position_and_keeps_process_alive(self):
        from execution import ExecutionEngine
        root=Path(tempfile.mkdtemp())
        store=StateStore(root/"state.json")
        p=PositionState(symbol="TEST",instrument_token=1,signal_time="2026-08-26T09:15:00",entry_order_id="E1",entry_price=100.0,entry_quantity=100,remaining_quantity=100,signal_low=99.0,risk_per_share=1.0,one_r=101.0,two_r=103.0,partial_quantity=50,final_quantity=50)
        store.upsert_position(p)
        broker=FakeBroker(); engine=ExecutionEngine(broker,store,FakeRisk())
        r=engine.manual_exit("TEST",reason="UNIT_TEST")
        self.assertTrue(r["ok"]); self.assertEqual(r["status"],"FLAT"); self.assertNotIn("TEST",store.positions())
        self.assertEqual(broker.sells,[])

    def test_manual_exit_uses_exit_gate_not_entry_gate(self):
        text=Path(__file__).resolve().parents[1].joinpath("execution.py").read_text()
        self.assertIn("assert_live_exit_allowed",text)
        self.assertIn("manual_exit_pending",text)

if __name__=="__main__": unittest.main()
