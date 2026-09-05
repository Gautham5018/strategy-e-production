
import os, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class KiteSafetyTests(unittest.TestCase):
    def test_readonly_script_contains_no_order_api(self):
        s=(ROOT/"kite_readonly_check.py").read_text()
        # Inspect executable AST rather than string literals used by the
        # self-check itself.
        import ast
        tree=ast.parse(s)
        calls=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):
                calls.append(n.func.attr)
        for name in ("place_order","modify_order","cancel_order","exit_order"):
            self.assertNotIn(name,calls)

    def test_live_orders_are_explicitly_gated(self):
        s=(ROOT/"risk_manager.py").read_text()
        self.assertIn("allow_live_orders",s)
        self.assertIn("LIVE_ORDERS_NOT_ARMED",s)

    def test_environment_example_does_not_arm_live(self):
        s=(ROOT/".env.example").read_text()
        self.assertIn("ALLOW_LIVE_ORDERS=FALSE",s.upper())

if __name__=="__main__":
    unittest.main(verbosity=2)
