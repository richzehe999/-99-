import pandas as pd
from modules.indicators import add_rsi


def generate_signals(
    df: pd.DataFrame,
    rsi_period: int = 14,
    buy_threshold: float = 30,
    sell_threshold: float = 70,
) -> pd.DataFrame:
    """
    RSI reversal strategy.

    Buy signal: RSI crosses upward through buy_threshold.
    Sell signal: RSI crosses downward through sell_threshold after overbought.
    """
    out = add_rsi(df, rsi_period)
    rsi_col = f"rsi{rsi_period}"

    out["signal"] = 0
    prev_rsi = out[rsi_col].shift(1)

    buy = (prev_rsi < buy_threshold) & (out[rsi_col] >= buy_threshold)
    sell = (prev_rsi > sell_threshold) & (out[rsi_col] <= sell_threshold)

    out.loc[buy, "signal"] = 1
    out.loc[sell, "signal"] = -1
    return out


class RSIStrategy:
    def __init__(self, rsi_period: int = 14, buy_threshold: float = 30, sell_threshold: float = 70):
        self.rsi_period = rsi_period
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.name = f"RSI_{rsi_period}_{buy_threshold}_{sell_threshold}"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        return generate_signals(df, self.rsi_period, self.buy_threshold, self.sell_threshold)
