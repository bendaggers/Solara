"""
tests/conftest.py — Shared Test Fixtures
==========================================
Provides common fixtures for all test domains.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock


@pytest.fixture
def sample_raw_df():
    """Minimal valid raw DataFrame as would come from MT5 EA CSV."""
    n = 50  # enough for all lookback requirements
    base_time = datetime(2026, 1, 1, 0, 0, 0)
    return pd.DataFrame({
        "timestamp":   [base_time + timedelta(hours=i) for i in range(n)],
        "symbol":      ["EURUSD"] * n,
        "open":        np.linspace(1.0800, 1.0900, n),
        "high":        np.linspace(1.0820, 1.0920, n),
        "low":         np.linspace(1.0780, 1.0880, n),
        "close":       np.linspace(1.0810, 1.0910, n),
        "tick_volume": [100] * n,
        "spread":      [2] * n,
        "price":       np.linspace(1.0811, 1.0911, n),
    })


@pytest.fixture
def multi_symbol_raw_df(sample_raw_df):
    """Raw DataFrame with two symbols."""
    df2 = sample_raw_df.copy()
    df2["symbol"] = "GBPUSD"
    df2["open"] += 0.2
    df2["high"] += 0.2
    df2["low"] += 0.2
    df2["close"] += 0.2
    df2["price"] += 0.2
    return pd.concat([sample_raw_df, df2], ignore_index=True)


@pytest.fixture
def featured_df(sample_raw_df):
    """Pre-computed feature DataFrame (1 row per symbol)."""
    from features.feature_engineer import FeatureEngineer
    fe = FeatureEngineer()
    return fe.compute(sample_raw_df, "H4")


@pytest.fixture
def mock_mt5():
    """Mock MT5Manager for tests that don't need a real MT5 connection."""
    mock = MagicMock()
    mock.get_account_info.return_value = MagicMock(
        equity=10000.0, balance=10000.0, margin_free=9000.0
    )
    mock.get_positions_by_magic.return_value = []
    mock.get_all_positions.return_value = []
    mock.get_margin_required.return_value = 100.0
    mock.place_order.return_value = (10009, 123456)  # success code + ticket
    mock.modify_position_sl_tp.return_value = True

    symbol_info = MagicMock()
    symbol_info.point = 0.00001
    symbol_info.digits = 5
    symbol_info.trade_tick_value = 1.0
    symbol_info.trade_tick_size = 0.00001
    symbol_info.volume_min = 0.01
    symbol_info.volume_max = 100.0
    mock.get_symbol_info.return_value = symbol_info

    return mock


@pytest.fixture
def mock_registry_entry():
    """A valid ModelRegistryEntry-like object for testing predictors."""
    entry = MagicMock()
    entry.name = "BB Reversal Long H4 v2"
    entry.magic = 201000
    entry.model_type = "LONG"
    entry.timeframe = "H4"
    entry.feature_version = "v3"
    entry.min_confidence = 0.65
    entry.weight = 1.0
    entry.comment = "SAQ_BBLong_H4"
    entry.symbols = []
    entry.max_positions = 3
    return entry
