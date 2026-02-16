"""
features.py - IMPROVED VERSION with Optimal Balance Approach

Feature engineering class for calculating technical indicators and quality features.

NEW in this version:
- Fixed BB position formula (was inverted)
- Baseline filter method (broad but reasonable - creates 2,000-5,000 candidates)
- Quality indicator features (ML learns which setups work best)
- Exhaustion score (composite signal strength)
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional, Tuple


class FeatureEngineering:
    """
    Feature engineering class for calculating technical indicators.
    
    TWO-STAGE APPROACH:
    1. Calculate all features (including quality indicators)
    2. Provide baseline_filter() method for broad signal filtering
    
    Then ML learns which quality features predict success within the baseline.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        if verbose:
            logging.basicConfig(level=logging.INFO)
    
    def calculate_features(
        self, 
        df: pd.DataFrame,
        drop_na: bool = True,
        min_periods: int = 5
    ) -> pd.DataFrame:
        """
        Calculate all engineered features from the raw data.
        
        Args:
            df: DataFrame with raw data including columns like open, high, low, close, 
                volume, lower_band, middle_band, upper_band, rsi_value, etc.
            drop_na: If True, drop rows with NaN. If False, forward fill.
            min_periods: Number of initial rows to drop (default 5 for max lag)
                
        Returns:
            DataFrame with original data and calculated features
        """
        # Validate input
        self._validate_input(df)
        
        if self.verbose:
            logging.info(f"Input shape: {df.shape}")
        
        # Create a copy to avoid modifying the original DataFrame
        df_features = df.copy()
        
        # FIX: Verify BB position formula is correct
        df_features = self._fix_bb_position_if_needed(df_features)
        
        # Calculate features in order
        df_features = self._add_binary_features(df_features)
        df_features = self._add_candle_features(df_features)
        df_features = self._add_price_features(df_features)
        df_features = self._add_lag_features(df_features)
        df_features = self._add_slope_features(df_features)
        
        # NEW: Add quality indicator features
        df_features = self._add_quality_features(df_features)
        
        # NEW: Add exhaustion score (composite feature)
        df_features = self._add_exhaustion_score(df_features)
        
        # Handle NaN values
        if drop_na:
            df_features = df_features.iloc[min_periods:]
            if self.verbose:
                logging.info(f"Dropped first {min_periods} rows with NaN")
        else:
            df_features = df_features.ffill()  # Forward fill only
            if self.verbose:
                logging.info("Forward-filled NaN values")
        
        if self.verbose:
            logging.info(f"Final shape: {df_features.shape}")
            nan_count = df_features.isnull().sum().sum()
            logging.info(f"Remaining NaN values: {nan_count}")
        
        return df_features
    
    def _validate_input(self, df: pd.DataFrame) -> None:
        """Validate input DataFrame has required columns and sufficient data."""
        required_columns = [
            'open', 'high', 'low', 'close', 'volume',
            'lower_band', 'middle_band', 'upper_band', 
            'rsi_value', 'bb_position', 'bb_width_pct',
            'volume_ratio', 'trend_strength'
        ]
        
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        if len(df) < 25:
            raise ValueError(f"Insufficient data: need at least 25 rows, got {len(df)}")
    
    def _fix_bb_position_if_needed(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Verify and fix BB position formula if incorrect.
        
        CORRECT: bb_position = (close - lower) / (upper - lower)
        Result: 0.0 = at lower band, 1.0 = at upper band
        
        WRONG: bb_position = (upper - lower) / (close - lower)
        Result: Unbounded, can be > 1, divide by zero issues
        """
        # Check if bb_position looks wrong (values > 1.5 or negative)
        if df['bb_position'].max() > 1.5 or df['bb_position'].min() < -0.5:
            if self.verbose:
                logging.warning("BB position formula appears incorrect. Recalculating...")
            
            # Recalculate correctly
            df['bb_position'] = (
                (df['close'] - df['lower_band']) / 
                (df['upper_band'] - df['lower_band'])
            )
            
            # Handle edge cases (divide by zero when bands converge)
            df['bb_position'] = df['bb_position'].clip(0, 1)
            
            if self.verbose:
                logging.info(f"BB position recalculated. Range: {df['bb_position'].min():.3f} to {df['bb_position'].max():.3f}")
        
        return df
    
    def _add_binary_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add binary indicator features."""
        df['touched_upper_bb'] = (df['high'] >= df['upper_band']).astype(int)
        df['rsi_overbought'] = (df['rsi_value'] > 70).astype(int)
        df['rsi_extreme_overbought'] = (df['rsi_value'] > 80).astype(int)
        df['bearish_candle'] = (df['close'] < df['open']).astype(int)
        return df
    
    def _add_candle_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add candle pattern features with zero-protection."""
        # Upper wick
        df['upper_wick'] = np.where(
            df['open'] != 0,
            (df['high'] - df[['open', 'close']].max(axis=1)) / df['open'],
            0
        )
        
        # Lower wick
        df['lower_wick'] = np.where(
            df['open'] != 0,
            (df[['open', 'close']].min(axis=1) - df['low']) / df['open'],
            0
        )
        
        return df
    
    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price change features."""
        df['price_change_1'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1)
        df['price_change_5'] = (df['close'] - df['close'].shift(5)) / df['close'].shift(5)
        return df
    
    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add lag features for RSI, BB position, price change, and volume."""
        # RSI lags
        for i in range(1, 6):
            df[f'rsi_lag{i}'] = df['rsi_value'].shift(i)
        
        # BB position lags
        for i in range(1, 4):
            df[f'bb_position_lag{i}'] = df['bb_position'].shift(i)
        
        # Price change lags
        for i in range(1, 4):
            df[f'price_change_lag{i}'] = df['price_change_1'].shift(i)
        
        # Volume ratio lags
        for i in range(1, 4):
            df[f'volume_ratio_lag{i}'] = df['volume_ratio'].shift(i)
        
        return df
    
    def _add_slope_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add slope (rate of change) features."""
        # RSI slopes
        df['rsi_slope_3'] = (df['rsi_value'] - df['rsi_lag3']) / 3
        df['rsi_slope_5'] = (df['rsi_value'] - df['rsi_lag5']) / 5
        
        # Price slopes
        df['price_slope_3'] = ((df['close'] - df['close'].shift(3)) / df['close'].shift(3)) / 3
        df['price_slope_5'] = ((df['close'] - df['close'].shift(5)) / df['close'].shift(5)) / 5
        
        # BB position slope
        df['bb_position_slope_3'] = (df['bb_position'] - df['bb_position_lag3']) / 3
        
        # Volume slope
        df['volume_slope_3'] = ((df['volume'] - df['volume'].shift(3)) / df['volume'].shift(3)) / 3
        
        # BB width slope
        df['bb_width_slope_3'] = (df['bb_width_pct'] - df['bb_width_pct'].shift(3)) / 3
        
        # Trend strength slope
        df['trend_strength_slope_3'] = (df['trend_strength'] - df['trend_strength'].shift(3)) / 3
        
        return df
    
    def _add_quality_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add quality indicator features.
        
        These are NOT used for filtering, but as features for ML to learn from.
        They indicate high-quality exhaustion setups within the baseline filter.
        """
        
        # === RSI EXHAUSTION INDICATORS ===
        
        # RSI peaked (declining now)
        df['rsi_peaked'] = (df['rsi_value'] < df['rsi_lag1']).astype(int)
        
        # RSI drop size (how much it fell)
        df['rsi_drop_size'] = df['rsi_lag1'] - df['rsi_value']
        df['rsi_drop_size'] = df['rsi_drop_size'].clip(lower=0)  # Only positive drops
        
        # Large RSI drop (>5 points)
        df['rsi_drop_large'] = (df['rsi_drop_size'] > 5).astype(int)
        
        # RSI was extreme (>70)
        df['rsi_was_extreme'] = (df['rsi_lag1'] > 70).astype(int)
        
        # Strong negative RSI slope
        df['rsi_slope_strong_neg'] = (df['rsi_slope_3'] < -5).astype(int)
        
        # RSI momentum shift (was rising, now falling)
        rsi_was_rising = (df['rsi_lag1'] > df['rsi_lag2']).astype(int)
        rsi_now_falling = (df['rsi_value'] < df['rsi_lag1']).astype(int)
        df['rsi_momentum_shift'] = (rsi_was_rising & rsi_now_falling).astype(int)
        
        # === BB POSITION QUALITY ===
        
        # Very high BB position (>0.95)
        df['bb_very_high'] = (df['bb_position'] > 0.95).astype(int)
        
        # Previous bar at extreme
        df['bb_extreme_prev'] = (df['bb_position'].shift(1) > 0.95).astype(int)
        
        # Touched upper in previous 1-2 bars
        df['touched_prev_1'] = df['touched_upper_bb'].shift(1)
        df['touched_prev_2'] = df['touched_upper_bb'].shift(2)
        df['touched_recently'] = (
            (df['touched_prev_1'] == 1) | 
            (df['touched_prev_2'] == 1)
        ).astype(int)
        
        # === CANDLE CONFIRMATION ===
        
        # Strong bearish candle (bearish + large body)
        df['strong_bearish'] = (
            (df['bearish_candle'] == 1) & 
            (df['candle_body_pct'] > 0.5)
        ).astype(int)
        
        # Rejection candle (long upper wick)
        df['rejection_candle'] = (df['upper_wick'] > 0.003).astype(int)
        
        # === VOLUME CONFIRMATION ===
        
        # Volume spike
        df['volume_spike'] = (df['volume_ratio'] > 1.3).astype(int)
        
        # High volume on reversal
        df['high_volume_reversal'] = (
            (df['bearish_candle'] == 1) & 
            (df['volume_ratio'] > 1.2)
        ).astype(int)
        
        # === CONTEXT FEATURES ===
        
        # Not choppy (hasn't touched upper BB recently before this)
        # This prevents entering during consolidation at upper band
        if 'time_since_last_touch' in df.columns:
            df['not_choppy'] = (df['time_since_last_touch'] > 3).astype(int)
        else:
            df['not_choppy'] = 1  # Default to true if feature missing
        
        # First touch (vs repeated touches)
        if 'previous_touches' in df.columns:
            df['first_touch'] = (df['previous_touches'] <= 1).astype(int)
        else:
            df['first_touch'] = 1  # Default
        
        return df
    
    def _add_exhaustion_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add composite exhaustion score (0-1).
        
        This is a weighted combination of quality indicators.
        ML can learn if higher exhaustion scores predict better outcomes.
        """
        
        # Normalize components to 0-1 range
        
        # BB extremity (already 0-1)
        bb_score = df['bb_position'].clip(0, 1)
        
        # RSI exhaustion (combine multiple signals)
        rsi_score = (
            0.3 * df['rsi_peaked'] +
            0.3 * df['rsi_drop_large'] +
            0.2 * df['rsi_was_extreme'] +
            0.2 * df['rsi_slope_strong_neg']
        )
        
        # Momentum reversal strength
        momentum_score = (
            0.5 * df['rsi_momentum_shift'] +
            0.5 * np.clip(-df['rsi_slope_3'] / 10, 0, 1)  # Normalize slope
        )
        
        # Confirmation signals
        confirm_score = (
            0.4 * df['strong_bearish'] +
            0.3 * df['volume_spike'] +
            0.3 * df['rejection_candle']
        )
        
        # Composite score (weighted average)
        df['exhaustion_score'] = (
            0.25 * bb_score +
            0.30 * rsi_score +
            0.25 * momentum_score +
            0.20 * confirm_score
        )
        
        # Clip to 0-1 range
        df['exhaustion_score'] = df['exhaustion_score'].clip(0, 1)
        
        return df
    
    def exhaustion_signal(self, df: pd.DataFrame, 
                         bb_threshold: float = 0.95,
                         rsi_peak_min: int = 60,
                         rsi_drop_min: int = 5) -> pd.Series:
        """
        USER'S NEW SIGNAL: Momentum exhaustion after BB touch.
        
        Logic:
        1. Previous candle touched/near upper BB (setup)
        2. RSI was rising and peaked (momentum built)
        3. RSI slope turned negative (exhaustion confirmed)
        
        Example RSI sequence: 37 → 58 → 63 (peak) → 49 (enter here)
        
        OPTIMIZED: Uses existing lag features (no redundant shifting)
        
        Args:
            bb_threshold: How close to upper BB counts as "near" (0.95 = within 5%)
            rsi_peak_min: Minimum RSI value at peak (default 60)
            rsi_drop_min: Minimum RSI drop to confirm reversal (default 5 points)
        
        Returns:
            Boolean Series indicating entry signals
        """
        
        # === CONDITION 1: Previous candle at/near upper BB ===
        # Use existing pre-calculated lag features (no redundant shifting)
        
        # Previous bar touched upper BB (uses existing feature)
        prev_touched = df['touched_prev_1'] == 1
        
        # OR previous bar was very close (uses existing bb_position_lag1)
        prev_near_upper = df['bb_position_lag1'] > bb_threshold
        
        # OR 2 bars ago touched (uses existing feature)
        prev2_touched = df['touched_prev_2'] == 1
        
        bb_setup = prev_touched | prev_near_upper | prev2_touched
        
        
        # === CONDITION 2: RSI momentum reversal ===
        # Uses existing rsi_lag features (already calculated)
        
        # RSI peaked (current < previous) - uses existing rsi_lag1
        rsi_peaked = df['rsi_value'] < df['rsi_lag1']
        
        # RSI was at a meaningful level when it peaked
        rsi_was_elevated = df['rsi_lag1'] >= rsi_peak_min
        
        # RSI drop is significant (not just noise)
        rsi_drop = df['rsi_lag1'] - df['rsi_value']
        rsi_drop_significant = rsi_drop >= rsi_drop_min
        
        # RSI was RISING before the peak (uses existing lags)
        # Check if rsi_lag1 > rsi_lag2 (was increasing into the peak)
        rsi_was_rising = df['rsi_lag1'] > df['rsi_lag2']
        
        # Combine RSI conditions
        rsi_exhaustion = (
            rsi_peaked & 
            rsi_was_elevated & 
            rsi_drop_significant & 
            rsi_was_rising
        )
        
        
        # === OPTIONAL: Add confirmation filters ===
        
        # Bearish candle confirmation (already calculated)
        bearish_confirm = df['bearish_candle'] == 1
        
        # Not in choppy consolidation (uses existing feature if available)
        if 'not_choppy' in df.columns:
            not_choppy = df['not_choppy'] == 1
        else:
            # Fallback: calculate if feature missing
            if 'time_since_last_touch' in df.columns:
                not_choppy = df['time_since_last_touch'] > 2
            else:
                not_choppy = True  # Default to True
        
        
        # === COMBINE ALL CONDITIONS ===
        
        signal = (
            bb_setup &              # Previous candle at upper BB
            rsi_exhaustion &        # RSI peaked and falling
            bearish_confirm &       # Current candle bearish
            not_choppy              # Not consolidating
        )
        
        return signal.astype(int)
    
    
    def baseline_filter(self, df: pd.DataFrame, strictness: str = 'moderate') -> pd.Series:
        """
        Apply baseline filter to create universe of potential exhaustion setups.
        
        This is the FIRST stage: broad filter to get 2,000-5,000 candidates.
        Then ML learns which of these candidates actually work (Stage 2).
        
        Args:
            df: DataFrame with calculated features
            strictness: 'relaxed' (5k+ signals), 'moderate' (2-4k signals), 
                       'strict' (1-2k signals)
        
        Returns:
            Boolean Series indicating which bars meet baseline criteria
        """
        
        if strictness == 'relaxed':
            # Very broad: Any hint of upper BB reversal setup
            # Expected: 5,000-8,000 signals
            # Win rate: ~26-28%
            
            upper_bb_context = (
                (df['bb_position'] > 0.70) |                    # Currently near upper
                (df['bb_position'].shift(1) > 0.75) |           # Previous bar near
                (df['touched_upper_bb'].shift(1) == 1) |        # Previous touched
                (df['touched_upper_bb'].shift(2) == 1)          # 2 bars ago touched
            )
            
            momentum_context = (
                (df['rsi_value'] > 50) |                        # Elevated
                (df['rsi_lag1'] > 55)                           # Was elevated
            )
            
            reversal_hint = (
                (df['bearish_candle'] == 1) |                   # Bearish
                (df['rsi_value'] < df['rsi_lag1']) |            # RSI declining
                (df['price_change_1'] < 0)                      # Price down
            )
            
            baseline = upper_bb_context & momentum_context & reversal_hint
        
        elif strictness == 'moderate':
            # Balanced: Clear upper BB interaction + some momentum reversal
            # Expected: 2,000-4,000 signals
            # Win rate: ~28-31%
            
            upper_bb_context = (
                (df['bb_position'] > 0.80) |                    # High position
                (df['bb_position'].shift(1) > 0.85) |           # Previous very high
                (df['touched_upper_bb'].shift(1) == 1) |        # Previous touched
                (df['bb_extreme_prev'] == 1)                    # Previous extreme
            )
            
            momentum_context = (
                (df['rsi_value'] > 55) |                        # Somewhat elevated
                (df['rsi_lag1'] > 60)                           # Was overbought
            )
            
            reversal_signal = (
                (df['rsi_peaked'] == 1) |                       # RSI peaked
                (df['rsi_slope_3'] < -2) |                      # Declining slope
                (df['rsi_momentum_shift'] == 1)                 # Momentum shifted
            )
            
            confirmation = (
                (df['bearish_candle'] == 1) |                   # Bearish candle
                (df['rejection_candle'] == 1)                   # OR rejection wick
            )
            
            baseline = upper_bb_context & momentum_context & reversal_signal & confirmation
        
        elif strictness == 'strict':
            # Selective: Strong signals only
            # Expected: 1,000-2,000 signals
            # Win rate: ~30-34%
            
            upper_bb_extreme = (
                (df['bb_position'] > 0.85) |                    # Very high
                (df['bb_very_high'] == 1) |                     # Extreme
                (df['touched_prev_1'] == 1)                     # Just touched
            )
            
            strong_overbought = (
                (df['rsi_value'] > 60) &                        # Currently elevated
                (df['rsi_lag1'] > 65)                           # Was more elevated
            )
            
            clear_reversal = (
                (df['rsi_peaked'] == 1) &                       # Peaked
                (
                    (df['rsi_drop_large'] == 1) |               # Large drop
                    (df['rsi_slope_strong_neg'] == 1)           # Strong slope
                )
            )
            
            strong_confirmation = (
                (df['bearish_candle'] == 1) &                   # Must be bearish
                (
                    (df['strong_bearish'] == 1) |               # Strong bearish OR
                    (df['volume_spike'] == 1)                   # Volume spike
                )
            )
            
            baseline = upper_bb_extreme & strong_overbought & clear_reversal & strong_confirmation
        
        else:
            raise ValueError(f"Unknown strictness: {strictness}. Use 'relaxed', 'moderate', or 'strict'")
        
        return baseline
    
    def get_baseline_statistics(self, df: pd.DataFrame) -> dict:
        """
        Get statistics for each baseline filter strictness level.
        
        Useful for choosing the right balance of quantity vs quality.
        """
        stats = {}
        
        for strictness in ['relaxed', 'moderate', 'strict']:
            mask = self.baseline_filter(df, strictness=strictness)
            count = mask.sum()
            pct = mask.mean() * 100
            
            stats[strictness] = {
                'signal_count': int(count),
                'percentage': f"{pct:.1f}%",
                'expected_win_rate': {
                    'relaxed': '26-28%',
                    'moderate': '28-31%',
                    'strict': '30-34%'
                }[strictness]
            }
        
        return stats
    
    def get_feature_names(self) -> list:
        """Return list of all calculated feature names."""
        base_features = [
            # Binary
            'touched_upper_bb', 'rsi_overbought', 'rsi_extreme_overbought', 
            'bearish_candle',
            # Candle patterns
            'upper_wick', 'lower_wick',
            # Price changes
            'price_change_1', 'price_change_5',
            # RSI lags
            'rsi_lag1', 'rsi_lag2', 'rsi_lag3', 'rsi_lag4', 'rsi_lag5',
            # BB lags
            'bb_position_lag1', 'bb_position_lag2', 'bb_position_lag3',
            # Price lags
            'price_change_lag1', 'price_change_lag2', 'price_change_lag3',
            # Volume lags
            'volume_ratio_lag1', 'volume_ratio_lag2', 'volume_ratio_lag3',
            # Slopes
            'rsi_slope_3', 'rsi_slope_5', 'price_slope_3', 'price_slope_5',
            'bb_position_slope_3', 'volume_slope_3', 'bb_width_slope_3',
            'trend_strength_slope_3'
        ]
        
        quality_features = [
            # RSI exhaustion
            'rsi_peaked', 'rsi_drop_size', 'rsi_drop_large', 'rsi_was_extreme',
            'rsi_slope_strong_neg', 'rsi_momentum_shift',
            # BB quality
            'bb_very_high', 'bb_extreme_prev', 'touched_prev_1', 'touched_prev_2',
            'touched_recently',
            # Confirmation
            'strong_bearish', 'rejection_candle', 'volume_spike', 'high_volume_reversal',
            # Context
            'not_choppy', 'first_touch',
            # Composite
            'exhaustion_score'
        ]
        
        return base_features + quality_features