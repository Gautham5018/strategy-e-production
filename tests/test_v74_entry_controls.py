import unittest
from config import SETTINGS
from state_store import StateStore
import tempfile, os

class V74Controls(unittest.TestCase):
    def test_defaults(self):
        self.assertTrue(SETTINGS.delayed_entry_enabled)
        self.assertEqual(SETTINGS.delayed_entry_mode,'PULLBACK_BOS')
        self.assertEqual(SETTINGS.delayed_entry_wait_minutes,20)
        self.assertAlmostEqual(SETTINGS.fib_min,.50)
        self.assertAlmostEqual(SETTINGS.fib_max,.618)
    def test_pending_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            s=StateStore(os.path.join(d,'state.json'))
            self.assertEqual(s.pending_entries(),{})
            s.upsert_pending_entry('ABC',{'symbol':'ABC','status':'PENDING'})
            self.assertIn('ABC',s.pending_entries())
            s.remove_pending_entry('ABC')
            self.assertNotIn('ABC',s.pending_entries())

    def test_separate_one_minute_cache_path(self):
        from config import SETTINGS
        self.assertNotEqual(SETTINGS.feature_cache_dir, SETTINGS.one_minute_cache_dir)
        self.assertTrue(SETTINGS.one_minute_cache_dir.endswith("live_1m_cache"))

    def test_final_target_is_three_r(self):
        self.assertEqual(SETTINGS.final_r_multiple, 3.0)

class V74RuntimeTests(unittest.TestCase):
    def test_incremental_5m_fake_broker(self):
        from backtest.incremental_ohlc import update_symbol
        from tempfile import TemporaryDirectory
        from datetime import datetime
        class B:
            def instrument(self, symbol): return {'instrument_token': 123}
            def historical_data(self, token, start, end, interval):
                return [{'date': datetime(2026,9,2,9,15), 'open':100, 'high':101, 'low':99, 'close':100.5, 'volume':1000}]
        with TemporaryDirectory() as d:
            out=update_symbol(B(),'TEST',d,initial_history_days=1)
            self.assertEqual(out['symbol'],'TEST')
            self.assertTrue((__import__('pathlib').Path(d)/'TEST_5minute.csv').exists())
