# Hotstock Quant Skill

Hotstock Quant Skill is a local Python research toolkit for catalyst parsing,
theme strength tracking, stock pool scoring, simple strategy backtesting, and
parameter optimization.

It is designed for research and education. It must not be treated as a trading
recommendation system.

## Project Structure

```text
config.enhanced.yaml       Enhanced research configuration
data/sample/               Sample universe, quotes, and news data
examples/                  Runnable daily, optimization, and backtest scripts
modules/                   Indicators, scoring, reports, backtesting utilities
providers/                 Data provider templates
strategies/                MA, RSI, and theme strategy templates
reports/                   Generated Markdown and Excel reports
logs/app.log               Runtime log output
tests/                     Basic regression tests
```

## Install

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` when connecting real data or push providers.

## Run

Using Make:

```bash
make daily
make optimize
make backtest
make test
```

Or run directly:

```bash
python examples/run_enhanced_daily.py
python examples/run_parameter_optimization.py
python examples/run_batch_backtest.py
python -m unittest discover -s tests -p "test_*.py"
```

## Outputs

```text
reports/daily/daily_hot_pool_<date>.md
reports/daily/daily_hot_pool_<date>.html
reports/daily/latest.html
reports/daily/daily_hot_pool_<date>.xlsx
reports/optimized/parameter_optimization.xlsx
reports/backtests/batch_backtest.xlsx
logs/app.log
```

## Data Configuration

The current examples use local sample data:

```text
data/sample/universe.csv
data/sample/quotes.csv
data/sample/news.csv
```

For real research, configure authorized data sources such as Tushare, AkShare,
Eastmoney, Tonghuashun/iFinD, Wind, Choice, or broker APIs. Check data licensing,
API terms, rate limits, and compliance requirements before use.

Environment variables:

```text
TUSHARE_TOKEN
EASTMONEY_ENABLED
TONGHUASHUN_ENABLED
WEBHOOK_URL
```

## Disclaimer

All outputs are for research and educational analysis only. This project does
not provide buy, sell, hold, target price, position sizing, guaranteed return,
tax, legal, or investment advice. Historical backtests and sample outputs do not
represent future results. Independently verify data before making decisions.
