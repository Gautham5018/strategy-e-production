import unittest
from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]
class CleanKiteSessionTests(unittest.TestCase):
    def test_env_loader_uses_shared_and_package_env(self):
        s=(ROOT/'env_loader.py').read_text(); self.assertIn('PACKAGE_ENV_FILE = ROOT / ".env"',s); self.assertIn('SHARED_ENV_FILE',s)
    def test_readonly_uses_explicit_env_loader(self):
        s=(ROOT/'kite_readonly_check.py').read_text(); self.assertIn('load_env()',s); self.assertNotIn('load_dotenv()',s)
    def test_session_helper_has_no_order_api(self):
        tree=ast.parse((ROOT/'kite_session.py').read_text()); names=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Attribute): names.append(n.attr)
        self.assertFalse(set(names)&{'place_order','modify_order','cancel_order','exit_order'})
    def test_session_helper_updates_shared_token(self):
        s=(ROOT/'kite_session.py').read_text(); self.assertIn('write_token(token)',s); self.assertIn('generate_session',s); self.assertIn('profile()',s); self.assertIn('SHARED_ENV_FILE',s)
    def test_clean_start_does_not_delete_env(self):
        s=(ROOT/'clean_start.sh').read_text(); self.assertIn('setup-shared',s); self.assertNotIn('rm .env',s)
if __name__=='__main__': unittest.main(verbosity=2)
