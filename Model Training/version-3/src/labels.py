"""
Label generation and signal filtering - OPTIMIZED VERSION.

Optimizations implemented:
1. Numba JIT compilation for 50-100x faster label generation
2. Pre-computation of ALL label sets (unique TP×Holding combinations)
3. Pre-computation of ALL signal masks (unique BB×RSI combinations)
4. Vectorized operations throughout

This module handles:
1. Label generation (trade outcome based on TP/SL/holding period)
2. Signal generation (entry rules based on BB/RSI thresholds)
3. Pre-computation for batch processing
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
class SignalStats:
    """Statistics about signal generation."""
    total_rows: int
    signal_rows: int
    signal_pct: float


@dataclass
class PrecomputedLabels:
    """Container for pre-computed labels."""
    labels: np.ndarray  # Shape: (n_rows,)
    reasons: np.ndarray  # Shape: (n_rows,)
    tp_pips: int
    sl_pips: int
    max_holding_bars: int
    valid_mask: np.ndarray  # Which rows have valid labels
    stats: LabelStats


@dataclass
class PrecomputedSignals:
    """Container for pre-computed signal masks."""
    signal_mask: np.ndarray  # Boolean array
    bb_threshold: float
    rsi_threshold: int
    signal_count: int


@dataclass
class LabelCache:
    """Cache for all pre-computed labels."""
    cache: Dict[str, PrecomputedLabels]  # Key: "tp{tp}_sl{sl}_hold{hold}"
    base_df_hash: str  # To verify cache validity
    
    def get_key(self, tp_pips: int, sl_pips: int, max_holding_bars: int) -> str:
        return f"tp{tp_pips}_sl{sl_pips}_hold{max_holding_bars}"
    
    def get(self, tp_pips: int, sl_pips: int, max_holding_bars: int) -> Optional[PrecomputedLabels]:
        key = self.get_key(tp_pips, sl_pips, max_holding_bars)
        return self.cache.get(key)
    
    def set(self, tp_pips: int, sl_pips: int, max_holding_bars: int, labels: PrecomputedLabels):
        key = self.get_key(tp_pips, sl_pips, max_holding_bars)
        self.cache[key] = labels


@dataclass
class SignalCache:
    """Cache for all pre-computed signal masks."""
    cache: Dict[str, PrecomputedSignals]  # Key: "bb{bb}_rsi{rsi}"
    base_df_hash: str
    
    def get_key(self, bb_threshold: float, rsi_threshold: int) -> str:
        return f"bb{bb_threshold:.2f}_rsi{rsi_threshold}"
    
    def get(self, bb_threshold: float, rsi_threshold: int) -> Optional[PrecomputedSignals]:
        key = self.get_key(bb_threshold, rsi_threshold)
        return self.cache.get(key)
    
    def set(self, bb_threshold: float, rsi_threshold: int, signals: PrecomputedSignals):
        key = self.get_key(bb_threshold, rsi_threshold)
        self.cache[key] = signals


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
        
        Returns:
            Tuple of (labels array, reasons array)
            reasons: 0=insufficient_data, 1=tp_hit, 2=sl_hit, 3=timeout
        """
        n = len(close)
        labels = np.zeros(n, dtype=np.int8)
        reasons = np.zeros(n, dtype=np.int8)  # 0=insufficient, 1=tp, 2=sl, 3=timeout
        
        # Parallel loop over all candles
        for i in prange(n):
            # Check if we have enough future data
            if i + max_holding_bars >= n:
                labels[i] = 0
                reasons[i] = 0  # insufficient_data
                continue
            
            entry_price = close[i]
            tp_price = entry_price - tp_distance
            sl_price = entry_price + sl_distance
            
            # Check future bars
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
# LABEL GENERATION (SINGLE CONFIG)
# =============================================================================

def generate_labels_fast(
    df: pd.DataFrame,
    tp_pips: float,
    sl_pips: float,
    max_holding_bars: int,
    pip_value: float = 0.0001,
    direction: TradeDirection = TradeDirection.SHORT,
    close_col: str = 'close',
    high_col: str = 'high',
    low_col: str = 'low'
) -> Tuple[np.ndarray, np.ndarray, LabelStats]:
    """
    Fast label generation using Numba.
    
    Returns labels and reasons as arrays (doesn't modify DataFrame).
    
    Args:
        df: DataFrame with OHLC data
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        max_holding_bars: Maximum bars to hold trade
        pip_value: Value of one pip
        direction: Trade direction
        
    Returns:
        Tuple of (labels array, reasons array, LabelStats)
    """
    n_rows = len(df)
    
    # Convert pips to price distance
    tp_distance = tp_pips * pip_value
    sl_distance = sl_pips * pip_value
    
    # Get price arrays
    close = df[close_col].values.astype(np.float64)
    high = df[high_col].values.astype(np.float64)
    low = df[low_col].values.astype(np.float64)
    
    # Generate labels using Numba
    if direction == TradeDirection.SHORT:
        labels, reasons = _generate_labels_numba_short(
            close, high, low, tp_distance, sl_distance, max_holding_bars
        )
    else:
        labels, reasons = _generate_labels_numba_long(
            close, high, low, tp_distance, sl_distance, max_holding_bars
        )
    
    # Convert reason codes to strings for stats
    reason_map = {0: 'insufficient_data', 1: 'tp_hit', 2: 'sl_hit', 3: 'timeout'}
    reason_counts = {}
    for code in [0, 1, 2, 3]:
        count = int((reasons == code).sum())
        if count > 0:
            reason_counts[reason_map[code]] = count
    
    # Valid mask (excluding insufficient data)
    valid_mask = reasons != 0
    valid_labels = labels[valid_mask]
    
    win_count = int((valid_labels == 1).sum())
    loss_count = int((valid_labels == 0).sum())
    labeled_rows = len(valid_labels)
    
    stats = LabelStats(
        total_rows=n_rows,
        labeled_rows=labeled_rows,
        dropped_rows=n_rows - labeled_rows,
        win_count=win_count,
        loss_count=loss_count,
        win_rate=win_count / labeled_rows if labeled_rows > 0 else 0.0,
        reason_counts=reason_counts
    )
    
    return labels, reasons, stats


def generate_labels(
    df: pd.DataFrame,
    tp_pips: float,
    sl_pips: float,
    max_holding_bars: int,
    pip_value: float = 0.0001,
    direction: TradeDirection = TradeDirection.SHORT,
    close_col: str = 'close',
    high_col: str = 'high',
    low_col: str = 'low'
) -> Tuple[pd.DataFrame, LabelStats]:
    """
    Generate binary labels based on trade outcome.
    
    Returns DataFrame with label columns added.
    """
    df = df.copy()
    
    labels, reasons, stats = generate_labels_fast(
        df, tp_pips, sl_pips, max_holding_bars,
        pip_value, direction, close_col, high_col, low_col
    )
    
    # Convert reason codes to strings
    reason_map = {0: 'insufficient_data', 1: 'tp_hit', 2: 'sl_hit', 3: 'timeout'}
    reason_strings = np.array([reason_map[r] for r in reasons])
    
    df['label'] = labels
    df['label_reason'] = reason_strings
    
    # Filter out insufficient data
    valid_mask = reasons != 0
    df_valid = df[valid_mask].copy().reset_index(drop=True)
    
    return df_valid, stats


# =============================================================================
# PRE-COMPUTATION: ALL LABEL COMBINATIONS
# =============================================================================

def precompute_all_labels(
    df: pd.DataFrame,
    tp_values: List[int],
    sl_pips: int,
    holding_values: List[int],
    pip_value: float = 0.0001,
    direction: TradeDirection = TradeDirection.SHORT,
    verbose: bool = True
) -> LabelCache:
    """
    Pre-compute labels for ALL unique (TP, SL, Holding) combinations.
    
    This is run ONCE before processing all configs.
    
    Args:
        df: Base DataFrame with OHLC data
        tp_values: List of TP pip values to pre-compute
        sl_pips: SL pip value (fixed)
        holding_values: List of max holding bar values
        pip_value: Pip value for instrument
        direction: Trade direction
        verbose: Print progress
        
    Returns:
        LabelCache with all pre-computed labels
    """
    if verbose:
        total = len(tp_values) * len(holding_values)
        print(f"\n📊 Pre-computing {total} label combinations...")
    
    # Create cache
    cache = LabelCache(
        cache={},
        base_df_hash=str(hash(tuple(df['close'].head(100).values)))
    )
    
    # Get price arrays once
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    n_rows = len(df)
    
    count = 0
    for tp_pips in tp_values:
        for max_holding_bars in holding_values:
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
            valid_labels = labels[valid_mask]
            
            win_count = int((valid_labels == 1).sum())
            loss_count = int((valid_labels == 0).sum())
            labeled_rows = len(valid_labels)
            
            # Convert reason codes
            reason_map = {0: 'insufficient_data', 1: 'tp_hit', 2: 'sl_hit', 3: 'timeout'}
            reason_counts = {}
            for code in [0, 1, 2, 3]:
                c = int((reasons == code).sum())
                if c > 0:
                    reason_counts[reason_map[code]] = c
            
            stats = LabelStats(
                total_rows=n_rows,
                labeled_rows=labeled_rows,
                dropped_rows=n_rows - labeled_rows,
                win_count=win_count,
                loss_count=loss_count,
                win_rate=win_count / labeled_rows if labeled_rows > 0 else 0.0,
                reason_counts=reason_counts
            )
            
            # Store in cache
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
            
            count += 1
            if verbose and count % 10 == 0:
                print(f"   Computed {count}/{total} label sets...")
    
    if verbose:
        print(f"   ✅ Pre-computed {count} label combinations")
    
    return cache


# =============================================================================
# SIGNAL GENERATION
# =============================================================================

def generate_signals_fast(
    bb_position: np.ndarray,
    rsi_values: np.ndarray,
    bb_threshold: float,
    rsi_threshold: float,
    direction: TradeDirection = TradeDirection.SHORT
) -> np.ndarray:
    """
    Fast vectorized signal generation.
    
    Returns boolean mask array.
    """
    if direction == TradeDirection.SHORT:
        # SHORT: BB position high AND RSI high
        signal_mask = (bb_position >= bb_threshold) & (rsi_values >= rsi_threshold)
    else:
        # LONG: BB position low AND RSI low
        signal_mask = (bb_position <= (1 - bb_threshold)) & (rsi_values <= (100 - rsi_threshold))
    
    return signal_mask.astype(np.int8)


def generate_signals(
    df: pd.DataFrame,
    bb_threshold: float,
    rsi_threshold: float,
    bb_column: str = 'bb_position',
    rsi_column: str = 'rsi_value',
    direction: TradeDirection = TradeDirection.SHORT
) -> Tuple[pd.DataFrame, SignalStats]:
    """
    Generate entry signals based on BB position and RSI.
    """
    df = df.copy()
    
    bb_values = df[bb_column].values
    rsi_values = df[rsi_column].values
    
    signals = generate_signals_fast(
        bb_values, rsi_values, bb_threshold, rsi_threshold, direction
    )
    
    df['signal'] = signals
    signal_count = int(signals.sum())
    
    stats = SignalStats(
        total_rows=len(df),
        signal_rows=signal_count,
        signal_pct=100.0 * signal_count / len(df) if len(df) > 0 else 0.0
    )
    
    return df, stats


# =============================================================================
# PRE-COMPUTATION: ALL SIGNAL COMBINATIONS
# =============================================================================

def precompute_all_signals(
    df: pd.DataFrame,
    bb_values: List[float],
    rsi_values: List[int],
    bb_column: str = 'bb_position',
    rsi_column: str = 'rsi_value',
    direction: TradeDirection = TradeDirection.SHORT,
    verbose: bool = True
) -> SignalCache:
    """
    Pre-compute signal masks for ALL unique (BB, RSI) combinations.
    
    This is run ONCE before processing all configs.
    
    Args:
        df: Base DataFrame with indicator data
        bb_values: List of BB threshold values
        rsi_values: List of RSI threshold values
        bb_column: Name of BB position column
        rsi_column: Name of RSI column
        direction: Trade direction
        verbose: Print progress
        
    Returns:
        SignalCache with all pre-computed signal masks
    """
    if verbose:
        total = len(bb_values) * len(rsi_values)
        print(f"\n📊 Pre-computing {total} signal combinations...")
    
    cache = SignalCache(
        cache={},
        base_df_hash=str(hash(tuple(df[bb_column].head(100).values)))
    )
    
    # Get arrays once
    bb_arr = df[bb_column].values.astype(np.float64)
    rsi_arr = df[rsi_column].values.astype(np.float64)
    
    count = 0
    for bb_threshold in bb_values:
        for rsi_threshold in rsi_values:
            signal_mask = generate_signals_fast(
                bb_arr, rsi_arr, bb_threshold, rsi_threshold, direction
            )
            
            signal_count = int(signal_mask.sum())
            
            precomputed = PrecomputedSignals(
                signal_mask=signal_mask,
                bb_threshold=bb_threshold,
                rsi_threshold=rsi_threshold,
                signal_count=signal_count
            )
            cache.set(bb_threshold, rsi_threshold, precomputed)
            
            count += 1
    
    if verbose:
        print(f"   ✅ Pre-computed {count} signal combinations")
    
    return cache


# =============================================================================
# FILTERING
# =============================================================================

def filter_by_signal(
    df: pd.DataFrame,
    signal_column: str = 'signal'
) -> pd.DataFrame:
    """Filter DataFrame to only rows where signal == 1."""
    if signal_column not in df.columns:
        raise ValueError(f"Signal column '{signal_column}' not found")
    
    return df[df[signal_column] == 1].copy().reset_index(drop=True)


def apply_precomputed_labels_and_signals(
    df: pd.DataFrame,
    label_cache: LabelCache,
    signal_cache: SignalCache,
    tp_pips: int,
    sl_pips: int,
    max_holding_bars: int,
    bb_threshold: float,
    rsi_threshold: int
) -> Tuple[pd.DataFrame, LabelStats, SignalStats]:
    """
    Apply pre-computed labels and signals to DataFrame.
    
    This is the FAST path - no computation, just lookup and filter.
    
    Args:
        df: Base DataFrame
        label_cache: Pre-computed label cache
        signal_cache: Pre-computed signal cache
        tp_pips, sl_pips, max_holding_bars: Label parameters
        bb_threshold, rsi_threshold: Signal parameters
        
    Returns:
        Tuple of (filtered DataFrame, LabelStats, SignalStats)
    """
    # Look up pre-computed labels
    precomputed_labels = label_cache.get(tp_pips, sl_pips, max_holding_bars)
    if precomputed_labels is None:
        raise ValueError(f"Labels not pre-computed for TP={tp_pips}, SL={sl_pips}, HOLD={max_holding_bars}")
    
    # Look up pre-computed signals
    precomputed_signals = signal_cache.get(bb_threshold, rsi_threshold)
    if precomputed_signals is None:
        raise ValueError(f"Signals not pre-computed for BB={bb_threshold}, RSI={rsi_threshold}")
    
    # Apply labels
    df = df.copy()
    df['label'] = precomputed_labels.labels
    
    # Convert reason codes to strings
    reason_map = {0: 'insufficient_data', 1: 'tp_hit', 2: 'sl_hit', 3: 'timeout'}
    df['label_reason'] = [reason_map[r] for r in precomputed_labels.reasons]
    
    # Apply signals
    df['signal'] = precomputed_signals.signal_mask
    
    # Filter: valid labels AND signal == 1
    valid_mask = precomputed_labels.valid_mask & (precomputed_signals.signal_mask == 1)
    df_filtered = df[valid_mask].copy().reset_index(drop=True)
    
    # Stats
    label_stats = precomputed_labels.stats
    signal_stats = SignalStats(
        total_rows=int(precomputed_labels.valid_mask.sum()),
        signal_rows=len(df_filtered),
        signal_pct=100.0 * len(df_filtered) / precomputed_labels.valid_mask.sum() 
                   if precomputed_labels.valid_mask.sum() > 0 else 0.0
    )
    
    return df_filtered, label_stats, signal_stats


# =============================================================================
# COMBINED PIPELINE (BACKWARD COMPATIBLE)
# =============================================================================

def generate_labels_and_signals(
    df: pd.DataFrame,
    tp_pips: float,
    sl_pips: float,
    max_holding_bars: int,
    bb_threshold: float,
    rsi_threshold: float,
    pip_value: float = 0.0001,
    direction: TradeDirection = TradeDirection.SHORT,
    bb_column: str = 'bb_position',
    rsi_column: str = 'rsi_value',
    use_vectorized: bool = True,
    label_cache: Optional[LabelCache] = None,
    signal_cache: Optional[SignalCache] = None
) -> Tuple[pd.DataFrame, LabelStats, SignalStats]:
    """
    Combined pipeline: generate labels, then signals, then filter.
    
    If caches are provided, uses pre-computed values (FAST).
    Otherwise, computes on the fly (SLOW but works).
    """
    # FAST PATH: Use pre-computed caches
    if label_cache is not None and signal_cache is not None:
        return apply_precomputed_labels_and_signals(
            df=df,
            label_cache=label_cache,
            signal_cache=signal_cache,
            tp_pips=int(tp_pips),
            sl_pips=int(sl_pips),
            max_holding_bars=max_holding_bars,
            bb_threshold=bb_threshold,
            rsi_threshold=int(rsi_threshold)
        )
    
    # SLOW PATH: Compute on the fly
    df_labeled, label_stats = generate_labels(
        df=df,
        tp_pips=tp_pips,
        sl_pips=sl_pips,
        max_holding_bars=max_holding_bars,
        pip_value=pip_value,
        direction=direction
    )
    
    df_signaled, signal_stats = generate_signals(
        df=df_labeled,
        bb_threshold=bb_threshold,
        rsi_threshold=rsi_threshold,
        bb_column=bb_column,
        rsi_column=rsi_column,
        direction=direction
    )
    
    df_filtered = filter_by_signal(df_signaled)
    
    signal_stats = SignalStats(
        total_rows=len(df_labeled),
        signal_rows=len(df_filtered),
        signal_pct=100.0 * len(df_filtered) / len(df_labeled) if len(df_labeled) > 0 else 0.0
    )
    
    return df_filtered, label_stats, signal_stats


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
    tp_cfg = config_space.get('tp_pips', {'min': 40, 'max': 120, 'step': 10})
    sl_pips = config_space.get('sl_pips', 40)
    hold_cfg = config_space.get('max_holding_bars', {'min': 18, 'max': 40, 'step': 6})
    
    tp_values = list(range(tp_cfg['min'], tp_cfg['max'] + 1, tp_cfg['step']))
    hold_values = list(range(hold_cfg['min'], hold_cfg['max'] + 1, hold_cfg['step']))
    
    configs = []
    for tp in tp_values:
        for hold in hold_values:
            configs.append((tp, sl_pips, hold))
    
    return configs


def get_unique_signal_configs(config_space: Dict[str, Any]) -> List[Tuple[float, int]]:
    """
    Extract unique (BB, RSI) combinations from config space.
    
    Args:
        config_space: Config space dictionary
        
    Returns:
        List of (bb_threshold, rsi_threshold) tuples
    """
    bb_cfg = config_space.get('bb_threshold', {'min': 0.85, 'max': 0.95, 'step': 0.01})
    rsi_cfg = config_space.get('rsi_threshold', {'min': 50, 'max': 95, 'step': 1})
    
    bb_values = []
    bb = bb_cfg['min']
    while bb <= bb_cfg['max'] + 0.001:
        bb_values.append(round(bb, 2))
        bb += bb_cfg['step']
    
    rsi_values = list(range(rsi_cfg['min'], rsi_cfg['max'] + 1, rsi_cfg['step']))
    
    configs = []
    for bb in bb_values:
        for rsi in rsi_values:
            configs.append((bb, rsi))
    
    return configs


def estimate_precomputation_size(
    n_rows: int,
    n_label_configs: int,
    n_signal_configs: int
) -> Dict[str, float]:
    """
    Estimate memory usage for pre-computed caches.
    
    Returns:
        Dictionary with size estimates in MB
    """
    # Labels: int8 array per config
    labels_per_config = n_rows * 1  # 1 byte per label
    reasons_per_config = n_rows * 1  # 1 byte per reason
    valid_mask_per_config = n_rows * 1  # 1 byte per bool
    
    total_labels_bytes = n_label_configs * (labels_per_config + reasons_per_config + valid_mask_per_config)
    
    # Signals: int8 array per config
    signal_per_config = n_rows * 1
    total_signals_bytes = n_signal_configs * signal_per_config
    
    return {
        'label_cache_mb': total_labels_bytes / (1024 * 1024),
        'signal_cache_mb': total_signals_bytes / (1024 * 1024),
        'total_mb': (total_labels_bytes + total_signals_bytes) / (1024 * 1024)
    }
