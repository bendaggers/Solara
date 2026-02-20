"""
ingestion/data_validator.py — Data Validation
===============================================
Validates the raw DataFrame from the CSV adapter before feature engineering.
All rules defined in FS Section 5.2.
"""
import pandas as pd
import structlog

log = structlog.get_logger(__name__)

REQUIRED_COLUMNS = [
    "timestamp", "symbol", "open", "high", "low",
    "close", "tick_volume", "spread", "price",
]
MIN_LOOKBACK_BARS = 30


class DataValidationError(Exception):
    """Raised when data fails validation and the cycle must be aborted."""
    pass


class DataValidator:
    """Validates raw MT5 CSV data before feature engineering."""

    def validate(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Run all validation rules. Returns cleaned DataFrame sorted by
        timestamp ascending, with bad rows dropped.

        Raises:
            DataValidationError: On fatal validation failure (cycle must abort).
        """
        # RULE 1 — Not empty
        if df.empty:
            raise DataValidationError(f"[{timeframe}] DataFrame is empty")

        # RULE 2 — Required columns present
        missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            raise DataValidationError(
                f"[{timeframe}] Missing required columns: {missing_cols}"
            )

        # RULE 3 — No nulls in OHLC + symbol
        critical_cols = ["open", "high", "low", "close", "symbol"]
        null_counts = df[critical_cols].isnull().sum()
        if null_counts.any():
            raise DataValidationError(
                f"[{timeframe}] Null values in critical columns: "
                f"{null_counts[null_counts > 0].to_dict()}"
            )

        # RULE 4 — high >= low (drop violating rows)
        bad_rows = df["high"] < df["low"]
        if bad_rows.any():
            log.warning(
                "dropped_invalid_ohlc_rows",
                timeframe=timeframe,
                count=int(bad_rows.sum()),
            )
            df = df[~bad_rows].copy()

        # RULE 5 — Timestamp parseable (already done in CSVAdapter parse_dates)
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            raise DataValidationError(
                f"[{timeframe}] timestamp column is not datetime"
            )

        # RULE 6 — Minimum lookback bars per symbol
        df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
        symbol_counts = df.groupby("symbol").size()
        excluded = symbol_counts[symbol_counts < MIN_LOOKBACK_BARS].index.tolist()
        if excluded:
            log.warning(
                "symbols_excluded_insufficient_bars",
                timeframe=timeframe,
                symbols=excluded,
                required=MIN_LOOKBACK_BARS,
            )
            df = df[~df["symbol"].isin(excluded)].copy()

        if df.empty:
            raise DataValidationError(
                f"[{timeframe}] No symbols with sufficient lookback bars "
                f"(need >= {MIN_LOOKBACK_BARS} bars per symbol)"
            )

        return df
