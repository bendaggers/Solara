"""
ingestion/csv_adapter.py — MT5 CSV Adapter
============================================
Reads the CSV file exported by the MT5 Expert Advisor for a given timeframe.
"""
import pandas as pd
from pathlib import Path
from ingestion.base_adapter import BaseAdapter
import config


class CSVAdapter(BaseAdapter):
    """Reads MT5-exported CSV files from MQL5/Files/ directory."""

    REQUIRED_COLUMNS = [
        "timestamp", "symbol", "open", "high", "low",
        "close", "tick_volume", "spread", "price",
    ]

    def read(self, timeframe: str) -> pd.DataFrame:
        """
        Read raw CSV for the given timeframe.

        Returns:
            Raw multi-bar DataFrame (multiple rows per symbol).

        Raises:
            FileNotFoundError: If CSV file does not exist.
            ValueError: If file is empty or cannot be parsed.
        """
        path: Path = config.WATCHED_FILES[timeframe]

        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")

        df = pd.read_csv(path, parse_dates=["timestamp"])

        if df.empty:
            raise ValueError(f"CSV is empty: {path}")

        return df
