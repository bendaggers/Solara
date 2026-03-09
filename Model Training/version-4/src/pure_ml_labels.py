"""
Label generation for Pure ML model - NO signal filtering.

This module generates labels for EVERY candle, unlike the Signal Filter model
which only labels pre-filtered candles.

Key difference from Signal Filter model:
- Signal Filter: ~5% of candles get labels (only those passing BB/RSI filter)
- Pure ML: 100% of candles get labels (model learns what's important)

This means:
- Much larger dataset
- More severe class imbalance (~95% label=0)
- Model must learn the entry conditions itself
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional, List, Any
from dataclasses import dataclass
from enum import Enum
import warnings

# Try to import Numba for JIT compilation
try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    warnings.warn("Numba not installed. Using slower pure Python implementation.")


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class LabelReason(Enum):
    """Reason for label assignment."""
    TP_HIT = "tp_hit"
    SL_HIT = "sl_hit"
    TIMEOUT = "timeout"
    INSUFFICIENT_DATA = "insufficient_data"


class TradeDirection(Enum):
    """Trade direction."""
    SHORT = "short"
    LONG = "long"


@dataclass
class LabelStats:
    """Statistics about label generation."""
    total_rows: int
    labeled_rows: int
    dropped_rows: int
    win_count: int
    loss_count: int
    win_rate: float
    reason_counts: Dict[str, int]


@dataclass
class PrecomputedLabels:
    """Container for pre-computed labels."""
    labels: np.ndarray          # Shape: (n_rows,)
    reasons: np.ndarray         # Shape: (n_rows,)
    tp_pips: int
    sl_pips: int
    max_holding_bars: int
    valid_mask: np.ndarray      # Which rows have valid labels
    stats: LabelStats


@dataclass
class LabelCache:
    """Cache for all pre-computed labels."""
    cache: Dict[str, PrecomputedLabels]  # Key: "tp{tp}_sl{sl}_hold{hold}"
    base_df_hash: str
    
    def get_key(self, tp_pips: int, sl_pips: int, max_holding_bars: int) -> str:
        return f"tp{tp_pips}_sl{sl_pips}_hold{max_holding_bars}"
    
    def get(self, tp_pips: int, sl_pips: int, max_holding_bars: int) -> Optional[PrecomputedLabels]:
        key = self.get_key(tp_pips, sl_pips, max_holding_bars)
        return self.cache.get(key)
    
    def set(self, tp_pips: int, sl_pips: int, max_holding_bars: int, labels: PrecomputedLabels):
        key = self.get_key(tp_pips, sl_pips, max_holding_bars)
        self.cache[key] = labels


# =============================================================================
# NUMBA-ACCELERATED LABEL GENERATION
# =============================================================================

if NUMBA_AVAILABLE:
    @jit(nopython=True, parallel=True, cache=True)
    def _generate_labels_numba_short(
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        tp_distance: float,
        sl_distance: float,
        max_holding_bars: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Numba-accelerated SHORT label generation.
        
        For each candle:
        - Entry at close price
        - TP hit if any future low <= entry - tp_distance
        - SL hit if any future high >= entry + sl_distance
        - TP must hit BEFORE SL for label=1
        
        Returns:
            Tuple of (labels array, reasons array)
            reasons: 0=insufficient_data, 1=tp_hit, 2=sl_hit, 3=timeout
        """
        n = len(close)
        labels = np.zeros(n, dtype=np.int8)
        reasons = np.zeros(n, dtype=np.int8)
        
        for i in prange(n):
            # Check if we have enough future data
            if i + max_holding_bars >= n:
                labels[i] = 0
                reasons[i] = 0  # insufficient_data
                continue
            
            entry_price = close[i]
            tp_price = entry_price - tp_distance
            sl_price = entry_price + sl_distance
            
            found = False
            for j in range(i + 1, i + max_holding_bars + 1):
                # Check TP hit (price dropped to TP level)
                if low[j] <= tp_price:
                    labels[i] = 1
                    reasons[i] = 1  # tp_hit
                    found = True
                    break
                
                # Check SL hit (price rose to SL level)
                if high[j] >= sl_price:
                    labels[i] = 0
                    reasons[i] = 2  # sl_hit
                    found = True
                    break
            
            # Neither TP nor SL hit within max_holding_bars
            if not found:
                labels[i] = 0
                reasons[i] = 3  # timeout
        
        return labels, reasons

    @jit(nopython=True, parallel=True, cache=True)
    def _generate_labels_numba_long(
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        tp_distance: float,
        sl_distance: float,
        max_holding_bars: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Numba-accelerated LONG label generation.
        """
        n = len(close)
        labels = np.zeros(n, dtype=np.int8)
        reasons = np.zeros(n, dtype=np.int8)
        
        for i in prange(n):
            if i + max_holding_bars >= n:
                labels[i] = 0
                reasons[i] = 0
                continue
            
            entry_price = close[i]
            tp_price = entry_price + tp_distance
            sl_price = entry_price - sl_distance
            
            found = False
            for j in range(i + 1, i + max_holding_bars + 1):
                # Check TP hit (price rose to TP level)
                if high[j] >= tp_price:
                    labels[i] = 1
                    reasons[i] = 1
                    found = True
                    break
                
                # Check SL hit (price dropped to SL level)
                if low[j] <= sl_price:
                    labels[i] = 0
                    reasons[i] = 2
                    found = True
                    break
            
            if not found:
                labels[i] = 0
                reasons[i] = 3
        
        return labels, reasons

else:
    # Fallback pure Python implementation
    def _generate_labels_numba_short(close, high, low, tp_distance, sl_distance, max_holding_bars):
        n = len(close)
        labels = np.zeros(n, dtype=np.int8)
        reasons = np.zeros(n, dtype=np.int8)
        
        for i in range(n):
            if i + max_holding_bars >= n:
                labels[i] = 0
                reasons[i] = 0
                continue
            
            entry_price = close[i]
            tp_price = entry_price - tp_distance
            sl_price = entry_price + sl_distance
            
            found = False
            for j in range(i + 1, i + max_holding_bars + 1):
                if low[j] <= tp_price:
                    labels[i] = 1
                    reasons[i] = 1
                    found = True
                    break
                if high[j] >= sl_price:
                    labels[i] = 0
                    reasons[i] = 2
                    found = True
                    break
            
            if not found:
                labels[i] = 0
                reasons[i] = 3
        
        return labels, reasons

    def _generate_labels_numba_long(close, high, low, tp_distance, sl_distance, max_holding_bars):
        n = len(close)
        labels = np.zeros(n, dtype=np.int8)
        reasons = np.zeros(n, dtype=np.int8)
        
        for i in range(n):
            if i + max_holding_bars >= n:
                labels[i] = 0
                reasons[i] = 0
                continue
            
            entry_price = close[i]
            tp_price = entry_price + tp_distance
            sl_price = entry_price - sl_distance
            
            found = False
            for j in range(i + 1, i + max_holding_bars + 1):
                if high[j] >= tp_price:
                    labels[i] = 1
                    reasons[i] = 1
                    found = True
                    break
                if low[j] <= sl_price:
                    labels[i] = 0
                    reasons[i] = 2
                    found = True
                    break
            
            if not found:
                labels[i] = 0
                reasons[i] = 3
        
        return labels, reasons


# =============================================================================
# MAIN LABEL GENERATION FUNCTION
# =============================================================================

def generate_labels(
    df: pd.DataFrame,
    tp_pips: float,
    sl_pips: float,
    max_holding_bars: int,
    pip_value: float = 0.0001,
    direction: TradeDirection = TradeDirection.SHORT
) -> Tuple[pd.DataFrame, LabelStats]:
    """
    Generate labels for ALL candles (Pure ML approach).
    
    Unlike Signal Filter model, this labels EVERY candle without pre-filtering.
    
    Args:
        df: DataFrame with OHLC data
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        max_holding_bars: Maximum holding period
        pip_value: Value of one pip (0.0001 for EUR/USD)
        direction: Trade direction
        
    Returns:
        Tuple of (labeled DataFrame, LabelStats)
    """
    df = df.copy()
    n_rows = len(df)
    
    # Convert pips to price distance
    tp_distance = tp_pips * pip_value
    sl_distance = sl_pips * pip_value
    
    # Get price arrays
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    
    # Generate labels using Numba-accelerated function
    if direction == TradeDirection.SHORT:
        labels, reasons = _generate_labels_numba_short(
            close, high, low, tp_distance, sl_distance, max_holding_bars
        )
    else:
        labels, reasons = _generate_labels_numba_long(
            close, high, low, tp_distance, sl_distance, max_holding_bars
        )
    
    # Add labels to DataFrame
    df['label'] = labels
    
    # Convert reason codes to strings
    reason_map = {0: 'insufficient_data', 1: 'tp_hit', 2: 'sl_hit', 3: 'timeout'}
    df['label_reason'] = [reason_map[r] for r in reasons]
    
    # Create valid mask (exclude insufficient_data)
    valid_mask = reasons != 0
    
    # Compute statistics
    valid_labels = labels[valid_mask]
    win_count = int((valid_labels == 1).sum())
    loss_count = int((valid_labels == 0).sum())
    total_valid = len(valid_labels)
    
    # Count reasons
    reason_counts = {
        'tp_hit': int((reasons == 1).sum()),
        'sl_hit': int((reasons == 2).sum()),
        'timeout': int((reasons == 3).sum()),
        'insufficient_data': int((reasons == 0).sum())
    }
    
    stats = LabelStats(
        total_rows=n_rows,
        labeled_rows=total_valid,
        dropped_rows=reason_counts['insufficient_data'],
        win_count=win_count,
        loss_count=loss_count,
        win_rate=win_count / total_valid if total_valid > 0 else 0.0,
        reason_counts=reason_counts
    )
    
    return df, stats


def filter_valid_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter DataFrame to only rows with valid labels.
    
    Removes rows where label couldn't be computed (insufficient future data).
    """
    if 'label_reason' in df.columns:
        return df[df['label_reason'] != 'insufficient_data'].copy().reset_index(drop=True)
    return df.copy()


# =============================================================================
# PRE-COMPUTATION FOR BATCH PROCESSING
# =============================================================================

def precompute_all_labels(
    df: pd.DataFrame,
    label_configs: List[Tuple[int, int, int]],  # (tp, sl, hold) tuples
    pip_value: float = 0.0001,
    direction: TradeDirection = TradeDirection.SHORT,
    verbose: bool = True
) -> LabelCache:
    """
    Pre-compute labels for all (TP, SL, Hold) configurations.
    
    This is a MAJOR optimization - compute once, use many times.
    
    Args:
        df: Base DataFrame
        label_configs: List of (tp_pips, sl_pips, max_holding_bars) tuples
        pip_value: Pip value
        direction: Trade direction
        verbose: Print progress
        
    Returns:
        LabelCache with all pre-computed labels
    """
    # Create hash of base DataFrame for cache validation
    df_hash = f"{len(df)}_{df['close'].iloc[0]:.6f}_{df['close'].iloc[-1]:.6f}"
    
    cache = LabelCache(cache={}, base_df_hash=df_hash)
    
    # Get price arrays once
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    n_rows = len(df)
    
    if verbose:
        print(f"   Pre-computing {len(label_configs)} label configurations...")
    
    for idx, (tp_pips, sl_pips, max_holding_bars) in enumerate(label_configs):
        tp_distance = tp_pips * pip_value
        sl_distance = sl_pips * pip_value
        
        # Generate labels
        if direction == TradeDirection.SHORT:
            labels, reasons = _generate_labels_numba_short(
                close, high, low, tp_distance, sl_distance, max_holding_bars
            )
        else:
            labels, reasons = _generate_labels_numba_long(
                close, high, low, tp_distance, sl_distance, max_holding_bars
            )
        
        # Create valid mask
        valid_mask = reasons != 0
        
        # Compute stats
        valid_labels = labels[valid_mask]
        win_count = int((valid_labels == 1).sum())
        loss_count = int((valid_labels == 0).sum())
        total_valid = len(valid_labels)
        
        reason_counts = {
            'tp_hit': int((reasons == 1).sum()),
            'sl_hit': int((reasons == 2).sum()),
            'timeout': int((reasons == 3).sum()),
            'insufficient_data': int((reasons == 0).sum())
        }
        
        stats = LabelStats(
            total_rows=n_rows,
            labeled_rows=total_valid,
            dropped_rows=reason_counts['insufficient_data'],
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_count / total_valid if total_valid > 0 else 0.0,
            reason_counts=reason_counts
        )
        
        precomputed = PrecomputedLabels(
            labels=labels,
            reasons=reasons,
            tp_pips=tp_pips,
            sl_pips=sl_pips,
            max_holding_bars=max_holding_bars,
            valid_mask=valid_mask,
            stats=stats
        )
        
        cache.set(tp_pips, sl_pips, max_holding_bars, precomputed)
        
        if verbose and (idx + 1) % 10 == 0:
            print(f"      Computed {idx + 1}/{len(label_configs)}")
    
    if verbose:
        print(f"   ✅ Pre-computed {len(label_configs)} label configurations")
    
    return cache


def apply_precomputed_labels(
    df: pd.DataFrame,
    label_cache: LabelCache,
    tp_pips: int,
    sl_pips: int,
    max_holding_bars: int
) -> Tuple[pd.DataFrame, LabelStats]:
    """
    Apply pre-computed labels to DataFrame (Pure ML - no signal filtering).
    
    Args:
        df: Base DataFrame
        label_cache: Pre-computed label cache
        tp_pips, sl_pips, max_holding_bars: Label parameters
        
    Returns:
        Tuple of (labeled DataFrame with valid rows only, LabelStats)
    """
    precomputed = label_cache.get(tp_pips, sl_pips, max_holding_bars)
    if precomputed is None:
        raise ValueError(f"Labels not pre-computed for TP={tp_pips}, SL={sl_pips}, HOLD={max_holding_bars}")
    
    # Apply labels
    df = df.copy()
    df['label'] = precomputed.labels
    
    # Convert reason codes to strings
    reason_map = {0: 'insufficient_data', 1: 'tp_hit', 2: 'sl_hit', 3: 'timeout'}
    df['label_reason'] = [reason_map[r] for r in precomputed.reasons]
    
    # Filter to valid rows only (unlike Signal Filter, we keep ALL valid rows)
    df_valid = df[precomputed.valid_mask].copy().reset_index(drop=True)
    
    return df_valid, precomputed.stats


# =============================================================================
# UTILITIES
# =============================================================================

def get_unique_label_configs(config_space: Dict[str, Any]) -> List[Tuple[int, int, int]]:
    """
    Extract unique (TP, SL, Holding) combinations from config space.
    
    Args:
        config_space: Config space dictionary with tp_pips, sl_pips, max_holding_bars
        
    Returns:
        List of (tp, sl, holding) tuples
    """
    tp_cfg = config_space.get('tp_pips', {'min': 30, 'max': 80, 'step': 10})
    sl_pips = config_space.get('sl_pips', 40)  # Fixed SL for Pure ML
    hold_cfg = config_space.get('max_holding_bars', {'min': 12, 'max': 30, 'step': 6})
    
    # Handle both range and fixed values
    if isinstance(tp_cfg, dict):
        tp_values = list(range(tp_cfg['min'], tp_cfg['max'] + 1, tp_cfg['step']))
    else:
        tp_values = [tp_cfg]
    
    if isinstance(sl_pips, dict):
        sl_values = list(range(sl_pips['min'], sl_pips['max'] + 1, sl_pips['step']))
    else:
        sl_values = [sl_pips]
    
    if isinstance(hold_cfg, dict):
        hold_values = list(range(hold_cfg['min'], hold_cfg['max'] + 1, hold_cfg['step']))
    else:
        hold_values = [hold_cfg]
    
    configs = []
    for tp in tp_values:
        for sl in sl_values:
            for hold in hold_values:
                configs.append((tp, sl, hold))
    
    return configs


def estimate_class_imbalance(label_stats: LabelStats) -> Dict[str, float]:
    """
    Estimate class imbalance from label statistics.
    
    Args:
        label_stats: Label generation statistics
        
    Returns:
        Dictionary with imbalance metrics
    """
    total = label_stats.win_count + label_stats.loss_count
    if total == 0:
        return {'imbalance_ratio': 0, 'minority_pct': 0, 'majority_pct': 0}
    
    minority = min(label_stats.win_count, label_stats.loss_count)
    majority = max(label_stats.win_count, label_stats.loss_count)
    
    return {
        'imbalance_ratio': majority / minority if minority > 0 else float('inf'),
        'minority_pct': 100.0 * minority / total,
        'majority_pct': 100.0 * majority / total,
        'win_count': label_stats.win_count,
        'loss_count': label_stats.loss_count
    }
