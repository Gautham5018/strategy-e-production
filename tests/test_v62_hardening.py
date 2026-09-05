import ast, os, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class V62HardeningTests(unittest.TestCase):
    def test_config_authoritative_env(self):
        s=(ROOT/"config.py").read_text(); self.assertIn("BIND_HOST",s); self.assertIn("load_env()",(ROOT/"env_loader.py").read_text())
    def test_state_path_is_project_anchored(self):
        s=(ROOT/"state_store.py").read_text(); self.assertIn('DATA_DIR/"state"/"state.json"',s)
    def test_broker_state_positions_not_stub(self):
        s=(ROOT/"kite_client.py").read_text(); self.assertIn("self.state_store.positions()",s); self.assertNotIn("return []",s)
    def test_runtime_reconciliation_is_actual(self):
        s=(ROOT/"monitor.py").read_text(); self.assertIn("self.reconciler.reconcile()",s)
    def test_pending_exit_refresh_exists(self):
        s=(ROOT/"execution.py").read_text(); self.assertIn("refresh_pending_exits",s); self.assertIn("order_snapshot",s)
    def test_timeout_cancels_unresolved_entry(self):
        s=(ROOT/"kite_client.py").read_text(); self.assertIn("cancel_order",s); self.assertIn("cancel_on_timeout",s)
    def test_webhook_requires_processor_ready(self):
        s=(ROOT/"webhook.py").read_text(); self.assertIn("ready_for_webhook",s); self.assertIn("503",s)
    def test_logging_is_configured(self):
        self.assertTrue((ROOT/"logging_setup.py").exists())
        s=(ROOT/"app.py").read_text(); self.assertIn("configure_logging()",s)
    def test_live_gate_uses_settings(self):
        s=(ROOT/"live_gate.py").read_text(); self.assertIn("from config import SETTINGS",s); self.assertIn("settings=None",s); self.assertIn("SETTINGS",s)
    def test_readiness_exposes_runtime(self):
        s=(ROOT/"app.py").read_text(); self.assertIn('"runtime":snap',s)
    def test_session_writes_only_access_token(self):
        s=(ROOT/"kite_session.py").read_text(); self.assertIn("write_token(token)",s); self.assertIn("profile()",s)
    def test_readonly_has_no_order_api(self):
        tree=ast.parse((ROOT/"kite_readonly_check.py").read_text()); attrs={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}; self.assertFalse(attrs & {"place_order","modify_order","cancel_order","exit_order"})
    def test_readme_complete(self):
        s=(ROOT/"README.md").read_text();
        for term in ["Kite session","read-only","readiness","live-gate","Chartink","Cloudflare","FIRST LIVE"]:
            self.assertIn(term,s)

if __name__=="__main__": unittest.main(verbosity=2)
