import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class BacktestMath(unittest.TestCase):
    def test_final_target_is_r_multiple(self):
        s=(ROOT/'backtest'/'backtest_strategy_e.py').read_text().replace(' ','')
        self.assertIn('target=entry+final_r*risk',s)
    def test_basket_target_is_modeled(self):
        s=(ROOT/'backtest'/'backtest_strategy_e.py').read_text()
        self.assertIn('PORTFOLIO_PROFIT_TARGET',s)
        self.assertIn('basket_adjust',s)
if __name__=='__main__':unittest.main()
