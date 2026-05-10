import unittest

import pandas as pd

from strategies.ma_cross_strategy import generate_signals as ma_signals
from strategies.rsi_strategy import generate_signals as rsi_signals


class StrategyTests(unittest.TestCase):
    def test_ma_cross_strategy_emits_cross_signals(self):
        df = pd.DataFrame({"close": [5, 4, 3, 4, 5, 4, 3, 2]})

        out = ma_signals(df, short_window=2, long_window=3)

        self.assertIn(1, out["signal"].tolist())
        self.assertIn(-1, out["signal"].tolist())

    def test_rsi_strategy_emits_buy_signal_on_recovery(self):
        df = pd.DataFrame({"close": [10, 9, 8, 9, 10]})

        out = rsi_signals(df, rsi_period=2, buy_threshold=40, sell_threshold=70)

        self.assertEqual(out["signal"].iloc[3], 1)


if __name__ == "__main__":
    unittest.main()
