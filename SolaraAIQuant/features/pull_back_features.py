"""
Solara AI Quant — Pull Back Entry Feature Engineer
===================================================

Computes the full feature set for the Pull Back Entry model (entry_H1.joblib).

This is a 3-stage pipeline:
  Stage 1 — Trend Alignment   : W1 + D1 + H4 trend models (≥ 2/3 must agree)
  Stage 2 — Pullback Detector : H4 pullback model (class-2 prob ≥ 0.65)
  Stage 3 — Entry Features    : 37-feature H1 vector for the entry model

Trigger TF: H1
merge_timeframes: []  — this FE loads H4 / D1 / W1 CSVs directly.

Output columns (per symbol, latest H1 bar):
  - All 37 ENTRY_FEATURES
  - _pb_trend_aligned  (bool)  — ≥ 2/3 trend models agree
  - _pb_direction      (str)   — 'uptrend' | 'downtrend' | 'sideways'
  - _pb_exhaust_prob   (float) — pullback model class-2 probability
  - _pb_h4_label       (int)   — pullback model argmax class (0/1/2)
  - symbol             (str)
  - close              (float) — current H1 close (entry price)
  - timestamp          (datetime)

Notes
-----
- `trend_strength` in PULLBACK_FEATURES is the CSV column (SMA-based from EA),
  NOT |prob_up - prob_down|.  This matches what the model was trained on.
- Long-side BB features (bb_touch_strength_long, candle_rejection_long, etc.)
  are not exported by the production EA; they are computed here from OHLCV + BB
  bands using the same logic as the original EA.
- Trend models are loaded from the Pull Back Strategy models directory (same
  forex_trend_model package as TI V2).
- Pullback model is loaded from SAQ's Models/ directory.
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

# ── External package path (same as TI V2) ─────────────────────────────────────
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
    logger.info("[PullBackFE] Trend Identifier package loaded")
except ImportError as _e:
    _TI_AVAILABLE = False
    logger.critical(
        f"[PullBackFE] Cannot import Trend Identifier package: {_e}. "
        f"Check that {_TI_ROOT} exists."
    )

# ── Pull Back Strategy model paths ────────────────────────────────────────────
_PB_STRATEGY_ROOT = Path(
    r"C:\Users\Ben Michael Oracion\Documents\Solara\Model Training\Pull Back Strategy"
)
_TREND_MODEL_PATHS = {
    'H4': _PB_STRATEGY_ROOT / 'models' / 'Trend_Identifier_H4.joblib',
    'D1': _PB_STRATEGY_ROOT / 'models' / 'Trend_Identifier_D1.joblib',
    'W1': _PB_STRATEGY_ROOT / 'models' / 'Trend_Identifier_W1.joblib',
}
_PULLBACK_MODEL_PATH = MODELS_DIR / 'pull_back_pullback_h4.joblib'

# ── Constants (mirror EA values) ──────────────────────────────────────────────
_TOUCH_LOOKBACK  = 20   # matches EA Touch_Lookback
_SWING_WINDOW    = 20   # H4 bars for swing high/low
_MIN_H4_BARS     = 260  # warmup: 250 for trend model + 10 buffer

# ── Entry model feature list (37 features — must match training exactly) ──────
ENTRY_FEATURES = [
    # ── H1 CSV features (25) ──────────────────────────────────────────────────
    'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
    'candle_body_pct', 'atr_pct', 'trend_strength',
    'prev_candle_body_pct', 'prev_volume_ratio', 'gap_from_prev_close',
    'session',
    'bb_touch_strength', 'candle_rejection', 'rsi_divergence',
    'price_momentum', 'prev_was_rally', 'previous_touches', 'time_since_last_touch',
    'bb_touch_strength_long', 'candle_rejection_long', 'rsi_divergence_long',
    'price_momentum_long', 'prev_was_selloff', 'previous_touches_long',
    'time_since_last_touch_long',
    # ── Computed H1 candle structure (3) ──────────────────────────────────────
    'close_location', 'upper_wick_ratio', 'lower_wick_ratio',
    # ── H4 context features (9) ───────────────────────────────────────────────
    'h4_pb_label', 'h4_pb_depth', 'h4_trend_dir',
    'h4_trend_prob_up', 'h4_trend_prob_down',
    'candles_since_exhaustion',
    'h4_pb_prob_trend', 'h4_pb_prob_pullback', 'h4_pb_prob_exhaust',
]


class PullBackFeatureEngineer(BaseFeatureEngineer):
    """
    Feature engineer for the Pull Back Entry model.

    Loads H4 / D1 / W1 CSVs directly (no merge_timeframes needed).
    Runs trend models and the pullback model internally.
    Returns one row per symbol (latest H1 bar) with all 37 entry features
    plus context columns used by the predictor for gating.
    """

    # ── Class-level caches (shared across instances per process) ──────────────
    _trend_predictors: dict  = {}   # tf -> LiveTrendPredictor
    _pb_model        = None
    _pb_feature_cols : list  = []
    _pb_threshold    : float = 0.65

    # ── CSV cache (refreshed each compute() call) ─────────────────────────────
    _csv_cache: dict = {}

    def __init__(self):
        self._load_pullback_model()
        self._load_trend_models()

    # ─────────────────────────────────────────────────────────────────────────
    # BaseFeatureEngineer contract
    # ─────────────────────────────────────────────────────────────────────────

    def get_required_input_columns(self) -> List[str]:
        # Only need the H1 CSV columns (trigger TF)
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
        return ENTRY_FEATURES

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main entry point. Receives the full H1 DataFrame (all symbols).
        Returns one row per symbol with all 37 entry features + context cols.
        """
        if not _TI_AVAILABLE:
            logger.error("[PullBackFE] Trend Identifier not available — skipping")
            return pd.DataFrame()

        if PullBackFeatureEngineer._pb_model is None:
            logger.error("[PullBackFE] Pullback model not loaded — skipping")
            return pd.DataFrame()

        # Normalise symbol column
        df = df.copy()
        if 'pair' in df.columns and 'symbol' not in df.columns:
            df = df.rename(columns={'pair': 'symbol'})
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Load secondary TF CSVs once per compute() call
        self._csv_cache = {}
        h4_all = self._load_tf_csv('H4')
        d1_all = self._load_tf_csv('D1')
        w1_all = self._load_tf_csv('W1')

        if h4_all is None:
            logger.error("[PullBackFE] H4 CSV unavailable — skipping")
            return pd.DataFrame()

        symbols = df['symbol'].dropna().unique()
        rows = []
        for sym in symbols:
            try:
                row = self._compute_for_symbol(df, sym, h4_all, d1_all, w1_all)
                if row is not None:
                    rows.append(row)
            except Exception as exc:
                logger.error(f"[PullBackFE] {sym} failed: {exc}", exc_info=True)

        if not rows:
            return pd.DataFrame()

        result = pd.DataFrame(rows)
        # Ensure all ENTRY_FEATURES are present; fill missing with 0
        for col in ENTRY_FEATURES:
            if col not in result.columns:
                logger.warning(f"[PullBackFE] Missing output feature '{col}' — filling 0")
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
        if len(h1) < 1:
            return None

        # ── 2. Secondary TF data ──────────────────────────────────────────
        h4 = self._filter_symbol(h4_all, sym)
        d1 = self._filter_symbol(d1_all, sym) if d1_all is not None else None
        w1 = self._filter_symbol(w1_all, sym) if w1_all is not None else None

        if h4 is None or len(h4) < _MIN_H4_BARS:
            logger.debug(f"[PullBackFE] {sym}: insufficient H4 bars ({len(h4) if h4 is not None else 0})")
            return None

        # ── 3. Trend models ───────────────────────────────────────────────
        h4_trend_pred = self._get_trend_pred(h4, 'H4', sym)
        d1_trend_pred = self._get_trend_pred(d1, 'D1', sym) if d1 is not None and len(d1) >= _MIN_H4_BARS else None
        w1_trend_pred = self._get_trend_pred(w1, 'W1', sym) if w1 is not None and len(w1) >= 260 else None

        if h4_trend_pred is None:
            logger.debug(f"[PullBackFE] {sym}: H4 trend prediction failed")
            return None

        # ── 4. Trend alignment check ──────────────────────────────────────
        trend_aligned, trend_direction = self._check_alignment(
            h4_trend_pred, d1_trend_pred, w1_trend_pred
        )

        # ── 5. H4 pullback features (last _SWING_WINDOW + buffer bars) ────
        h4_with_pb = self._compute_h4_pullback_features(h4, h4_trend_pred)

        # ── 6. Run pullback model on last N H4 bars ────────────────────────
        #    We need the last ~30 bars to cover candles_since_exhaustion window
        h4_classified = self._run_pullback_model(h4_with_pb, last_n=30)

        # ── 7. Get current H4 context (latest H4 bar before current H1 ts) ─
        current_h1_ts = h1['timestamp'].iloc[-1]
        h4_ctx        = self._get_h4_context(h4_classified, current_h1_ts)

        # ── 8. candles_since_exhaustion ───────────────────────────────────
        cse = self._compute_candles_since_exhaustion(h4_classified, h1, max_candles=20)

        # ── 9. H1 structure + long-side features for latest bar ────────────
        h1_feats = self._compute_h1_features(h1)

        # ── 10. Assemble output row ────────────────────────────────────────
        row: dict = {}

        # H1 CSV features (pass-through from latest bar)
        h1_pass = [
            'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
            'candle_body_pct', 'atr_pct', 'trend_strength',
            'prev_candle_body_pct', 'prev_volume_ratio', 'gap_from_prev_close',
            'session',
            'bb_touch_strength', 'candle_rejection', 'rsi_divergence',
            'price_momentum', 'prev_was_rally', 'previous_touches',
            'time_since_last_touch', 'prev_was_selloff',
        ]
        latest = h1.iloc[-1]
        for col in h1_pass:
            row[col] = float(latest[col]) if col in h1.columns else 0.0

        # Computed H1 features
        row.update(h1_feats)

        # Long-side BB features (computed in _compute_h1_features)
        # (already in h1_feats)

        # H4 context
        row['h4_pb_label']        = h4_ctx['h4_pb_label']
        row['h4_pb_depth']        = h4_ctx['h4_pb_depth']
        row['h4_trend_dir']       = h4_ctx['h4_trend_dir']
        row['h4_trend_prob_up']   = h4_ctx['h4_trend_prob_up']
        row['h4_trend_prob_down'] = h4_ctx['h4_trend_prob_down']
        row['h4_pb_prob_trend']   = h4_ctx['h4_pb_prob_trend']
        row['h4_pb_prob_pullback']= h4_ctx['h4_pb_prob_pullback']
        row['h4_pb_prob_exhaust'] = h4_ctx['h4_pb_prob_exhaust']
        row['candles_since_exhaustion'] = cse

        # Metadata / context cols for predictor
        row['symbol']             = sym
        row['close']              = float(latest['close'])
        row['timestamp']          = latest['timestamp']
        row['_pb_trend_aligned']  = trend_aligned
        row['_pb_direction']      = trend_direction
        row['_pb_exhaust_prob']   = h4_ctx['h4_pb_prob_exhaust']
        row['_pb_h4_label']       = h4_ctx['h4_pb_label']

        return row

    # ─────────────────────────────────────────────────────────────────────────
    # H4 pullback features
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_h4_pullback_features(
        self, h4: pd.DataFrame, trend_pred: pd.DataFrame
    ) -> pd.DataFrame:
        """Compute swing/fib/candle-structure features + merge trend context."""
        df = h4.copy()

        # Candle structure
        candle_range = (df['high'] - df['low']).replace(0, np.nan)
        df['close_location']   = (df['close'] - df['low']) / candle_range
        df['upper_wick_ratio'] = (df['high'] - df[['open', 'close']].max(axis=1)) / candle_range
        df['lower_wick_ratio'] = (df[['open', 'close']].min(axis=1) - df['low']) / candle_range

        # Swing high/low over _SWING_WINDOW bars
        df['swing_high']    = df['high'].rolling(_SWING_WINDOW, min_periods=_SWING_WINDOW).max()
        df['swing_low']     = df['low'].rolling(_SWING_WINDOW, min_periods=_SWING_WINDOW).min()
        df['impulse_range'] = (df['swing_high'] - df['swing_low']).replace(0, np.nan)

        # Fibonacci distance
        for fib, label in [(0.382, '382'), (0.618, '618')]:
            fib_level = df['swing_high'] - fib * df['impulse_range']
            df[f'dist_to_fib{label}'] = (df['close'] - fib_level).abs() / df['impulse_range']

        # Trend context (from H4 trend model)
        df['trend_prob_up']    = trend_pred['prob_up'].values
        df['trend_prob_down']  = trend_pred['prob_down'].values
        df['predicted_class']  = trend_pred['predicted_class'].values
        df['model_valid']      = trend_pred['model_valid'].values

        class_map = {'uptrend': 1, 'downtrend': -1, 'sideways': 0}
        df['trend_dir_encoded'] = (
            df['predicted_class'].map(class_map).fillna(0).astype(int)
        )

        # Direction-aware pullback depth
        df['pb_depth_bull'] = (df['swing_high'] - df['close']) / df['impulse_range']
        df['pb_depth_bear'] = (df['close'] - df['swing_low'])  / df['impulse_range']
        is_bull = df['predicted_class'] == 'uptrend'
        is_bear = df['predicted_class'] == 'downtrend'
        df['pb_depth_pct'] = np.where(
            is_bull, df['pb_depth_bull'],
            np.where(is_bear, df['pb_depth_bear'], np.nan)
        )

        return df.fillna(0)

    # ─────────────────────────────────────────────────────────────────────────
    # Pullback model inference
    # ─────────────────────────────────────────────────────────────────────────

    def _run_pullback_model(self, h4: pd.DataFrame, last_n: int = 30) -> pd.DataFrame:
        """
        Run the H4 pullback model on the last `last_n` bars.
        Adds columns: pb_prob_trend, pb_prob_pullback, pb_prob_exhaust, pb_label.
        Returns the slice DataFrame with those columns added.
        """
        df = h4.tail(last_n).copy().reset_index(drop=True)

        pb_feats = [
            'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
            'candle_body_pct', 'atr_pct', 'trend_strength',
            'prev_candle_body_pct', 'prev_volume_ratio',
            'close_location', 'upper_wick_ratio', 'lower_wick_ratio',
            'dist_to_fib382', 'dist_to_fib618',
            'trend_dir_encoded', 'trend_prob_up', 'trend_prob_down',
        ]

        avail = [f for f in pb_feats if f in df.columns]
        X = df[avail].fillna(0).astype(float)

        try:
            probs = PullBackFeatureEngineer._pb_model.predict_proba(X)
        except Exception as exc:
            logger.error(f"[PullBackFE] Pullback model predict_proba failed: {exc}")
            df['pb_prob_trend']    = 1 / 3
            df['pb_prob_pullback'] = 1 / 3
            df['pb_prob_exhaust']  = 1 / 3
            df['pb_label']         = 0
            return df

        df['pb_prob_trend']    = probs[:, 0]
        df['pb_prob_pullback'] = probs[:, 1]
        df['pb_prob_exhaust']  = probs[:, 2]

        # Apply threshold: class 2 only if prob >= threshold; else argmax of [0,1]
        threshold = PullBackFeatureEngineer._pb_threshold
        labels = np.argmax(probs, axis=1)
        exhaust_mask = probs[:, 2] >= threshold
        labels[exhaust_mask]  = 2
        labels[~exhaust_mask] = np.argmax(probs[~exhaust_mask][:, :2], axis=1)
        df['pb_label'] = labels

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # H4 context for H1 row
    # ─────────────────────────────────────────────────────────────────────────

    def _get_h4_context(
        self, h4_classified: pd.DataFrame, current_h1_ts: pd.Timestamp
    ) -> dict:
        """
        Get the H4 context (latest H4 bar at or before current_h1_ts).
        Falls back to last row if no timestamp check is feasible.
        """
        neutral = {
            'h4_pb_label': 0, 'h4_pb_depth': 0.0,
            'h4_trend_dir': 0, 'h4_trend_prob_up': 1/3,
            'h4_trend_prob_down': 1/3,
            'h4_pb_prob_trend': 1/3, 'h4_pb_prob_pullback': 1/3,
            'h4_pb_prob_exhaust': 1/3,
        }

        if h4_classified is None or len(h4_classified) == 0:
            return neutral

        # Get rows where H4 timestamp <= current H1 timestamp
        if 'timestamp' in h4_classified.columns:
            h4_classified['timestamp'] = pd.to_datetime(h4_classified['timestamp'])
            valid = h4_classified[h4_classified['timestamp'] <= current_h1_ts]
            row = valid.iloc[-1] if len(valid) > 0 else h4_classified.iloc[-1]
        else:
            row = h4_classified.iloc[-1]

        return {
            'h4_pb_label':        int(row.get('pb_label', 0)),
            'h4_pb_depth':        float(row.get('pb_depth_pct', 0.0)),
            'h4_trend_dir':       int(row.get('trend_dir_encoded', 0)),
            'h4_trend_prob_up':   float(row.get('trend_prob_up', 1/3)),
            'h4_trend_prob_down': float(row.get('trend_prob_down', 1/3)),
            'h4_pb_prob_trend':   float(row.get('pb_prob_trend', 1/3)),
            'h4_pb_prob_pullback':float(row.get('pb_prob_pullback', 1/3)),
            'h4_pb_prob_exhaust': float(row.get('pb_prob_exhaust', 1/3)),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # candles_since_exhaustion
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_candles_since_exhaustion(
        self,
        h4_classified: pd.DataFrame,
        h1: pd.DataFrame,
        max_candles: int = 20,
    ) -> float:
        """
        Find the most recent H4 exhaustion bar (pb_label == 2) in the
        classified H4 slice. Count how many H1 candles have passed since
        that H4 bar. Returns max_candles + 1 if no exhaustion found.
        """
        if 'pb_label' not in h4_classified.columns or 'timestamp' not in h4_classified.columns:
            return float(max_candles + 1)

        exhaust_bars = h4_classified[h4_classified['pb_label'] == 2]
        if len(exhaust_bars) == 0:
            return float(max_candles + 1)

        last_exhaust_ts = pd.to_datetime(exhaust_bars['timestamp'].iloc[-1])
        h1_ts = pd.to_datetime(h1['timestamp'])

        # Count H1 bars strictly after the H4 exhaustion bar
        candles_after = int((h1_ts > last_exhaust_ts).sum())
        return float(min(candles_after, max_candles + 1))

    # ─────────────────────────────────────────────────────────────────────────
    # H1 candle features
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_h1_features(self, h1: pd.DataFrame) -> dict:
        """
        Compute computed H1 features and long-side BB features for the latest bar.
        Returns a dict with the relevant keys.
        """
        df = h1.copy()

        # Candle structure (vectorised, for long-side rolling features)
        candle_range = (df['high'] - df['low']).replace(0, np.nan)
        df['close_location']   = (df['close'] - df['low']) / candle_range
        df['upper_wick_ratio'] = (df['high'] - df[['open', 'close']].max(axis=1)) / candle_range
        df['lower_wick_ratio'] = (df[['open', 'close']].min(axis=1) - df['low']) / candle_range

        # Long-side BB touch: lower_band / low  (> 1 when low < lower_band)
        if 'lower_band' in df.columns:
            df['bb_touch_strength_long'] = df['lower_band'] / df['low'].replace(0, np.nan)
        else:
            df['bb_touch_strength_long'] = 0.0

        # Long-side candle rejection: lower_wick / body
        body = (df['close'] - df['open']).abs().replace(0, np.nan)
        lower_wick = (df[['open', 'close']].min(axis=1) - df['low']).clip(lower=0)
        df['candle_rejection_long'] = lower_wick / body

        # Long-side RSI divergence: lower low but higher RSI (bullish divergence)
        if 'rsi_value' in df.columns:
            df['rsi_divergence_long'] = (
                (df['low'] < df['low'].shift(5)) &
                (df['rsi_value'] > df['rsi_value'].shift(5))
            ).astype(int)
        else:
            df['rsi_divergence_long'] = 0

        # Long-side price momentum: (low - prev_low) / prev_low * 100
        df['price_momentum_long'] = (
            (df['low'] - df['low'].shift(1)) / df['low'].shift(1).replace(0, np.nan)
        ) * 100.0

        # Long-side previous touches: bars in last TOUCH_LOOKBACK where low <= lower_band
        if 'lower_band' in df.columns:
            df['_long_touch'] = (df['low'] <= df['lower_band']).astype(int)
            df['previous_touches_long'] = df['_long_touch'].rolling(
                _TOUCH_LOOKBACK, min_periods=_TOUCH_LOOKBACK
            ).sum()
        else:
            df['previous_touches_long'] = 0.0

        # Long-side time since last touch: bars since low <= lower_band
        tst_long = np.full(len(df), 999, dtype=float)
        if 'lower_band' in df.columns:
            touched = (df['low'] <= df['lower_band']).values
            for i in range(len(df)):
                for j in range(i, -1, -1):
                    if touched[j]:
                        tst_long[i] = i - j
                        break
        df['time_since_last_touch_long'] = tst_long

        # Extract latest bar values
        latest = df.iloc[-1]
        return {
            'close_location':          float(latest.get('close_location', 0.0)),
            'upper_wick_ratio':        float(latest.get('upper_wick_ratio', 0.0)),
            'lower_wick_ratio':        float(latest.get('lower_wick_ratio', 0.0)),
            'bb_touch_strength_long':  float(latest.get('bb_touch_strength_long', 0.0)),
            'candle_rejection_long':   float(latest.get('candle_rejection_long', 0.0)),
            'rsi_divergence_long':     float(latest.get('rsi_divergence_long', 0.0)),
            'price_momentum_long':     float(latest.get('price_momentum_long', 0.0)),
            'previous_touches_long':   float(latest.get('previous_touches_long', 0.0)),
            'time_since_last_touch_long': float(latest.get('time_since_last_touch_long', 999.0)),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Trend model
    # ─────────────────────────────────────────────────────────────────────────

    def _get_trend_pred(
        self, df: Optional[pd.DataFrame], tf: str, sym: str
    ) -> Optional[pd.DataFrame]:
        """Run the trend model for the given TF DataFrame. Returns a results DF."""
        if df is None or len(df) < 260 or not _TI_AVAILABLE:
            return None

        predictor = PullBackFeatureEngineer._trend_predictors.get(tf)
        if predictor is None:
            return None

        try:
            ohlcv = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
            ohlcv = ohlcv.rename(columns={'timestamp': 'time', 'volume': 'tick_volume'})
            ohlcv = ohlcv.sort_values('time').reset_index(drop=True)

            atr = compute_atr(ohlcv, period=14)
            features_df = compute_quant_v2_features(
                ohlcv, timeframe=tf, atr=atr, feature_subset='full'
            )

            # Pair encoding: set to 0 (matches pullback_labeler.py behaviour)
            features_df['pair_encoded']      = 0
            features_df['base_ccy_encoded']  = 0
            features_df['quote_ccy_encoded'] = 0

            n = len(ohlcv)
            results = {
                'predicted_class':  np.full(n, 'sideways', dtype=object),
                'prob_up':          np.full(n, 1/3),
                'prob_down':        np.full(n, 1/3),
                'model_valid':      np.zeros(n, dtype=bool),
            }

            valid_mask = features_df['feature_valid'].values
            valid_idx  = np.where(valid_mask)[0]

            if len(valid_idx) > 0:
                feature_cols = predictor.feature_cols
                missing = [c for c in feature_cols if c not in features_df.columns]
                for c in missing:
                    features_df[c] = 0

                X = features_df.loc[valid_mask, feature_cols].copy()

                # CatBoost categorical columns must be int
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
            logger.error(f"[PullBackFE] Trend model {tf} failed for {sym}: {exc}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Trend alignment
    # ─────────────────────────────────────────────────────────────────────────

    def _check_alignment(
        self,
        h4_pred: Optional[pd.DataFrame],
        d1_pred: Optional[pd.DataFrame],
        w1_pred: Optional[pd.DataFrame],
    ) -> tuple[bool, str]:
        """
        Check if ≥ 2/3 trend models agree on a directional (non-sideways) class.
        Returns (aligned: bool, consensus_direction: str).
        """
        preds = []
        for pred in (h4_pred, d1_pred, w1_pred):
            if pred is not None and pred['model_valid'].any():
                # Take the last valid bar's prediction
                valid = pred[pred['model_valid']]
                cls = valid['predicted_class'].iloc[-1]
                preds.append(cls)

        if len(preds) < 2:
            return False, 'sideways'

        up_count   = preds.count('uptrend')
        down_count = preds.count('downtrend')

        if up_count >= 2:
            return True, 'uptrend'
        if down_count >= 2:
            return True, 'downtrend'
        return False, 'sideways'

    # ─────────────────────────────────────────────────────────────────────────
    # CSV loading helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _load_tf_csv(self, tf: str) -> Optional[pd.DataFrame]:
        if tf in self._csv_cache:
            return self._csv_cache[tf]

        tf_cfg = TIMEFRAMES.get(tf)
        if tf_cfg is None:
            logger.warning(f"[PullBackFE] No TIMEFRAMES config for {tf}")
            return None

        csv_path = MQL5_FILES_DIR / tf_cfg.csv_filename
        if not csv_path.exists():
            logger.warning(f"[PullBackFE] {tf} CSV not found: {csv_path}")
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
            logger.error(f"[PullBackFE] Failed to load {tf} CSV: {exc}")
            return None

    @staticmethod
    def _filter_symbol(df: Optional[pd.DataFrame], sym: str) -> Optional[pd.DataFrame]:
        if df is None:
            return None
        sym_col = 'symbol' if 'symbol' in df.columns else 'pair'
        filtered = df[df[sym_col] == sym].copy()
        filtered = filtered.sort_values('timestamp').reset_index(drop=True)
        return filtered if len(filtered) > 0 else None

    # ─────────────────────────────────────────────────────────────────────────
    # Model loading (class-level cache)
    # ─────────────────────────────────────────────────────────────────────────

    def _load_pullback_model(self):
        if PullBackFeatureEngineer._pb_model is not None:
            return
        if not _PULLBACK_MODEL_PATH.exists():
            logger.error(f"[PullBackFE] Pullback model not found: {_PULLBACK_MODEL_PATH}")
            return
        try:
            pkg = joblib.load(_PULLBACK_MODEL_PATH)
            PullBackFeatureEngineer._pb_model        = pkg['model']
            PullBackFeatureEngineer._pb_feature_cols = pkg.get('feature_cols', [])
            PullBackFeatureEngineer._pb_threshold    = float(pkg.get('threshold', 0.65))
            logger.info(
                f"[PullBackFE] Pullback model loaded — "
                f"threshold={PullBackFeatureEngineer._pb_threshold} "
                f"features={len(PullBackFeatureEngineer._pb_feature_cols)}"
            )
        except Exception as exc:
            logger.error(f"[PullBackFE] Failed to load pullback model: {exc}")

    def _load_trend_models(self):
        if not _TI_AVAILABLE:
            return
        for tf, model_path in _TREND_MODEL_PATHS.items():
            if tf in PullBackFeatureEngineer._trend_predictors:
                continue
            if not model_path.exists():
                logger.warning(f"[PullBackFE] Trend model {tf} not found: {model_path}")
                continue
            try:
                predictor = LiveTrendPredictor.from_package(str(model_path))
                PullBackFeatureEngineer._trend_predictors[tf] = predictor
                logger.info(f"[PullBackFE] Trend model {tf} loaded from {model_path}")
            except Exception as exc:
                logger.error(f"[PullBackFE] Failed to load trend model {tf}: {exc}")
