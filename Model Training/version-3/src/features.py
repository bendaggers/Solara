"""
Feature engineering and selection.

This module handles:
1. Feature CALCULATION - computing technical indicators and derived features
2. Feature SELECTION - Recursive Feature Elimination (RFE)
3. Feature validation and utilities

PART 1: FeatureEngineering class (from your old features.py)
- Calculates all derived features from raw OHLCV + basic indicators
- Binary features, candle patterns, lags, slopes, quality indicators

PART 2: RFE functions (for model training)
- Selects optimal feature subset
- Prevents overfitting
- Runs on training data only

Critical rules:
- Feature calculation happens BEFORE label generation
- RFE runs on TRAINING data only (per fold)
- No leakage from calibration or threshold sets
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass
import warnings
import logging

from sklearn.feature_selection import RFE, RFECV
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.exceptions import ConvergenceWarning


# =============================================================================
# PART 1: FEATURE ENGINEERING (CALCULATION)
# =============================================================================

class FeatureEngineering:
    """
    Feature engineering class for calculating technical indicators.
    
    Calculates derived features from raw data including:
    - Binary features (touched BB, overbought, etc.)
    - Candle pattern features (wicks, body)
    - Price change features
    - Lag features (RSI, BB position, price, volume)
    - Slope features (rate of change)
    - Quality indicator features (exhaustion signals)
    - Composite exhaustion score
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
        
        # Fix BB position formula if needed
        df_features = self._fix_bb_position_if_needed(df_features)
        
        # Calculate features in order
        df_features = self._add_binary_features(df_features)
        df_features = self._add_candle_features(df_features)
        df_features = self._add_price_features(df_features)
        df_features = self._add_lag_features(df_features)
        df_features = self._add_slope_features(df_features)
        
        # Add quality indicator features
        df_features = self._add_quality_features(df_features)
        
        # Add exhaustion score (composite feature)
        df_features = self._add_exhaustion_score(df_features)
        
        # Handle NaN values
        if drop_na:
            df_features = df_features.iloc[min_periods:]
            if self.verbose:
                logging.info(f"Dropped first {min_periods} rows with NaN")
        else:
            df_features = df_features.ffill()
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
        df['touched_prev_1'] = df['touched_upper_bb'].shift(1).fillna(0).astype(int)
        df['touched_prev_2'] = df['touched_upper_bb'].shift(2).fillna(0).astype(int)
        df['touched_recently'] = (
            (df['touched_prev_1'] == 1) | 
            (df['touched_prev_2'] == 1)
        ).astype(int)
        
        # === CANDLE CONFIRMATION ===
        
        # Strong bearish candle (bearish + large body)
        if 'candle_body_pct' in df.columns:
            df['strong_bearish'] = (
                (df['bearish_candle'] == 1) & 
                (df['candle_body_pct'] > 0.5)
            ).astype(int)
        else:
            df['strong_bearish'] = df['bearish_candle']
        
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


# =============================================================================
# CONVENIENCE FUNCTION FOR FEATURE CALCULATION
# =============================================================================

def calculate_all_features(
    df: pd.DataFrame,
    verbose: bool = False,
    drop_na: bool = True
) -> pd.DataFrame:
    """
    Calculate all derived features from raw data.
    
    This is a convenience function that creates a FeatureEngineering instance
    and calculates all features.
    
    Args:
        df: DataFrame with OHLCV and basic indicators
        verbose: Print progress information
        drop_na: Drop rows with NaN values
        
    Returns:
        DataFrame with all calculated features
    """
    fe = FeatureEngineering(verbose=verbose)
    return fe.calculate_features(df, drop_na=drop_na)


# =============================================================================
# PART 2: DATA CLASSES FOR RFE
# =============================================================================

@dataclass
class FeatureRanking:
    """Feature ranking information."""
    feature_name: str
    rank: int
    selected: bool
    importance: float = 0.0


@dataclass
class RFEResult:
    """Result of RFE feature selection."""
    selected_features: List[str]
    n_features_selected: int
    n_features_original: int
    feature_rankings: List[FeatureRanking]
    optimal_n_features: Optional[int] = None
    cv_scores: Optional[List[float]] = None
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert rankings to DataFrame."""
        data = [
            {
                'feature_name': r.feature_name,
                'rank': r.rank,
                'selected': r.selected,
                'importance': r.importance
            }
            for r in self.feature_rankings
        ]
        return pd.DataFrame(data).sort_values('rank').reset_index(drop=True)
    
    def get_selected_features(self) -> List[str]:
        """Get list of selected feature names."""
        return self.selected_features.copy()


# =============================================================================
# PART 2: FEATURE COLUMN UTILITIES
# =============================================================================

def get_feature_columns(
    df: pd.DataFrame,
    exclude_columns: Optional[List[str]] = None
) -> List[str]:
    """
    Identify feature columns from DataFrame.
    
    Features are numeric columns excluding specified columns.
    
    Args:
        df: DataFrame to analyze
        exclude_columns: Columns to exclude from features
        
    Returns:
        List of feature column names
    """
    if exclude_columns is None:
        exclude_columns = []
    
    # Default exclusions (meta, target, derived columns)
    default_exclusions = {
        'timestamp', 'pair', 'symbol',
        'open', 'high', 'low', 'close', 'volume',
        'label', 'label_reason', 'signal', 'regime',
        'lower_band', 'middle_band', 'upper_band'
    }
    
    exclude_set = set(col.lower() for col in exclude_columns)
    exclude_set.update(default_exclusions)
    
    feature_columns = [
        col for col in df.columns
        if col.lower() not in exclude_set
        and pd.api.types.is_numeric_dtype(df[col])
    ]
    
    return feature_columns


def validate_features(
    df: pd.DataFrame,
    feature_columns: List[str]
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Validate feature columns and return valid ones.
    
    Checks for:
    - Missing columns
    - NaN values
    - Infinite values
    - Zero variance
    
    Args:
        df: DataFrame containing features
        feature_columns: List of feature column names to validate
        
    Returns:
        Tuple of (valid feature columns, validation report)
    """
    report = {
        'original_count': len(feature_columns),
        'valid_count': 0,
        'issues': {},
        'dropped': []
    }
    
    valid_features = []
    
    for col in feature_columns:
        issues = []
        
        # Check if column exists
        if col not in df.columns:
            issues.append('missing')
            report['issues'][col] = issues
            report['dropped'].append(col)
            continue
        
        series = df[col]
        
        # Check for NaN
        nan_count = series.isna().sum()
        if nan_count > 0:
            nan_pct = nan_count / len(series) * 100
            if nan_pct > 10:  # More than 10% NaN
                issues.append(f'high_nan ({nan_pct:.1f}%)')
            else:
                issues.append(f'some_nan ({nan_count})')
        
        # Check for infinite values
        if np.isinf(series).any():
            inf_count = np.isinf(series).sum()
            issues.append(f'infinite ({inf_count})')
        
        # Check for zero variance
        if series.std() == 0:
            issues.append('zero_variance')
        
        # Decide if valid
        critical_issues = {'missing', 'zero_variance'}
        has_critical = any(
            issue.split()[0] in critical_issues or issue.startswith('high_nan')
            for issue in issues
        )
        
        if has_critical:
            report['issues'][col] = issues
            report['dropped'].append(col)
        else:
            valid_features.append(col)
            if issues:
                report['issues'][col] = issues  # Non-critical warnings
    
    report['valid_count'] = len(valid_features)
    
    return valid_features, report


def prepare_features(
    df: pd.DataFrame,
    feature_columns: List[str],
    handle_nan: str = 'drop',
    handle_inf: str = 'clip'
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Prepare feature DataFrame for model training.
    
    Args:
        df: DataFrame containing features
        feature_columns: List of feature column names
        handle_nan: How to handle NaN ('drop', 'fill_mean', 'fill_zero')
        handle_inf: How to handle infinite values ('clip', 'replace_nan')
        
    Returns:
        Tuple of (prepared feature DataFrame, final feature columns)
    """
    # Select only feature columns that exist
    available_features = [col for col in feature_columns if col in df.columns]
    X = df[available_features].copy()
    
    # Handle infinite values
    if handle_inf == 'clip':
        for col in X.columns:
            if X[col].dtype in [np.float64, np.float32]:
                max_val = np.finfo(X[col].dtype).max / 10
                X[col] = X[col].clip(-max_val, max_val)
    elif handle_inf == 'replace_nan':
        X = X.replace([np.inf, -np.inf], np.nan)
    
    # Handle NaN values
    if handle_nan == 'drop':
        # This will be handled at row level by caller
        pass
    elif handle_nan == 'fill_mean':
        X = X.fillna(X.mean())
    elif handle_nan == 'fill_zero':
        X = X.fillna(0)
    
    return X, available_features


# =============================================================================
# PART 2: RECURSIVE FEATURE ELIMINATION
# =============================================================================

def rfe_select(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    feature_columns: List[str],
    min_features: int = 5,
    max_features: int = 15,
    cv_folds: int = 3,
    scoring: str = 'average_precision',
    use_rfecv: bool = True,
    random_state: int = 42
) -> RFEResult:
    """
    Perform Recursive Feature Elimination to select optimal features.
    
    Args:
        X_train: Training features DataFrame
        y_train: Training labels Series
        feature_columns: List of feature column names to consider
        min_features: Minimum number of features to select
        max_features: Maximum number of features to select
        cv_folds: Number of cross-validation folds
        scoring: Scoring metric for evaluation
        use_rfecv: If True, use RFECV to find optimal number; else use RFE
        random_state: Random state for reproducibility
        
    Returns:
        RFEResult with selected features and rankings
    """
    # Prepare feature matrix
    available_features = [col for col in feature_columns if col in X_train.columns]
    X = X_train[available_features].copy()
    y = y_train.copy()
    
    # Handle NaN - drop rows with any NaN
    valid_mask = ~(X.isna().any(axis=1) | y.isna())
    X = X[valid_mask]
    y = y[valid_mask]
    
    if len(X) < 50:
        warnings.warn(f"Very small training set for RFE: {len(X)} rows")
    
    # Handle infinite values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.mean())
    
    n_original = len(available_features)
    
    # Create base estimator
    estimator = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        min_samples_leaf=20,
        random_state=random_state,
        validation_fraction=0.1,
        n_iter_no_change=10
    )
    
    # Suppress convergence warnings during RFE
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=ConvergenceWarning)
        warnings.filterwarnings('ignore', category=UserWarning)
        
        if use_rfecv:
            # Use cross-validation to find optimal number of features
            cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
            
            selector = RFECV(
                estimator=estimator,
                step=1,
                cv=cv,
                scoring=scoring,
                min_features_to_select=min_features,
                n_jobs=-1
            )
            
            try:
                selector.fit(X, y)
                optimal_n = selector.n_features_
                cv_scores = selector.cv_results_['mean_test_score'].tolist()
            except Exception as e:
                warnings.warn(f"RFECV failed: {e}. Falling back to RFE.")
                use_rfecv = False
        
        if not use_rfecv:
            # Use fixed number of features
            n_features_to_select = min(max_features, n_original)
            n_features_to_select = max(n_features_to_select, min_features)
            
            selector = RFE(
                estimator=estimator,
                n_features_to_select=n_features_to_select,
                step=1
            )
            
            selector.fit(X, y)
            optimal_n = n_features_to_select
            cv_scores = None
    
    # Clamp to max_features
    if optimal_n > max_features:
        # Re-run RFE with max_features
        selector = RFE(
            estimator=estimator,
            n_features_to_select=max_features,
            step=1
        )
        selector.fit(X, y)
        optimal_n = max_features
    
    # Extract results
    selected_mask = selector.support_
    rankings = selector.ranking_
    
    # Get feature importances from the fitted estimator
    try:
        importances = selector.estimator_.feature_importances_
    except AttributeError:
        importances = np.zeros(sum(selected_mask))
    
    # Build feature rankings
    feature_rankings = []
    importance_idx = 0
    
    for i, (feat, rank, selected) in enumerate(zip(available_features, rankings, selected_mask)):
        if selected and importance_idx < len(importances):
            imp = importances[importance_idx]
            importance_idx += 1
        else:
            imp = 0.0
        
        feature_rankings.append(FeatureRanking(
            feature_name=feat,
            rank=int(rank),
            selected=bool(selected),
            importance=float(imp)
        ))
    
    # Sort by rank
    feature_rankings.sort(key=lambda x: x.rank)
    
    # Get selected feature names
    selected_features = [fr.feature_name for fr in feature_rankings if fr.selected]
    
    return RFEResult(
        selected_features=selected_features,
        n_features_selected=len(selected_features),
        n_features_original=n_original,
        feature_rankings=feature_rankings,
        optimal_n_features=optimal_n,
        cv_scores=cv_scores
    )


def rfe_select_simple(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    feature_columns: List[str],
    n_features: int = 10,
    random_state: int = 42
) -> RFEResult:
    """
    Simple RFE without cross-validation (faster).
    
    Args:
        X_train: Training features DataFrame
        y_train: Training labels Series
        feature_columns: List of feature column names
        n_features: Number of features to select
        random_state: Random state for reproducibility
        
    Returns:
        RFEResult with selected features
    """
    return rfe_select(
        X_train=X_train,
        y_train=y_train,
        feature_columns=feature_columns,
        min_features=n_features,
        max_features=n_features,
        cv_folds=3,
        use_rfecv=False,
        random_state=random_state
    )


# =============================================================================
# FEATURE IMPORTANCE FROM TRAINED MODEL
# =============================================================================

def extract_feature_importance(
    model: Any,
    feature_names: List[str]
) -> List[FeatureRanking]:
    """
    Extract feature importance from a trained model.
    
    Args:
        model: Trained model with feature_importances_ attribute
        feature_names: List of feature names in order
        
    Returns:
        List of FeatureRanking sorted by importance
    """
    try:
        importances = model.feature_importances_
    except AttributeError:
        # Model doesn't have feature_importances_
        # Try coef_ for linear models
        try:
            importances = np.abs(model.coef_).flatten()
        except AttributeError:
            # Return uniform importance
            importances = np.ones(len(feature_names)) / len(feature_names)
    
    # Normalize importances
    total = importances.sum()
    if total > 0:
        importances = importances / total
    
    # Create rankings
    rankings = []
    sorted_indices = np.argsort(importances)[::-1]  # Descending
    
    for rank, idx in enumerate(sorted_indices, 1):
        rankings.append(FeatureRanking(
            feature_name=feature_names[idx],
            rank=rank,
            selected=True,
            importance=float(importances[idx])
        ))
    
    return rankings


def get_top_features(
    rankings: List[FeatureRanking],
    n: int = 10
) -> List[str]:
    """
    Get top N features by importance.
    
    Args:
        rankings: List of FeatureRanking
        n: Number of top features to return
        
    Returns:
        List of feature names
    """
    sorted_rankings = sorted(rankings, key=lambda x: x.importance, reverse=True)
    return [r.feature_name for r in sorted_rankings[:n]]


# =============================================================================
# CONSENSUS FEATURES ACROSS FOLDS
# =============================================================================

def get_consensus_features(
    fold_results: List[RFEResult],
    min_fold_frequency: float = 0.8,
    method: str = 'frequency'
) -> List[str]:
    """
    Get consensus features selected across multiple folds.
    
    Args:
        fold_results: List of RFEResult from each fold
        min_fold_frequency: Minimum fraction of folds a feature must appear in
        method: 'frequency' (by selection count) or 'intersection' (must be in all)
        
    Returns:
        List of consensus feature names
    """
    if not fold_results:
        return []
    
    n_folds = len(fold_results)
    
    if method == 'intersection':
        # Features must be in ALL folds
        feature_sets = [set(r.selected_features) for r in fold_results]
        consensus = feature_sets[0]
        for fs in feature_sets[1:]:
            consensus = consensus.intersection(fs)
        return list(consensus)
    
    else:  # frequency
        # Count how often each feature is selected
        feature_counts = {}
        for result in fold_results:
            for feat in result.selected_features:
                feature_counts[feat] = feature_counts.get(feat, 0) + 1
        
        # Select features that appear in enough folds
        min_count = int(n_folds * min_fold_frequency)
        consensus = [
            feat for feat, count in feature_counts.items()
            if count >= min_count
        ]
        
        # Sort by frequency (most common first)
        consensus.sort(key=lambda x: feature_counts[x], reverse=True)
        
        return consensus


def aggregate_feature_importance(
    fold_results: List[RFEResult]
) -> pd.DataFrame:
    """
    Aggregate feature importance across folds.
    
    Args:
        fold_results: List of RFEResult from each fold
        
    Returns:
        DataFrame with mean importance per feature
    """
    if not fold_results:
        return pd.DataFrame()
    
    # Collect all importances
    all_importances = {}
    
    for result in fold_results:
        for ranking in result.feature_rankings:
            if ranking.feature_name not in all_importances:
                all_importances[ranking.feature_name] = []
            all_importances[ranking.feature_name].append(ranking.importance)
    
    # Calculate statistics
    rows = []
    for feat, imps in all_importances.items():
        rows.append({
            'feature_name': feat,
            'mean_importance': np.mean(imps),
            'std_importance': np.std(imps),
            'selection_count': len(imps),
            'selection_rate': len(imps) / len(fold_results)
        })
    
    df = pd.DataFrame(rows)
    df = df.sort_values('mean_importance', ascending=False).reset_index(drop=True)
    df['rank'] = range(1, len(df) + 1)
    
    return df


# =============================================================================
# FEATURE SELECTION RESULT SERIALIZATION
# =============================================================================

def result_to_csv(
    result: RFEResult,
    filepath: str
) -> None:
    """
    Save RFE result to CSV file.
    
    Args:
        result: RFEResult to save
        filepath: Path to output CSV file
    """
    df = result.to_dataframe()
    df.to_csv(filepath, index=False)


def selected_features_to_csv(
    features: List[str],
    importances: Optional[List[float]],
    filepath: str
) -> None:
    """
    Save selected features to CSV file.
    
    Args:
        features: List of feature names
        importances: Optional list of importance scores
        filepath: Path to output CSV file
    """
    if importances is None:
        importances = [1.0 / len(features)] * len(features)
    
    # Ensure same length
    if len(importances) != len(features):
        importances = [1.0 / len(features)] * len(features)
    
    df = pd.DataFrame({
        'feature_name': features,
        'rank': range(1, len(features) + 1),
        'importance': importances
    })
    
    df.to_csv(filepath, index=False)


# =============================================================================
# FEATURE CORRELATION ANALYSIS
# =============================================================================

def analyze_feature_correlation(
    df: pd.DataFrame,
    feature_columns: List[str],
    threshold: float = 0.95
) -> Dict[str, Any]:
    """
    Analyze correlation between features.
    
    Identifies highly correlated feature pairs that may be redundant.
    
    Args:
        df: DataFrame containing features
        feature_columns: List of feature column names
        threshold: Correlation threshold for flagging
        
    Returns:
        Dictionary with correlation analysis
    """
    available = [col for col in feature_columns if col in df.columns]
    X = df[available]
    
    # Calculate correlation matrix
    corr_matrix = X.corr()
    
    # Find highly correlated pairs
    high_corr_pairs = []
    
    for i in range(len(available)):
        for j in range(i + 1, len(available)):
            corr = abs(corr_matrix.iloc[i, j])
            if corr >= threshold:
                high_corr_pairs.append({
                    'feature_1': available[i],
                    'feature_2': available[j],
                    'correlation': corr
                })
    
    # Sort by correlation
    high_corr_pairs.sort(key=lambda x: x['correlation'], reverse=True)
    
    return {
        'n_features': len(available),
        'n_high_corr_pairs': len(high_corr_pairs),
        'high_corr_pairs': high_corr_pairs,
        'threshold': threshold
    }


def remove_correlated_features(
    feature_columns: List[str],
    corr_analysis: Dict[str, Any],
    keep_first: bool = True
) -> List[str]:
    """
    Remove one feature from each highly correlated pair.
    
    Args:
        feature_columns: List of feature column names
        corr_analysis: Output from analyze_feature_correlation
        keep_first: If True, keep the first feature; else keep second
        
    Returns:
        Filtered list of feature names
    """
    to_remove = set()
    
    for pair in corr_analysis.get('high_corr_pairs', []):
        if keep_first:
            to_remove.add(pair['feature_2'])
        else:
            to_remove.add(pair['feature_1'])
    
    return [f for f in feature_columns if f not in to_remove]