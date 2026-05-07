"""
Solara AI Quant — Failed Pullback Reversal LONG Feature Engineer
================================================================

Computes the full feature set for the Failed PB Reversal LONG entry model
(reversal_entry_H1_long.joblib).

Strategy thesis: When a bullish pullback in a prior downtrend FAILS to exhaust
(Pull Back model class-2 prob is LOW), the downtrend is breaking — enter LONG.

Pipeline:
  Stage 1 — Prior trend check  : H4 trend was DOWN (trend_dir_encoded == -1)
                                  AND pullback has been active ≥ 2 H4 bars
  Stage 2 — Failed pullback    : PB model exhaust_prob < 0.40 (failure_threshold)
  Stage 3 — Entry features     : ~50-feature H1 vector for the XGBoost entry model

Trigger TF:      H1
merge_timeframes: []  — this FE loads H4 / D1 / W1 CSVs directly.

Gate columns output (read by predictor, not by the entry model):
  _fpb_condition_met   (bool)  — all H4-level conditions passed
  _fpb_exhaust_prob    (float) — PB model class-2 prob on latest H4 bar
  _fpb_pullback_duration (int) — consecutive H4 bars in active pullback band
  close                (float) — H1 close price (entry price)
  symbol               (str)
  timestamp            (datetime)

Trend models: Models/trend_identifier/short/  (same as Pull Back Short)
PB model:     Models/pull_back_pullback_h4.joblib  (read-only, for exhaust prob)
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

# ── Trend Identifier package (bundled in vendor/) ────────────────────────────
_SAQ_ROOT   = Path(__file__).resolve().parent.parent
_VENDOR_DIR = _SAQ_ROOT / 'vendor'
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

try:
    from forex_trend_model.inference.live_pipeline import LiveTrendPredictor
    from forex_trend_model.features.pipeline import compute_atr
    from forex_trend_model.features.quant_v2 import compute_quant_v2_features
    _TI_AVAILABLE = True
    logger.info("[FPBRevLongFE] Trend Identifier package loaded")
except ImportError as _e:
    _TI_AVAILABLE = False
    logger.critical(
        f"[FPBRevLongFE] Cannot import forex_trend_model: {_e}. "
        f"Copy the forex_trend_model/ package into {_VENDOR_DIR}/"
    )

# ── Trend model paths (short/ — same models as PB Short + Reversal H4) ───────
_TREND_MODELS_DIR = _SAQ_ROOT / 'Models' / 'trend_identifier' / 'short'
_TREND_MODEL_PATHS = {
    'H4': _TREND_MODELS_DIR / 'Trend_Identifier_H4.joblib',
    'D1': _TREND_MODELS_DIR / 'Trend_Identifier_D1.joblib',
    'W1': _TREND_MODELS_DIR / 'Trend_Identifier_W1.joblib',
}

# Pull Back H4 model — used read-only to get exhaust probability
_PB_MODEL_PATH = MODELS_DIR / 'pull_back_pullback_h4.joblib'

# ── Constants ─────────────────────────────────────────────────────────────────
_MIN_H4_BARS       = 260   # trend model warmup
_SWING_WINDOW      = 20    # H4 bars for swing high/low lookback
_TOUCH_LOOKBACK    = 20    # H1 bars for BB touch history
_FAILURE_THRESHOLD = 0.40  # PB exhaust_prob below this → "failed pullback"
_MIN_PERSISTENCE   = 2     # min consecutive H4 bars in pullback band
_PB_BAND_MIN       = 0.25  # pullback retracement band lower bound
_PB_BAND_MAX       = 0.75  # pullback retracement band upper bound

# ── Feature list (superset; predictor selects from pkg['feature_cols']) ───────
ENTRY_FEATURES = [
    # ── Standard H1 CSV features ──────────────────────────────────────────────
    'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
    'candle_body_pct', 'atr_pct', 'trend_strength',
    'prev_candle_body_pct', 'prev_volume_ratio', 'gap_from_prev_close',
    'bb_touch_strength', 'candle_rejection', 'rsi_divergence',
    'price_momentum', 'prev_was_rally', 'previous_touches',
    'time_since_last_touch', 'resistance_distance_pct', 'support_distance_pct',
    'prev_was_selloff',
    # ── Long-side BB features (not in live EA CSV — computed here) ────────────
    'bb_touch_strength_long', 'candle_rejection_long',
    'rsi_divergence_long', 'price_momentum_long',
    'previous_touches_long', 'time_since_last_touch_long',
    # ── Computed H1 candle structure ──────────────────────────────────────────
    'close_location', 'upper_wick_ratio', 'lower_wick_ratio', 'body_size_atr',
    # ── H4 context ────────────────────────────────────────────────────────────
    'h4_fpb_label', 'h4_trend_dir_encoded',
    'h4_trend_prob_up', 'h4_trend_prob_down',
    'h4_pb_exhaust_prob', 'h4_exhaust_prob_slope',
    'h4_pullback_duration_bars', 'candles_since_failure',
    'h4_trend_conviction_delta',
    'h4_d1_trend_agreement', 'h4_d1_prob_against_trend',
    'h4_w1_d1_h4_alignment_score',
    # ── Reversal-specific H1 features ─────────────────────────────────────────
    'h1_momentum_vs_trend', 'h1_rsi_divergence_from_trend',
    'bars_since_pb_start',
    'rsi_slope_5', 'rsi_above_50', 'bb_pos_slope_3',
    'h1_higher_low', 'h1_new_high_3', 'h1_consecutive_bull', 'h1_volume_surge',
    # ── Session dummies ───────────────────────────────────────────────────────
    'session_london', 'session_new_york', 'session_asian', 'session_other',
]


class FailedPBReversalLongFeatureEngineer(BaseFeatureEngineer):
    """
    Feature engineer for the Failed PB Reversal LONG entry model.

    Mirrors PullBackFeatureEngineer in structure but inverts the pullback logic:
    instead of looking for exhaustion (high class-2 prob), it looks for failure
    (low class-2 prob) during an active bullish pullback within a prior downtrend.

    Class-level caches ensure models are loaded once and reused across cycles.
    """

    _trend_predictors : dict  = {}
    _pb_model                 = None
    _pb_feature_cols  : list  = []
    _csv_cache        : dict  = {}

    def __init__(self):
        self._load_pb_model()
        self._load_trend_models()

    # ─────────────────────────────────────────────────────────────────────────
    # BaseFeatureEngineer contract
    # ─────────────────────────────────────────────────────────────────────────

    def get_required_input_columns(self) -> List[str]:
        return [
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
            'candle_body_pct', 'atr_pct', 'trend_strength',
            'prev_candle_body_pct', 'prev_volume_ratio', 'gap_from_prev_close',
            'session',
            'bb_touch_strength', 'candle_rejection', 'rsi_divergence',
            'price_momentum', 'prev_was_rally', 'previous_touches',
            'time_since_last_touch', 'prev_was_selloff',
            'lower_band', 'upper_band',
        ]

    def get_output_features(self) -> List[str]:
        return ENTRY_FEATURES + [
            '_fpb_condition_met', '_fpb_exhaust_prob',
            '_fpb_pullback_duration', 'close',
        ]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Receives the full H1 DataFrame (all symbols, latest bar per symbol).
        Returns one row per symbol with all entry features + gate columns.
        """
        if not _TI_AVAILABLE:
            logger.error("[FPBRevLongFE] Trend Identifier not available — skipping")
            return pd.DataFrame()

        if FailedPBReversalLongFeatureEngineer._pb_model is None:
            logger.error("[FPBRevLongFE] PB model not loaded — skipping")
            return pd.DataFrame()

        df = df.copy()
        if 'pair' in df.columns and 'symbol' not in df.columns:
            df = df.rename(columns={'pair': 'symbol'})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        self._csv_cache = {}
        h4_all = self._load_tf_csv('H4')
        d1_all = self._load_tf_csv('D1')
        w1_all = self._load_tf_csv('W1')

        if h4_all is None:
            logger.error("[FPBRevLongFE] H4 CSV unavailable — skipping")
            return pd.DataFrame()

        symbols = df['symbol'].dropna().unique()
        rows = []
        for sym in symbols:
            try:
                row = self._compute_for_symbol(df, sym, h4_all, d1_all, w1_all)
                if row is not None:
                    rows.append(row)
            except Exception as exc:
                logger.error(f"[FPBRevLongFE] {sym} failed: {exc}", exc_info=True)

        if not rows:
            logger.warning(
                f"[FPBRevLongFE] compute() produced 0 rows from {len(symbols)} symbols"
            )
            return pd.DataFrame()

        result = pd.DataFrame(rows)
        for col in ENTRY_FEATURES:
            if col not in result.columns:
                result[col] = 0.0
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Per-symbol pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_for_symbol(
        self,
        h1_df:  pd.DataFrame,
        sym:    str,
        h4_all: pd.DataFrame,
        d1_all: Optional[pd.DataFrame],
        w1_all: Optional[pd.DataFrame],
    ) -> Optional[dict]:

        # ── 1. H1 data for this symbol ────────────────────────────────────
        h1 = h1_df[h1_df['symbol'] == sym].copy()
        h1 = h1.sort_values('timestamp').reset_index(drop=True)
        if len(h1) < 5:
            return None

        # ── 2. Secondary TF data ──────────────────────────────────────────
        h4 = self._filter_symbol(h4_all, sym)
        d1 = self._filter_symbol(d1_all, sym) if d1_all is not None else None
        w1 = self._filter_symbol(w1_all, sym) if w1_all is not None else None

        if h4 is None or len(h4) < _MIN_H4_BARS:
            logger.debug(
                f"[FPBRevLongFE] {sym}: insufficient H4 bars "
                f"({len(h4) if h4 is not None else 0})"
            )
            return None

        # ── 3. Trend models ───────────────────────────────────────────────
        h4_trend = self._get_trend_pred(h4, 'H4', sym)
        d1_trend = (
            self._get_trend_pred(d1, 'D1', sym)
            if d1 is not None and len(d1) >= 260 else None
        )
        w1_trend = (
            self._get_trend_pred(w1, 'W1', sym)
            if w1 is not None and len(w1) >= 260 else None
        )

        if h4_trend is None:
            logger.debug(f"[FPBRevLongFE] {sym}: H4 trend prediction failed")
            return None

        # ── 4. H4 features: pullback band + PB model + multi-TF context ───
        h4_full = self._compute_h4_features(h4, h4_trend, d1_trend, w1_trend)

        # ── 5. H4 context dict for current H1 bar ─────────────────────────
        current_h1_ts = h1['timestamp'].iloc[-1]
        h4_ctx = self._get_h4_context(h4_full, current_h1_ts)

        # ── 6. Candles since failure and bars since pb start ───────────────
        candles_since_failure = self._compute_candles_since_failure(h4_full, h1)
        bars_since_pb_start   = self._compute_bars_since_pb_start(h4_full, h1)

        # ── 7. H1 features ────────────────────────────────────────────────
        h1_feats = self._compute_h1_features(h1, h4_ctx)

        # ── 8. Log H4 state ───────────────────────────────────────────────
        _ep   = h4_ctx['h4_pb_exhaust_prob']
        _dur  = h4_ctx['h4_pullback_duration_bars']
        _tdir = h4_ctx['h4_trend_dir_encoded']
        _ok   = '✓' if h4_ctx['_fpb_condition_met'] else '✗'
        logger.debug(
            f"[FPBRevLongFE] {sym}: trend_dir={_tdir}  "
            f"exhaust_prob={_ep:.3f}  pb_duration={_dur}  cond={_ok}  "
            f"csf={candles_since_failure:.0f}"
        )

        # ── 9. Assemble output row ─────────────────────────────────────────
        latest = h1.iloc[-1]
        row: dict = {}

        # H1 CSV pass-throughs
        h1_pass = [
            'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
            'candle_body_pct', 'atr_pct', 'trend_strength',
            'prev_candle_body_pct', 'prev_volume_ratio', 'gap_from_prev_close',
            'bb_touch_strength', 'candle_rejection', 'rsi_divergence',
            'price_momentum', 'prev_was_rally', 'previous_touches',
            'time_since_last_touch', 'resistance_distance_pct', 'support_distance_pct',
            'prev_was_selloff',
        ]
        for col in h1_pass:
            row[col] = float(latest[col]) if col in h1.columns else 0.0

        # H1 computed features
        row.update(h1_feats)

        # H4 context features (prefixed h4_*)
        row['h4_fpb_label']               = h4_ctx['h4_fpb_label']
        row['h4_trend_dir_encoded']        = h4_ctx['h4_trend_dir_encoded']
        row['h4_trend_prob_up']            = h4_ctx['h4_trend_prob_up']
        row['h4_trend_prob_down']          = h4_ctx['h4_trend_prob_down']
        row['h4_pb_exhaust_prob']          = h4_ctx['h4_pb_exhaust_prob']
        row['h4_exhaust_prob_slope']       = h4_ctx['h4_exhaust_prob_slope']
        row['h4_pullback_duration_bars']   = h4_ctx['h4_pullback_duration_bars']
        row['h4_trend_conviction_delta']   = h4_ctx['h4_trend_conviction_delta']
        row['h4_d1_trend_agreement']       = h4_ctx['h4_d1_trend_agreement']
        row['h4_d1_prob_against_trend']    = h4_ctx['h4_d1_prob_against_trend']
        row['h4_w1_d1_h4_alignment_score'] = h4_ctx['h4_w1_d1_h4_alignment_score']
        row['candles_since_failure']       = candles_since_failure
        row['bars_since_pb_start']         = bars_since_pb_start

        # Reversal H1 features (already computed in h1_feats but set h4 context ones)
        row['h1_momentum_vs_trend'] = (
            -float(latest.get('price_momentum_long', 0.0) or 0.0)
            * h4_ctx['h4_trend_dir_encoded']
        )
        row['h1_rsi_divergence_from_trend'] = h1_feats.get('h1_rsi_divergence_from_trend', 0.0)

        # Session dummies
        sess = int(latest.get('session', 0))
        row['session_london']   = float(sess == 1)
        row['session_new_york'] = float(sess == 2)
        row['session_asian']    = float(sess == 3)
        row['session_other']    = float(sess not in (1, 2, 3))

        # Gate / metadata columns
        row['symbol']                = sym
        row['close']                 = float(latest['close'])
        row['timestamp']             = latest['timestamp']
        row['_fpb_condition_met']    = h4_ctx['_fpb_condition_met']
        row['_fpb_exhaust_prob']     = h4_ctx['h4_pb_exhaust_prob']
        row['_fpb_pullback_duration']= h4_ctx['h4_pullback_duration_bars']

        return row

    # ─────────────────────────────────────────────────────────────────────────
    # H4 feature computation
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_h4_features(
        self,
        h4:       pd.DataFrame,
        h4_trend: pd.DataFrame,
        d1_trend: Optional[pd.DataFrame],
        w1_trend: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        """
        Compute full H4 feature set:
          - Trend direction + probabilities from trend model
          - D1 / W1 context (as-of merged)
          - Swing levels + fib features (for PB model)
          - PB model exhaust probability
          - Pullback band active mask + duration
          - Multi-TF context features (conviction delta, D1 agreement, etc.)
        """
        df = h4.copy().reset_index(drop=True)

        # ── Trend context from H4 trend model ─────────────────────────────
        df['trend_prob_up']   = h4_trend['prob_up'].values
        df['trend_prob_down'] = h4_trend['prob_down'].values
        df['predicted_class'] = h4_trend['predicted_class'].values

        class_map = {'uptrend': 1, 'downtrend': -1, 'sideways': 0}
        df['trend_dir_encoded'] = (
            df['predicted_class'].map(class_map).fillna(0).astype(int)
        )

        # ── D1 / W1 context (as-of merge → forward-fill lower-TF votes) ──
        for prefix, pred in (('d1', d1_trend), ('w1', w1_trend)):
            if pred is not None and 'prob_down' in pred.columns:
                tf_sub = h4[['timestamp']].copy()
                tf_sub[f'{prefix}_trend_dir_encoded'] = np.nan
                tf_sub[f'{prefix}_trend_prob_up']     = np.nan
                tf_sub[f'{prefix}_trend_prob_down']   = np.nan

                src = pd.DataFrame({
                    'timestamp':                  h4['timestamp'].values,
                    f'{prefix}_trend_dir_encoded': (
                        pred['predicted_class'].map(class_map).fillna(0).values
                    ),
                    f'{prefix}_trend_prob_up':    pred['prob_up'].values,
                    f'{prefix}_trend_prob_down':  pred['prob_down'].values,
                })
                src = src.sort_values('timestamp').reset_index(drop=True)
                merged = pd.merge_asof(
                    df[['timestamp']].sort_values('timestamp'),
                    src, on='timestamp', direction='backward'
                )
                for col in [f'{prefix}_trend_dir_encoded',
                            f'{prefix}_trend_prob_up', f'{prefix}_trend_prob_down']:
                    df[col] = merged[col].values
            else:
                df[f'{prefix}_trend_dir_encoded'] = np.nan
                df[f'{prefix}_trend_prob_up']     = np.nan
                df[f'{prefix}_trend_prob_down']   = np.nan

        # ── Swing levels + fib features (LONG convention — from swing_high down) ─
        sw = _SWING_WINDOW
        df['swing_high']    = df['high'].rolling(sw, min_periods=sw).max()
        df['swing_low']     = df['low'].rolling(sw, min_periods=sw).min()
        df['impulse_range'] = (df['swing_high'] - df['swing_low']).replace(0, np.nan)

        for fib, label in [(0.382, '382'), (0.618, '618')]:
            fib_level = df['swing_high'] - fib * df['impulse_range']
            df[f'dist_to_fib{label}'] = (
                (df['close'] - fib_level).abs() / df['impulse_range']
            )

        # Pullback band (25%–75% retracement of impulse from swing_low)
        retrace = (df['close'] - df['swing_low']) / df['impulse_range']
        df['pb_active'] = retrace.between(_PB_BAND_MIN, _PB_BAND_MAX).fillna(False)

        # ── PB model exhaust probability ───────────────────────────────────
        pb_feats = [
            'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
            'candle_body_pct', 'atr_pct', 'trend_strength',
            'prev_candle_body_pct', 'prev_volume_ratio',
            'close_location', 'upper_wick_ratio', 'lower_wick_ratio',
            'dist_to_fib382', 'dist_to_fib618',
            'trend_dir_encoded', 'trend_prob_up', 'trend_prob_down',
        ]
        candle_range = (df['high'] - df['low']).replace(0, np.nan)
        df['close_location']   = (df['close'] - df['low']) / candle_range
        df['upper_wick_ratio'] = (
            df['high'] - df[['open', 'close']].max(axis=1)
        ) / candle_range
        df['lower_wick_ratio'] = (
            df[['open', 'close']].min(axis=1) - df['low']
        ) / candle_range

        df_tail = df.tail(35).copy().reset_index(drop=True)
        avail   = [f for f in pb_feats if f in df_tail.columns]
        X_pb    = df_tail[avail].fillna(0).astype(float)

        try:
            probs = FailedPBReversalLongFeatureEngineer._pb_model.predict_proba(X_pb)
            exhaust_probs = probs[:, 2].astype(float)
        except Exception as exc:
            logger.warning(f"[FPBRevLongFE] PB model predict_proba failed: {exc}")
            exhaust_probs = np.full(len(df_tail), np.nan)

        df['pb_exhaust_prob'] = np.nan
        df.loc[df.index[-len(df_tail):], 'pb_exhaust_prob'] = exhaust_probs

        # ── Pullback duration (consecutive pb_active bars) ─────────────────
        pb_arr  = df['pb_active'].values
        dur_arr = np.zeros(len(df), dtype=np.float32)
        count   = 0
        for i in range(len(pb_arr)):
            if pb_arr[i]:
                count += 1
            else:
                count = 0
            dur_arr[i] = count
        df['pullback_duration_bars'] = dur_arr

        # ── Failed pullback label (for candles_since_failure lookup) ───────
        tdir = df['trend_dir_encoded'].values
        ep   = df['pb_exhaust_prob'].fillna(1.0).values
        dur  = df['pullback_duration_bars'].values
        df['fpb_label'] = (
            (tdir == -1) &
            (ep < _FAILURE_THRESHOLD) &
            (dur >= _MIN_PERSISTENCE)
        ).astype(int)

        # ── Multi-TF context features ──────────────────────────────────────
        peak_pd = (
            df['trend_prob_down'].rolling(10, min_periods=3).max().shift(1)
        )
        df['trend_conviction_delta'] = peak_pd - df['trend_prob_down']

        d1_dir    = df.get('d1_trend_dir_encoded', pd.Series(np.nan, index=df.index))
        d1_prob_up = df.get('d1_trend_prob_up',    pd.Series(np.nan, index=df.index))
        w1_dir    = df.get('w1_trend_dir_encoded', pd.Series(np.nan, index=df.index))
        h4_dir    = df['trend_dir_encoded']

        if d1_dir.notna().any():
            agreement = np.where(
                d1_dir.isna(), 0,
                np.where(d1_dir == -1, 1, np.where(d1_dir == 1, -1, 0))
            )
        else:
            agreement = np.zeros(len(df))

        df['d1_trend_agreement']    = agreement.astype(float)
        df['d1_prob_against_trend'] = d1_prob_up.values
        df['w1_d1_h4_alignment_score'] = (
            np.where(w1_dir.isna(), 0, w1_dir.values.astype(float))
            + np.where(d1_dir.isna(), 0, d1_dir.values.astype(float))
            + h4_dir.values.astype(float)
        )

        df['exhaust_prob_slope'] = df['pb_exhaust_prob'].diff(3)

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # H4 context extraction
    # ─────────────────────────────────────────────────────────────────────────

    def _get_h4_context(
        self, h4: pd.DataFrame, current_h1_ts: pd.Timestamp
    ) -> dict:
        """Extract H4 context dict for the latest H4 bar at or before current_h1_ts."""
        neutral = {
            'h4_fpb_label': 0, 'h4_trend_dir_encoded': 0,
            'h4_trend_prob_up': 1/3, 'h4_trend_prob_down': 1/3,
            'h4_pb_exhaust_prob': 1.0, 'h4_exhaust_prob_slope': 0.0,
            'h4_pullback_duration_bars': 0,
            'h4_trend_conviction_delta': 0.0,
            'h4_d1_trend_agreement': 0.0, 'h4_d1_prob_against_trend': 1/3,
            'h4_w1_d1_h4_alignment_score': 0.0,
            '_fpb_condition_met': False,
        }

        if h4 is None or len(h4) == 0:
            return neutral

        if 'timestamp' in h4.columns:
            h4 = h4.copy()
            h4['timestamp'] = pd.to_datetime(h4['timestamp'])
            valid = h4[h4['timestamp'] <= current_h1_ts]
            row = valid.iloc[-1] if len(valid) > 0 else h4.iloc[-1]
        else:
            row = h4.iloc[-1]

        tdir     = int(row.get('trend_dir_encoded', 0))
        ep       = float(row.get('pb_exhaust_prob', 1.0) or 1.0)
        dur      = int(row.get('pullback_duration_bars', 0))
        fpb_lbl  = int(row.get('fpb_label', 0))

        condition_met = (
            tdir == -1 and
            ep < _FAILURE_THRESHOLD and
            dur >= _MIN_PERSISTENCE
        )

        return {
            'h4_fpb_label':               fpb_lbl,
            'h4_trend_dir_encoded':       tdir,
            'h4_trend_prob_up':           float(row.get('trend_prob_up',   1/3) or 1/3),
            'h4_trend_prob_down':         float(row.get('trend_prob_down', 1/3) or 1/3),
            'h4_pb_exhaust_prob':         ep,
            'h4_exhaust_prob_slope':      float(row.get('exhaust_prob_slope', 0.0) or 0.0),
            'h4_pullback_duration_bars':  dur,
            'h4_trend_conviction_delta':  float(row.get('trend_conviction_delta', 0.0) or 0.0),
            'h4_d1_trend_agreement':      float(row.get('d1_trend_agreement', 0.0) or 0.0),
            'h4_d1_prob_against_trend':   float(row.get('d1_prob_against_trend', 1/3) or 1/3),
            'h4_w1_d1_h4_alignment_score':float(row.get('w1_d1_h4_alignment_score', 0.0) or 0.0),
            '_fpb_condition_met':         condition_met,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # candles_since_failure
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_candles_since_failure(
        self, h4: pd.DataFrame, h1: pd.DataFrame, max_candles: int = 20
    ) -> float:
        """Count H1 bars since the most recent H4 failed pullback bar (fpb_label == 1)."""
        if 'fpb_label' not in h4.columns or 'timestamp' not in h4.columns:
            return float(max_candles + 1)

        failed_bars = h4[h4['fpb_label'] == 1]
        if len(failed_bars) == 0:
            return float(max_candles + 1)

        last_ts = pd.to_datetime(failed_bars['timestamp'].iloc[-1])
        h1_ts   = pd.to_datetime(h1['timestamp'])
        return float(min(int((h1_ts > last_ts).sum()), max_candles + 1))

    def _compute_bars_since_pb_start(
        self, h4: pd.DataFrame, h1: pd.DataFrame, max_candles: int = 30
    ) -> float:
        """H1 bars since the H4 pullback streak first became active."""
        if 'pb_active' not in h4.columns or 'timestamp' not in h4.columns:
            return float(max_candles + 1)

        pb_arr = h4['pb_active'].values
        ts_arr = pd.to_datetime(h4['timestamp'].values)

        # Walk backwards to find start of current pb_active streak
        start_ts = None
        for i in range(len(pb_arr) - 1, -1, -1):
            if pb_arr[i]:
                start_ts = ts_arr[i]
            else:
                break

        if start_ts is None:
            return float(max_candles + 1)

        h1_ts = pd.to_datetime(h1['timestamp'])
        return float(min(int((h1_ts > start_ts).sum()), max_candles + 1))

    # ─────────────────────────────────────────────────────────────────────────
    # H1 feature computation
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_h1_features(self, h1: pd.DataFrame, h4_ctx: dict) -> dict:
        """
        Compute all H1-level features for the latest bar.
        Requires H1 history for slope/momentum/consecutive-bar features.
        """
        df = h1.copy()

        # ── Candle structure ───────────────────────────────────────────────
        candle_range = (df['high'] - df['low']).replace(0, np.nan)
        body = (df['close'] - df['open']).abs()
        df['close_location']   = (df['close'] - df['low']) / candle_range
        df['upper_wick_ratio'] = (
            df['high'] - df[['open', 'close']].max(axis=1)
        ) / candle_range
        df['lower_wick_ratio'] = (
            df[['open', 'close']].min(axis=1) - df['low']
        ) / candle_range
        atr_abs = (df['atr_pct'] * df['close']).replace(0, np.nan)
        df['body_size_atr']    = body / atr_abs

        # ── Long-side BB features (not in live EA CSV) ─────────────────────
        if 'lower_band' in df.columns:
            df['bb_touch_strength_long'] = (
                df['lower_band'] / df['low'].replace(0, np.nan)
            )
        else:
            df['bb_touch_strength_long'] = 0.0

        lower_wick = (df[['open', 'close']].min(axis=1) - df['low']).clip(lower=0)
        df['candle_rejection_long'] = lower_wick / body.replace(0, np.nan)

        if 'rsi_value' in df.columns:
            df['rsi_divergence_long'] = (
                (df['low'] < df['low'].shift(5)) &
                (df['rsi_value'] > df['rsi_value'].shift(5))
            ).astype(int)
        else:
            df['rsi_divergence_long'] = 0

        df['price_momentum_long'] = (
            (df['low'] - df['low'].shift(1)) /
            df['low'].shift(1).replace(0, np.nan)
        ) * 100.0

        if 'lower_band' in df.columns:
            df['_long_touch'] = (df['low'] <= df['lower_band']).astype(int)
            df['previous_touches_long'] = (
                df['_long_touch']
                .rolling(_TOUCH_LOOKBACK, min_periods=_TOUCH_LOOKBACK)
                .sum()
            )
        else:
            df['previous_touches_long'] = 0.0

        tst_long = np.full(len(df), 999, dtype=float)
        if 'lower_band' in df.columns:
            touched = (df['low'] <= df['lower_band']).values
            for i in range(len(df)):
                for j in range(i, -1, -1):
                    if touched[j]:
                        tst_long[i] = i - j
                        break
        df['time_since_last_touch_long'] = tst_long

        # ── RSI momentum features ──────────────────────────────────────────
        if 'rsi_value' in df.columns:
            df['rsi_slope_5'] = df['rsi_value'].diff(5)
            df['rsi_above_50'] = (df['rsi_value'] > 50).astype(float)
        else:
            df['rsi_slope_5'] = 0.0
            df['rsi_above_50'] = 0.0

        # ── BB position slope ──────────────────────────────────────────────
        if 'bb_position' in df.columns:
            df['bb_pos_slope_3'] = df['bb_position'].diff(3)
        else:
            df['bb_pos_slope_3'] = 0.0

        # ── Price structure ────────────────────────────────────────────────
        df['h1_higher_low'] = (df['low'] > df['low'].shift(1)).astype(float)
        df['h1_new_high_3'] = (
            df['close'] > df['high'].shift(1).rolling(3, min_periods=1).max()
        ).astype(float)

        # Consecutive bullish bars
        is_bull = (df['close'] > df['open']).astype(int).values
        consec  = np.zeros(len(is_bull), dtype=np.float32)
        count   = 0
        for i in range(len(is_bull)):
            count = count + 1 if is_bull[i] else 0
            consec[i] = count
        df['h1_consecutive_bull'] = consec

        # Volume surge
        if 'volume_ratio' in df.columns:
            df['h1_volume_surge'] = (df['volume_ratio'] > 1.5).astype(float)
        else:
            df['h1_volume_surge'] = 0.0

        # ── RSI divergence from trend ──────────────────────────────────────
        tdir = h4_ctx.get('h4_trend_dir_encoded', 0)
        if 'rsi_value' in df.columns:
            rsi_slope3 = df['rsi_value'].diff(3)
            df['h1_rsi_divergence_from_trend'] = (
                (rsi_slope3 > 0) & (tdir == -1)
            ).astype(float)
        else:
            df['h1_rsi_divergence_from_trend'] = 0.0

        # ── Extract latest bar ─────────────────────────────────────────────
        latest = df.iloc[-1]
        return {
            'close_location':               float(latest.get('close_location', 0.0) or 0.0),
            'upper_wick_ratio':             float(latest.get('upper_wick_ratio', 0.0) or 0.0),
            'lower_wick_ratio':             float(latest.get('lower_wick_ratio', 0.0) or 0.0),
            'body_size_atr':                float(latest.get('body_size_atr', 0.0) or 0.0),
            'bb_touch_strength_long':       float(latest.get('bb_touch_strength_long', 0.0) or 0.0),
            'candle_rejection_long':        float(latest.get('candle_rejection_long', 0.0) or 0.0),
            'rsi_divergence_long':          float(latest.get('rsi_divergence_long', 0.0) or 0.0),
            'price_momentum_long':          float(latest.get('price_momentum_long', 0.0) or 0.0),
            'previous_touches_long':        float(latest.get('previous_touches_long', 0.0) or 0.0),
            'time_since_last_touch_long':   float(latest.get('time_since_last_touch_long', 999.0) or 999.0),
            'rsi_slope_5':                  float(latest.get('rsi_slope_5', 0.0) or 0.0),
            'rsi_above_50':                 float(latest.get('rsi_above_50', 0.0) or 0.0),
            'bb_pos_slope_3':               float(latest.get('bb_pos_slope_3', 0.0) or 0.0),
            'h1_higher_low':                float(latest.get('h1_higher_low', 0.0) or 0.0),
            'h1_new_high_3':                float(latest.get('h1_new_high_3', 0.0) or 0.0),
            'h1_consecutive_bull':          float(latest.get('h1_consecutive_bull', 0.0) or 0.0),
            'h1_volume_surge':              float(latest.get('h1_volume_surge', 0.0) or 0.0),
            'h1_rsi_divergence_from_trend': float(latest.get('h1_rsi_divergence_from_trend', 0.0) or 0.0),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Trend model inference (mirrors PullBackFeatureEngineer._get_trend_pred)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_trend_pred(
        self, df: Optional[pd.DataFrame], tf: str, sym: str
    ) -> Optional[pd.DataFrame]:
        if df is None or len(df) < 260 or not _TI_AVAILABLE:
            return None

        predictor = FailedPBReversalLongFeatureEngineer._trend_predictors.get(tf)
        if predictor is None:
            return None

        try:
            ohlcv = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
            ohlcv = ohlcv.rename(columns={'timestamp': 'time', 'volume': 'tick_volume'})
            ohlcv = ohlcv.sort_values('time').reset_index(drop=True)

            atr          = compute_atr(ohlcv, period=14)
            features_df  = compute_quant_v2_features(
                ohlcv, timeframe=tf, atr=atr, feature_subset='full'
            )

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
                missing = [c for c in feature_cols if c not in features_df.columns]
                for c in missing:
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
                probs = predictor.model.predict_proba(X)   # [down, sideways, up]

                pred_cls = np.where(
                    probs[:, 2] > probs[:, 0],
                    np.where(probs[:, 2] > probs[:, 1], 'uptrend',   'sideways'),
                    np.where(probs[:, 0] > probs[:, 1], 'downtrend', 'sideways'),
                )
                results['predicted_class'][valid_idx] = pred_cls
                results['prob_up'][valid_idx]         = probs[:, 2]
                results['prob_down'][valid_idx]       = probs[:, 0]
                results['model_valid'][valid_idx]     = True

            return pd.DataFrame(results, index=df.index)

        except Exception as exc:
            logger.error(
                f"[FPBRevLongFE] Trend model {tf} failed for {sym}: {exc}",
                exc_info=True
            )
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # CSV loading
    # ─────────────────────────────────────────────────────────────────────────

    def _load_tf_csv(self, tf: str) -> Optional[pd.DataFrame]:
        if tf in self._csv_cache:
            return self._csv_cache[tf]

        tf_cfg = TIMEFRAMES.get(tf)
        if tf_cfg is None:
            logger.warning(f"[FPBRevLongFE] No TIMEFRAMES config for {tf}")
            return None

        csv_path = MQL5_FILES_DIR / tf_cfg.csv_filename
        if not csv_path.exists():
            logger.warning(f"[FPBRevLongFE] {tf} CSV not found: {csv_path}")
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
            logger.error(f"[FPBRevLongFE] Failed to load {tf} CSV: {exc}")
            return None

    @staticmethod
    def _filter_symbol(df: Optional[pd.DataFrame], sym: str) -> Optional[pd.DataFrame]:
        if df is None:
            return None
        sym_col  = 'symbol' if 'symbol' in df.columns else 'pair'
        filtered = df[df[sym_col] == sym].copy()
        filtered = filtered.sort_values('timestamp').reset_index(drop=True)
        return filtered if len(filtered) > 0 else None

    # ─────────────────────────────────────────────────────────────────────────
    # Model loading
    # ─────────────────────────────────────────────────────────────────────────

    def _load_pb_model(self):
        if FailedPBReversalLongFeatureEngineer._pb_model is not None:
            return
        if not _PB_MODEL_PATH.exists():
            logger.error(f"[FPBRevLongFE] PB model not found: {_PB_MODEL_PATH}")
            return
        try:
            pkg = joblib.load(_PB_MODEL_PATH)
            FailedPBReversalLongFeatureEngineer._pb_model        = pkg['model']
            FailedPBReversalLongFeatureEngineer._pb_feature_cols = pkg.get('feature_cols', [])
            logger.info(
                f"[FPBRevLongFE] PB model loaded — "
                f"features={len(FailedPBReversalLongFeatureEngineer._pb_feature_cols)}"
            )
        except Exception as exc:
            logger.error(f"[FPBRevLongFE] Failed to load PB model: {exc}")

    def _load_trend_models(self):
        if not _TI_AVAILABLE:
            return
        for tf, model_path in _TREND_MODEL_PATHS.items():
            if tf in FailedPBReversalLongFeatureEngineer._trend_predictors:
                continue
            if not model_path.exists():
                logger.warning(f"[FPBRevLongFE] Trend model {tf} not found: {model_path}")
                continue
            try:
                predictor = LiveTrendPredictor.from_package(str(model_path))
                FailedPBReversalLongFeatureEngineer._trend_predictors[tf] = predictor
                logger.info(f"[FPBRevLongFE] Trend model {tf} loaded from {model_path}")
            except Exception as exc:
                logger.error(f"[FPBRevLongFE] Failed to load trend model {tf}: {exc}")
