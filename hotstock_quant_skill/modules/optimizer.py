"""
Batch parameter optimizer for simple strategies.
"""
from __future__ import annotations
from itertools import product
from typing import Callable, Dict, Iterable
import pandas as pd

from modules.backtester import Backtester
from strategies.ma_cross_strategy import MACrossStrategy
from strategies.rsi_strategy import RSIStrategy


def optimize_ma(price_df: pd.DataFrame, short_windows, long_windows, initial_cash=1_000_000) -> pd.DataFrame:
    rows = []
    for s, l in product(short_windows, long_windows):
        if s >= l:
            continue
        strategy = MACrossStrategy(short_window=int(s), long_window=int(l))
        bt = Backtester(initial_cash=initial_cash)
        result = bt.run(price_df.copy(), strategy)
        metrics = result.get("metrics", {})
        rows.append({"strategy": "MA", "short_window": s, "long_window": l, **metrics})
    return pd.DataFrame(rows).sort_values(["sharpe_ratio", "total_return"], ascending=False, na_position="last")


def optimize_rsi(price_df: pd.DataFrame, periods, buy_thresholds, sell_thresholds, initial_cash=1_000_000) -> pd.DataFrame:
    rows = []
    for p, b, s in product(periods, buy_thresholds, sell_thresholds):
        if b >= s:
            continue
        strategy = RSIStrategy(rsi_period=int(p), buy_threshold=float(b), sell_threshold=float(s))
        bt = Backtester(initial_cash=initial_cash)
        result = bt.run(price_df.copy(), strategy)
        metrics = result.get("metrics", {})
        rows.append({"strategy": "RSI", "rsi_period": p, "buy_threshold": b, "sell_threshold": s, **metrics})
    return pd.DataFrame(rows).sort_values(["sharpe_ratio", "total_return"], ascending=False, na_position="last")


def save_optimization(df: pd.DataFrame, path: str) -> None:
    path = str(path)
    if path.endswith(".xlsx"):
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")
