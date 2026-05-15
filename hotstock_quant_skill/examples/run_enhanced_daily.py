"""
Run enhanced daily catalyst + stock pool report.

Usage:
  python examples/run_enhanced_daily.py
  python examples/run_enhanced_daily.py --slot premarket --send-email
"""
from __future__ import annotations
import argparse
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
from modules.daily_report import get_report_slot, render_daily_markdown, render_daily_html, save_daily_report, save_daily_html, save_daily_excel
from modules.email_notifier import build_email_settings, send_html_email
from modules.runtime_logging import setup_run_logging
from modules.trading_calendar import a_share_calendar_status


def parse_args():
    parser = argparse.ArgumentParser(description="Generate enhanced daily report and optionally email it.")
    parser.add_argument("--slot", choices=["premarket", "midday", "close"], default="close")
    parser.add_argument("--send-email", action="store_true", help="Send the generated HTML report by SMTP.")
    parser.add_argument("--attach-excel", action="store_true", help="Attach the generated Excel workbook.")
    parser.add_argument("--dry-run", action="store_true", help="Generate files and print email status without sending.")
    parser.add_argument("--date", help="Override report date in YYYY-MM-DD format.")
    parser.add_argument("--require-trading-day", action="store_true", help="Skip generation and email when the date is not an A-share trading day.")
    return parser.parse_args()


def main():
    args = parse_args()
    setup_run_logging(ROOT, "run_enhanced_daily")
    cfg = yaml.safe_load((ROOT / "config.enhanced.yaml").read_text(encoding="utf-8"))
    trade_date = args.date or str(date.today())
    calendar_status = a_share_calendar_status(trade_date)
    print(f"A-share calendar: {calendar_status}")
    if args.require_trading_day and not calendar_status["is_trading_day"]:
        print(f"Skip report/email: {calendar_status['date']} is not an A-share trading day ({calendar_status['reason']}).")
        return

    universe = pd.read_csv(ROOT / cfg["universe"]["csv_path"])
    quotes = pd.read_csv(ROOT / "data/sample/quotes.csv")
    news = load_local_news(ROOT / cfg["news"]["local_news_csv"])

    hits = parse_theme_hits(news, cfg["themes"], lookback_days=cfg["news"].get("lookback_days", 7))
    catalyst_strength = theme_catalyst_strength(hits)
    theme_strength = build_theme_strength_index(universe, quotes, catalyst_strength, cfg["themes"])
    pool = build_stock_pool(universe, quotes, catalyst_strength, cfg["themes"], cfg)

    slot_meta = get_report_slot(args.slot)
    report_stem = f"daily_hot_pool_{trade_date}_{args.slot}"
    md = render_daily_markdown(trade_date, theme_strength, pool, catalyst_strength, slot=args.slot)
    html = render_daily_html(trade_date, theme_strength, pool, catalyst_strength, slot=args.slot)
    md_path = ROOT / f"reports/daily/{report_stem}.md"
    html_path = ROOT / f"reports/daily/{report_stem}.html"
    xlsx_path = ROOT / f"reports/daily/{report_stem}.xlsx"
    save_daily_report(md, md_path)
    save_daily_html(html, html_path)
    save_daily_html(html, ROOT / "reports/daily/latest.html")
    save_daily_excel(xlsx_path, theme_strength, pool, catalyst_strength, hits)

    print(md)
    print(f"\nSaved {md_path.relative_to(ROOT)}, {html_path.relative_to(ROOT)}, {xlsx_path.relative_to(ROOT)} and reports/daily/latest.html")

    if args.send_email or args.dry_run:
        settings = build_email_settings(cfg)
        subject = f"{slot_meta['title']}｜{trade_date}｜{slot_meta['label']}"
        attachments = [xlsx_path] if args.attach_excel else []
        email_html = html
        template_path = cfg.get("email", {}).get("html_template_path")
        if template_path and Path(template_path).exists():
            email_html = Path(template_path).read_text(encoding="utf-8")
        if args.dry_run:
            missing = [key for key in ["smtp_host", "smtp_user", "smtp_password", "from_addr", "to_addrs"] if not settings.get(key)]
            print(f"Email dry run: subject={subject}; to={settings.get('to_addrs')}; template={template_path or 'generated'}; missing={missing}")
        else:
            result = send_html_email(settings, subject, email_html, md, attachments=attachments)
            print(f"Email send result: {result}")


if __name__ == "__main__":
    main()
