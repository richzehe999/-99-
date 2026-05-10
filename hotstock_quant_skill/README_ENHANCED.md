# Hotstock Quant Skill - Enhanced Edition

This enhanced version upgrades the original hot theme + backtesting skill with:

- News/catalyst parsing
- Theme strength index
- Enhanced core/watch pool scoring
- Batch backtesting
- MA/RSI parameter optimization
- Markdown and Excel daily reports
- Webhook push template
- Sample data for immediate local testing

## Install

```bash
pip install -r requirements.txt
```

## Run Enhanced Daily Report

```bash
python examples/run_enhanced_daily.py
```

Outputs:

```text
reports/daily/daily_hot_pool_<date>.md
reports/daily/daily_hot_pool_<date>.xlsx
```

## Run Parameter Optimization

```bash
python examples/run_parameter_optimization.py
```

Outputs:

```text
reports/optimized/parameter_optimization.xlsx
```

## Run Batch Backtest

```bash
python examples/run_batch_backtest.py
```

Outputs:

```text
reports/backtests/batch_backtest.xlsx
```

## Replace Sample Data

The enhanced package uses these sample files by default:

```text
data/sample/universe.csv
data/sample/quotes.csv
data/sample/news.csv
```

Replace them with provider outputs from AkShare, Tushare, Eastmoney, Tonghuashun/iFinD, Wind, Choice, or broker APIs.

## Important

This project is for educational and research use only. It is not financial advice, investment advice, tax advice, legal advice, or a trading recommendation system.
