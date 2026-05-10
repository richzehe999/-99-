from pathlib import Path
import pandas as pd
from .base_provider import BaseMarketDataProvider


class CSVMarketDataProvider(BaseMarketDataProvider):
    """Read local CSV files for testing and offline backtests."""

    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)

    def get_daily_bars(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        path = self.data_dir / f"{symbol}.csv"
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        mask = (df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))
        return df.loc[mask].reset_index(drop=True)

    def get_stock_universe(self) -> pd.DataFrame:
        path = self.data_dir / "stock_universe.csv"
        if not path.exists():
            raise FileNotFoundError(f"Stock universe file not found: {path}")
        return pd.read_csv(path)
