import pandas as pd
import numpy as np


def add_moving_average(df: pd.DataFrame, windows=(5, 10, 20, 60)) -> pd.DataFrame:
    out = df.copy()
    for w in windows:
        out[f"ma{w}"] = out["close"].rolling(w).mean()
    return out


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    delta = out["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    out[f"rsi{period}"] = 100 - (100 / (1 + rs))
    return out


def add_returns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["return"] = out["close"].pct_change()
    return out
