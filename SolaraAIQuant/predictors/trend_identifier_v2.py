"""
Solara AI Quant - Trend Identifier V2 Predictor
================================================
Production predictor wrapping the V2 universal pooled ensemble model.

Model facts (version 20260402_230006 — overnight AutoML run):
  Algorithm   : LightGBM + XGBoost + CatBoost soft-voting ensemble
  Calibration : Platt scaling (LogisticRegression on raw probs)
  Training    : 28 forex pairs, H4, 2000-2025 (~950k bars per fold)
  Accuracy    : 92.59% balanced accuracy (5-fold purged walk-forward)
  Calibration : ECE = 1.53% (excellent — probabilities are trustworthy)
  Classes     : -1 = Downtrend, 0 = Sideways, 1 = Uptrend
  Features    : 41 (QUANT_V2_CORE)
  Signal stab.: 39.5% raw → hysteresis raises to 85%+ at inference

Signal Logic:
  Probabilities from the calibrated ensemble: (p_down, p_side, p_up)
  - p_up   >= threshold → LONG  signal (trend upward)
  - p_down >= threshold → SHORT signal (trend downward)
  - Otherwise           → No signal    (sideways or uncertain)

Registry usage:
  Two entries in model_registry.yaml share the SAME model file:
    "TI V2 Long"  (model_type: LONG)  → emits LONG  signals only
    "TI V2 Short" (model_type: SHORT) → emits SHORT signals only
  This lets SAQ's conflict checker handle LONG/SHORT independently.

Threshold guidance (paper trading starting point):
  0.55 — captures most trend signals, higher false-positive rate
  0.60 — balanced precision/recall (recommended start)
  0.70 — high precision, fewer signals
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── joblib for loading V2 ensemble (saved with joblib.dump) ──────────────────
try:
    import joblib as _joblib
    _JOBLIB_AVAILABLE = True
except ImportError:
    _JOBLIB_AVAILABLE = False
    logger.error(
        "[TrendIDV2] joblib not installed. "
        "Run: pip install joblib  (it ships with scikit-learn)"
    )

from .base_predictor import BasePredictor, PredictionSignal


# ── 41 QUANT_V2_CORE features (must match training order exactly) ─────────────
_V2_FEATURES: list[str] = [
    # ADX system (2)
    'adx_14', 'di_spread_14',
    # EMA alignment (7)
    'price_vs_ema_8', 'price_vs_ema_21', 'price_vs_ema_50',
    'ema_8_vs_21', 'ema_21_vs_50',
    'ema_slope_8', 'ema_slope_21',
    # Momentum (6)
    'rsi_7', 'rsi_14',
    'stoch_k_14', 'stoch_kd_cross',
    'cci_14', 'roc_10',
    # MACD (2)
    'macd_hist', 'macd_hist_slope',
    # Volatility (6)
    'atr_pct', 'vol_regime_pct', 'bb_width_20', 'bb_position',
    'realized_vol_20', 'vol_expansion',
    # Price structure (9)
    'log_return_1', 'log_return_3', 'log_return_5', 'log_return_10', 'log_return_20',
    'close_location', 'range_position_20', 'regression_slope_20', 'open_gap_pct',
    # Market structure (4)
    'efficiency_ratio_10', 'efficiency_ratio_20', 'choppiness_14', 'aroon_osc_25',
    # Volume (1)
    'vol_ratio_20',
    # Encoding (4)
    'tf_log_minutes', 'pair_encoded', 'base_ccy_encoded', 'quote_ccy_encoded',
]

# Calibrated probability array indices: probs shape = (1, 3)
_IDX_DOWN = 0   # p(downtrend)
_IDX_SIDE = 1   # p(sideways)
_IDX_UP   = 2   # p(uptrend)

# Fallback TP/SL for trend following on H4 (2:1 R:R)
_DEFAULT_TP_PIPS = 80
_DEFAULT_SL_PIPS = 40

# Default signal threshold (override via min_confidence in model_registry.yaml)
_DEFAULT_THRESHOLD = 0.55


class TrendIdentifierV2Predictor(BasePredictor):
    """
    Trend Identifier V2 — Universal 28-pair H4 trend classifier.

    Wraps a TrendModelCalibrator object (Platt-scaled ensemble).
    The calibrator exposes predict_proba(X) returning (n, 3) probabilities
    ordered [p_downtrend, p_sideways, p_uptrend].

    Emits signals based on self.config.model_type:
      LONG  entry → model_type = "LONG"  (uses p_uptrend)
      SHORT entry → model_type = "SHORT" (uses p_downtrend)
    """

    # ── Model loading ─────────────────────────────────────────────────────────

    def load_model(self, model_path: Path):
        """
        Override BasePredictor.load_model() to use joblib.

        V2 models are saved with joblib.dump() as a dict artifact:
          {
            'model':         TrendModelCalibrator  ← the callable predictor
            'feature_cols':  list[str]             ← 41 QUANT_V2_CORE names
            'pair_map':      dict[str, int]        ← pair → encoding index
            ...              (training metadata)
          }

        We extract the TrendModelCalibrator and attach the pair_map so the
        predictor can verify encodings at runtime.
        """
        if not _JOBLIB_AVAILABLE:
            raise ImportError(
                "joblib is required to load V2 models. "
                "Install with: pip install joblib"
            )

        # Ensure forex_trend_model is importable before joblib deserializes it.
        # The FE adds vendor/ to sys.path at import time, but the predictor may
        # load in a parallel thread before the FE module is imported.
        import sys
        from pathlib import Path as _Path
        _vendor_dir = str(_Path(__file__).resolve().parent.parent / 'vendor')
        if _vendor_dir not in sys.path:
            sys.path.insert(0, _vendor_dir)

        artifact = _joblib.load(model_path)

        # Artifact is a dict — extract the calibrated ensemble
        if isinstance(artifact, dict):
            calibrator = artifact.get('model')
            if calibrator is None:
                raise ValueError(
                    f"Model artifact at {model_path} has no 'model' key. "
                    f"Keys found: {list(artifact.keys())}"
                )
            # Attach pair_map so the predictor can log it
            self._pair_map = artifact.get('pair_map', {})
            self._artifact_feature_cols = artifact.get('feature_cols', [])
            logger.info(
                f"[TrendIDV2] Loaded calibrated ensemble from {model_path.name} "
                f"(type: {type(calibrator).__name__}, "
                f"pairs: {len(self._pair_map)}, "
                f"features: {len(self._artifact_feature_cols)})"
            )
            return calibrator
        else:
            # Fallback: artifact is already the calibrator
            logger.info(
                f"[TrendIDV2] Loaded model directly from {model_path.name} "
                f"(type: {type(artifact).__name__})"
            )
            return artifact

    # ── Feature declaration ───────────────────────────────────────────────────

    def get_required_features(self) -> List[str]:
        """Return the 41 QUANT_V2_CORE feature names."""
        return _V2_FEATURES.copy()

    # ── Main prediction entry point ───────────────────────────────────────────

    def predict(
        self,
        df_features: pd.DataFrame,
        config,
    ) -> List[Dict]:
        """
        Generate trend signals from V2-engineered features.

        Args:
            df_features : Output of TrendIDV2FeatureEngineer.compute().
                          One row per symbol, with all 41 V2 features.
            config      : ModelRegistryEntry — provides name, magic, comment,
                          model_type, and (if present) min_confidence,
                          tp_pips, sl_pips.

        Returns:
            List of signal dicts compatible with SAQ signal aggregator.
            Empty list when no symbols pass the probability threshold.
        """
        predictions: List[Dict] = []

        # Guard: model must be loaded
        if not self.model_loaded or self.model is None:
            logger.error(f"[TrendIDV2] Model not loaded for '{config.name}'")
            return predictions

        # Filter to allowed symbols (config.symbols = [] means all)
        df = self.filter_by_symbols(df_features)
        if df.empty:
            logger.debug(f"[TrendIDV2] No rows after symbol filtering for '{config.name}'")
            return predictions

        # Validate all 41 features are present
        if not self.validate_features(df, _V2_FEATURES):
            return predictions

        # Determine which direction this registry entry handles
        model_type = getattr(config, 'model_type', 'LONG')
        if hasattr(model_type, 'value'):
            model_type = model_type.value   # handle enum
        emit_long  = model_type == 'LONG'
        emit_short = model_type == 'SHORT'

        # Threshold: use config.min_confidence if set, else default
        threshold = float(
            getattr(config, 'min_confidence', _DEFAULT_THRESHOLD) or _DEFAULT_THRESHOLD
        )

        for _, row in df.iterrows():
            try:
                signal = self._predict_row(
                    row, config,
                    emit_long=emit_long,
                    emit_short=emit_short,
                    threshold=threshold,
                )
                if signal is not None:
                    predictions.append(signal.to_dict())
            except Exception as exc:
                symbol = row.get('symbol', 'unknown')
                logger.error(
                    f"[TrendIDV2] Error predicting for {symbol}: {exc}",
                    exc_info=True,
                )

        if predictions:
            logger.info(
                f"[TrendIDV2] '{config.name}': {len(predictions)} signal(s) generated"
            )

        return predictions

    # ── Per-symbol prediction ─────────────────────────────────────────────────

    def _predict_row(
        self,
        row: pd.Series,
        config,
        emit_long: bool,
        emit_short: bool,
        threshold: float,
    ) -> Optional[PredictionSignal]:
        """
        Generate a prediction signal for a single symbol row.

        Returns a PredictionSignal if the probability exceeds the threshold
        and the direction matches this predictor's model_type.
        Returns None if no signal should be emitted.
        """
        symbol = str(row.get('symbol', 'UNKNOWN'))

        # Build single-row DataFrame with correct dtypes for CatBoost cat features
        X = self._prepare_features(row)
        if X is None:
            logger.warning(f"[TrendIDV2] {symbol}: could not prepare features")
            return None

        # Get calibrated probabilities — shape (1, 3): [p_down, p_side, p_up]
        # TrendModelCalibrator.predict_proba() expects a pd.DataFrame
        try:
            probs = self.model.predict_proba(X)
        except Exception as exc:
            logger.error(
                f"[TrendIDV2] model.predict_proba failed for {symbol}: {exc}"
            )
            return None

        p_down = float(probs[0, _IDX_DOWN])
        p_side = float(probs[0, _IDX_SIDE])
        p_up   = float(probs[0, _IDX_UP])

        # Apply threshold and direction filter
        if emit_long and p_up >= threshold:
            direction  = 'LONG'
            confidence = p_up
        elif emit_short and p_down >= threshold:
            direction  = 'SHORT'
            confidence = p_down
        else:
            logger.debug(
                f"[TrendIDV2] {symbol}: no signal "
                f"(p_up={p_up:.3f}, p_dn={p_down:.3f}, threshold={threshold:.3f})"
            )
            return None

        # Entry price (latest close from feature engineer passthrough)
        entry_price = float(row.get('close', 0.0))

        # TP / SL — prefer values from registry config, fallback to defaults
        tp_pips = int(getattr(config, 'tp_pips', _DEFAULT_TP_PIPS) or _DEFAULT_TP_PIPS)
        sl_pips = int(getattr(config, 'sl_pips', _DEFAULT_SL_PIPS) or _DEFAULT_SL_PIPS)

        # Key features for logging and SAQ signal database
        key_features = {
            'p_uptrend':     round(p_up,   4),
            'p_downtrend':   round(p_down, 4),
            'p_sideways':    round(p_side, 4),
            'adx_14':        round(float(row.get('adx_14',      0.0)), 4),
            'rsi_14':        round(float(row.get('rsi_14',       0.0)), 2),
            'ema_8_vs_21':   round(float(row.get('ema_8_vs_21',  0.0)), 4),
            'di_spread_14':  round(float(row.get('di_spread_14', 0.0)), 4),
        }

        signal = PredictionSignal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            tp_pips=tp_pips,
            sl_pips=sl_pips,
            model_name=config.name,
            magic=config.magic,
            comment=config.comment,
            features=key_features,
        )

        logger.info(
            f"[TrendIDV2] SIGNAL: {symbol} {direction} @ {entry_price:.5f} | "
            f"conf={confidence:.3f} (p_up={p_up:.3f} p_dn={p_down:.3f} "
            f"p_side={p_side:.3f}) | "
            f"ADX={key_features['adx_14']:.3f} RSI={key_features['rsi_14']:.1f} "
            f"EMA8vs21={key_features['ema_8_vs_21']:.4f}"
        )

        return signal

    # ── Feature preparation ───────────────────────────────────────────────────

    # Encoding columns that CatBoost treats as categorical (must be int, not float)
    _CAT_FEATURES = {'pair_encoded', 'base_ccy_encoded', 'quote_ccy_encoded'}

    def _prepare_features(self, row: pd.Series) -> Optional[pd.DataFrame]:
        """
        Build a single-row DataFrame from a feature row for model inference.

        IMPORTANT: The V2 ensemble uses CatBoost which requires categorical
        features (pair_encoded, base_ccy_encoded, quote_ccy_encoded) to be
        integer dtype — NOT float. This method enforces correct dtypes so that
        CatBoost does not raise a 'cat_features must be integer or string' error.

        Missing or invalid float values are filled with 0.0.
        Missing or invalid cat values are filled with -1 (unknown encoding).
        """
        record = {}
        for feat in _V2_FEATURES:
            val = row.get(feat, None)
            if feat in self._CAT_FEATURES:
                # Cat feature: must be int (CatBoost requirement)
                try:
                    v = int(val) if val is not None and not pd.isna(val) else -1
                except (TypeError, ValueError):
                    v = -1
                record[feat] = v
            else:
                # Continuous feature: float, NaN/Inf → 0.0
                try:
                    v = float(val)
                    if pd.isna(v) or np.isinf(v):
                        v = 0.0
                except (TypeError, ValueError):
                    v = 0.0
                record[feat] = v

        df = pd.DataFrame([record])

        # Ensure correct dtypes on cat columns
        for cat_col in self._CAT_FEATURES:
            if cat_col in df.columns:
                df[cat_col] = df[cat_col].astype(int)

        return df

    # ── Metadata ──────────────────────────────────────────────────────────────

    def get_metadata(self) -> Dict:
        """Extended metadata for logging and health checks."""
        base = super().get_metadata()
        base.update({
            'strategy':          'V2 Universal Trend Identification (28 pairs)',
            'n_features':        len(_V2_FEATURES),
            'pairs_trained':     28,
            'balanced_accuracy': 0.9259,
            'calibration_ece':   0.0153,
            'model_version':     '20260402_230006',
            'ensemble':          'LightGBM + XGBoost + CatBoost + Platt scaling',
            'timeframe':         'H4',
        })
        return base
