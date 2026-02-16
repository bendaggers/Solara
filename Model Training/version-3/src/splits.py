"""
Walk-forward validation splitting.

This module handles:
1. Defining time-based fold boundaries
2. Splitting DataFrames into train/calibration/threshold subsets
3. Validation of split integrity

Critical rules:
- No shuffling (chronological order preserved)
- No overlap between subsets
- Calibration always follows train
- Threshold always follows calibration
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Iterator, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FoldBoundary:
    """Defines time boundaries for a single fold."""
    fold_number: int
    
    # Training set boundaries
    train_start: datetime
    train_end: datetime
    
    # Calibration set boundaries
    calibration_start: datetime
    calibration_end: datetime
    
    # Threshold optimization set boundaries
    threshold_start: datetime
    threshold_end: datetime
    
    # Row indices (populated when applied to DataFrame)
    train_start_idx: Optional[int] = None
    train_end_idx: Optional[int] = None
    calibration_start_idx: Optional[int] = None
    calibration_end_idx: Optional[int] = None
    threshold_start_idx: Optional[int] = None
    threshold_end_idx: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'fold_number': self.fold_number,
            'train_start': self.train_start.strftime('%Y-%m-%d') if self.train_start else None,
            'train_end': self.train_end.strftime('%Y-%m-%d') if self.train_end else None,
            'cal_start': self.calibration_start.strftime('%Y-%m-%d') if self.calibration_start else None,
            'cal_end': self.calibration_end.strftime('%Y-%m-%d') if self.calibration_end else None,
            'thresh_start': self.threshold_start.strftime('%Y-%m-%d') if self.threshold_start else None,
            'thresh_end': self.threshold_end.strftime('%Y-%m-%d') if self.threshold_end else None
        }


@dataclass
class FoldData:
    """Contains the actual DataFrames for a fold."""
    fold_number: int
    train_df: pd.DataFrame
    calibration_df: pd.DataFrame
    threshold_df: pd.DataFrame
    boundary: FoldBoundary
    
    @property
    def train_size(self) -> int:
        return len(self.train_df)
    
    @property
    def calibration_size(self) -> int:
        return len(self.calibration_df)
    
    @property
    def threshold_size(self) -> int:
        return len(self.threshold_df)
    
    def get_sizes(self) -> Dict[str, int]:
        """Get sizes of all subsets."""
        return {
            'train': self.train_size,
            'calibration': self.calibration_size,
            'threshold': self.threshold_size,
            'total': self.train_size + self.calibration_size + self.threshold_size
        }


@dataclass
class SplitStats:
    """Statistics about the walk-forward splits."""
    n_folds: int
    total_rows: int
    fold_sizes: List[Dict[str, int]]
    date_ranges: List[Dict[str, str]]
    
    # Validation results
    is_valid: bool = True
    validation_issues: List[str] = field(default_factory=list)


# =============================================================================
# SPLIT DEFINITION
# =============================================================================

def define_walk_forward_splits(
    df: pd.DataFrame,
    n_folds: int,
    train_ratio: float = 0.60,
    calibration_ratio: float = 0.20,
    threshold_ratio: float = 0.20,
    timestamp_column: str = 'timestamp',
    expanding_window: bool = True
) -> Tuple[List[FoldBoundary], SplitStats]:
    """
    Define walk-forward fold boundaries based on time.
    
    Expanding window (default):
        Fold 1: Train [T0 → T1], Cal [T1 → T1.5], Thresh [T1.5 → T2]
        Fold 2: Train [T0 → T2], Cal [T2 → T2.5], Thresh [T2.5 → T3]
        ...
    
    Rolling window:
        Fold 1: Train [T0 → T1], Cal [T1 → T1.5], Thresh [T1.5 → T2]
        Fold 2: Train [T1 → T2], Cal [T2 → T2.5], Thresh [T2.5 → T3]
        ...
    
    Args:
        df: DataFrame with timestamp column (must be sorted)
        n_folds: Number of folds
        train_ratio: Proportion of each fold's data for training
        calibration_ratio: Proportion for calibration
        threshold_ratio: Proportion for threshold optimization
        timestamp_column: Name of timestamp column
        expanding_window: If True, use expanding window; else rolling
        
    Returns:
        Tuple of (list of FoldBoundary, SplitStats)
    """
    # Validate ratios
    total_ratio = train_ratio + calibration_ratio + threshold_ratio
    if not np.isclose(total_ratio, 1.0, atol=0.01):
        raise ValueError(f"Ratios must sum to 1.0, got {total_ratio}")
    
    # Validate timestamp column
    if timestamp_column not in df.columns:
        raise ValueError(f"Timestamp column '{timestamp_column}' not found")
    
    # Ensure sorted
    if not df[timestamp_column].is_monotonic_increasing:
        raise ValueError("DataFrame must be sorted by timestamp")
    
    n_rows = len(df)
    timestamps = df[timestamp_column].values
    
    # Calculate fold sizes
    # For expanding window: we need space for n_folds validation periods
    # Each validation period = calibration + threshold
    validation_ratio = calibration_ratio + threshold_ratio
    
    if expanding_window:
        # Expanding: first fold has train_ratio of initial data
        # Each subsequent fold adds more training data
        # Total data is divided into n_folds+1 segments
        segment_size = n_rows // (n_folds + 1)
    else:
        # Rolling: each fold has same size
        fold_size = n_rows // n_folds
        segment_size = fold_size
    
    boundaries = []
    
    for fold_idx in range(n_folds):
        if expanding_window:
            # Training starts from beginning, ends at expanding point
            train_start_idx = 0
            train_end_idx = (fold_idx + 1) * segment_size
            
            # Calibration follows training
            cal_start_idx = train_end_idx
            cal_end_idx = cal_start_idx + int(segment_size * calibration_ratio / validation_ratio)
            
            # Threshold follows calibration
            thresh_start_idx = cal_end_idx
            thresh_end_idx = min(cal_start_idx + segment_size, n_rows - 1)
        else:
            # Rolling window
            fold_start_idx = fold_idx * segment_size
            fold_end_idx = min((fold_idx + 1) * segment_size, n_rows)
            
            fold_rows = fold_end_idx - fold_start_idx
            train_rows = int(fold_rows * train_ratio)
            cal_rows = int(fold_rows * calibration_ratio)
            
            train_start_idx = fold_start_idx
            train_end_idx = train_start_idx + train_rows
            
            cal_start_idx = train_end_idx
            cal_end_idx = cal_start_idx + cal_rows
            
            thresh_start_idx = cal_end_idx
            thresh_end_idx = fold_end_idx
        
        # Ensure indices are within bounds
        train_end_idx = min(train_end_idx, n_rows - 1)
        cal_start_idx = min(cal_start_idx, n_rows - 1)
        cal_end_idx = min(cal_end_idx, n_rows - 1)
        thresh_start_idx = min(thresh_start_idx, n_rows - 1)
        thresh_end_idx = min(thresh_end_idx, n_rows - 1)
        
        # Skip fold if insufficient data
        if thresh_end_idx <= thresh_start_idx:
            continue
        
        boundary = FoldBoundary(
            fold_number=fold_idx + 1,
            train_start=pd.Timestamp(timestamps[train_start_idx]),
            train_end=pd.Timestamp(timestamps[train_end_idx]),
            calibration_start=pd.Timestamp(timestamps[cal_start_idx]),
            calibration_end=pd.Timestamp(timestamps[cal_end_idx]),
            threshold_start=pd.Timestamp(timestamps[thresh_start_idx]),
            threshold_end=pd.Timestamp(timestamps[thresh_end_idx]),
            train_start_idx=train_start_idx,
            train_end_idx=train_end_idx,
            calibration_start_idx=cal_start_idx,
            calibration_end_idx=cal_end_idx,
            threshold_start_idx=thresh_start_idx,
            threshold_end_idx=thresh_end_idx
        )
        
        boundaries.append(boundary)
    
    # Compute stats
    fold_sizes = []
    date_ranges = []
    validation_issues = []
    
    for boundary in boundaries:
        train_size = boundary.train_end_idx - boundary.train_start_idx
        cal_size = boundary.calibration_end_idx - boundary.calibration_start_idx
        thresh_size = boundary.threshold_end_idx - boundary.threshold_start_idx
        
        fold_sizes.append({
            'fold': boundary.fold_number,
            'train': train_size,
            'calibration': cal_size,
            'threshold': thresh_size
        })
        
        date_ranges.append(boundary.to_dict())
        
        # Validate no overlap
        if boundary.calibration_start_idx < boundary.train_end_idx:
            validation_issues.append(
                f"Fold {boundary.fold_number}: Calibration overlaps with training"
            )
        if boundary.threshold_start_idx < boundary.calibration_end_idx:
            validation_issues.append(
                f"Fold {boundary.fold_number}: Threshold overlaps with calibration"
            )
    
    stats = SplitStats(
        n_folds=len(boundaries),
        total_rows=n_rows,
        fold_sizes=fold_sizes,
        date_ranges=date_ranges,
        is_valid=len(validation_issues) == 0,
        validation_issues=validation_issues
    )
    
    return boundaries, stats


# =============================================================================
# SPLIT APPLICATION
# =============================================================================

def apply_split(
    df: pd.DataFrame,
    boundary: FoldBoundary,
    timestamp_column: str = 'timestamp'
) -> FoldData:
    """
    Apply a fold boundary to split DataFrame into train/cal/threshold.
    
    Args:
        df: DataFrame to split
        boundary: FoldBoundary defining the split points
        timestamp_column: Name of timestamp column
        
    Returns:
        FoldData containing the three DataFrames
    """
    # Use index-based slicing if indices are available
    if boundary.train_start_idx is not None:
        train_df = df.iloc[boundary.train_start_idx:boundary.train_end_idx].copy()
        cal_df = df.iloc[boundary.calibration_start_idx:boundary.calibration_end_idx].copy()
        thresh_df = df.iloc[boundary.threshold_start_idx:boundary.threshold_end_idx].copy()
    else:
        # Fall back to timestamp-based filtering
        train_df = df[
            (df[timestamp_column] >= boundary.train_start) &
            (df[timestamp_column] < boundary.train_end)
        ].copy()
        
        cal_df = df[
            (df[timestamp_column] >= boundary.calibration_start) &
            (df[timestamp_column] < boundary.calibration_end)
        ].copy()
        
        thresh_df = df[
            (df[timestamp_column] >= boundary.threshold_start) &
            (df[timestamp_column] <= boundary.threshold_end)
        ].copy()
    
    # Reset indices
    train_df = train_df.reset_index(drop=True)
    cal_df = cal_df.reset_index(drop=True)
    thresh_df = thresh_df.reset_index(drop=True)
    
    return FoldData(
        fold_number=boundary.fold_number,
        train_df=train_df,
        calibration_df=cal_df,
        threshold_df=thresh_df,
        boundary=boundary
    )


def apply_all_splits(
    df: pd.DataFrame,
    boundaries: List[FoldBoundary],
    timestamp_column: str = 'timestamp'
) -> List[FoldData]:
    """
    Apply all fold boundaries to create list of FoldData.
    
    Args:
        df: DataFrame to split
        boundaries: List of FoldBoundary objects
        timestamp_column: Name of timestamp column
        
    Returns:
        List of FoldData objects
    """
    folds = []
    for boundary in boundaries:
        fold_data = apply_split(df, boundary, timestamp_column)
        folds.append(fold_data)
    return folds


# =============================================================================
# ITERATOR FOR WALK-FORWARD
# =============================================================================

def walk_forward_iterator(
    df: pd.DataFrame,
    n_folds: int,
    train_ratio: float = 0.60,
    calibration_ratio: float = 0.20,
    threshold_ratio: float = 0.20,
    timestamp_column: str = 'timestamp',
    expanding_window: bool = True
) -> Iterator[FoldData]:
    """
    Iterator that yields FoldData for each walk-forward fold.
    
    This is a convenience function that combines define and apply.
    
    Args:
        df: DataFrame with timestamp column
        n_folds: Number of folds
        train_ratio: Proportion for training
        calibration_ratio: Proportion for calibration
        threshold_ratio: Proportion for threshold optimization
        timestamp_column: Name of timestamp column
        expanding_window: Use expanding window (True) or rolling (False)
        
    Yields:
        FoldData for each fold
    """
    boundaries, _ = define_walk_forward_splits(
        df=df,
        n_folds=n_folds,
        train_ratio=train_ratio,
        calibration_ratio=calibration_ratio,
        threshold_ratio=threshold_ratio,
        timestamp_column=timestamp_column,
        expanding_window=expanding_window
    )
    
    for boundary in boundaries:
        yield apply_split(df, boundary, timestamp_column)


# =============================================================================
# SPLIT FOR FILTERED DATA
# =============================================================================

def apply_split_to_filtered(
    df_filtered: pd.DataFrame,
    boundary: FoldBoundary,
    timestamp_column: str = 'timestamp'
) -> FoldData:
    """
    Apply fold boundary to a filtered DataFrame.
    
    When the DataFrame has been filtered (e.g., by signal), we can't use
    index-based slicing. This function uses timestamp-based filtering.
    
    Args:
        df_filtered: Filtered DataFrame (may have non-contiguous original indices)
        boundary: FoldBoundary with timestamp boundaries
        timestamp_column: Name of timestamp column
        
    Returns:
        FoldData containing the three DataFrames
    """
    # Use timestamp-based filtering (boundaries have datetime objects)
    train_df = df_filtered[
        (df_filtered[timestamp_column] >= boundary.train_start) &
        (df_filtered[timestamp_column] < boundary.calibration_start)
    ].copy().reset_index(drop=True)
    
    cal_df = df_filtered[
        (df_filtered[timestamp_column] >= boundary.calibration_start) &
        (df_filtered[timestamp_column] < boundary.threshold_start)
    ].copy().reset_index(drop=True)
    
    thresh_df = df_filtered[
        (df_filtered[timestamp_column] >= boundary.threshold_start) &
        (df_filtered[timestamp_column] <= boundary.threshold_end)
    ].copy().reset_index(drop=True)
    
    return FoldData(
        fold_number=boundary.fold_number,
        train_df=train_df,
        calibration_df=cal_df,
        threshold_df=thresh_df,
        boundary=boundary
    )


# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def validate_fold_data(
    fold_data: FoldData,
    min_train_rows: int = 100,
    min_calibration_rows: int = 30,
    min_threshold_rows: int = 30,
    label_column: str = 'label'
) -> Dict[str, Any]:
    """
    Validate a fold's data meets minimum requirements.
    
    Args:
        fold_data: FoldData to validate
        min_train_rows: Minimum training rows required
        min_calibration_rows: Minimum calibration rows required
        min_threshold_rows: Minimum threshold rows required
        label_column: Name of label column
        
    Returns:
        Validation report dictionary
    """
    report = {
        'fold_number': fold_data.fold_number,
        'is_valid': True,
        'issues': [],
        'sizes': fold_data.get_sizes()
    }
    
    # Check minimum sizes
    if fold_data.train_size < min_train_rows:
        report['is_valid'] = False
        report['issues'].append(
            f"Insufficient training rows: {fold_data.train_size} < {min_train_rows}"
        )
    
    if fold_data.calibration_size < min_calibration_rows:
        report['is_valid'] = False
        report['issues'].append(
            f"Insufficient calibration rows: {fold_data.calibration_size} < {min_calibration_rows}"
        )
    
    if fold_data.threshold_size < min_threshold_rows:
        report['is_valid'] = False
        report['issues'].append(
            f"Insufficient threshold rows: {fold_data.threshold_size} < {min_threshold_rows}"
        )
    
    # Check for both classes in each subset
    for name, subset_df in [
        ('train', fold_data.train_df),
        ('calibration', fold_data.calibration_df),
        ('threshold', fold_data.threshold_df)
    ]:
        if label_column in subset_df.columns:
            n_classes = subset_df[label_column].nunique()
            if n_classes < 2:
                report['issues'].append(
                    f"Warning: {name} has only {n_classes} class(es)"
                )
    
    return report


def validate_no_leakage(
    fold_data: FoldData,
    timestamp_column: str = 'timestamp'
) -> Dict[str, Any]:
    """
    Validate there's no data leakage between subsets.
    
    Args:
        fold_data: FoldData to validate
        timestamp_column: Name of timestamp column
        
    Returns:
        Validation report dictionary
    """
    report = {
        'fold_number': fold_data.fold_number,
        'is_valid': True,
        'issues': []
    }
    
    # Get max/min timestamps for each subset
    train_max = fold_data.train_df[timestamp_column].max()
    cal_min = fold_data.calibration_df[timestamp_column].min()
    cal_max = fold_data.calibration_df[timestamp_column].max()
    thresh_min = fold_data.threshold_df[timestamp_column].min()
    
    # Check ordering
    if not fold_data.calibration_df.empty and train_max >= cal_min:
        report['is_valid'] = False
        report['issues'].append(
            f"Leakage: train_max ({train_max}) >= cal_min ({cal_min})"
        )
    
    if not fold_data.threshold_df.empty and cal_max >= thresh_min:
        report['is_valid'] = False
        report['issues'].append(
            f"Leakage: cal_max ({cal_max}) >= thresh_min ({thresh_min})"
        )
    
    return report


# =============================================================================
# COMBINING DATA ACROSS FOLDS
# =============================================================================

def combine_train_data(
    folds: List[FoldData]
) -> pd.DataFrame:
    """
    Combine training data from all folds for final model training.
    
    For expanding window, later folds include earlier data, so we just
    take the last fold's training data.
    
    For rolling window, we concatenate all unique training data.
    
    Args:
        folds: List of FoldData objects
        
    Returns:
        Combined training DataFrame
    """
    if not folds:
        return pd.DataFrame()
    
    # For expanding window, last fold has all training data
    # This is a simple heuristic - just return the largest training set
    largest_fold = max(folds, key=lambda f: f.train_size)
    return largest_fold.train_df.copy()


def combine_calibration_data(
    folds: List[FoldData]
) -> pd.DataFrame:
    """
    Combine calibration data from all folds.
    
    Args:
        folds: List of FoldData objects
        
    Returns:
        Combined calibration DataFrame
    """
    if not folds:
        return pd.DataFrame()
    
    cal_dfs = [fold.calibration_df for fold in folds if not fold.calibration_df.empty]
    if not cal_dfs:
        return pd.DataFrame()
    
    combined = pd.concat(cal_dfs, ignore_index=True)
    
    # Remove duplicates based on timestamp if present
    if 'timestamp' in combined.columns:
        combined = combined.drop_duplicates(subset=['timestamp']).reset_index(drop=True)
    
    return combined


# =============================================================================
# SUMMARY UTILITIES
# =============================================================================

def get_split_summary(
    boundaries: List[FoldBoundary],
    stats: SplitStats
) -> str:
    """
    Generate human-readable summary of splits.
    
    Args:
        boundaries: List of FoldBoundary objects
        stats: SplitStats object
        
    Returns:
        Formatted summary string
    """
    lines = [
        f"Walk-Forward Split Summary",
        f"=" * 50,
        f"Total Rows: {stats.total_rows:,}",
        f"Number of Folds: {stats.n_folds}",
        f"",
        "Fold Details:"
    ]
    
    for boundary, sizes in zip(boundaries, stats.fold_sizes):
        lines.append(
            f"  Fold {boundary.fold_number}: "
            f"Train={sizes['train']:,} | "
            f"Cal={sizes['calibration']:,} | "
            f"Thresh={sizes['threshold']:,}"
        )
        lines.append(
            f"    Dates: {boundary.train_start.strftime('%Y-%m-%d')} → "
            f"{boundary.threshold_end.strftime('%Y-%m-%d')}"
        )
    
    if stats.validation_issues:
        lines.append("")
        lines.append("Validation Issues:")
        for issue in stats.validation_issues:
            lines.append(f"  ⚠️ {issue}")
    
    return "\n".join(lines)


def boundaries_to_dict(boundaries: List[FoldBoundary]) -> List[Dict[str, Any]]:
    """
    Convert list of FoldBoundary to list of dictionaries.
    
    Useful for logging and serialization.
    
    Args:
        boundaries: List of FoldBoundary objects
        
    Returns:
        List of dictionaries
    """
    return [b.to_dict() for b in boundaries]
