import unittest
from datetime import datetime, timedelta, time
from feature_engine import score_trade
from feature_cache import FeatureBarCache

class V7FeatureTests(unittest.TestCase):
    def _bars(self,n=40):
        base=datetime(2026,8,31,9,15); rows=[]; px=100.0
        for i in range(n):
            o=px; c=px*1.001; h=c*1.002; l=o*0.999
            rows.append({'ts':base+timedelta(minutes=5*i),'open':o,'high':h,'low':l,'close':c,'volume':1000+i*10})
            px=c
        return rows
    def test_feature_score_has_expected_fields(self):
        b=self._bars()
        s=score_trade(symbol='TEST',signal_time=b[-1]['ts'],signal_open=b[-1]['open'],signal_high=b[-1]['high'],signal_low=b[-1]['low'],signal_close=b[-1]['close'],entry_price=b[-1]['close'],bars=b,market_bars=b,market_filter=True)
        self.assertGreaterEqual(s.score,0);self.assertLessEqual(s.score,100);self.assertIn(s.grade,{'A+','A','B','C'})
    def test_cache_append_replaces_same_bar(self):
        c=FeatureBarCache();b=self._bars(3);c.put('TEST',b);c.append('TEST',dict(b[-1],close=999));self.assertEqual(len(c.get('TEST')),3);self.assertEqual(c.get('TEST')[-1]['close'],999)
    def test_backtest_auto_market_context_path(self):
        from pathlib import Path
        src=Path(Path(__file__).resolve().parents[1]/'backtest/backtest_strategy_e.py').read_text()
        self.assertIn("NIFTY 50_5minute.csv", src)

    def test_cache_age_and_ready(self):
        c=FeatureBarCache();b=self._bars(40);c.put('TEST',b);self.assertTrue(c.ready('TEST',30));self.assertIsNotNone(c.age_seconds('TEST',b[-1]['ts']))

if __name__=='__main__':unittest.main()

class MomentumAndCacheTests(unittest.TestCase):
    def test_momentum_module_exists(self):
        import momentum_universe
        self.assertTrue(hasattr(momentum_universe,'rank'))
    def test_cache_health_module_exists(self):
        import backtest.cache_health
        self.assertTrue(hasattr(backtest.cache_health,'main'))
