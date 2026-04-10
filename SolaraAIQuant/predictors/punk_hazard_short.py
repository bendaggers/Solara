"""
Solara AI Quant — Punk Hazard Short Predictor
=============================================

EURUSD H4 mean-reversion SHORT model.  Fires when price touches the Bollinger
upper band in a supportive regime, and the calibrated LightGBM model assigns
P(win) ≥ 0.48.

Model Summary (Run 29 — deployment candidate)
---------------------------------------------
  Strategy   : H4 BB upper-band reversal, SHORT
  Instrument : EURUSD (trained exclusively on EURUSD H4)
  Walk-forward: 303 folds, 2000–2025, 6-month train / 1-month test
  EV (mean)  : +5.19 pips/trade (combined long+short system)
  Direction   : SHORT — temporally dominant in 2010–2025 eras
  Calibration : sigmoid (ECE = 0.179)
  2020–2025   : +3.97 pips combined (short was positive: +0.6p in Run 16)

Temporal edge
-------------
  Long dominates pre-2010 (+8–12 pip EV), Short dominates 2010–2025.
  Combined system covers all eras (4/5 positive in Run 29).

  Long+Short EV by era (Run 29):
    2000–2005: +8.94  ← Long dominant
    2005–2010: +3.24  ← Long dominant
    2010–2015: +6.00  ← Short dominant
    2015–2020: +4.54  ← Short dominant
    2020–2025: +3.97  ← Short primary

Entry gates (all must pass)
---------------------------
  1. Entry filter : bb_touch_strength > 0.997
     → Price must be at or above the BB upper band.  Eliminates ~75% of bars.
  2. Regime filter: NOT in suppress_regimes_short = {(0,1)}
     → Block LowVol+Up only.  HighVol+Range was tested but restored (Run 19):
       suppressing it killed trade volume (155→134 valid folds, -3.3% EV+%).
  3. Proba gate   : P(win) ≥ 0.48
     → Intentionally lower than long (0.50).  Tuned in isolation (Run 20 tune)
       as the optimal operating point for the short direction.
     NOTE: Do NOT raise to 0.52 in combined mode — Run 21 confirmed interaction
       effects: raising short threshold removes short entries, which get replaced
       by long entries that are negative in 2020–2025.  HighVol+Range EV
       flipped from +1.05 → -0.42 when short threshold was raised.

Magic number: 300402
  XX=30 (Punk Hazard strategy)  YY=04 (H4 timeframe)  ZZ=02 (short variant)
"""

import logging
import warnings
from typing import List, Dict, Optional

import numpy as np
import pandas as pd

from .base_predictor import BasePredictor, PredictionSignal

logger = logging.getLogger(__name__)


# ── Punk Hazard Short — locked constants ─────────────────────────────────────

PROBA_THRESHOLD        = 0.48    # Run 20 tune: optimal for short direction
ENTRY_FILTER_COL       = 'bb_touch_strength'
ENTRY_FILTER_THRESHOLD = 0.997   # BB upper-band touch gate
PIP_VALUE              = 0.0001  # 1 pip for 5-decimal forex

# Regime quadrants to suppress (vol, trend)
# (0, 1) = LowVol+Up — quiet uptrend fights short reversal, EV=-0.63
# HighVol+Range (1,0) intentionally NOT suppressed — restoring it improved
# trade volume (134→155 valid folds) and EV+% (42.5%→45.8%) per Run 19.
SUPPRESS_REGIMES = frozenset({(0, 1)})

# Feature columns the model expects — direction-neutral + short-specific + computed
REQUIRED_FEATURES = [
    # Direction-neutral CSV features
    'rsi_value', 'bb_position', 'bb_width_pct', 'atr_pct', 'candle_body_pct',
    'trend_strength', 'volume_ratio', 'prev_candle_body_pct', 'prev_volume_ratio',
    'gap_from_prev_close',
    # Short-specific CSV features
    'bb_touch_strength', 'candle_rejection', 'rsi_divergence', 'price_momentum',
    'prev_was_rally', 'previous_touches', 'time_since_last_touch',
    'resistance_distance_pct',
    # Supplementary computed
    'dist_sma50', 'dist_sma100', 'dist_sma200',
    'atr_ratio', 'stoch_k', 'macd_hist', 'dist_extreme',
    'body_position', 'lower_wick_ratio', 'upper_wick_ratio',
    'rsi_slope_5', 'rsi_slope_10', 'bb_width_zscore',
    'dist_52w_low', 'atr_percentile', 'atr_longterm_zscore',
    'price_accel', 'vol_divergence',
    # Validated lag features
    'trend_strength_lag1', 'bb_width_pct_lag3', 'atr_pct_lag3',
    'atr_ratio_lag2', 'bb_width_zscore_lag2',
    # Regime columns (input features to the model — not gates)
    'regime_volatility', 'regime_trend',
]


class PunkHazardShortPredictor(BasePredictor):
    """
    Punk Hazard H4 Mean-Reversion SHORT.

    Receives the full feature-engineered DataFrame from the SAQ pipeline
    (after PunkHazardFeatureEngineer.transform() has been applied) and
    produces SHORT signals for EURUSD H4.

    One row per symbol per pipeline cycle.  For EURUSD H4, the signal
    row represents the most recently closed H4 bar.
    """

    def __init__(self, config):
        super().__init__(config)
        self._tp_pips: Optional[float] = None
        self._sl_pips: Optional[float] = None
        self._feature_names: Optional[List[str]] = None
        self._load_ph_metadata()

    # ── model loading ─────────────────────────────────────────────────────────

    def load_model(self, model_path):
        """
        Load the Punk Hazard .pkl export dict.

        The export contains:
            model         : CalibratedClassifierCV (sklearn)
            feature_names : list[str]
            tp_pips       : float
            sl_pips       : float
            timeout       : int
            metadata      : dict
        """
        import pickle
        with open(model_path, 'rb') as f:
            export = pickle.load(f)

        if not isinstance(export, dict) or 'model' not in export:
            raise ValueError(
                f"Expected Punk Hazard export dict with 'model' key, "
                f"got {type(export)}"
            )
        return export

    def _load_ph_metadata(self):
        """Extract TP/SL/feature names from the loaded export dict."""
        if not self.model_loaded or self.model is None:
            return
        export = self.model
        self._tp_pips       = export.get('tp_pips',      40.0)
        self._sl_pips       = export.get('sl_pips',      30.0)
        self._feature_names = export.get('feature_names', REQUIRED_FEATURES)
        meta = export.get('metadata', {})
        logger.info(
            f"PunkHazardShort loaded: "
            f"TP={self._tp_pips:.0f}p SL={self._sl_pips:.0f}p "
            f"features={len(self._feature_names)} "
            f"exported_at={meta.get('exported_at', 'unknown')}"
        )

    def _get_calibrated_model(self):
        """Return the inner CalibratedClassifierCV from the export dict."""
        if self.model is None:
            return None
        return self.model.get('model')

    # ── required interface ────────────────────────────────────────────────────

    def get_required_features(self) -> List[str]:
        """Return feature names expected by this model."""
        if self._feature_names:
            return list(self._feature_names)
        return list(REQUIRED_FEATURES)

    def predict(self, df_features: pd.DataFrame, config) -> List[Dict]:
        """
        Generate SHORT signals from the feature-engineered DataFrame.

        Parameters
        ----------
        df_features : pd.DataFrame
            One row per symbol (latest bar only, or full history).
            Must contain all REQUIRED_FEATURES + regime columns.
        config : ModelConfig
            SAQ model configuration.

        Returns
        -------
        List of signal dicts (may be empty).
        """
        predictions = []

        if not self.model_loaded or self.model is None:
            logger.warning("PunkHazardShort: model not loaded")
            return predictions

        calibrated = self._get_calibrated_model()
        if calibrated is None:
            logger.warning("PunkHazardShort: calibrated model not found in export")
            return predictions

        # Filter to allowed symbols (EURUSD only for Punk Hazard)
        df = self.filter_by_symbols(df_features)
        if df.empty:
            return predictions

        # Process each symbol row
        for _, row in df.iterrows():
            try:
                signal = self._predict_row(row, config, calibrated)
                if signal is not None:
                    predictions.append(signal.to_dict())
            except Exception as e:
                symbol = row.get('symbol', 'unknown')
                logger.error(f"PunkHazardShort: error processing {symbol}: {e}", exc_info=True)

        if predictions:
            logger.info(f"PunkHazardShort: {len(predictions)} signal(s) generated")

        return predictions

    def _predict_row(
        self,
        row: pd.Series,
        config,
        calibrated,
    ) -> Optional[PredictionSignal]:
        """
        Apply all entry gates and generate a signal for a single symbol row.

        Gates applied in order (fail-fast):
          1. Entry filter  — bb_touch_strength > 0.997
          2. Regime filter — not in suppress_regimes_short
          3. Proba gate    — P(win) ≥ 0.48
        """
        symbol = row.get('symbol', 'EURUSD')

        # ── Gate 1: BB upper-band touch filter ────────────────────────────────
        bb_touch = float(row.get(ENTRY_FILTER_COL, 0.0))
        if bb_touch <= ENTRY_FILTER_THRESHOLD:
            logger.debug(
                f"{symbol}: entry filter FAIL "
                f"({ENTRY_FILTER_COL}={bb_touch:.4f} ≤ {ENTRY_FILTER_THRESHOLD})"
            )
            return None

        # ── Gate 2: Regime filter ─────────────────────────────────────────────
        regime_vol   = int(row.get('regime_volatility', 0))
        regime_trend = int(row.get('regime_trend',      0))
        if (regime_vol, regime_trend) in SUPPRESS_REGIMES:
            regime_name = _regime_name(regime_vol, regime_trend)
            logger.debug(f"{symbol}: regime SUPPRESSED ({regime_name})")
            return None

        # ── Gate 3: Model probability ─────────────────────────────────────────
        try:
            X = self._prepare_features(row)
        except Exception as e:
            logger.error(f"{symbol}: feature prep error: {e}")
            return None

        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                proba = calibrated.predict_proba(X)
            confidence = float(proba[0][1])
        except Exception as e:
            logger.error(f"{symbol}: model inference error: {e}")
            return None

        if confidence < PROBA_THRESHOLD:
            logger.debug(
                f"{symbol}: proba FAIL ({confidence:.4f} < {PROBA_THRESHOLD})"
            )
            return None

        # ── Signal ────────────────────────────────────────────────────────────
        entry_price = float(row.get('close', row.get('price', 0.0)))
        regime_name = _regime_name(regime_vol, regime_trend)

        key_features = {
            'bb_touch_strength':  round(bb_touch, 4),
            'rsi_value':          round(float(row.get('rsi_value', 0)), 2),
            'regime':             regime_name,
            'regime_volatility':  regime_vol,
            'regime_trend':       regime_trend,
            'atr_pct':            round(float(row.get('atr_pct', 0)), 5),
            'trend_strength':     round(float(row.get('trend_strength', 0)), 4),
            'dist_sma50':         round(float(row.get('dist_sma50', 0)), 3),
            'dist_52w_low':       round(float(row.get('dist_52w_low', 0)), 3),
            'confidence':         round(confidence, 4),
        }

        signal = self.create_signal(
            symbol      = symbol,
            direction   = 'SHORT',
            confidence  = confidence,
            entry_price = entry_price,
            features    = key_features,
        )

        # Override TP/SL with values from the .pkl export if available
        if self._tp_pips is not None:
            signal.tp_pips = int(round(self._tp_pips))
        if self._sl_pips is not None:
            signal.sl_pips = int(round(self._sl_pips))

        logger.info(
            f"SIGNAL ✅ {symbol} SHORT @ {entry_price:.5f} | "
            f"P={confidence:.4f} | regime={regime_name} | "
            f"TP={signal.tp_pips}p SL={signal.sl_pips}p | "
            f"bb_touch={bb_touch:.4f}"
        )
        return signal

    def _prepare_features(self, row: pd.Series) -> np.ndarray:
        """
        Extract and order features for model input.

        Uses the feature list from the .pkl export (same order as training).
        Missing features are filled with 0.
        """
        feat_names = self._feature_names or REQUIRED_FEATURES
        values = []
        for feat in feat_names:
            val = row.get(feat, 0.0)
            if pd.isna(val) or (isinstance(val, float) and np.isinf(val)):
                val = 0.0
            values.append(float(val))
        return np.array([values])

    def get_metadata(self) -> Dict:
        """Return predictor metadata for logging."""
        base = super().get_metadata()
        base.update({
            'strategy':         'H4 BB Upper-Band Reversal',
            'direction':        'SHORT',
            'n_features':       len(self.get_required_features()),
            'proba_threshold':  PROBA_THRESHOLD,
            'entry_filter':     f'{ENTRY_FILTER_COL} > {ENTRY_FILTER_THRESHOLD}',
            'suppress_regimes': [list(r) for r in SUPPRESS_REGIMES],
            'tp_pips':          self._tp_pips,
            'sl_pips':          self._sl_pips,
            'run':              'Run 29 — sigmoid calibration',
            'note':             'Dominant in 2010-2025 eras; use paired with Long',
            'ev_2020_2025_combined': 3.97,
        })
        return base


# ── helpers ───────────────────────────────────────────────────────────────────

def _regime_name(vol: int, trend: int) -> str:
    names = {
        (0, -1): 'LowVol+Down',
        (0,  0): 'LowVol+Range',
        (0, +1): 'LowVol+Up',
        (1, -1): 'HighVol+Down',
        (1,  0): 'HighVol+Range',
        (1, +1): 'HighVol+Up',
    }
    return names.get((vol, trend), f'vol={vol},trend={trend}')
