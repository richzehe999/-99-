"""
Run enhanced daily catalyst + stock pool report.

Usage:
  python examples/run_enhanced_daily.py
"""
from __future__ import annotations
from pathlib import Path
from datetime import date
import sys
import yaml
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.news_catalyst_parser import load_local_news, parse_theme_hits, theme_catalyst_strength
from modules.theme_strength import build_theme_strength_index
from modules.enhanced_pool_builder import build_stock_pool
from modules.daily_report import render_daily_markdown, render_daily_html, save_daily_report, save_daily_html, save_daily_excel
from modules.runtime_logging import setup_run_logging


def main():
    setup_run_logging(ROOT, "run_enhanced_daily")
    cfg = yaml.safe_load((ROOT / "config.enhanced.yaml").read_text(encoding="utf-8"))
    universe = pd.read_csv(ROOT / cfg["universe"]["csv_path"])
    quotes = pd.read_csv(ROOT / "data/sample/quotes.csv")
    news = load_local_news(ROOT / cfg["news"]["local_news_csv"])

    hits = parse_theme_hits(news, cfg["themes"], lookback_days=cfg["news"].get("lookback_days", 7))
    catalyst_strength = theme_catalyst_strength(hits)
    theme_strength = build_theme_strength_index(universe, quotes, catalyst_strength, cfg["themes"])
    pool = build_stock_pool(universe, quotes, catalyst_strength, cfg["themes"], cfg)

    trade_date = str(date.today())
    md = render_daily_markdown(trade_date, theme_strength, pool, catalyst_strength)
    html = render_daily_html(trade_date, theme_strength, pool, catalyst_strength)
    save_daily_report(md, ROOT / f"reports/daily/daily_hot_pool_{trade_date}.md")
    save_daily_html(html, ROOT / f"reports/daily/daily_hot_pool_{trade_date}.html")
    save_daily_html(html, ROOT / "reports/daily/latest.html")
    save_daily_excel(ROOT / f"reports/daily/daily_hot_pool_{trade_date}.xlsx", theme_strength, pool, catalyst_strength, hits)

    print(md)
    print(f"\nSaved reports/daily/daily_hot_pool_{trade_date}.md, .html, .xlsx and reports/daily/latest.html")


if __name__ == "__main__":
    main()
