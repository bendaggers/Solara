"""
ingestion/base_adapter.py — Abstract Base Adapter
===================================================
All data adapters must inherit from this class.
"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseAdapter(ABC):
    """Abstract interface for all market data sources."""

    @abstractmethod
    def read(self, timeframe: str) -> pd.DataFrame:
        """
        Read raw market data for a given timeframe.

        Args:
            timeframe: One of M5, M15, H1, H4

        Returns:
            Raw DataFrame with at minimum: timestamp, symbol, open, high, low, close,
            tick_volume, spread, price columns.

        Raises:
            FileNotFoundError: If the data source is unavailable.
            ValueError: If the data cannot be parsed.
        """
        ...
