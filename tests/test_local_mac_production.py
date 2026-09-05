
import ast, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class LocalMacTests(unittest.TestCase):
    def test_01_watchdog_exists_and_has_health_check(self):
        s=(ROOT/"watchdog.py").read_text()
        self.assertIn("/health",s)
        self.assertIn("FAIL_THRESHOLD",s)

    def test_02_watchdog_cannot_run_armed_live(self):
        s=(ROOT/"watchdog.py").read_text()
        self.assertIn("LIVE_ORDERS_ARMED",s)
        self.assertIn("REFUSING TO RUN",s)

    def test_03_watchdog_has_no_order_calls(self):
        tree=ast.parse((ROOT/"watchdog.py").read_text())
        calls={n.func.attr for n in ast.walk(tree)
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse({"place_order","modify_order","cancel_order","exit_order"} & calls)

    def test_04_launchd_keepalive(self):
        s=(ROOT/"deploy/com.strategyE.trading.plist.template").read_text()
        self.assertIn("<key>KeepAlive</key>",s)
        self.assertIn("<true/>",s)
        self.assertIn("<key>RunAtLoad</key>",s)

    def test_05_ist_environment(self):
        s=(ROOT/"deploy/com.strategyE.trading.plist.template").read_text()
        self.assertIn("Asia/Kolkata",s)

    def test_06_install_script_present(self):
        self.assertTrue((ROOT/"deploy/install_mac_launchd.sh").exists())
        self.assertTrue((ROOT/"deploy/uninstall_mac_launchd.sh").exists())

if __name__=="__main__":
    unittest.main(verbosity=2)
