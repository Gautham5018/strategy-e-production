import unittest, ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class V65FeatureTests(unittest.TestCase):
    def test_config_has_trailing_and_basket_controls(self):
        s=(ROOT/'config.py').read_text()
        for term in ('TRAILING_STOP_ENABLED','TRAILING_LOCK_R','TRAILING_DISTANCE_R','PORTFOLIO_PROFIT_TARGET_INR','PORTFOLIO_PROFIT_TRAILING_DISTANCE_INR'):
            self.assertIn(term,s)
    def test_monitor_has_trailing_and_basket_logic(self):
        s=(ROOT/'monitor.py').read_text()
        self.assertIn('trailing_stop_enabled',s)
        self.assertIn('portfolio_profit_target_inr',s)
        self.assertIn('PORTFOLIO_PROFIT_TARGET',s)
        self.assertIn('PORTFOLIO_TRAILING_STOP',s)
        self.assertIn('basket_peak_pnl',s)
    def test_backtest_uses_5minute(self):
        s=(ROOT/'backtest'/'historical_5m.py').read_text()
        self.assertIn('INTERVAL="5minute"',s)
        s2=(ROOT/'backtest'/'backtest_strategy_e.py').read_text()
        self.assertIn('target=entry+final_r*risk',s2.replace(' ','') )
        self.assertIn('basket-trailing',s2)
        self.assertIn('PORTFOLIO_PROFIT_TARGET_TRAILING_STOP',s2)
    def test_run_wires_backtest(self):
        s=(ROOT/'run.py').read_text();self.assertIn('pull-5m',s);self.assertIn('backtest_strategy_e',s)
    def test_first_live_template_is_safe(self):
        s=(ROOT/'FIRST_LIVE_TRADE.env').read_text();self.assertIn('LIVE_ORDERS_ARMED=false',s);self.assertIn('MAX_ENTRIES_PER_DAY=1',s)
if __name__=='__main__':unittest.main()
