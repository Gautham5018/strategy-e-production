import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class EnvLoadingTests(unittest.TestCase):
    def test_config_has_deterministic_env_path(self):
        s=(ROOT/'env_loader.py').read_text()
        self.assertIn('PACKAGE_ENV_FILE = ROOT / ".env"',s)
        self.assertIn('SHARED_ENV_FILE = SECRETS_DIR / ".env"',s)
        self.assertIn('load_dotenv(dotenv_path=chosen, override=True)',s)
    def test_reset_docs_present(self):
        self.assertTrue((ROOT/'RESET_AND_SETUP.md').exists())
if __name__=='__main__': unittest.main(verbosity=2)
