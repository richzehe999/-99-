"""
Run MA/RSI parameter optimization on synthetic sample price data.

Usage:
  python examples/run_parameter_optimization.py
"""
from __future__ import annotations
from pathlib import Path
import sys
import yaml
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.optimizer import optimize_ma, optimize_rsi, save_optimization
from modules.runtime_logging import setup_run_logging


def table(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except ImportError:
        return df.to_string(index=False)


def make_sample_price(days=360, seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days, freq="B")
    returns = rng.normal(0.0008, 0.025, size=days)
    close = 50 * np.exp(np.cumsum(returns))
    turnover = rng.uniform(200, 1200, size=days)
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": close, "turnover": turnover})


def main():
    setup_run_logging(ROOT, "run_parameter_optimization")
    cfg = yaml.safe_load((ROOT / "config.enhanced.yaml").read_text(encoding="utf-8"))
    price = make_sample_price()
    opt = cfg["parameter_optimization"]

    ma = optimize_ma(price, opt["ma_short"], opt["ma_long"], cfg["backtest"]["initial_cash"])
    rsi = optimize_rsi(price, opt["rsi_period"], opt["rsi_buy"], opt["rsi_sell"], cfg["backtest"]["initial_cash"])

    out = pd.concat([ma, rsi], ignore_index=True, sort=False)
    save_optimization(out, ROOT / "reports/optimized/parameter_optimization.xlsx")
    print(table(out.head(20)))
    print("\nSaved reports/optimized/parameter_optimization.xlsx")


if __name__ == "__main__":
    main()
