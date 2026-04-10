"""
Solara AI Quant — Punk Hazard Feature Engineer
===============================================

Computes the full Punk Hazard H4 Reversal Model feature set from raw OHLCV
data + CSV indicator columns.  Called by the SAQ pipeline before each
PunkHazardLongPredictor / PunkHazardShortPredictor inference call.

Design
------
Punk Hazard was trained on a specific feature set derived from:
  (a) Pre-calculated indicators in the Punk Hazard CSV (RSI, BB, ATR, etc.)
  (b) Supplementary features computed from OHLCV (SMA distances, Stochastic,
      MACD, regime columns, lag features, etc.)

In SAQ, the OHLCV + indicator columns arrive via the ingestion pipeline.
This class replicates the exact feature engineering from the research
codebase (Punk Hazard/features.py and regime.py) so that inference uses the
same distributions the model was trained on.

Required input columns
----------------------
Direction-neutral (both long and short):
    rsi_value, bb_position, bb_width_pct, atr_pct, candle_body_pct,
    trend_strength, volume_ratio, prev_candle_body_pct, prev_volume_ratio,
    gap_from_prev_close

Long-specific (only needed by PunkHazardLongPredictor):
    bb_touch_strength_long, candle_rejection_long, price_momentum_long,
    previous_touches_long, time_since_last_touch_long, support_distance_pct

Short-specific (only needed by PunkHazardShortPredictor):
    bb_touch_strength, candle_rejection, rsi_divergence, price_momentum,
    prev_was_rally, previous_touches, time_since_last_touch,
    resistance_distance_pct

OHLCV (always required):
    open, high, low, close, volume  (or tick_volume)

Output
------
Returns a DataFrame with the same index as the input, with all 43 Punk
Hazard features + 2 regime columns added as new columns.  The predictor
then extracts its REQUIRED_FEATURES slice.
"""

import warnings
from typing import Optional

import numpy as np
import pandas as pd


# ── Configuration (mirrors Punk Hazard CONFIG exactly) ───────────────────────

ATR_PERIOD              = 14
ATR_PERCENTILE_WINDOW   = 100      # rolling window for volatility regime
VOL_SPLIT_PERCENTILE    = 50.0     # < 50th pct = Low Vol
SMA_PERIOD              = 50       # for trend regime
TREND_SLOPE_THRESHOLD   = 0.10     # ±0.10 normalised slope
PIP_VALUE               = 0.0001   # 1 pip for 5-decimal forex
WARMUP_BARS             = 300      # first N bars are NaN-heavy; skip in production


# ── Indicator helpers (identical to Punk Hazard research code) ────────────────

def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    """EWM Average True Range."""
    high       = df['high']
    low        = df['low']
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _stochastic_k(df: pd.DataFrame, period: int = 14) -> pd.Series:
    low_min  = df['low'].rolling(period).min()
    high_max = df['high'].rolling(period).max()
    denom    = (high_max - low_min).replace(0, np.nan)
    return 100.0 * (df['close'] - low_min) / denom


def _macd_hist_norm(close: pd.Series, atr: pd.Series,
                    fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    macd_line   = _ema(close, fast) - _ema(close, slow)
    signal_line = _ema(macd_line, signal)
    hist        = macd_line - signal_line
    return hist / atr.replace(0, np.nan)


def _rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    """Rolling percentile rank (0–100) — value of current bar within the window."""
    def _pct(x):
        return (x[:-1] < x[-1]).mean() * 100.0 if len(x) > 1 else np.nan
    return series.rolling(window).apply(_pct, raw=True)


# ── Regime computation (mirrors regime.py exactly) ────────────────────────────

def _compute_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute regime_volatility (0=Low, 1=High) and regime_trend (-1/0/+1).

    Uses rolling past data only — no look-ahead.
    Exact copy of Punk Hazard regime.py:compute().
    """
    atr = _atr(df, ATR_PERIOD)

    # Volatility: ATR percentile rank in rolling 100-bar window
    atr_pct = (
        atr
        .rolling(ATR_PERCENTILE_WINDOW)
        .apply(lambda w: pd.Series(w).rank(pct=True).iloc[-1], raw=False)
    )
    regime_vol = (atr_pct >= VOL_SPLIT_PERCENTILE / 100.0).astype(int)

    # Trend: normalised SMA50 slope
    sma       = _sma(df['close'], SMA_PERIOD)
    sma_slope = sma.diff(1)
    norm_slope = sma_slope / atr.replace(0, np.nan)

    regime_trend = pd.Series(0, index=df.index, dtype=int)
    regime_trend[norm_slope >  TREND_SLOPE_THRESHOLD] =  1
    regime_trend[norm_slope < -TREND_SLOPE_THRESHOLD] = -1

    return pd.DataFrame({
        'regime_volatility': regime_vol,
        'regime_trend':      regime_trend,
    }, index=df.index)


# ── Main feature engineer class ───────────────────────────────────────────────

class PunkHazardFeatureEngineer:
    """
    Computes the full Punk Hazard feature set for SAQ inference.

    Usage (called by the SAQ pipeline internally):
        engineer = PunkHazardFeatureEngineer(direction='long')
        df_out = engineer.transform(df_ohlcv_with_indicators)

    The output DataFrame has all original columns PLUS the 43 Punk Hazard
    features and 2 regime columns appended.  Missing CSV indicator columns
    are filled with 0 and logged as warnings — this is safe for columns that
    are irrelevant to the requested direction.
    """

    # Direction-neutral CSV columns (both long and short)
    _CSV_NEUTRAL = [
        'rsi_value',
        'bb_position',
        'bb_width_pct',
        'atr_pct',
        'candle_body_pct',
        'trend_strength',
        'volume_ratio',
        'prev_candle_body_pct',
        'prev_volume_ratio',
        'gap_from_prev_close',
    ]

    # Long-specific CSV columns
    _CSV_LONG = [
        'bb_touch_strength_long',
        'candle_rejection_long',
        'price_momentum_long',
        'previous_touches_long',
        'time_since_last_touch_long',
        'support_distance_pct',
    ]

    # Short-specific CSV columns
    _CSV_SHORT = [
        'bb_touch_strength',
        'candle_rejection',
        'rsi_divergence',
        'price_momentum',
        'prev_was_rally',
        'previous_touches',
        'time_since_last_touch',
        'resistance_distance_pct',
    ]

    # Lag spec (5 stability-validated lags, same as research code)
    _LAG_SPEC = [
        ('trend_strength',   [1]),
        ('bb_width_pct',     [3]),
        ('atr_pct',          [3]),
        ('atr_ratio',        [2]),
        ('bb_width_zscore',  [2]),
    ]

    def __init__(self, direction: str = 'long'):
        """
        Args:
            direction: 'long' or 'short' — selects direction-specific features.
        """
        if direction not in ('long', 'short'):
            raise ValueError(f"direction must be 'long' or 'short', got '{direction}'")
        self.direction = direction

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Punk Hazard features from the raw OHLCV + indicator DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Full historical OHLCV + CSV indicator data for a single symbol.
            Must have a DatetimeIndex sorted ascending.
            Must contain: open, high, low, close, volume (or tick_volume).

        Returns
        -------
        pd.DataFrame
            Original df columns PLUS all Punk Hazard feature columns.
            Last row contains the most recent bar (latest signal).
        """
        import logging
        log = logging.getLogger(__name__)

        if len(df) < WARMUP_BARS:
            log.warning(
                f"PunkHazardFeatureEngineer: only {len(df)} bars provided; "
                f"recommend ≥ {WARMUP_BARS} for indicator convergence."
            )

        df = df.copy()

        # Normalise volume column name
        if 'tick_volume' in df.columns and 'volume' not in df.columns:
            df['volume'] = df['tick_volume']

        # ── direction-specific CSV columns ────────────────────────────────────
        dir_cols = self._CSV_LONG if self.direction == 'long' else self._CSV_SHORT
        expected = self._CSV_NEUTRAL + dir_cols
        for col in expected:
            if col not in df.columns:
                log.warning(f"[PunkHazard] Missing CSV column '{col}' — filling with 0")
                df[col] = 0.0

        # Start feature DataFrame with CSV columns
        X = df[self._CSV_NEUTRAL].copy().astype(float)
        for col in dir_cols:
            X[col] = df[col].astype(float)

        # ── supplementary computed features ──────────────────────────────────
        close  = df['close']
        atr14  = _atr(df, ATR_PERIOD).replace(0, np.nan)
        atr50  = _atr(df, 50).replace(0, np.nan)
        sma50  = _sma(close, 50)
        sma100 = _sma(close, 100)
        sma200 = _sma(close, 200)

        X['dist_sma50']  = (close - sma50)  / atr14
        X['dist_sma100'] = (close - sma100) / atr14
        X['dist_sma200'] = (close - sma200) / atr14
        X['atr_ratio']   = atr14 / atr50
        X['stoch_k']     = _stochastic_k(df)
        X['macd_hist']   = _macd_hist_norm(close, atr14)

        # Distance from 20-period extreme (low for long, high for short)
        if self.direction == 'long':
            extreme = df['low'].rolling(20).min()
            X['dist_extreme'] = (close - extreme) / atr14
        else:
            extreme = df['high'].rolling(20).max()
            X['dist_extreme'] = (extreme - close) / atr14

        # Candle structure
        candle_range = (df['high'] - df['low']).replace(0, np.nan)
        X['body_position']   = ((close - df['low']) / candle_range).clip(0, 1)
        lower_wick           = np.minimum(df['open'], close) - df['low']
        X['lower_wick_ratio'] = (lower_wick / candle_range).clip(0, 1)
        upper_wick           = df['high'] - np.maximum(df['open'], close)
        X['upper_wick_ratio'] = (upper_wick / candle_range).clip(0, 1)

        # RSI momentum
        rsi = df['rsi_value'].astype(float)
        X['rsi_slope_5']  = rsi - rsi.shift(5)
        X['rsi_slope_10'] = rsi - rsi.shift(10)

        # BB width Z-score
        bw_mean = df['bb_width_pct'].rolling(50).mean()
        bw_std  = df['bb_width_pct'].rolling(50).std().replace(0, np.nan)
        X['bb_width_zscore'] = (df['bb_width_pct'] - bw_mean) / bw_std

        # Distance from 52-week (252-bar) low
        low_252 = df['low'].rolling(252).min()
        X['dist_52w_low'] = (close - low_252) / atr14

        # ATR percentile (rolling 100-bar)
        X['atr_percentile'] = _rolling_percentile(atr14, ATR_PERCENTILE_WINDOW)

        # ATR long-term Z-score (era-level ATR context, 1300-bar window ≈ 1yr H4)
        _atr_pct_raw    = atr14 / close
        _atr_roll_mean  = _atr_pct_raw.rolling(1300, min_periods=200).mean()
        _atr_roll_std   = _atr_pct_raw.rolling(1300, min_periods=200).std()
        X['atr_longterm_zscore'] = (
            (_atr_pct_raw - _atr_roll_mean) / _atr_roll_std.clip(lower=1e-8)
        )

        # Price acceleration (second derivative)
        roc1 = close.diff(1)
        X['price_accel'] = roc1.diff(1) / atr14

        # Volume divergence (volume rising while price falling)
        # Uses volume_ratio directly — exact match to research features.py:
        #   vol_slope = df['volume_ratio'] - df['volume_ratio'].shift(5)
        # volume_ratio is already in _CSV_NEUTRAL (filled with 0 if missing).
        vol_ratio  = df['volume_ratio'].astype(float)
        vol_slope  = vol_ratio - vol_ratio.shift(5)
        price_move = close - close.shift(5)
        X['vol_divergence'] = vol_slope * np.sign(-price_move)

        # ── lag features ──────────────────────────────────────────────────────
        for col, lags in self._LAG_SPEC:
            if col in X.columns:
                for lag in lags:
                    X[f'{col}_lag{lag}'] = X[col].shift(lag)

        # ── regime features ───────────────────────────────────────────────────
        regime_df = _compute_regime(df)
        X['regime_volatility'] = regime_df['regime_volatility']
        X['regime_trend']      = regime_df['regime_trend']

        # ── merge back into original df ───────────────────────────────────────
        # Keep original columns; add new feature columns
        for col in X.columns:
            df[col] = X[col]

        return df

    def get_feature_names(self) -> list:
        """
        Return the ordered list of feature names (excluding regime columns).
        Matches the order used during training in the research codebase.
        """
        dir_cols = self._CSV_LONG if self.direction == 'long' else self._CSV_SHORT
        base = self._CSV_NEUTRAL + dir_cols + [
            'dist_sma50', 'dist_sma100', 'dist_sma200',
            'atr_ratio', 'stoch_k', 'macd_hist', 'dist_extreme',
            'body_position', 'lower_wick_ratio', 'upper_wick_ratio',
            'rsi_slope_5', 'rsi_slope_10', 'bb_width_zscore',
            'dist_52w_low', 'atr_percentile', 'atr_longterm_zscore',
            'price_accel', 'vol_divergence',
            # lags
            'trend_strength_lag1', 'bb_width_pct_lag3', 'atr_pct_lag3',
            'atr_ratio_lag2', 'bb_width_zscore_lag2',
            # regime
            'regime_volatility', 'regime_trend',
        ]
        return base
