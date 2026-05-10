"""
Run batch backtest template.

Usage:
  python examples/run_batch_backtest.py
"""
from __future__ import annotations
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.batch_backtester import run_batch_backtest, export_batch_report
from modules.runtime_logging import setup_run_logging
from strategies.ma_cross_strategy import MACrossStrategy


def table(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except ImportError:
        return df.to_string(index=False)


def load_price(symbol: str) -> pd.DataFrame:
    # Replace this with AkShare/Tushare/Eastmoney OHLCV retrieval in production.
    seed = sum(ord(c) for c in symbol)
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=260, freq="B")
    returns = rng.normal(0.0006, 0.023, size=len(dates))
    close = 30 * np.exp(np.cumsum(returns))
    turnover = rng.uniform(100, 1000, size=len(dates))
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": close, "turnover": turnover})


def main():
    setup_run_logging(ROOT, "run_batch_backtest")
    universe = pd.read_csv(ROOT / "data/sample/universe.csv")
    symbols = universe["symbol"].astype(str).head(8).tolist()
    result = run_batch_backtest(
        symbols=symbols,
        load_price_func=load_price,
        strategy_factory=lambda: MACrossStrategy(5, 20),
        initial_cash=1_000_000,
    )
    export_batch_report(result, ROOT / "reports/backtests/batch_backtest.xlsx")
    print(table(result))
    print("\nSaved reports/backtests/batch_backtest.xlsx")


if __name__ == "__main__":
    main()
