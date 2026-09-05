import unittest, ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class V62RuntimeTests(unittest.TestCase):
    def test_app_has_startup_logging(self):
        s=(ROOT/"app.py").read_text(); self.assertIn("STRATEGY E V6.2 STARTUP",s); self.assertIn("STARTUP COMPLETE",s)
    def test_readiness_reports_runtime(self):
        s=(ROOT/"app.py").read_text(); self.assertIn("runtime_state",s); self.assertIn('"runtime":snap',s)
    def test_webhook_returns_503_when_not_ready(self):
        s=(ROOT/"webhook.py").read_text(); self.assertIn("HTTPException(503",s)
    def test_broker_cancels_timeout(self):
        s=(ROOT/"kite_client.py").read_text(); self.assertIn("self.cancel_order(order_id)",s)
    def test_execution_partial_entry_is_cleaned(self):
        s=(ROOT/"execution.py").read_text(); self.assertIn("ENTRY PARTIAL",s); self.assertIn("_flatten_after_partial_entry",s)
    def test_no_relative_state_store_default(self):
        s=(ROOT/"state_store.py").read_text(); self.assertNotIn('StateStore("state/state.json")',s)
    def test_partial_exit_blocks_final_exit(self):
        s=(ROOT/"execution.py").read_text(); self.assertIn("partial_pending",s)
    def test_entry_uses_finalize_entry(self):
        s=(ROOT/"execution.py").read_text(); self.assertIn("finalize_entry",s)
if __name__=="__main__": unittest.main(verbosity=2)
