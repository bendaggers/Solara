"""
Solara AI Quant - Trend Identifier V2 Feature Engineer
=======================================================
Computes the 41 QUANT_V2_CORE features required by the TrendIdentifier V2
ensemble model (LightGBM + XGBoost + CatBoost, Platt-scaled).

Called by SAQ's execution engine in Stage 4, BEFORE the predictor runs.
Receives the full OHLCV history from the MT5 CSV, applies rolling windows,
and returns ONE row per symbol (the latest valid bar).

Model facts (20260402_230006):
  - 28 forex pairs trained, H4 timeframe
  - 92.59% balanced accuracy, ECE = 1.53%
  - Features: QUANT_V2_CORE (41 features)
"""

import sys
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Trend Identifier package (bundled in vendor/) ────────────────────────────
_SAQ_ROOT   = Path(__file__).resolve().parent.parent
_VENDOR_DIR = _SAQ_ROOT / 'vendor'
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

try:
    from forex_trend_model.features.quant_v2 import (
        compute_quant_v2_features,
        get_quant_v2_feature_names,
    )
    from forex_trend_model.features.pipeline import compute_atr
    _TREND_ID_AVAILABLE = True
    logger.info("[TrendIDV2Features] Trend Identifier package imported successfully")
except ImportError as _e:
    _TREND_ID_AVAILABLE = False
    logger.critical(
        f"[TrendIDV2Features] Cannot import forex_trend_model: {_e}. "
        f"Copy the forex_trend_model/ package into {_VENDOR_DIR}/"
    )

# ── Pair encoding: MUST match the training order (alphabetical, 0-indexed) ───
# Source: results_V2_POOLED_H4_20260402_230006.json → pairs_trained list
_PAIR_ENCODING: dict[str, int] = {
    'AUDCAD':  0, 'AUDCHF':  1, 'AUDJPY':  2, 'AUDNZD':  3,
    'AUDUSD':  4, 'CADCHF':  5, 'CADJPY':  6, 'CHFJPY':  7,
    'EURAUD':  8, 'EURCAD':  9, 'EURCHF': 10, 'EURGBP': 11,
    'EURJPY': 12, 'EURNZD': 13, 'EURUSD': 14, 'GBPAUD': 15,
    'GBPCAD': 16, 'GBPCHF': 17, 'GBPJPY': 18, 'GBPNZD': 19,
    'GBPUSD': 20, 'NZDCAD': 21, 'NZDCHF': 22, 'NZDJPY': 23,
    'NZDUSD': 24, 'USDCAD': 25, 'USDCHF': 26, 'USDJPY': 27,
}

# ── Currency group encoding: MUST match train_v2.py CCY_GROUP ────────────────
_CCY_GROUP: dict[str, int] = {
    'USD': 0, 'EUR': 1, 'GBP': 2, 'JPY': 3,
    'AUD': 4, 'NZD': 5, 'CAD': 6, 'CHF': 7,
}

# EMA200 warmup + 50-bar buffer — below this the features are unreliable
_MIN_BARS = 250

# Timeframe for V2 feature computation (model was trained on H4)
_TIMEFRAME = 'H4'


class TrendIDV2FeatureEngineer:
    """
    Feature engineer for the Trend Identifier V2 ensemble model.

    Wraps compute_quant_v2_features() from the Trend Identifier project,
    adds pair/currency group encodings, and returns the latest valid bar
    per symbol as a single-row DataFrame suitable for predict().

    The execution engine must provide the full OHLCV history per symbol
    (at least 250 bars) so that rolling indicators can be computed correctly.
    """

    def safe_compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Wrapper matching the execution engine's expected interface.
        Calls compute() and returns None on any unhandled exception.
        """
        try:
            result = self.compute(df)
            return result if result is not None and not result.empty else None
        except Exception as exc:
            logger.error(f"[TrendIDV2Features] safe_compute failed: {exc}")
            return None

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute V2 features for all symbols in the input DataFrame.

        Args:
            df: Full OHLCV history with columns:
                  timestamp, symbol, open, high, low, close, volume
                One symbol can span many rows (the full bar history).

        Returns:
            DataFrame with ONE row per symbol (latest valid bar),
            containing all 41 QUANT_V2_CORE features plus 'symbol',
            'close', and 'timestamp' columns needed downstream.
            Returns an empty DataFrame if feature computation fails.
        """
        if not _TREND_ID_AVAILABLE:
            logger.error(
                "[TrendIDV2Features] Trend Identifier package not available — "
                "cannot compute V2 features."
            )
            return pd.DataFrame()

        if df is None or df.empty:
            logger.warning("[TrendIDV2Features] Input DataFrame is empty")
            return pd.DataFrame()

        symbols = df['symbol'].unique() if 'symbol' in df.columns else [None]
        results = []

        for symbol in symbols:
            try:
                row = self._compute_for_symbol(df, symbol)
                if row is not None:
                    results.append(row)
            except Exception as exc:
                logger.error(
                    f"[TrendIDV2Features] Feature computation failed for "
                    f"{symbol}: {exc}",
                    exc_info=True,
                )

        if not results:
            logger.warning(
                "[TrendIDV2Features] No valid feature rows produced for any symbol"
            )
            return pd.DataFrame()

        result_df = pd.DataFrame(results).reset_index(drop=True)
        logger.info(
            f"[TrendIDV2Features] Produced {len(result_df)} feature rows "
            f"for symbols: {list(result_df['symbol'])}"
        )
        return result_df

    def _compute_for_symbol(
        self,
        df: pd.DataFrame,
        symbol: str | None,
    ) -> pd.Series | None:
        """
        Compute V2 features for one symbol and return the latest valid bar.

        Returns None if there is insufficient history or all bars are invalid.
        """
        # ── Filter to this symbol's bars ──────────────────────────────────────
        if symbol is not None and 'symbol' in df.columns:
            sym_df = df[df['symbol'] == symbol].copy()
        else:
            sym_df = df.copy()

        # ── Sort ascending by time ─────────────────────────────────────────────
        time_col = 'timestamp' if 'timestamp' in sym_df.columns else None
        if time_col:
            sym_df = sym_df.sort_values(time_col).reset_index(drop=True)
        else:
            sym_df = sym_df.reset_index(drop=True)

        # ── Check minimum bar count ────────────────────────────────────────────
        if len(sym_df) < _MIN_BARS:
            logger.warning(
                f"[TrendIDV2Features] {symbol}: only {len(sym_df)} bars "
                f"(minimum {_MIN_BARS} required for reliable rolling features)"
            )
            return None

        # ── Normalise volume column name ───────────────────────────────────────
        # SAQ uses 'volume'; V2 feature computation uses 'tick_volume'
        if 'volume' in sym_df.columns and 'tick_volume' not in sym_df.columns:
            sym_df = sym_df.rename(columns={'volume': 'tick_volume'})

        # ── Compute Wilder ATR (period=14) ────────────────────────────────────
        atr = compute_atr(sym_df, period=14)

        # ── Compute all 41 QUANT_V2_CORE features ────────────────────────────
        feat_df = compute_quant_v2_features(
            df=sym_df,
            timeframe=_TIMEFRAME,
            atr=atr,
            feature_subset='core',
        )

        # ── Inject pair / currency group encodings ────────────────────────────
        # These are NOT computed by compute_quant_v2_features — they're added
        # by the training pipeline per-pair. We replicate the exact mapping here.
        pair_key = str(symbol).upper().replace('/', '') if symbol else ''
        feat_df['pair_encoded']      = _PAIR_ENCODING.get(pair_key, -1)
        feat_df['base_ccy_encoded']  = _CCY_GROUP.get(pair_key[:3], -1)
        feat_df['quote_ccy_encoded'] = _CCY_GROUP.get(pair_key[3:], -1)

        # ── Take the latest valid row ─────────────────────────────────────────
        valid_col = feat_df.get('feature_valid', pd.Series(True, index=feat_df.index))
        valid_rows = feat_df[valid_col]

        if valid_rows.empty:
            logger.warning(
                f"[TrendIDV2Features] {symbol}: zero valid rows after warmup exclusion"
            )
            return None

        last_row = valid_rows.iloc[-1].copy()

        # ── Attach passthrough columns needed by the predictor ────────────────
        last_row['symbol']    = symbol
        last_row['close']     = float(sym_df['close'].iloc[-1])
        if time_col:
            last_row['timestamp'] = sym_df[time_col].iloc[-1]

        return last_row

    # ── Interface methods (informational) ─────────────────────────────────────

    def get_required_input_columns(self) -> list[str]:
        """Columns that must exist in the input DataFrame."""
        return ['open', 'high', 'low', 'close', 'timestamp', 'symbol']

    def get_output_features(self) -> list[str]:
        """V2 feature columns that compute() guarantees to produce."""
        if _TREND_ID_AVAILABLE:
            return get_quant_v2_feature_names('core')
        return []
