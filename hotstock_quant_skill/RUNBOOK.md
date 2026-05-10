# Hotstock Quant Skill Runbook

This project is for research and education only. It does not provide buy, sell,
hold, price target, position sizing, or guaranteed-return advice.

## 1. Environment

From the project directory:

```bash
cd "/Users/wuzehe/Documents/New project/hotstock_quant_skill"
source .venv/bin/activate
```

If using the included Makefile, the common commands are:

```bash
make install
make daily
make optimize
make backtest
make test
make clean
```

If rebuilding from scratch on macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If rebuilding from scratch on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Local note: this machine could not reach PyPI during validation, so the current
`.venv` was created with the bundled local Python runtime and inherited local
pandas/numpy/openpyxl packages. The examples also include offline fallbacks for
missing `PyYAML` and `tabulate`.

## 2. Daily Hot Pool

Run:

```bash
python examples/run_enhanced_daily.py
```

Outputs:

```text
reports/daily/daily_hot_pool_<date>.md
reports/daily/daily_hot_pool_<date>.html
reports/daily/latest.html
reports/daily/daily_hot_pool_<date>.xlsx
```

What it does:

- Reads `config.enhanced.yaml`
- Reads sample universe, quotes, and news CSV files
- Parses catalyst keywords by theme
- Builds theme strength ranking
- Builds core/watch stock pools
- Exports Markdown and Excel reports

## 3. Parameter Optimization

Run:

```bash
python examples/run_parameter_optimization.py
```

Output:

```text
reports/optimized/parameter_optimization.xlsx
```

What it does:

- Generates synthetic sample price data
- Tests MA and RSI parameter combinations from `config.enhanced.yaml`
- Ranks results by Sharpe ratio and total return

## 4. Batch Backtest

Run:

```bash
python examples/run_batch_backtest.py
```

Output:

```text
reports/backtests/batch_backtest.xlsx
```

What it does:

- Reads symbols from `data/sample/universe.csv`
- Generates synthetic sample prices for each symbol
- Runs the MA cross strategy across the batch
- Exports summary metrics to Excel

## 5. Report Output Directories

```text
reports/daily/
reports/optimized/
reports/backtests/
logs/app.log
```

## 6. Data and API Configuration Still Needed

Current local validation uses sample/offline data. For real research use, replace
or connect these inputs:

```text
data/sample/universe.csv
data/sample/quotes.csv
data/sample/news.csv
```

Provider/API items to configure before live use:

- AkShare or another market data provider for real quotes and historical bars
- Tushare token, Wind/Choice/iFinD/Bloomberg/Refinitiv credentials, or broker API
  credentials if those providers are used
- Licensed news/RSS/announcement source if replacing local news CSV
- Webhook URL/secret in `config.enhanced.yaml` if enabling push notifications

## 7. What Is Still Example Data

- `examples/run_parameter_optimization.py` uses synthetic generated price data.
- `examples/run_batch_backtest.py` uses synthetic generated price data.
- `examples/run_enhanced_daily.py` uses local sample files under `data/sample/`.
- Existing provider classes are templates until real provider credentials and
  data retrieval rules are configured.
