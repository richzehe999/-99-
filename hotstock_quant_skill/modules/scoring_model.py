import pandas as pd
import numpy as np


def minmax_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if s.max() == s.min():
        return pd.Series(50, index=series.index)
    score = (s - s.min()) / (s.max() - s.min()) * 100
    if not higher_is_better:
        score = 100 - score
    return score.fillna(0)


def score_stock_pool(df: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """
    Score stocks for core/watch pool generation.

    Expected columns:
    symbol, name, theme_relevance, turnover, pct_change_5d, market_cap, catalyst_quality
    """
    if weights is None:
        weights = {
            "theme_relevance": 0.30,
            "capital_strength": 0.25,
            "trend_strength": 0.20,
            "market_cap_elasticity": 0.15,
            "catalyst_quality": 0.10,
        }

    out = df.copy()
    out["theme_relevance_score"] = minmax_score(out.get("theme_relevance", 0), True)
    out["capital_strength_score"] = minmax_score(out.get("turnover", 0), True)
    out["trend_strength_score"] = minmax_score(out.get("pct_change_5d", 0), True)
    out["market_cap_elasticity_score"] = minmax_score(out.get("market_cap", 0), False)
    out["catalyst_quality_score"] = minmax_score(out.get("catalyst_quality", 0), True)

    out["total_score"] = (
        out["theme_relevance_score"] * weights["theme_relevance"]
        + out["capital_strength_score"] * weights["capital_strength"]
        + out["trend_strength_score"] * weights["trend_strength"]
        + out["market_cap_elasticity_score"] * weights["market_cap_elasticity"]
        + out["catalyst_quality_score"] * weights["catalyst_quality"]
    )

    return out.sort_values("total_score", ascending=False).reset_index(drop=True)


def assign_pool(df: pd.DataFrame, core_threshold: float = 80, watch_threshold: float = 60) -> pd.DataFrame:
    out = df.copy()
    out["pool"] = "exclude"
    out.loc[out["total_score"] >= watch_threshold, "pool"] = "watch"
    out.loc[out["total_score"] >= core_threshold, "pool"] = "core"
    return out
