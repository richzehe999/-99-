import pandas as pd
from modules.scoring_model import score_stock_pool, assign_pool
from modules.report_generator import save_pool_report


def main():
    # Sample data only. Replace with real market and catalyst data.
    data = [
        {"symbol": "300502", "name": "新易盛", "theme_relevance": 95, "turnover": 2_500_000_000, "pct_change_5d": 0.18, "market_cap": 80_000_000_000, "catalyst_quality": 90},
        {"symbol": "301205", "name": "联特科技", "theme_relevance": 92, "turnover": 1_200_000_000, "pct_change_5d": 0.15, "market_cap": 20_000_000_000, "catalyst_quality": 85},
        {"symbol": "300563", "name": "神宇股份", "theme_relevance": 80, "turnover": 900_000_000, "pct_change_5d": 0.20, "market_cap": 12_000_000_000, "catalyst_quality": 75},
        {"symbol": "601138", "name": "工业富联", "theme_relevance": 88, "turnover": 3_600_000_000, "pct_change_5d": 0.07, "market_cap": 500_000_000_000, "catalyst_quality": 85},
        {"symbol": "002463", "name": "沪电股份", "theme_relevance": 84, "turnover": 1_800_000_000, "pct_change_5d": 0.10, "market_cap": 80_000_000_000, "catalyst_quality": 78},
    ]

    df = pd.DataFrame(data)
    scored = score_stock_pool(df)
    pooled = assign_pool(scored, core_threshold=80, watch_threshold=60)
    print(pooled[["symbol", "name", "total_score", "pool"]])

    save_pool_report(pooled)
    pooled.to_csv("reports/daily_hot_pool.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
