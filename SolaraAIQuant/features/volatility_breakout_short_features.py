"""
Solara AI Quant — Volatility Breakout SHORT Feature Engineer
=============================================================

Runs the 2-stage Volatility Breakout pipeline at inference time for SHORT entries.

Strategy overview:
  Market "coils" (compresses) in a tight ATR/BB/range zone on H4, then breaks
  decisively downward. We enter SHORT at the moment of confirmed breakout.

Stage 1 — Compression detection (H4, rule-based, inlined from training project):
  ALL of:
    ATR < 15th-percentile of last 20 H4 bars
    BB width < 0.03
    High-low range of last 15 H4 bars < 4.0 × ATR

Stage 2 — Breakout classifier (H1, XGBoost 3-class):
  Fires when current H1 bar:
    - Falls inside an active compression zone
    - Close < comp_lower − 0.3 × ATR_H1  (excursion gate)
    - breakout_prob_valid >= bc['threshold'] (0.50)

Gate column: _vb_break_detected (bool)
  True only when excursion + breakout model both confirm.
  The predictor (VolatilityBreakoutEntryShortPredictor) gates on this before
  running the entry model.

Output: all 52 breakout features + 5 entry-specific features + gate columns.
  The entry model selects from em['feature_cols'] (57 features).

Trigger TF: H1 — fires on every H1 bar close.
H4/D1/W1 CSVs are loaded directly for compression detection and trend context.

Trend features are SOFT only — the model fires in any trend regime.
D1/W1 trend probabilities included as features but not as hard gates.

Model files:
  Models/breakout_H1_short.joblib  — Stage 2 breakout classifier (loaded here)
  Models/entry_breakout_H1_short.joblib — Stage 3 entry model (loaded by predictor)

Magic number: 700301  (XX=70 VolBreakout, YY=03 H1, ZZ=01 Short)

Walk-forward validation (5 folds, 2003-2021, 28 pairs):
  Mean EV/trade: +8.0 pips | Win rate: 35.0% | Break-even: 25.0%
  All 5 folds positive after 2-pip costs.
  EURGBP excluded (17.9% raw WR, 7pp below break-even).
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

# ── Vendor: forex_trend_model ────────────────────────────────────────────────
_SAQ_ROOT   = Path(__file__).resolve().parent.parent
_VENDOR_DIR = _SAQ_ROOT / 'vendor'
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

try:
    from forex_trend_model.inference.live_pipeline import LiveTrendPredictor
    from forex_trend_model.features.pipeline import compute_atr
    from forex_trend_model.features.quant_v2 import compute_quant_v2_features
    _TI_AVAILABLE = True
    logger.info("[VBShortFE] Trend Identifier package loaded")
except ImportError as _e:
    _TI_AVAILABLE = False
    logger.critical(
        f"[VBShortFE] Cannot import forex_trend_model: {_e}. "
        f"Copy the package into {_VENDOR_DIR}/"
    )

# ── Model paths ───────────────────────────────────────────────────────────────
_TREND_MODEL_PATHS = {
    'H4': _SAQ_ROOT / 'Models' / 'trend_identifier' / 'short' / 'Trend_Identifier_H4.joblib',
    'D1': _SAQ_ROOT / 'Models' / 'trend_identifier' / 'short' / 'Trend_Identifier_D1.joblib',
    'W1': _SAQ_ROOT / 'Models' / 'trend_identifier' / 'short' / 'Trend_Identifier_W1.joblib',
}
_BREAKOUT_MODEL_PATH = MODELS_DIR / 'breakout_H1_short.joblib'

# ── Compression detection defaults (grid-search locked values) ────────────────
_COMP_ATR_PERCENTILE  = 15     # ATR must be below 15th percentile
_COMP_ATR_LOOKBACK    = 20     # trailing window (H4 bars) for ATR percentile
_COMP_RANGE_WINDOW    = 15     # rolling high-low range window (H4 bars)
_COMP_RANGE_TIGHTNESS = 4.0    # range must be < 4.0 × ATR (min valid: 3.0)
_COMP_MIN_DURATION    = 3      # minimum consecutive compressed H4 bars
_COMP_BB_THRESHOLD    = 0.03   # BB width must be < 3%
_COMP_EXPIRY_MULT     = 2.0    # zone stays active for 2× its duration after ending

# ── Breakout gate default ─────────────────────────────────────────────────────
_EXCURSION_K = 0.3   # close must be > 0.3 × ATR below comp_lower

# ── Minimum H4 bars for trend model warmup ────────────────────────────────────
_MIN_TF_BARS = 260

# ── Full feature candidate list (superset of bc['feature_cols'] + em extras) ──
# Predictor uses em['feature_cols'] to select exactly what the entry model needs.
_ALL_FEATURE_CANDIDATES = [
    # Volatility
    "atr_percentile_rank", "bb_width_norm", "rolling_std_norm", "vol_expansion",
    # Compression metadata
    "comp_duration", "comp_tightness", "comp_range_atr", "comp_atr_pct", "comp_bb_width",
    "dist_to_lower", "dist_to_upper",
    # Breakout candle
    "excursion_atr", "body_ratio", "close_position", "breakout_candle_size", "close_vs_boundary",
    # Momentum
    "roc_3", "roc_5", "momentum_acceleration", "consecutive_bearish",
    # Trend soft features
    "trend_dir_h4", "trend_dir_d1", "trend_dir_w1", "trend_alignment",
    # Standard technicals (from H1 EA CSV — passed through)
    "rsi_value", "atr_pct", "atr",
    "lower_band", "middle_band", "upper_band", "bb_position", "bb_width_pct",
    "volume_ratio", "candle_body_pct",
    "trend_strength", "price_momentum", "price_momentum_long",
    "prev_candle_body_pct", "prev_volume_ratio", "gap_from_prev_close",
    "bb_touch_strength", "candle_rejection", "rsi_divergence",
    "prev_was_rally", "previous_touches", "time_since_last_touch",
    "resistance_distance_pct",
    "prev_was_selloff",
    # Session (one-hot encoded)
    "session_london", "session_new_york", "session_asian", "session_other",
    # Entry model extras (Stage 3 — added after breakout model confirms)
    "breakout_prob_valid", "breakout_prob_false", "breakout_prob_no_setup",
    "candles_since_breakout", "post_breakout_momentum",
]


class VolatilityBreakoutShortFeatureEngineer(BaseFeatureEngineer):
    """
    Feature engineer for the Volatility Breakout SHORT strategy.

    Fires on H1 bar closes. For each symbol:
      1. Load H4 bars → detect compression zones (rule-based, inlined from training)
      2. Check if current H1 bar falls inside an active zone + excursion gate
      3. Compute 52 breakout features (volatility, compression metadata, candle,
         momentum, session, trend direction soft features)
      4. Run breakout model → if breakout_prob_valid >= threshold:
           - Add 5 entry-specific features (breakout probs + inference-time zeros)
           - Set _vb_break_detected = True
      5. Return one row per symbol

    The predictor (VolatilityBreakoutEntryShortPredictor) gates on _vb_break_detected
    and runs the entry model on em['feature_cols'] (57 features).
    """

    # ── Class-level caches (shared across all instances, loaded once) ─────────
    _trend_predictors: dict = {}
    _bc_package:       dict = {}      # full joblib dict for breakout model
    _bc_feature_cols:  list = []
    _bc_threshold:     float = 0.5

    # ── Per-compute() CSV cache ───────────────────────────────────────────────
    _csv_cache: dict = {}

    def __init__(self, config=None):
        # Compression params — read from registry config if provided, else locked defaults
        self._atr_percentile  = int(getattr(config,   'vb_atr_percentile',  _COMP_ATR_PERCENTILE))
        self._atr_lookback    = int(getattr(config,   'vb_atr_lookback',    _COMP_ATR_LOOKBACK))
        self._range_window    = int(getattr(config,   'vb_range_window',    _COMP_RANGE_WINDOW))
        self._range_tightness = float(getattr(config, 'vb_range_tightness', _COMP_RANGE_TIGHTNESS))
        self._min_duration    = int(getattr(config,   'vb_min_duration',    _COMP_MIN_DURATION))
        self._bb_threshold    = float(getattr(config, 'vb_bb_threshold',    _COMP_BB_THRESHOLD))
        self._expiry_mult     = float(getattr(config, 'vb_expiry_mult',     _COMP_EXPIRY_MULT))
        self._excursion_k     = float(getattr(config, 'vb_excursion_k',     _EXCURSION_K))

        self._load_breakout_model()
        self._load_trend_models()

    # ─────────────────────────────────────────────────────────────────────────
    # BaseFeatureEngineer contract
    # ─────────────────────────────────────────────────────────────────────────

    def get_required_input_columns(self) -> List[str]:
        """H1 trigger CSV columns consumed by this FE."""
        return [
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'bb_position', 'bb_width_pct', 'lower_band', 'middle_band', 'upper_band',
            'rsi_value', 'volume_ratio', 'atr_pct',
            'candle_body_pct', 'trend_strength', 'price_momentum',
            'prev_candle_body_pct', 'prev_volume_ratio', 'gap_from_prev_close',
            'bb_touch_strength', 'candle_rejection', 'rsi_divergence',
            'prev_was_rally', 'previous_touches', 'time_since_last_touch',
            'resistance_distance_pct', 'prev_was_selloff', 'session',
        ]

    def get_output_features(self) -> List[str]:
        """All candidate features + gate + close (predictor reads both)."""
        return _ALL_FEATURE_CANDIDATES + ['_vb_break_detected', 'close']

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main entry point. Receives the H1 trigger DataFrame (all symbols, ~350 bars each).
        Returns one row per symbol with all computed features + gate column.
        """
        if not _TI_AVAILABLE:
            logger.error("[VBShortFE] Trend Identifier not available — skipping all symbols")
            return pd.DataFrame()

        if VolatilityBreakoutShortFeatureEngineer._bc_package is None:
            logger.error("[VBShortFE] Breakout model not loaded — skipping all symbols")
            return pd.DataFrame()

        # Normalise column names
        h1_all = df.copy()
        if 'pair' in h1_all.columns and 'symbol' not in h1_all.columns:
            h1_all = h1_all.rename(columns={'pair': 'symbol'})
        h1_all['timestamp'] = pd.to_datetime(h1_all['timestamp'])

        # Load secondary timeframes
        self._csv_cache = {}
        h4_all = self._load_tf_csv('H4')
        d1_all = self._load_tf_csv('D1')
        w1_all = self._load_tf_csv('W1')

        if h4_all is None:
            logger.error("[VBShortFE] H4 CSV not found — cannot detect compression zones")
            return pd.DataFrame()

        symbols = h1_all['symbol'].dropna().unique()
        rows = []
        for sym in symbols:
            try:
                row = self._compute_for_symbol(h1_all, h4_all, d1_all, w1_all, sym)
                if row is not None:
                    rows.append(row)
            except Exception as exc:
                logger.error(f"[VBShortFE] {sym} failed: {exc}", exc_info=True)

        if not rows:
            logger.debug(f"[VBShortFE] compute() produced 0 signal rows from {len(symbols)} symbols")
            return pd.DataFrame()

        return pd.DataFrame(rows)

    # ─────────────────────────────────────────────────────────────────────────
    # Per-symbol pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_for_symbol(
        self,
        h1_all: pd.DataFrame,
        h4_all: pd.DataFrame,
        d1_all: Optional[pd.DataFrame],
        w1_all: Optional[pd.DataFrame],
        sym: str,
    ) -> Optional[dict]:

        # ── 1. Current H1 bar ─────────────────────────────────────────────
        h1 = self._filter_symbol(h1_all, sym, 'timestamp')
        if h1 is None or len(h1) == 0:
            return None

        curr = h1.iloc[-1]
        curr_ts    = pd.Timestamp(curr['timestamp'])
        close_val  = float(curr['close'])
        h1_atr_pct = float(curr.get('atr_pct', 0.0) or 0.0)
        h1_atr     = h1_atr_pct / 100.0 * close_val if h1_atr_pct > 0 else 0.0

        # ── 2. H4 data ────────────────────────────────────────────────────
        h4 = self._filter_symbol(h4_all, sym, 'timestamp')
        min_bars = max(self._atr_lookback, self._range_window) + self._min_duration + 10
        if h4 is None or len(h4) < min_bars:
            logger.debug(
                f"[VBShortFE] {sym}: insufficient H4 bars "
                f"({len(h4) if h4 is not None else 0} < {min_bars})"
            )
            return self._null_row(sym, curr, curr_ts)

        # Derive raw ATR for H4 (EA exports atr_pct, not atr)
        h4 = h4.copy()
        if 'atr' not in h4.columns:
            h4['atr'] = h4['atr_pct'] / 100.0 * h4['close']

        # Rename for compression detection (expects 'time', 'pair')
        h4_for_cd = h4.rename(columns={'timestamp': 'time'}).copy()
        h4_for_cd['pair'] = sym
        h4_for_cd = h4_for_cd.sort_values('time').reset_index(drop=True)

        # ── 3. Detect compression zones ───────────────────────────────────
        zones = self._detect_compression_zones(h4_for_cd, sym)

        # ── 4. Find most-recent active zone for current H1 timestamp ─────
        active_zone = None
        for zone in zones:
            # Zone expires: zone_end + comp_duration * expiry_mult H4 bars (×4h each)
            expiry = zone['zone_end'] + pd.Timedelta(
                hours=zone['comp_duration'] * self._expiry_mult * 4
            )
            if zone['zone_end'] <= curr_ts <= expiry:
                # Multiple zones could qualify — keep the most recent (last one wins)
                active_zone = zone

        if active_zone is None:
            logger.debug(f"[VBShortFE] {sym}: no active compression zone at {curr_ts}")
            return self._null_row(sym, curr, curr_ts)

        comp_lower = float(active_zone['comp_lower'])
        comp_upper = float(active_zone['comp_upper'])

        # ── 5. Excursion gate ─────────────────────────────────────────────
        # Close must be > excursion_k × ATR below comp_lower (SHORT direction)
        excursion = comp_lower - close_val
        required_excursion = self._excursion_k * h1_atr

        if excursion < required_excursion:
            logger.debug(
                f"[VBShortFE] {sym}: excursion={excursion:.5f} < "
                f"{self._excursion_k}×ATR={required_excursion:.5f} — skip"
            )
            return self._null_row(sym, curr, curr_ts)

        # ── 6. Trend soft features (H4 / D1 / W1) ────────────────────────
        trend_dir_h4 = self._get_trend_direction(h4, 'H4', sym)
        trend_dir_d1 = self._get_trend_direction(
            self._filter_symbol(d1_all, sym, 'timestamp') if d1_all is not None else None,
            'D1', sym
        )
        trend_dir_w1 = self._get_trend_direction(
            self._filter_symbol(w1_all, sym, 'timestamp') if w1_all is not None else None,
            'W1', sym
        )

        # trend_alignment: ≥ 2/3 of TFs show downtrend (-1)
        down_count     = sum(1 for t in [trend_dir_h4, trend_dir_d1, trend_dir_w1] if t == -1)
        trend_alignment = 1.0 if down_count >= 2 else 0.0

        # ── 7. Compute derived features from H1 history ───────────────────
        n_h1 = len(h1)

        # ATR percentile rank (current ATR vs. last 100 H1 bars)
        h1_atr_series = h1['atr_pct'] / 100.0 * h1['close']
        rl_min = h1_atr_series.rolling(100, min_periods=20).min().iloc[-1]
        rl_max = h1_atr_series.rolling(100, min_periods=20).max().iloc[-1]
        span = (rl_max - rl_min)
        atr_percentile_rank = float(
            np.clip((h1_atr - rl_min) / span * 100, 0, 100)
            if (span and span > 0 and not np.isnan(span)) else 50.0
        )

        # Rolling std of close normalised by ATR (last 20 H1 bars)
        rolling_std = h1['close'].rolling(20, min_periods=5).std().iloc[-1]
        rolling_std_norm = float(rolling_std / h1_atr) if (h1_atr > 0 and not np.isnan(rolling_std)) else 0.0

        # Volatility expansion: current H1 ATR / avg ATR during compression
        comp_atr_val   = float(active_zone.get('comp_atr_val', 0.0) or 0.0)
        vol_expansion  = float(h1_atr / comp_atr_val) if comp_atr_val > 0 else 0.0

        # BB width normalised (from EA CSV bb_width_pct)
        bb_width_pct  = float(curr.get('bb_width_pct', 0.0) or 0.0)
        bb_width_norm = bb_width_pct / 100.0 if bb_width_pct > 0 else 0.0

        # Compression metadata from zone
        comp_duration  = float(active_zone['comp_duration'])
        comp_tightness = float(active_zone.get('comp_tightness', 0.0) or 0.0)
        comp_atr_pct   = float(active_zone.get('comp_atr_pct',   0.0) or 0.0)
        comp_bb_width  = float(active_zone.get('comp_bb_width',  0.0) or 0.0)
        comp_range_atr = float(active_zone.get('comp_range_atr', 0.0) or 0.0)

        # Distance features (normalised by H1 ATR)
        atr_safe = h1_atr if h1_atr > 0 else 1e-8
        dist_to_lower    = (close_val - comp_lower) / atr_safe   # negative for breakout
        dist_to_upper    = (comp_upper - close_val) / atr_safe   # positive
        excursion_atr    = excursion / atr_safe                   # positive for valid breakout
        close_vs_boundary = (close_val - comp_lower) / atr_safe  # negative = same as dist_to_lower

        # Candle anatomy
        h1_open = float(curr['open'])
        h1_high = float(curr['high'])
        h1_low  = float(curr['low'])
        candle_range  = max(h1_high - h1_low, 1e-8)
        body_ratio           = abs(close_val - h1_open) / candle_range
        close_position       = (close_val - h1_low) / candle_range
        breakout_candle_size = candle_range / atr_safe

        # Rate of change (from H1 history)
        close_3ago = float(h1.iloc[-4]['close']) if n_h1 >= 4 else close_val
        close_5ago = float(h1.iloc[-6]['close']) if n_h1 >= 6 else close_val
        roc_3 = (close_val - close_3ago) / close_3ago if close_3ago != 0 else 0.0
        roc_5 = (close_val - close_5ago) / close_5ago if close_5ago != 0 else 0.0
        momentum_acceleration = roc_3 - roc_5

        # Consecutive bearish candles leading into current bar (not including current bar)
        consecutive_bearish = 0
        for i in range(n_h1 - 2, max(n_h1 - 22, -1), -1):
            row_i = h1.iloc[i]
            if float(row_i['close']) < float(row_i['open']):
                consecutive_bearish += 1
            else:
                break

        # Session (one-hot)
        session_val      = float(curr.get('session', 0) or 0)
        session_london   = 1.0 if session_val == 1 else 0.0
        session_new_york = 1.0 if session_val == 2 else 0.0
        session_asian    = 1.0 if session_val == 3 else 0.0
        session_other    = 1.0 if session_val not in [1, 2, 3] else 0.0

        # ── 8. EA indicator pass-through helper ───────────────────────────
        def _g(col: str, default: float = 0.0) -> float:
            val = curr.get(col, default)
            if val is None:
                return default
            try:
                fv = float(val)
                return default if np.isnan(fv) else fv
            except (TypeError, ValueError):
                return default

        # ── 9. Assemble full feature dict ─────────────────────────────────
        features: dict = {
            # Volatility
            "atr_percentile_rank":   atr_percentile_rank,
            "bb_width_norm":         bb_width_norm,
            "rolling_std_norm":      rolling_std_norm,
            "vol_expansion":         vol_expansion,
            # Compression metadata
            "comp_duration":  comp_duration,
            "comp_tightness": comp_tightness,
            "comp_range_atr": comp_range_atr,
            "comp_atr_pct":   comp_atr_pct,
            "comp_bb_width":  comp_bb_width,
            "dist_to_lower":  dist_to_lower,
            "dist_to_upper":  dist_to_upper,
            # Breakout candle
            "excursion_atr":       excursion_atr,
            "body_ratio":          body_ratio,
            "close_position":      close_position,
            "breakout_candle_size": breakout_candle_size,
            "close_vs_boundary":   close_vs_boundary,
            # Momentum
            "roc_3":                  roc_3,
            "roc_5":                  roc_5,
            "momentum_acceleration":  momentum_acceleration,
            "consecutive_bearish":    float(consecutive_bearish),
            # Trend soft features
            "trend_dir_h4":    float(trend_dir_h4),
            "trend_dir_d1":    float(trend_dir_d1),
            "trend_dir_w1":    float(trend_dir_w1),
            "trend_alignment": trend_alignment,
            # EA indicators (H1 CSV pass-through)
            "rsi_value":               _g('rsi_value'),
            "atr_pct":                 h1_atr_pct,
            "atr":                     h1_atr,
            "lower_band":              _g('lower_band'),
            "middle_band":             _g('middle_band'),
            "upper_band":              _g('upper_band'),
            "bb_position":             _g('bb_position'),
            "bb_width_pct":            bb_width_pct,
            "volume_ratio":            _g('volume_ratio'),
            "candle_body_pct":         _g('candle_body_pct'),
            "trend_strength":          _g('trend_strength'),
            "price_momentum":          _g('price_momentum'),
            "price_momentum_long":     _g('price_momentum_long'),
            "prev_candle_body_pct":    _g('prev_candle_body_pct'),
            "prev_volume_ratio":       _g('prev_volume_ratio'),
            "gap_from_prev_close":     _g('gap_from_prev_close'),
            "bb_touch_strength":       _g('bb_touch_strength'),
            "candle_rejection":        _g('candle_rejection'),
            "rsi_divergence":          _g('rsi_divergence'),
            "prev_was_rally":          _g('prev_was_rally'),
            "previous_touches":        _g('previous_touches'),
            "time_since_last_touch":   _g('time_since_last_touch'),
            "resistance_distance_pct": _g('resistance_distance_pct'),
            "prev_was_selloff":        _g('prev_was_selloff'),
            # Session (one-hot)
            "session_london":   session_london,
            "session_new_york": session_new_york,
            "session_asian":    session_asian,
            "session_other":    session_other,
            # Entry extras (set to 0 by default; overwritten below if breakout confirms)
            "breakout_prob_valid":    0.0,
            "breakout_prob_no_setup": 0.0,
            "breakout_prob_false":    0.0,
            "candles_since_breakout": 0.0,
            "post_breakout_momentum": 0.0,
        }

        # ── 10. Run breakout model ────────────────────────────────────────
        bc_feature_cols = VolatilityBreakoutShortFeatureEngineer._bc_feature_cols
        bc_threshold    = VolatilityBreakoutShortFeatureEngineer._bc_threshold
        bc_pkg          = VolatilityBreakoutShortFeatureEngineer._bc_package

        if not bc_feature_cols or not bc_pkg:
            logger.warning(f"[VBShortFE] {sym}: breakout model not loaded, cannot score")
            return self._null_row(sym, curr, curr_ts)

        X_bc = self._build_row(features, bc_feature_cols)
        if X_bc is None:
            return self._null_row(sym, curr, curr_ts)

        try:
            bc_probs = bc_pkg['model'].predict_proba(X_bc)
            breakout_prob_no_setup = float(bc_probs[0, 0])
            breakout_prob_valid    = float(bc_probs[0, 1])
            breakout_prob_false    = float(bc_probs[0, 2]) if bc_probs.shape[1] > 2 else 0.0
        except Exception as exc:
            logger.error(f"[VBShortFE] {sym}: breakout predict_proba failed: {exc}")
            return self._null_row(sym, curr, curr_ts)

        if breakout_prob_valid < bc_threshold:
            logger.debug(
                f"[VBShortFE] {sym}: breakout_prob_valid={breakout_prob_valid:.3f} "
                f"< {bc_threshold:.3f} — skip"
            )
            return self._null_row(sym, curr, curr_ts)

        # ── Breakout model confirmed — set entry extras and gate ──────────
        features['breakout_prob_valid']    = breakout_prob_valid
        features['breakout_prob_no_setup'] = breakout_prob_no_setup
        features['breakout_prob_false']    = breakout_prob_false
        # candles_since_breakout = 0: we are at the breakout bar (no lookback at inference)
        # post_breakout_momentum = 0: no future price data at inference
        features['candles_since_breakout'] = 0.0
        features['post_breakout_momentum'] = 0.0

        logger.info(
            f"[VBShortFE] {sym}: BREAKOUT DETECTED — "
            f"breakout_prob={breakout_prob_valid:.3f}  "
            f"excursion={excursion_atr:.2f}ATR  "
            f"comp_dur={comp_duration:.0f}H4bars  "
            f"trend_h4={'down' if trend_dir_h4 == -1 else 'sideways' if trend_dir_h4 == 0 else 'up'}  "
            f"alignment={'yes' if trend_alignment else 'no'}  "
            f"close={close_val}"
        )

        return {
            'symbol':             sym,
            'timestamp':          curr_ts,
            'close':              close_val,
            '_vb_break_detected': True,
            **features,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Null row — no breakout detected (predictor gates on _vb_break_detected)
    # ─────────────────────────────────────────────────────────────────────────

    def _null_row(self, sym: str, curr, curr_ts) -> dict:
        row = {
            'symbol':             sym,
            'timestamp':          curr_ts,
            'close':              float(curr.get('close', 0.0)),
            '_vb_break_detected': False,
        }
        for feat in _ALL_FEATURE_CANDIDATES:
            row[feat] = 0.0
        return row

    # ─────────────────────────────────────────────────────────────────────────
    # Compression detection (inlined from training project)
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_compression_zones(self, h4_df: pd.DataFrame, sym: str) -> list:
        """
        Detect H4 compression zones for a single pair.
        h4_df must have columns: time, atr, high, low, close, upper_band/lower_band/middle_band.
        Returns list of zone dicts sorted by zone_end ascending.
        """
        p         = self._atr_percentile
        L         = self._atr_lookback
        N         = self._range_window
        r         = self._range_tightness
        min_dur   = self._min_duration
        bb_thresh = self._bb_threshold

        n = len(h4_df)
        if n < max(L, N) + min_dur:
            return []

        atr   = h4_df['atr'].astype(float)
        high  = h4_df['high'].astype(float)
        low   = h4_df['low'].astype(float)
        close = h4_df['close'].astype(float)
        times = h4_df['time']

        # ── ATR percentile (vectorised rolling quantile) ──
        thresh_p   = atr.shift(1).rolling(L, min_periods=max(5, L // 4)).quantile(p / 100)
        is_low_atr = atr < thresh_p

        # ── Bollinger Band width ──
        bb_col_found = False
        for u_col, l_col, m_col in [
            ('upper_band', 'lower_band', 'middle_band'),
            ('bb_upper',   'bb_lower',   'bb_middle'),
        ]:
            if all(c in h4_df.columns for c in [u_col, l_col, m_col]):
                mid_val  = h4_df[m_col].replace(0, np.nan).astype(float)
                bb_width = (h4_df[u_col].astype(float) - h4_df[l_col].astype(float)) / mid_val
                bb_col_found = True
                break

        if not bb_col_found:
            sma      = close.rolling(20, min_periods=10).mean()
            std      = close.rolling(20, min_periods=10).std()
            bb_width = (4 * std) / sma.replace(0, np.nan)

        is_narrow_bb = bb_width < bb_thresh

        # ── Range tightness (strict min_periods=N — avoids early-window artifacts) ──
        roll_high   = high.rolling(N, min_periods=N).max()
        roll_low    = low.rolling(N,  min_periods=N).min()
        range_ratio = (roll_high - roll_low) / atr.replace(0, np.nan)
        is_tight    = range_ratio < r

        # ── Combined flag ──
        is_compressed = (
            is_low_atr & is_narrow_bb & is_tight
            & is_low_atr.notna() & is_narrow_bb.notna() & is_tight.notna()
        ).values.astype(bool)

        atr_vals         = atr.values
        bb_width_vals    = bb_width.values
        atr_pct_vals     = (atr / thresh_p * 100).values
        range_ratio_vals = range_ratio.values
        times_vals       = times.values

        zones = []
        i = 0
        while i < n:
            if not is_compressed[i]:
                i += 1
                continue
            j = i
            while j < n and is_compressed[j]:
                j += 1
            duration = j - i

            if duration >= min_dur:
                s, e = i, j - 1
                comp_upper = float(high.iloc[s: e + 1].max())
                comp_lower = float(low.iloc[s: e + 1].min())

                comp_atr_pct   = float(np.nanmean(atr_pct_vals[s: e + 1]))
                comp_bb_width  = float(np.nanmean(bb_width_vals[s: e + 1]))
                comp_range_atr = float(np.nanmean(range_ratio_vals[s: e + 1]))
                comp_atr_val   = float(np.nanmean(atr_vals[s: e + 1]))

                # Composite tightness score (lower = tighter = more stored energy)
                comp_tightness = float(
                    (comp_atr_pct   / max(p,         1e-6)) * 0.4
                    + (comp_bb_width  / max(bb_thresh,  1e-6)) * 0.3
                    + (comp_range_atr / max(r,          1e-6)) * 0.3
                )

                zones.append({
                    'pair':           sym,
                    'zone_start':     pd.Timestamp(times_vals[s]),
                    'zone_end':       pd.Timestamp(times_vals[e]),
                    'comp_upper':     comp_upper,
                    'comp_lower':     comp_lower,
                    'comp_duration':  duration,
                    'comp_tightness': comp_tightness,
                    'comp_atr_pct':   comp_atr_pct,
                    'comp_bb_width':  comp_bb_width,
                    'comp_range_atr': comp_range_atr,
                    'comp_atr_val':   comp_atr_val,
                })
            i = j

        return zones

    # ─────────────────────────────────────────────────────────────────────────
    # Trend direction inference
    # ─────────────────────────────────────────────────────────────────────────

    def _get_trend_direction(
        self, df: Optional[pd.DataFrame], tf: str, sym: str
    ) -> int:
        """
        Run trend model for the given TF and return direction integer:
          1  = uptrend
         -1  = downtrend
          0  = sideways / not enough data / model unavailable
        """
        if df is None or len(df) < _MIN_TF_BARS or not _TI_AVAILABLE:
            return 0

        predictor = VolatilityBreakoutShortFeatureEngineer._trend_predictors.get(tf)
        if predictor is None:
            return 0

        try:
            # Derive ATR if missing
            df = df.copy()
            if 'atr' not in df.columns:
                df['atr'] = df['atr_pct'] / 100.0 * df['close']

            ohlcv = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
            ohlcv = ohlcv.rename(columns={'timestamp': 'time', 'volume': 'tick_volume'})
            ohlcv = ohlcv.sort_values('time').reset_index(drop=True)

            atr_vals    = compute_atr(ohlcv, period=14)
            features_df = compute_quant_v2_features(
                ohlcv, timeframe=tf, atr=atr_vals, feature_subset='full'
            )
            features_df['pair_encoded']      = 0
            features_df['base_ccy_encoded']  = 0
            features_df['quote_ccy_encoded'] = 0

            valid_mask = features_df['feature_valid'].values
            if not valid_mask.any():
                return 0

            feature_cols = predictor.feature_cols
            missing = [c for c in feature_cols if c not in features_df.columns]
            for c in missing:
                features_df[c] = 0

            X = features_df.loc[valid_mask, feature_cols].copy()

            # CatBoost integer cast for encoded columns
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

            # Most-probable class for the LAST valid bar
            last_prob = probs[-1]   # [p_down, p_sideways, p_up]
            if last_prob[2] > last_prob[0] and last_prob[2] > last_prob[1]:
                return 1    # uptrend
            elif last_prob[0] > last_prob[2] and last_prob[0] > last_prob[1]:
                return -1   # downtrend
            else:
                return 0    # sideways

        except Exception as exc:
            logger.error(f"[VBShortFE] Trend model {tf} failed for {sym}: {exc}", exc_info=True)
            return 0

    # ─────────────────────────────────────────────────────────────────────────
    # Feature row builder
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_row(features: dict, feature_cols: list) -> Optional[pd.DataFrame]:
        """Build a single-row DataFrame for predict_proba from a feature dict."""
        values = {}
        for col in feature_cols:
            val = features.get(col, 0.0)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                values[col] = 0.0
            else:
                try:
                    values[col] = float(val)
                except (TypeError, ValueError):
                    values[col] = 0.0
        return pd.DataFrame([values])[feature_cols]

    # ─────────────────────────────────────────────────────────────────────────
    # CSV loading helpers (mirroring reversal_short_features.py)
    # ─────────────────────────────────────────────────────────────────────────

    def _load_tf_csv(self, tf: str) -> Optional[pd.DataFrame]:
        """Load a timeframe CSV with per-compute() caching."""
        if tf in self._csv_cache:
            return self._csv_cache[tf]

        tf_cfg = TIMEFRAMES.get(tf)
        if tf_cfg is None:
            logger.warning(f"[VBShortFE] No TIMEFRAMES config for {tf}")
            return None

        csv_path = MQL5_FILES_DIR / tf_cfg.csv_filename
        if not csv_path.exists():
            logger.warning(f"[VBShortFE] {tf} CSV not found: {csv_path}")
            return None

        try:
            df = pd.read_csv(csv_path, parse_dates=['timestamp'])
            if 'pair' in df.columns and 'symbol' not in df.columns:
                df = df.rename(columns={'pair': 'symbol'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            self._csv_cache[tf] = df
            logger.debug(f"[VBShortFE] Loaded {tf} CSV: {len(df)} rows")
            return df
        except Exception as exc:
            logger.error(f"[VBShortFE] Failed to load {tf} CSV: {exc}")
            return None

    @staticmethod
    def _filter_symbol(
        df: Optional[pd.DataFrame], sym: str, ts_col: str = 'timestamp'
    ) -> Optional[pd.DataFrame]:
        """Filter DataFrame to a single symbol and sort by timestamp."""
        if df is None:
            return None
        sym_col  = 'symbol' if 'symbol' in df.columns else 'pair'
        filtered = df[df[sym_col] == sym].copy()
        filtered = filtered.sort_values(ts_col).reset_index(drop=True)
        return filtered if len(filtered) > 0 else None

    # ─────────────────────────────────────────────────────────────────────────
    # Model loading (class-level cache — loaded once per process)
    # ─────────────────────────────────────────────────────────────────────────

    def _load_breakout_model(self):
        """Load breakout_H1_short.joblib (Stage 2 classifier)."""
        if VolatilityBreakoutShortFeatureEngineer._bc_package:
            return   # already loaded

        if not _BREAKOUT_MODEL_PATH.exists():
            logger.error(
                f"[VBShortFE] Breakout model not found: {_BREAKOUT_MODEL_PATH}\n"
                f"  Copy breakout_H1_short.joblib from the training project "
                f"models/breakout/ to SAQ/Models/"
            )
            return

        try:
            pkg = joblib.load(_BREAKOUT_MODEL_PATH)
            VolatilityBreakoutShortFeatureEngineer._bc_package      = pkg
            VolatilityBreakoutShortFeatureEngineer._bc_feature_cols = pkg.get('feature_cols', [])
            VolatilityBreakoutShortFeatureEngineer._bc_threshold    = float(pkg.get('threshold', 0.5))
            logger.info(
                f"[VBShortFE] Breakout model loaded — "
                f"threshold={VolatilityBreakoutShortFeatureEngineer._bc_threshold:.3f}  "
                f"features={len(VolatilityBreakoutShortFeatureEngineer._bc_feature_cols)}  "
                f"direction={pkg.get('direction', 'short')}"
            )
        except Exception as exc:
            logger.error(f"[VBShortFE] Failed to load breakout model: {exc}")

    def _load_trend_models(self):
        """Load H4/D1/W1 SHORT trend models into class-level cache."""
        if not _TI_AVAILABLE:
            return
        for tf, model_path in _TREND_MODEL_PATHS.items():
            if tf in VolatilityBreakoutShortFeatureEngineer._trend_predictors:
                continue
            if not model_path.exists():
                logger.warning(f"[VBShortFE] Trend model {tf} not found: {model_path}")
                continue
            try:
                predictor = LiveTrendPredictor.from_package(str(model_path))
                VolatilityBreakoutShortFeatureEngineer._trend_predictors[tf] = predictor
                logger.info(f"[VBShortFE] Trend model {tf} loaded")
            except Exception as exc:
                logger.error(f"[VBShortFE] Failed to load trend model {tf}: {exc}")
