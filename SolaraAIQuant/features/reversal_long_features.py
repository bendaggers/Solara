"""
Solara AI Quant — Trend Reversal LONG Feature Engineer
========================================================

Mirror of reversal_short_features.py for the LONG direction.
Detects downtrend→uptrend reversals on H4.

A LONG reversal event is defined as:
  1. Cascade flip  : H4 predicted_class == 'uptrend' AND within last 6 H4 bars
                     the class was 'downtrend'  (uptrend started recently)
  2. Structure break: H4 close > swing_high(last 20 H4 bars, excluding current) + 2pip buffer

Trigger TF: H4 — fires every H4 bar close.
merge_timeframes: [] — loads D1/W1 CSVs directly for context features.

Gate column output:
  _rev_break_detected  (bool) — True only when flip+break conditions are met
  close                (float) — current H4 close (for entry price)

Feature columns (19 — must match REVERSAL_LONG_FEATURES in reversal_long_labeler.py):
  Break magnitude (3):  break_magnitude_pips, break_magnitude_atr, break_magnitude_vs_impulse
  Candle structure (4): brk_body_pct_of_range, brk_upper_wick_ratio, brk_lower_wick_ratio, brk_close_location
  EA indicators (7):    brk_bb_position, brk_volume_ratio, brk_rsi_value, brk_candle_rejection,
                        brk_bb_width_pct, brk_trend_strength, brk_candle_body_pct
  Trend context (3):    h4_prob_up_at_break, d1_prob_up_at_break, w1_prob_down_at_break
  Swing context (2):    impulse_range_pips, prior_downtrend_bars
"""

import logging
import sys
from pathlib import Path
from typing import Optional, List

import joblib
import numpy as np
import pandas as pd

from config import MQL5_FILES_DIR, TIMEFRAMES, MODELS_DIR
from features.base_feature_engineer import BaseFeatureEngineer

logger = logging.getLogger(__name__)

# ── External package path ─────────────────────────────────────────────────────
_TI_ROOT = Path(
    r"C:\Users\Ben Michael Oracion\Documents\Solara\Model Training\Trend Identifier"
)
if str(_TI_ROOT) not in sys.path:
    sys.path.insert(0, str(_TI_ROOT))

try:
    from forex_trend_model.inference.live_pipeline import LiveTrendPredictor
    from forex_trend_model.features.pipeline import compute_atr
    from forex_trend_model.features.quant_v2 import compute_quant_v2_features
    _TI_AVAILABLE = True
    logger.info("[RevLongFE] Trend Identifier package loaded")
except ImportError as _e:
    _TI_AVAILABLE = False
    logger.critical(
        f"[RevLongFE] Cannot import Trend Identifier package: {_e}. "
        f"Check that {_TI_ROOT} exists."
    )

# ── Trend model paths (shared with Pull Back SHORT) ───────────────────────────
_REV_STRATEGY_ROOT = Path(
    r"C:\Users\Ben Michael Oracion\Documents\Solara\Model Training\Pull Back Strategy Short"
)
_TREND_MODEL_PATHS = {
    'H4': _REV_STRATEGY_ROOT / 'models' / 'Trend_Identifier_H4.joblib',
    'D1': _REV_STRATEGY_ROOT / 'models' / 'Trend_Identifier_D1.joblib',
    'W1': _REV_STRATEGY_ROOT / 'models' / 'Trend_Identifier_W1.joblib',
}

# ── Reversal LONG model path ──────────────────────────────────────────────────
_REVERSAL_LONG_MODEL_PATH = MODELS_DIR / 'reversal_H4_long.joblib'

# ── Detection constants ───────────────────────────────────────────────────────
_SWING_WINDOW      = 20   # H4 bars for swing high/low
_FLIP_LOOKBACK     = 6    # H4 bars — downtrend must exist within this many bars before flip
_BREAK_BUFFER_PIPS = 2    # close must be this many pips above swing_high to count as break
_MIN_H4_BARS       = 260  # trend model warmup

# ── Feature list (must exactly match REVERSAL_LONG_FEATURES in reversal_long_labeler.py) ──
REVERSAL_LONG_FEATURES = [
    'break_magnitude_pips',
    'break_magnitude_atr',
    'break_magnitude_vs_impulse',
    'brk_body_pct_of_range',
    'brk_upper_wick_ratio',
    'brk_lower_wick_ratio',
    'brk_close_location',
    'brk_bb_position',
    'brk_volume_ratio',
    'brk_rsi_value',
    'brk_candle_rejection',
    'brk_bb_width_pct',
    'brk_trend_strength',
    'brk_candle_body_pct',
    'h4_prob_up_at_break',
    'd1_prob_up_at_break',
    'w1_prob_down_at_break',
    'impulse_range_pips',
    'prior_downtrend_bars',
]


class ReversalLongFeatureEngineer(BaseFeatureEngineer):
    """
    Feature engineer for the Trend Reversal LONG model (reversal_H4_long.joblib).

    Fires on H4 bar closes. For each symbol:
      1. Runs H4 trend model
      2. Checks if current H4 bar is a cascade flip (downtrend→uptrend) + structure break above swing_high
      3. If yes: extracts 19 reversal features + sets _rev_break_detected=True
      4. If no:  returns zero-filled row with _rev_break_detected=False
    """

    # ── Class-level caches ────────────────────────────────────────────────────
    _trend_predictors: dict = {}
    _rev_model              = None
    _rev_feature_cols: list = []
    _rev_threshold: float   = 0.76   # WF median; live threshold set by registry (0.50)

    _csv_cache: dict = {}

    def __init__(self):
        self._load_reversal_model()
        self._load_trend_models()

    # ─────────────────────────────────────────────────────────────────────────
    # BaseFeatureEngineer contract
    # ─────────────────────────────────────────────────────────────────────────

    def get_required_input_columns(self) -> List[str]:
        return [
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
            'atr_pct', 'candle_body_pct', 'candle_rejection', 'trend_strength',
        ]

    def get_output_features(self) -> List[str]:
        return REVERSAL_LONG_FEATURES + ['_rev_break_detected', 'close']

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        if not _TI_AVAILABLE:
            logger.error("[RevLongFE] Trend Identifier not available — skipping")
            return pd.DataFrame()

        h4_all = df.copy()
        if 'pair' in h4_all.columns and 'symbol' not in h4_all.columns:
            h4_all = h4_all.rename(columns={'pair': 'symbol'})
        h4_all['timestamp'] = pd.to_datetime(h4_all['timestamp'])

        self._csv_cache = {}
        d1_all = self._load_tf_csv('D1')
        w1_all = self._load_tf_csv('W1')

        symbols = h4_all['symbol'].dropna().unique()
        rows = []
        for sym in symbols:
            try:
                row = self._compute_for_symbol(h4_all, sym, d1_all, w1_all)
                if row is not None:
                    rows.append(row)
            except Exception as exc:
                logger.error(f"[RevLongFE] {sym} failed: {exc}", exc_info=True)

        if not rows:
            logger.warning(f"[RevLongFE] compute() produced 0 rows from {len(symbols)} symbols")
            return pd.DataFrame()

        result = pd.DataFrame(rows)
        for col in REVERSAL_LONG_FEATURES:
            if col not in result.columns:
                result[col] = 0.0
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Per-symbol pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_for_symbol(
        self,
        h4_all: pd.DataFrame,
        sym:    str,
        d1_all: Optional[pd.DataFrame],
        w1_all: Optional[pd.DataFrame],
    ) -> Optional[dict]:

        h4 = self._filter_symbol(h4_all, sym)
        if h4 is None or len(h4) < _MIN_H4_BARS:
            logger.debug(f"[RevLongFE] {sym}: insufficient H4 bars ({len(h4) if h4 is not None else 0})")
            return None

        h4_pred = self._get_trend_pred(h4, 'H4', sym)
        if h4_pred is None:
            logger.debug(f"[RevLongFE] {sym}: H4 trend prediction failed")
            return None

        h4 = h4.copy()
        h4['_predicted_class'] = h4_pred['predicted_class'].values
        h4['_prob_up']         = h4_pred['prob_up'].values
        h4['_prob_down']       = h4_pred['prob_down'].values
        h4['_model_valid']     = h4_pred['model_valid'].values

        curr_idx = len(h4) - 1
        curr     = h4.iloc[curr_idx]

        # ── Gate: model valid ─────────────────────────────────────────────
        if not curr['_model_valid']:
            return self._null_row(sym, curr)

        # ── Gate: current bar must be uptrend ─────────────────────────────
        if curr['_predicted_class'] != 'uptrend':
            logger.debug(f"[RevLongFE] {sym}: current H4 class={curr['_predicted_class']}, not uptrend")
            return self._null_row(sym, curr)

        # ── Gate: cascade flip — downtrend within last N bars ─────────────
        flip_start = max(0, curr_idx - _FLIP_LOOKBACK)
        recent_classes = h4.iloc[flip_start:curr_idx]['_predicted_class'].tolist()
        if 'downtrend' not in recent_classes:
            logger.debug(f"[RevLongFE] {sym}: no downtrend in last {_FLIP_LOOKBACK} bars — no flip")
            return self._null_row(sym, curr)

        # ── Gate: structure break above swing_high ────────────────────────
        pip = 0.01 if 'JPY' in sym else 0.0001
        buf = _BREAK_BUFFER_PIPS * pip

        swing_high = h4['high'].rolling(_SWING_WINDOW, min_periods=_SWING_WINDOW).max().shift(1)
        swing_low  = h4['low'].rolling(_SWING_WINDOW, min_periods=_SWING_WINDOW).min().shift(1)

        sh_curr = swing_high.iloc[curr_idx]
        sl_curr = swing_low.iloc[curr_idx]

        if pd.isna(sh_curr):
            logger.debug(f"[RevLongFE] {sym}: swing_high NaN — insufficient history")
            return self._null_row(sym, curr)

        close_val = float(curr['close'])
        if close_val <= float(sh_curr) + buf:
            logger.debug(
                f"[RevLongFE] {sym}: close={close_val:.5f} ≤ swing_high+buf={float(sh_curr)+buf:.5f} — no break"
            )
            return self._null_row(sym, curr)

        # ── Structure break confirmed! ─────────────────────────────────────
        broken_level = float(sh_curr)
        impulse = float(sh_curr) - float(sl_curr) if not pd.isna(sl_curr) else 0.0

        logger.info(
            f"[RevLongFE] {sym}: LONG BREAK DETECTED — "
            f"close={close_val:.5f} broke swing_high={broken_level:.5f} "
            f"(mag={(close_val - broken_level)/pip:.1f}p)"
        )

        # ── Break magnitude features ──────────────────────────────────────
        break_mag_pips = (close_val - broken_level) / pip

        atr_pct  = float(curr.get('atr_pct', 0.0) or 0.0)
        atr_pips = (atr_pct / 100.0 * close_val) / pip if atr_pct > 0 else np.nan
        break_mag_atr = (
            break_mag_pips / atr_pips
            if (atr_pips and not np.isnan(atr_pips) and atr_pips > 0)
            else 0.0
        )
        break_mag_imp = break_mag_pips / (impulse / pip) if impulse > 0 else 0.0

        # ── Candle structure ──────────────────────────────────────────────
        h4_range      = float(curr['high']) - float(curr['low'])
        h4_range_safe = h4_range if h4_range > 0 else np.nan

        body_pct  = abs(close_val - float(curr['open'])) / h4_range_safe if h4_range_safe else 0.0
        uwick     = (float(curr['high']) - max(float(curr['open']), close_val)) / h4_range_safe if h4_range_safe else 0.0
        lwick     = (min(float(curr['open']), close_val) - float(curr['low'])) / h4_range_safe if h4_range_safe else 0.0
        close_loc = (close_val - float(curr['low'])) / h4_range_safe if h4_range_safe else 0.0

        # ── D1 / W1 context features ──────────────────────────────────────
        d1_prob_up = 0.0
        if d1_all is not None:
            d1 = self._filter_symbol(d1_all, sym)
            if d1 is not None and len(d1) >= _MIN_H4_BARS:
                d1_pred = self._get_trend_pred(d1, 'D1', sym)
                if d1_pred is not None and d1_pred['model_valid'].any():
                    d1_prob_up = float(d1_pred[d1_pred['model_valid']].iloc[-1]['prob_up'])

        w1_prob_down = 0.0
        if w1_all is not None:
            w1 = self._filter_symbol(w1_all, sym)
            if w1 is not None and len(w1) >= 100:
                w1_pred = self._get_trend_pred(w1, 'W1', sym)
                if w1_pred is not None and w1_pred['model_valid'].any():
                    w1_prob_down = float(w1_pred[w1_pred['model_valid']].iloc[-1]['prob_down'])

        # ── Prior downtrend bar count ─────────────────────────────────────
        prior_downtrend_bars = 0
        for j in range(curr_idx - 1, max(0, curr_idx - 300), -1):
            if h4.iloc[j]['_predicted_class'] == 'downtrend':
                prior_downtrend_bars += 1
            else:
                break

        # ── EA indicator pass-through ─────────────────────────────────────
        def _g(col):
            val = curr.get(col, np.nan)
            if val is None:
                return 0.0
            try:
                fv = float(val)
                return 0.0 if np.isnan(fv) else fv
            except (TypeError, ValueError):
                return 0.0

        return {
            'symbol':              sym,
            'timestamp':           curr['timestamp'],
            'close':               close_val,
            '_rev_break_detected': True,
            # Break magnitude
            'break_magnitude_pips':       break_mag_pips,
            'break_magnitude_atr':        break_mag_atr,
            'break_magnitude_vs_impulse': break_mag_imp,
            # Candle structure
            'brk_body_pct_of_range': body_pct,
            'brk_upper_wick_ratio':  uwick,
            'brk_lower_wick_ratio':  lwick,
            'brk_close_location':    close_loc,
            # EA indicators
            'brk_bb_position':    _g('bb_position'),
            'brk_volume_ratio':   _g('volume_ratio'),
            'brk_rsi_value':      _g('rsi_value'),
            'brk_candle_rejection': _g('candle_rejection'),
            'brk_bb_width_pct':   _g('bb_width_pct'),
            'brk_trend_strength': _g('trend_strength'),
            'brk_candle_body_pct': _g('candle_body_pct'),
            # Trend model context
            'h4_prob_up_at_break':   float(curr['_prob_up']),
            'd1_prob_up_at_break':   d1_prob_up,
            'w1_prob_down_at_break': w1_prob_down,
            # Swing context
            'impulse_range_pips':  impulse / pip if impulse > 0 else 0.0,
            'prior_downtrend_bars': float(prior_downtrend_bars),
        }

    def _null_row(self, sym: str, curr) -> dict:
        row = {
            'symbol':              sym,
            'timestamp':           curr['timestamp'],
            'close':               float(curr.get('close', 0.0)),
            '_rev_break_detected': False,
        }
        for feat in REVERSAL_LONG_FEATURES:
            row[feat] = 0.0
        return row

    # ─────────────────────────────────────────────────────────────────────────
    # Trend model inference (identical to SHORT FE)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_trend_pred(self, df, tf, sym):
        if df is None or len(df) < 260 or not _TI_AVAILABLE:
            return None
        predictor = ReversalLongFeatureEngineer._trend_predictors.get(tf)
        if predictor is None:
            return None
        try:
            ohlcv = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
            ohlcv = ohlcv.rename(columns={'timestamp': 'time', 'volume': 'tick_volume'})
            ohlcv = ohlcv.sort_values('time').reset_index(drop=True)
            atr         = compute_atr(ohlcv, period=14)
            features_df = compute_quant_v2_features(ohlcv, timeframe=tf, atr=atr, feature_subset='full')
            features_df['pair_encoded']      = 0
            features_df['base_ccy_encoded']  = 0
            features_df['quote_ccy_encoded'] = 0
            n = len(ohlcv)
            results = {
                'predicted_class': np.full(n, 'sideways', dtype=object),
                'prob_up':         np.full(n, 1/3),
                'prob_down':       np.full(n, 1/3),
                'model_valid':     np.zeros(n, dtype=bool),
            }
            valid_mask = features_df['feature_valid'].values
            valid_idx  = np.where(valid_mask)[0]
            if len(valid_idx) > 0:
                feature_cols = predictor.feature_cols
                for c in [col for col in feature_cols if col not in features_df.columns]:
                    features_df[c] = 0
                X = features_df.loc[valid_mask, feature_cols].copy()
                cat_names: set = set()
                try:
                    base = getattr(predictor.model, 'base_model', None)
                    if base and hasattr(base, 'models'):
                        cb = base.models.get('cat')
                        if cb and hasattr(cb, 'cat_features'):
                            cat_names = set(cb.cat_features)
                except Exception:
                    pass
                for col in cat_names:
                    if col in X.columns:
                        X[col] = X[col].fillna(0).astype(int)
                X = X.fillna(0)
                probs = predictor.model.predict_proba(X)
                pred_cls = np.where(
                    probs[:, 2] > probs[:, 0],
                    np.where(probs[:, 2] > probs[:, 1], 'uptrend',   'sideways'),
                    np.where(probs[:, 0] > probs[:, 1], 'downtrend', 'sideways'),
                )
                results['predicted_class'][valid_idx] = pred_cls
                results['prob_up'][valid_idx]          = probs[:, 2]
                results['prob_down'][valid_idx]        = probs[:, 0]
                results['model_valid'][valid_idx]      = True
            return pd.DataFrame(results, index=df.index)
        except Exception as exc:
            logger.error(f"[RevLongFE] Trend model {tf} failed for {sym}: {exc}", exc_info=True)
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # CSV / model loading helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _load_tf_csv(self, tf):
        if tf in self._csv_cache:
            return self._csv_cache[tf]
        tf_cfg = TIMEFRAMES.get(tf)
        if tf_cfg is None:
            return None
        csv_path = MQL5_FILES_DIR / tf_cfg.csv_filename
        if not csv_path.exists():
            logger.warning(f"[RevLongFE] {tf} CSV not found: {csv_path}")
            return None
        try:
            df = pd.read_csv(csv_path, parse_dates=['timestamp'])
            if 'pair' in df.columns and 'symbol' not in df.columns:
                df = df.rename(columns={'pair': 'symbol'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            self._csv_cache[tf] = df
            return df
        except Exception as exc:
            logger.error(f"[RevLongFE] Failed to load {tf} CSV: {exc}")
            return None

    @staticmethod
    def _filter_symbol(df, sym):
        if df is None:
            return None
        sym_col  = 'symbol' if 'symbol' in df.columns else 'pair'
        filtered = df[df[sym_col] == sym].copy().sort_values('timestamp').reset_index(drop=True)
        return filtered if len(filtered) > 0 else None

    def _load_reversal_model(self):
        if ReversalLongFeatureEngineer._rev_model is not None:
            return
        if not _REVERSAL_LONG_MODEL_PATH.exists():
            logger.error(f"[RevLongFE] Reversal LONG model not found: {_REVERSAL_LONG_MODEL_PATH}")
            return
        try:
            pkg = joblib.load(_REVERSAL_LONG_MODEL_PATH)
            ReversalLongFeatureEngineer._rev_model        = pkg['model']
            ReversalLongFeatureEngineer._rev_feature_cols = pkg.get('feature_cols', REVERSAL_LONG_FEATURES)
            ReversalLongFeatureEngineer._rev_threshold    = float(pkg.get('threshold', 0.76))
            meta = pkg.get('metadata', {})
            logger.info(
                f"[RevLongFE] Reversal LONG model loaded — "
                f"joblib_threshold={ReversalLongFeatureEngineer._rev_threshold:.2f}  "
                f"features={len(ReversalLongFeatureEngineer._rev_feature_cols)}  "
                f"WF_precision={meta.get('wf_precision_mean', '?')}  "
                f"WF_ev={meta.get('wf_ev_mean', '?')}p  "
                f"(live threshold set by registry confidence_tiers)"
            )
        except Exception as exc:
            logger.error(f"[RevLongFE] Failed to load reversal LONG model: {exc}")

    def _load_trend_models(self):
        if not _TI_AVAILABLE:
            return
        for tf, model_path in _TREND_MODEL_PATHS.items():
            if tf in ReversalLongFeatureEngineer._trend_predictors:
                continue
            if not model_path.exists():
                logger.warning(f"[RevLongFE] Trend model {tf} not found: {model_path}")
                continue
            try:
                predictor = LiveTrendPredictor.from_package(str(model_path))
                ReversalLongFeatureEngineer._trend_predictors[tf] = predictor
                logger.info(f"[RevLongFE] Trend model {tf} loaded")
            except Exception as exc:
                logger.error(f"[RevLongFE] Failed to load trend model {tf}: {exc}")
