import pandas as pd


def generate_signals(
    df: pd.DataFrame,
    volume_multiple: float = 1.5,
    momentum_days: int = 5,
    momentum_threshold: float = 0.08,
) -> pd.DataFrame:
    """
    Hot theme trend strategy.

    Buy signal:
    - 5-day return exceeds threshold
    - turnover is above moving average turnover by volume_multiple
    - close is above MA5 and MA10

    Sell signal:
    - close falls below MA5
    """
    out = df.copy()
    out["ma5"] = out["close"].rolling(5).mean()
    out["ma10"] = out["close"].rolling(10).mean()
    out["turnover_ma20"] = out["turnover"].rolling(20).mean()
    out["momentum"] = out["close"].pct_change(momentum_days)

    out["signal"] = 0

    buy = (
        (out["momentum"] > momentum_threshold)
        & (out["turnover"] > out["turnover_ma20"] * volume_multiple)
        & (out["close"] > out["ma5"])
        & (out["close"] > out["ma10"])
    )

    sell = out["close"] < out["ma5"]

    out.loc[buy, "signal"] = 1
    out.loc[sell, "signal"] = -1
    return out
