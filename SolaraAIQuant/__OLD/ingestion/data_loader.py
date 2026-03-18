"""
ingestion/data_loader.py — Data Loader
========================================
Orchestrates CSVAdapter + DataValidator.
Single entry point for the pipeline to get clean data.
"""
import pandas as pd
import structlog
from ingestion.csv_adapter import CSVAdapter
from ingestion.data_validator import DataValidator, DataValidationError

log = structlog.get_logger(__name__)


class DataLoader:
    """Loads and validates MT5 CSV data for a given timeframe."""

    def __init__(self) -> None:
        self._adapter = CSVAdapter()
        self._validator = DataValidator()

    def load(self, timeframe: str) -> pd.DataFrame:
        """
        Load and validate data for the given timeframe.

        Returns:
            Clean, sorted DataFrame ready for feature engineering.

        Raises:
            DataValidationError: If data is unfit for model execution.
            FileNotFoundError: If CSV file does not exist.
        """
        df_raw = self._adapter.read(timeframe)
        df_clean = self._validator.validate(df_raw, timeframe)
        log.info(
            "data_loaded",
            timeframe=timeframe,
            rows=len(df_clean),
            symbols=df_clean["symbol"].nunique(),
        )
        return df_clean
