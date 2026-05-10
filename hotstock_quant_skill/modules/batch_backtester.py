"""
Batch backtesting across a stock universe.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Callable
import pandas as pd

from modules.backtester import Backtester


def run_batch_backtest(
    symbols: list[str],
    load_price_func: Callable[[str], pd.DataFrame],
    strategy_factory: Callable[[], object],
    initial_cash: float = 1_000_000,
) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        try:
            price_df = load_price_func(symbol)
            strategy = strategy_factory()
            result = Backtester(initial_cash=initial_cash).run(price_df, strategy)
            metrics = result.get("metrics", {})
            rows.append({"symbol": symbol, "status": "ok", **metrics})
        except Exception as exc:
            rows.append({"symbol": symbol, "status": f"error: {exc}"})
    return pd.DataFrame(rows)


def export_batch_report(df: pd.DataFrame, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".xlsx":
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")
