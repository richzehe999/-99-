import pandas as pd
from .base_provider import BaseMarketDataProvider


class AkShareMarketDataProvider(BaseMarketDataProvider):
    """
    AkShare provider placeholder.

    Notes:
    - AkShare function names and returned columns may change by version.
    - Normalize all external data into the standard schema before using it downstream.
    """

    def get_daily_bars(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError as exc:
            raise ImportError("Please install akshare first: pip install akshare") from exc

        raw = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )

        rename_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "turnover",
        }

        df = raw.rename(columns=rename_map)
        required = ["date", "open", "high", "low", "close", "volume", "turnover"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"AkShare returned data missing columns: {missing}")

        df = df[required].copy()
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)

    def get_stock_universe(self) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError as exc:
            raise ImportError("Please install akshare first: pip install akshare") from exc

        raw = ak.stock_info_a_code_name()
        df = raw.rename(columns={"code": "symbol", "name": "name"})
        df["market"] = "A-share"
        return df
