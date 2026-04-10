"""
Solara AI Quant - UBB Rejection Feature Engineer

Builds the exact a_/b_/c_ prefixed feature schema the UBB model was trained on.

Design principle (per functional spec):
    The EA CSV already contains all indicator values (RSI, BB, ATR etc.)
    pre-computed with sufficient history. Do NOT recompute them.
    Only compute features that are genuinely missing from the CSV.

What this class does:
    1. Rename resistance_distance_pct → support_distance_pct
       (EA v2.0 renamed the column but formula is identical)
    2. Sort by timestamp per symbol, validate consecutive A/B/C triplets
    3. Prefix each candle's CSV columns with a_/b_/c_
    4. Compute the 7 Candle A BB-event features not present in the CSV:
       a_bb_event_type, a_bb_event_strength, a_close_above_ubb,
       a_near_upper_bb, a_failed_break_ubb, a_ubb_distance_close,
       a_upper_wick_pct

What this class does NOT do:
    - Does NOT recompute RSI, BB bands, ATR, volume_ratio, trend_strength
      or any other column already present in the EA CSV
"""

import pandas as pd
import numpy as np
from typing import List
import logging

from .base_feature_engineer import BaseFeatureEngineer

logger = logging.getLogger(__name__)

TINY = 1e-10

# EA v2.0 renamed this column — formula is identical, just rename
EA_COLUMN_REMAP = {
    'resistance_distance_pct': 'support_distance_pct',
}

# All EA CSV columns that exist per candle row (after remap)
# These are prefixed with a_/b_/c_ and passed through unchanged
EA_CANDLE_COLS = [
    'open', 'high', 'low', 'close',
    'bb_touch_strength', 'bb_position', 'bb_width_pct',
    'rsi_value', 'rsi_divergence',
    'volume_ratio', 'candle_rejection', 'candle_body_pct',
    'atr_pct', 'trend_strength',
    'prev_candle_body_pct', 'prev_volume_ratio',
    'gap_from_prev_close', 'price_momentum',
    'previous_touches', 'time_since_last_touch',
    'support_distance_pct',
    'session',
]

# Subset of EA columns per candle role — matched exactly to v4 pkl feature_cols
A_COLS = [
    'open', 'high', 'low', 'close',
    'bb_position', 'bb_width_pct',
    'rsi_value', 'rsi_divergence',
    'candle_body_pct',
    'atr_pct', 'trend_strength',
    'gap_from_prev_close', 'price_momentum',
    'time_since_last_touch', 'support_distance_pct',
]

B_COLS = [
    'open', 'high', 'low', 'close',
    'bb_touch_strength', 'bb_position', 'bb_width_pct',
    'rsi_value', 'rsi_divergence',
    'volume', 'volume_ratio',
    'candle_rejection', 'candle_body_pct',
    'atr_pct', 'trend_strength',
    'prev_candle_body_pct', 'prev_volume_ratio', 'prev_was_selloff',
    'gap_from_prev_close', 'price_momentum',
    'time_since_last_touch', 'support_distance_pct',
]

C_COLS = [
    'open', 'low', 'close',
    'bb_touch_strength', 'bb_position', 'bb_width_pct',
    'rsi_value', 'rsi_divergence',
    'volume', 'volume_ratio',
    'candle_rejection', 'candle_body_pct',
    'atr_pct', 'trend_strength',
    'prev_candle_body_pct',
    'gap_from_prev_close', 'price_momentum',
    'time_since_last_touch', 'support_distance_pct',
]


class UBBFeatureEngineer(BaseFeatureEngineer):
    """
    Feature engineering for UBB Rejection Short predictor.

    For each symbol:
      1. Remap EA renamed column
      2. Sort by timestamp, find last valid A/B/C triplet
      3. Prefix A/B/C candle columns — no recomputation
      4. Compute 7 BB-event features for Candle A
    """

    MIN_ROWS = 3

    def get_required_input_columns(self) -> List[str]:
        """Minimum columns needed from the EA CSV."""
        return [
            'timestamp', 'symbol',
            'open', 'high', 'low', 'close',
            'volume',
            'upper_band', 'lower_band',
            'bb_position', 'bb_touch_strength',
            'rsi_value', 'rsi_divergence',
        ]

    def get_output_features(self) -> List[str]:
        """63 features matching v4 pkl feature_cols exactly."""
        return [
            'session',
            # Candle A (15 EA cols + 9 computed BB-event)
            'a_open', 'a_high', 'a_low', 'a_close',
            'a_bb_position', 'a_bb_width_pct',
            'a_rsi_value', 'a_rsi_divergence',
            'a_candle_body_pct',
            'a_atr_pct', 'a_trend_strength',
            'a_gap_from_prev_close', 'a_price_momentum',
            'a_time_since_last_touch', 'a_support_distance_pct',
            'a_bb_event_type', 'a_bb_event_strength',
            'a_close_above_ubb', 'a_high_touch_ubb',
            'a_near_upper_bb', 'a_no_upper_wick_bear_reject',
            'a_failed_break_ubb', 'a_ubb_distance_close',
            'a_upper_wick_pct',
            # Candle B (22 EA cols)
            'b_open', 'b_high', 'b_low', 'b_close',
            'b_bb_touch_strength', 'b_bb_position', 'b_bb_width_pct',
            'b_rsi_value', 'b_rsi_divergence',
            'b_volume', 'b_volume_ratio',
            'b_candle_rejection', 'b_candle_body_pct',
            'b_atr_pct', 'b_trend_strength',
            'b_prev_candle_body_pct', 'b_prev_volume_ratio', 'b_prev_was_selloff',
            'b_gap_from_prev_close', 'b_price_momentum',
            'b_time_since_last_touch', 'b_support_distance_pct',
            # Candle C (19 EA cols)
            'c_open', 'c_low', 'c_close',
            'c_bb_touch_strength', 'c_bb_position', 'c_bb_width_pct',
            'c_rsi_value', 'c_rsi_divergence',
            'c_volume', 'c_volume_ratio',
            'c_candle_rejection', 'c_candle_body_pct',
            'c_atr_pct', 'c_trend_strength',
            'c_prev_candle_body_pct',
            'c_gap_from_prev_close', 'c_price_momentum',
            'c_time_since_last_touch', 'c_support_distance_pct',
        ]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # ── Step 1: Rename EA v2.0 column to training name ────────────
        df = df.rename(columns=EA_COLUMN_REMAP)

        # Normalise symbol column (EA exports as 'pair')
        if 'pair' in df.columns and 'symbol' not in df.columns:
            df = df.rename(columns={'pair': 'symbol'})

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)

        output_rows = []

        for symbol, group in df.groupby('symbol'):
            group = group.reset_index(drop=True)

            if len(group) < self.MIN_ROWS:
                logger.debug(
                    f"UBB FE: {symbol} only {len(group)} rows — "
                    f"need {self.MIN_ROWS}"
                )
                continue

            # Infer modal bar step for this symbol
            diffs = group['timestamp'].diff().dropna()
            if diffs.empty:
                continue
            modal_step = diffs.mode()[0]

            # Walk backwards — find the last valid A/B/C triplet
            for i in range(len(group) - 1, 1, -1):
                row_a = group.iloc[i - 2]
                row_b = group.iloc[i - 1]
                row_c = group.iloc[i]

                step_ab = row_b['timestamp'] - row_a['timestamp']
                step_bc = row_c['timestamp'] - row_b['timestamp']

                if step_ab != modal_step or step_bc != modal_step:
                    continue

                # Valid triplet found — build output row and stop
                output_rows.append(
                    self._build_row(row_a, row_b, row_c)
                )
                break

        if not output_rows:
            logger.debug("UBB FE: no valid A/B/C triplets found")
            return pd.DataFrame()

        result = pd.DataFrame(output_rows).reset_index(drop=True)

        # Ensure all output features exist (fill missing with 0)
        for col in self.get_output_features():
            if col not in result.columns:
                result[col] = 0.0

        result = result.replace([np.inf, -np.inf], np.nan).fillna(0)

        logger.debug(
            f"UBB FE: built {len(result)} C-rows "
            f"across {result['symbol'].nunique()} symbols"
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────

    def _build_row(
        self,
        row_a: pd.Series,
        row_b: pd.Series,
        row_c: pd.Series,
    ) -> dict:
        """
        Build one output dict:
          - session from Candle C
          - A/B/C columns prefixed directly from EA CSV values
          - 7 computed BB-event features for Candle A
        """
        out = {}
        out['symbol']    = row_c.get('symbol', '')
        out['timestamp'] = row_c.get('timestamp', None)
        out['session']   = float(row_c.get('session', 0))

        # ── Candle A: prefix EA columns directly ──────────────────────
        for col in A_COLS:
            out[f'a_{col}'] = self._f(row_a, col)

        # ── Candle B: prefix EA columns directly ──────────────────────
        for col in B_COLS:
            out[f'b_{col}'] = self._f(row_b, col)

        # ── Candle C: prefix EA columns directly ──────────────────────
        for col in C_COLS:
            out[f'c_{col}'] = self._f(row_c, col)

        # ── Candle A: compute 7 BB-event features ─────────────────────
        a_open       = self._f(row_a, 'open')
        a_close      = self._f(row_a, 'close')
        a_high       = self._f(row_a, 'high')
        a_low        = self._f(row_a, 'low')
        a_upper_band = self._f(row_a, 'upper_band')
        a_bb_pos     = self._f(row_a, 'bb_position')
        a_bb_touch   = self._f(row_a, 'bb_touch_strength')

        # 1. Upper wick pct
        a_upper_wick  = a_high - max(a_open, a_close)
        a_range       = max(a_high - a_low, TINY)
        a_upper_wick_pct = a_upper_wick / a_range

        # 2. BB event flags
        close_above_ubb  = int(a_close > a_upper_band) if a_upper_band > 0 else 0
        high_touch_ubb   = int(a_high >= a_upper_band) if a_upper_band > 0 else 0
        near_upper_bb    = int(a_bb_pos >= 0.95)
        bearish_candle   = int(a_close < a_open)
        failed_break_ubb = int(
            near_upper_bb == 1
            and bearish_candle == 1
            and a_upper_wick_pct <= 0.15
        )

        # 3. BB event type: 1=close above, 2=high touch, 3=near/failed, 0=none
        if close_above_ubb:
            bb_event_type = 1
        elif high_touch_ubb:
            bb_event_type = 2
        elif failed_break_ubb or near_upper_bb:
            bb_event_type = 3
        else:
            bb_event_type = 0

        # 4. BB event strength: how far bb_touch_strength exceeded 1.0
        bb_event_strength  = max(a_bb_touch - 1.0, 0.0)

        # 5. Distance of close from upper band (signed)
        ubb_distance_close = (
            (a_close - a_upper_band) / a_upper_band
            if a_upper_band > 0 else 0.0
        )

        out['a_bb_event_type']              = float(bb_event_type)
        out['a_bb_event_strength']          = float(bb_event_strength)
        out['a_close_above_ubb']            = float(close_above_ubb)
        out['a_high_touch_ubb']             = float(high_touch_ubb)
        out['a_near_upper_bb']              = float(near_upper_bb)
        out['a_no_upper_wick_bear_reject']  = float(failed_break_ubb)  # same condition
        out['a_failed_break_ubb']           = float(failed_break_ubb)
        out['a_ubb_distance_close']         = float(ubb_distance_close)
        out['a_upper_wick_pct']             = float(a_upper_wick_pct)

        # 'pair' alias — the new model was trained with 'pair' as a feature
        # (build_ubb_signal_dataset.py uses 'pair' column from the EA CSV).
        # At inference time the EA CSV uses 'pair' too, so just pass it through.
        out['pair'] = out.get('symbol', '')

        return out

    @staticmethod
    def _f(row: pd.Series, col: str) -> float:
        """Safe float getter with NaN/inf protection."""
        val = row.get(col, 0)
        if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
            return 0.0
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0
