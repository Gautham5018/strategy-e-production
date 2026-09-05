import unittest
from dataclasses import replace
from config import SETTINGS
from live_gate import evaluate, REQUIRED_ACK

class LiveGateTests(unittest.TestCase):
    def make(self, **kw):
        defaults=dict(mode="LIVE", trading_enabled=True, allow_live_orders=True, kill_switch=False)
        defaults.update(kw)
        return replace(SETTINGS, **defaults)
    def test_01_default_is_blocked(self):
        r=evaluate(replace(SETTINGS, mode="PAPER"))
        self.assertFalse(r.allowed)
        self.assertIn("MODE_NOT_LIVE",r.reasons)
    def test_02_single_missing_gate_blocks(self):
        good=self.make()
        import os
        old=dict(os.environ)
        try:
            os.environ.update({"LIVE_TRADING_ACK":REQUIRED_ACK,"KITE_STATIC_IP_VERIFIED":"true","PRODUCTION_ENVIRONMENT":"LOCAL_MAC"})
            self.assertTrue(evaluate(good).allowed)
            os.environ.pop("KITE_STATIC_IP_VERIFIED",None)
            r=evaluate(good); self.assertFalse(r.allowed); self.assertIn("KITE_STATIC_IP_NOT_VERIFIED",r.reasons)
        finally:
            os.environ.clear(); os.environ.update(old)
    def test_03_wrong_ack_blocks(self):
        import os; old=dict(os.environ)
        try:
            os.environ.update({"LIVE_TRADING_ACK":"YES","KITE_STATIC_IP_VERIFIED":"true","PRODUCTION_ENVIRONMENT":"LOCAL_MAC"})
            r=evaluate(self.make()); self.assertFalse(r.allowed); self.assertIn("LIVE_TRADING_ACK_MISSING",r.reasons)
        finally: os.environ.clear(); os.environ.update(old)
    def test_04_kill_switch_always_blocks(self):
        import os; old=dict(os.environ)
        try:
            os.environ.update({"LIVE_TRADING_ACK":REQUIRED_ACK,"KITE_STATIC_IP_VERIFIED":"true","PRODUCTION_ENVIRONMENT":"LOCAL_MAC"})
            r=evaluate(self.make(kill_switch=True)); self.assertFalse(r.allowed); self.assertIn("KILL_SWITCH_ACTIVE",r.reasons)
        finally: os.environ.clear(); os.environ.update(old)
if __name__=="__main__": unittest.main(verbosity=2)
