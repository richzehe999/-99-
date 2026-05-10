import math
import pandas as pd
import numpy as np


class SimpleBacktester:
    """
    Long-only single-asset backtester.

    Assumptions:
    - Buy with full available cash on signal = 1.
    - Sell full position on signal = -1.
    - Trades execute at close price with commission and slippage.
    """

    def __init__(
        self,
        initial_cash: float = 100000,
        commission_rate: float = 0.0003,
        slippage_rate: float = 0.0005,
    ):
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
        required = {"date", "close", "signal"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Backtest data missing required columns: {missing}")

        cash = self.initial_cash
        shares = 0
        position = 0
        trades = []
        equity_records = []

        entry_price = None
        entry_date = None

        for _, row in df.iterrows():
            date = row["date"]
            close = float(row["close"])
            signal = int(row["signal"])

            if signal == 1 and position == 0:
                buy_price = close * (1 + self.slippage_rate)
                shares = math.floor(cash / (buy_price * (1 + self.commission_rate)))
                if shares > 0:
                    cost = shares * buy_price
                    commission = cost * self.commission_rate
                    cash -= cost + commission
                    position = 1
                    entry_price = buy_price
                    entry_date = date

            elif signal == -1 and position == 1:
                sell_price = close * (1 - self.slippage_rate)
                revenue = shares * sell_price
                commission = revenue * self.commission_rate
                cash += revenue - commission

                trade_return = (sell_price - entry_price) / entry_price
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": date,
                    "entry_price": entry_price,
                    "exit_price": sell_price,
                    "shares": shares,
                    "return": trade_return,
                    "profit": revenue - commission - shares * entry_price,
                })

                shares = 0
                position = 0
                entry_price = None
                entry_date = None

            equity = cash + shares * close
            equity_records.append({
                "date": date,
                "cash": cash,
                "shares": shares,
                "close": close,
                "equity": equity,
                "position": position,
            })

        equity_df = pd.DataFrame(equity_records)
        trades_df = pd.DataFrame(trades)
        metrics = calculate_metrics(equity_df, trades_df, self.initial_cash)
        return equity_df, trades_df, metrics


def calculate_metrics(equity_df: pd.DataFrame, trades_df: pd.DataFrame, initial_cash: float) -> dict:
    if equity_df.empty:
        return {}

    equity = equity_df["equity"]
    daily_returns = equity.pct_change().fillna(0)

    total_return = equity.iloc[-1] / initial_cash - 1
    days = max((pd.to_datetime(equity_df["date"].iloc[-1]) - pd.to_datetime(equity_df["date"].iloc[0])).days, 1)
    annualized_return = (1 + total_return) ** (365 / days) - 1

    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    max_drawdown = drawdown.min()

    sharpe = np.nan
    if daily_returns.std() != 0:
        sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252)

    trade_count = len(trades_df)
    if trade_count > 0:
        win_rate = (trades_df["return"] > 0).mean()
        avg_trade_return = trades_df["return"].mean()
        profit_sum = trades_df.loc[trades_df["profit"] > 0, "profit"].sum()
        loss_sum = abs(trades_df.loc[trades_df["profit"] < 0, "profit"].sum())
        profit_factor = profit_sum / loss_sum if loss_sum != 0 else np.inf
    else:
        win_rate = np.nan
        avg_trade_return = np.nan
        profit_factor = np.nan

    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "avg_trade_return": avg_trade_return,
        "profit_factor": profit_factor,
    }


class Backtester(SimpleBacktester):
    """
    Adapter used by enhanced modules.

    Accepts a strategy object with generate_signals(df) or a callable strategy.
    Returns dict with equity/trades/metrics for easier downstream reporting.
    """
    def run(self, df: pd.DataFrame, strategy=None) -> dict:
        if strategy is not None:
            if hasattr(strategy, "generate_signals"):
                df = strategy.generate_signals(df)
            elif callable(strategy):
                df = strategy(df)
            else:
                raise TypeError("strategy must expose generate_signals(df) or be callable")
        equity_df, trades_df, metrics = super().run(df)
        # Normalize field naming for dashboards/optimizers
        if "sharpe" in metrics and "sharpe_ratio" not in metrics:
            metrics["sharpe_ratio"] = metrics["sharpe"]
        return {"equity": equity_df, "trades": trades_df, "metrics": metrics}
