"""
Theme strength index.

Combines catalyst/news intensity with stock-level market activity.
"""
from __future__ import annotations
import pandas as pd


def build_theme_strength_index(
    universe_df: pd.DataFrame,
    quotes_df: pd.DataFrame,
    catalyst_strength_df: pd.DataFrame,
    themes: list[dict],
) -> pd.DataFrame:
    if universe_df.empty:
        return pd.DataFrame(columns=["theme", "theme_strength", "stock_count", "avg_pct_change", "avg_volume_ratio", "avg_turnover_million", "catalyst_score_norm"])

    merged = universe_df.merge(quotes_df, on=["symbol", "name"], how="left", suffixes=("", "_quote"))
    rows = []

    for theme in themes:
        theme_name = theme.get("name", "未知主题")
        keywords = [str(k) for k in theme.get("keywords", [])]
        mask = merged.get("theme_keywords", "").fillna("").apply(lambda x: any(k.lower() in str(x).lower() for k in keywords))
        part = merged[mask].copy()

        stock_count = len(part)
        avg_pct_change = float(part["pct_change"].fillna(0).mean()) if stock_count else 0.0
        avg_volume_ratio = float(part["volume_ratio"].fillna(0).mean()) if stock_count else 0.0
        avg_turnover = float(part["turnover_million_cny"].fillna(0).mean()) if stock_count else 0.0

        cscore = 0.0
        if not catalyst_strength_df.empty and "theme" in catalyst_strength_df.columns:
            m = catalyst_strength_df[catalyst_strength_df["theme"] == theme_name]
            if not m.empty:
                cscore = float(m["catalyst_score_norm"].iloc[0])

        # Simple interpretable score. Can be replaced by rank/z-score model later.
        market_score = min(max(avg_pct_change, 0) * 6, 35) + min(avg_volume_ratio * 12, 25) + min(avg_turnover / 50, 20)
        theme_strength = round(min(market_score + cscore * 0.20, 100), 2)

        rows.append({
            "theme": theme_name,
            "theme_strength": theme_strength,
            "stock_count": stock_count,
            "avg_pct_change": round(avg_pct_change, 2),
            "avg_volume_ratio": round(avg_volume_ratio, 2),
            "avg_turnover_million": round(avg_turnover, 2),
            "catalyst_score_norm": round(cscore, 2),
        })

    return pd.DataFrame(rows).sort_values("theme_strength", ascending=False).reset_index(drop=True)
