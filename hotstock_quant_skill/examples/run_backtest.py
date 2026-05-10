import numpy as np
import pandas as pd

from strategies.ma_cross_strategy import generate_signals
from modules.backtester import SimpleBacktester
from modules.report_generator import save_backtest_report


def make_sample_price_data():
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=260, freq="B")
    returns = np.random.normal(0.0008, 0.025, len(dates))
    close = 100 * (1 + pd.Series(returns)).cumprod()

    df = pd.DataFrame({
        "date": dates,
        "open": close * (1 + np.random.normal(0, 0.003, len(dates))),
        "high": close * (1 + np.random.uniform(0, 0.02, len(dates))),
        "low": close * (1 - np.random.uniform(0, 0.02, len(dates))),
        "close": close,
        "volume": np.random.randint(1_000_000, 8_000_000, len(dates)),
        "turnover": np.random.randint(100_000_000, 900_000_000, len(dates)),
    })

    return df


def main():
    df = make_sample_price_data()
    signal_df = generate_signals(df, short_window=5, long_window=20)

    bt = SimpleBacktester(initial_cash=100000)
    equity_df, trades_df, metrics = bt.run(signal_df)

    print("Backtest Metrics:")
    for k, v in metrics.items():
        print(f"{k}: {v}")

    save_backtest_report(equity_df, trades_df, metrics)


if __name__ == "__main__":
    main()
