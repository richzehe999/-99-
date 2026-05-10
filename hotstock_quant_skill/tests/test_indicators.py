import unittest

import pandas as pd

from modules.indicators import add_moving_average, add_returns, add_rsi


class IndicatorTests(unittest.TestCase):
    def test_moving_average_and_returns(self):
        df = pd.DataFrame({"close": [10, 20, 30, 40]})

        out = add_returns(add_moving_average(df, windows=(2,)))

        self.assertEqual(out["ma2"].tolist()[-1], 35)
        self.assertAlmostEqual(out["return"].iloc[1], 1.0)

    def test_rsi_calculation(self):
        df = pd.DataFrame({"close": [10, 9, 8, 9, 10]})

        out = add_rsi(df, period=2)

        self.assertAlmostEqual(out["rsi2"].iloc[3], 50.0)


if __name__ == "__main__":
    unittest.main()
