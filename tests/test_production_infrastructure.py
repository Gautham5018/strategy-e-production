
import ast, os, unittest
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]

class InfrastructureTests(unittest.TestCase):
    def test_01_ist_timezone(self):
        import config
        self.assertEqual(getattr(config,"APP_TIMEZONE","Asia/Kolkata"),"Asia/Kolkata")
        self.assertEqual(ZoneInfo("Asia/Kolkata").key,"Asia/Kolkata")

    def test_02_production_service_exists(self):
        p=ROOT/"deploy/strategy-e.service"
        self.assertTrue(p.exists())
        s=p.read_text()
        self.assertIn("Restart=always",s)
        self.assertIn("EnvironmentFile=/opt/strategy-e/.env",s)
        self.assertIn("KillSignal=SIGTERM",s)

    def test_03_https_proxy_example(self):
        s=(ROOT/"deploy/nginx.conf.example").read_text()
        self.assertIn("listen 443",s)
        self.assertIn("proxy_pass http://127.0.0.1:8081",s)

    def test_04_no_live_orders_in_preflight(self):
        s=(ROOT/"production_check.py").read_text()
        tree=ast.parse(s)
        calls={n.func.attr for n in ast.walk(tree)
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse({"place_order","modify_order","cancel_order","exit_order"} & calls)

    def test_05_core_files(self):
        for name in ["app.py","execution.py","risk_manager.py","state_store.py",
                     "reconciliation.py","monitor.py","market_data.py"]:
            self.assertTrue((ROOT/name).exists(),name)

if __name__=="__main__":
    unittest.main(verbosity=2)
