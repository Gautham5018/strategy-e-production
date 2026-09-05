import tempfile, unittest
from pathlib import Path

class UniverseTests(unittest.TestCase):
    def test_incremental_cache_helpers_exist(self):
        from backtest.incremental_ohlc import _last_complete_end, _read_rows, _write_rows
        self.assertIsNotNone(_last_complete_end())
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"ABC_5minute.csv"
            rows={}
            _write_rows(p, {})
            self.assertEqual(_read_rows(p), {})

    def test_cli_supports_bulk_enroll_and_backtest_wrappers(self):
        import run
        text=Path(run.__file__).read_text()
        self.assertIn('enroll-file', text)
        self.assertIn('sys.argv=[sys.argv[0]]+args[1:]', text)
        self.assertIn('if args[0] == "backtest"', text)
        self.assertIn('if args[0] == "optimize"', text)

    def test_dynamic_enroll_and_combined(self):
        import universe_manager as u
        with tempfile.TemporaryDirectory() as d:
            old=(u.CORE_FILE,u.DYNAMIC_FILE,u.COMBINED_FILE)
            u.CORE_FILE=Path(d)/"core.csv";u.DYNAMIC_FILE=Path(d)/"dynamic.txt";u.COMBINED_FILE=Path(d)/"feature.txt"
            u.CORE_FILE.parent.mkdir(parents=True,exist_ok=True);u.CORE_FILE.write_text("symbol,source\nABC,NIFTY_MIDSMALLCAP400\n")
            u.enroll("XYZ")
            self.assertIn("XYZ",u.read_dynamic())
            self.assertIn("NIFTY 50",u.rebuild_combined())
            self.assertIn("ABC",u.rebuild_combined())
            self.assertIn("XYZ",u.rebuild_combined())
            u.CORE_FILE,u.DYNAMIC_FILE,u.COMBINED_FILE=old

if __name__=='__main__':unittest.main()
