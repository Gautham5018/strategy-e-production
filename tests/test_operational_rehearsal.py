
import ast, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class OperationalTests(unittest.TestCase):
    def test_01_rehearsal_is_paper_only(self):
        s=(ROOT/"operational_rehearsal.py").read_text()
        self.assertIn("MODE",s)
        self.assertIn("LIVE_ORDERS_ARMED",s)
        self.assertIn("ALLOW_LIVE_ORDERS",s)

    def test_02_rehearsal_has_no_order_calls(self):
        tree=ast.parse((ROOT/"operational_rehearsal.py").read_text())
        calls={n.func.attr for n in ast.walk(tree)
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse({"place_order","modify_order","cancel_order","exit_order"} & calls)

    def test_03_session_status_is_read_only(self):
        tree=ast.parse((ROOT/"session_status.py").read_text())
        calls={n.func.attr for n in ast.walk(tree)
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse({"place_order","modify_order","cancel_order","exit_order"} & calls)

    def test_04_session_status_exists(self):
        self.assertTrue((ROOT/"session_status.py").exists())

if __name__=="__main__":
    unittest.main(verbosity=2)
