"""
Build enhanced core/watch pools with sample-compatible columns.
"""
from __future__ import annotations
import pandas as pd
from modules.scoring_model import score_stock_pool, assign_pool


def _theme_relevance(row, themes: list[dict]) -> float:
    blob = str(row.get("theme_keywords", ""))
    score = 0
    for theme in themes:
        for kw in theme.get("keywords", []):
            if str(kw).lower() in blob.lower():
                score += 1
    return min(score * 20, 100)


def build_stock_pool(universe_df: pd.DataFrame, quotes_df: pd.DataFrame, catalyst_strength_df: pd.DataFrame, themes: list[dict], config: dict) -> pd.DataFrame:
    df = universe_df.merge(quotes_df, on=["symbol", "name"], how="left", suffixes=("", "_q"))
    if df.empty:
        return df

    # Normalize to expected scoring_model fields.
    df["theme_relevance"] = df.apply(lambda r: _theme_relevance(r, themes), axis=1)
    df["turnover"] = df.get("turnover_million_cny", 0).fillna(0)
    df["pct_change_5d"] = df.get("pct_change", 0).fillna(0)
    df["market_cap"] = df.get("market_cap_billion_cny", df.get("market_cap_billion_cny_q", 0)).fillna(0)
    df["catalyst_quality"] = 0.0

    # Add catalyst score if company keywords match strong themes.
    if not catalyst_strength_df.empty:
        theme_scores = dict(zip(catalyst_strength_df["theme"], catalyst_strength_df["catalyst_score_norm"]))
        def catalyst_for_row(row):
            blob = str(row.get("theme_keywords", ""))
            best = 0.0
            for theme in themes:
                if any(str(kw).lower() in blob.lower() for kw in theme.get("keywords", [])):
                    best = max(best, float(theme_scores.get(theme.get("name"), 0)))
            return best
        df["catalyst_quality"] = df.apply(catalyst_for_row, axis=1)

    # Basic liquidity/risk filters.
    screening = config.get("screening", {})
    max_cap = screening.get("market_cap_max_billion_cny", 999999)
    min_turnover = screening.get("turnover_min_million_cny", 0)
    exclude_st = config.get("universe", {}).get("exclude_st", True)

    eligible = df.copy()
    if exclude_st and "is_st" in eligible.columns:
        eligible = eligible[eligible["is_st"].astype(str).str.lower().isin(["false", "0", "no"])]
    eligible = eligible[eligible["market_cap"] <= max_cap]
    eligible = eligible[eligible["turnover"] >= min_turnover]

    weights = {
        "theme_relevance": config.get("scoring_weights", {}).get("theme_relevance", 0.30),
        "capital_strength": config.get("scoring_weights", {}).get("money_strength", 0.25),
        "trend_strength": config.get("scoring_weights", {}).get("trend_strength", 0.20),
        "market_cap_elasticity": config.get("scoring_weights", {}).get("elasticity", 0.15),
        "catalyst_quality": config.get("scoring_weights", {}).get("catalyst_strength", 0.10),
    }

    scored = score_stock_pool(eligible, weights)
    scored = assign_pool(scored, screening.get("min_score_core", 80), screening.get("min_score_watch", 60))

    def reason(row):
        parts = []
        if row.get("theme_relevance_score", 0) >= 70:
            parts.append("主题相关性较高")
        if row.get("capital_strength_score", 0) >= 70:
            parts.append("成交/资金强度较高")
        if row.get("trend_strength_score", 0) >= 70:
            parts.append("短期趋势较强")
        if row.get("market_cap_elasticity_score", 0) >= 70:
            parts.append("市值弹性较高")
        if row.get("catalyst_quality_score", 0) >= 70:
            parts.append("近期催化较强")
        return "；".join(parts) if parts else "进入量化观察范围"

    scored["reason"] = scored.apply(reason, axis=1)
    return scored
