"""
Feature Pipeline — inference only (SAQ vendored copy).
Provides compute_atr, TIMEFRAME_MINUTES, and encode_timeframe.
Full v1 feature pipeline removed (not used by SAQ).
"""

import numpy as np
import pandas as pd

TIMEFRAME_MINUTES = {
    'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
    'H1': 60, 'H4': 240, 'D1': 1440, 'W1': 10080, 'MN1': 43200,
}


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's ATR using RMA (alpha=1/period). Consistent with MT5 and TradingView."""
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low']  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean().rename('atr')


def encode_timeframe(timeframe: str, length: int) -> pd.Series:
    """Encode timeframe as log(minutes) scalar feature."""
    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(f"Unknown timeframe: {timeframe}")
    tf_value = np.log(TIMEFRAME_MINUTES[timeframe])
    return pd.Series(np.full(length, tf_value), name='tf_log_minutes')
