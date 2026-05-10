import unittest

import pandas as pd

from modules.scoring_model import assign_pool, score_stock_pool


class ScoringModelTests(unittest.TestCase):
    def test_score_stock_pool_ranks_stronger_candidate_first(self):
        df = pd.DataFrame(
            [
                {
                    "symbol": "weak",
                    "theme_relevance": 20,
                    "turnover": 100,
                    "pct_change_5d": 1,
                    "market_cap": 500,
                    "catalyst_quality": 10,
                },
                {
                    "symbol": "strong",
                    "theme_relevance": 90,
                    "turnover": 900,
                    "pct_change_5d": 8,
                    "market_cap": 80,
                    "catalyst_quality": 80,
                },
            ]
        )

        scored = score_stock_pool(df)

        self.assertEqual(scored.iloc[0]["symbol"], "strong")
        self.assertGreater(scored.iloc[0]["total_score"], scored.iloc[1]["total_score"])

    def test_assign_pool_thresholds(self):
        df = pd.DataFrame({"symbol": ["a", "b", "c"], "total_score": [85, 65, 20]})

        out = assign_pool(df)

        self.assertEqual(out.loc[0, "pool"], "core")
        self.assertEqual(out.loc[1, "pool"], "watch")
        self.assertEqual(out.loc[2, "pool"], "exclude")


if __name__ == "__main__":
    unittest.main()
