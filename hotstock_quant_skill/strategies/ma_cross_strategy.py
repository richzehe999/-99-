import pandas as pd


def generate_signals(df: pd.DataFrame, short_window: int = 5, long_window: int = 20) -> pd.DataFrame:
    """
    Moving average cross strategy.

    Buy signal: short MA crosses above long MA.
    Sell signal: short MA crosses below long MA.
    """
    out = df.copy()
    out[f"ma{short_window}"] = out["close"].rolling(short_window).mean()
    out[f"ma{long_window}"] = out["close"].rolling(long_window).mean()

    out["signal"] = 0
    prev_short = out[f"ma{short_window}"].shift(1)
    prev_long = out[f"ma{long_window}"].shift(1)

    cross_up = (prev_short <= prev_long) & (out[f"ma{short_window}"] > out[f"ma{long_window}"])
    cross_down = (prev_short >= prev_long) & (out[f"ma{short_window}"] < out[f"ma{long_window}"])

    out.loc[cross_up, "signal"] = 1
    out.loc[cross_down, "signal"] = -1
    return out


class MACrossStrategy:
    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window
        self.name = f"MA_{short_window}_{long_window}"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        return generate_signals(df, self.short_window, self.long_window)
