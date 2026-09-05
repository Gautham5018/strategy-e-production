import unittest
from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]

class SharedRuntimeTests(unittest.TestCase):
    def test_shared_paths_are_build_independent(self):
        s=(ROOT/'env_loader.py').read_text()
        self.assertIn('KITE_ACCESS_TOKEN_FILE', (ROOT/'shared_paths.py').read_text())
        self.assertIn('STRATEGY_E_SECRETS_DIR', s)
        self.assertIn('STRATEGY_E_DATA_DIR', s)
        self.assertIn('PACKAGE_ENV_FILE', s)
        self.assertIn('SHARED_ENV_FILE', s)

    def test_token_file_is_default_shared_path(self):
        s=(ROOT/'config.py').read_text()
        self.assertIn('SECRETS_DIR / ".kite_access_token"', s)

    def test_kite_client_prefers_shared_token_file(self):
        s=(ROOT/'kite_client.py').read_text()
        self.assertIn('p.exists()', s)
        self.assertIn('token=p.read_text', s)

    def test_session_does_not_write_build_env(self):
        s=(ROOT/'kite_session.py').read_text()
        self.assertIn('SHARED_ENV_FILE', s)
        self.assertIn('write_token(token)', s)
        self.assertNotIn('ENV_FILE.replace', s)

    def test_cli_has_shared_runtime_commands(self):
        s=(ROOT/'run.py').read_text()
        for term in ('setup-shared','kite-login','session-status'):
            self.assertIn(term,s)

    def test_no_order_api_in_shared_setup(self):
        tree=ast.parse((ROOT/'setup_shared.py').read_text())
        attrs={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(attrs & {'place_order','modify_order','cancel_order','exit_order'})

if __name__=='__main__': unittest.main(verbosity=2)
