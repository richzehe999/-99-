from abc import ABC, abstractmethod
import pandas as pd


class BaseMarketDataProvider(ABC):
    """Base class for market data providers."""

    @abstractmethod
    def get_daily_bars(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Return OHLCV daily bars.

        Required columns:
        date, open, high, low, close, volume, turnover
        """
        raise NotImplementedError

    @abstractmethod
    def get_stock_universe(self) -> pd.DataFrame:
        """
        Return stock universe.

        Suggested columns:
        symbol, name, market, industry, market_cap, free_float_market_cap
        """
        raise NotImplementedError
