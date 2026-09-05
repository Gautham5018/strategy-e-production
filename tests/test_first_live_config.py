
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class FirstLiveConfigTests(unittest.TestCase):
    def _cfg(self):
        d={}
        for line in (ROOT/"FIRST_LIVE_TRADE.env").read_text().splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v=line.split("=",1)
            d[k]=v
        return d

    def test_01_one_entry_only(self):
        d=self._cfg()
        self.assertEqual(d["MAX_ENTRIES_PER_DAY"],"1")
        self.assertEqual(d["TRADE_CAPITAL_PER_POSITION"],"35000")

    def test_02_live_gates_all_explicit(self):
        d=self._cfg()
        for k in ("MODE","TRADING_ENABLED","ALLOW_LIVE_ORDERS",
                  "LIVE_ORDERS_ARMED","KITE_STATIC_IP_VERIFIED",
                  "PRODUCTION_ENVIRONMENT","LIVE_TRADING_ACK"):
            self.assertIn(k,d)
        self.assertEqual(d["MODE"],"LIVE")
        self.assertEqual(d["TRADING_ENABLED"],"true")
        self.assertEqual(d["ALLOW_LIVE_ORDERS"],"true")
        self.assertEqual(d["LIVE_ORDERS_ARMED"],"false")
        self.assertEqual(d["KILL_SWITCH"],"false")

    def test_03_strategy_e_exit_math(self):
        d=self._cfg()
        self.assertEqual(d["PARTIAL_R_FRACTION"],"0.50")
        self.assertEqual(d["FINAL_R_MULTIPLE"],"3.0")

    def test_04_mis_nse(self):
        d=self._cfg()
        self.assertEqual(d["PRODUCT"],"MIS")
        self.assertEqual(d["EXCHANGE"],"NSE")

if __name__=="__main__":
    unittest.main(verbosity=2)
