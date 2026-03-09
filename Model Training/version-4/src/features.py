"""
Feature selection module - Standalone implementation.

This module provides RFE (Recursive Feature Elimination) for selecting
the most predictive features.
"""

import os
import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')
os.environ['LIGHTGBM_VERBOSITY'] = '-1'

from sklearn.feature_selection import RFECV
from sklearn.model_selection import TimeSeriesSplit

# Try LightGBM, fallback to sklearn
try:
    import lightgbm as lgb
    from lightgbm import LGBMClassifier
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    lgb = None

if not LIGHTGBM_AVAILABLE:
    from sklearn.ensemble import GradientBoostingClassifier


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RFEResult:
    """Result of RFE feature selection."""
    selected_features: List[str]
    feature_ranking: Dict[str, int]
    n_features_selected: int
    optimal_n_features: int
    cv_scores: Optional[List[float]] = None


# =============================================================================
# FEATURE SELECTION
# =============================================================================

def rfe_select(
    X: pd.DataFrame,
    y: pd.Series,
    feature_columns: List[str],
    min_features: int = 5,
    max_features: int = 20,
    step: int = 1,
    cv: int = 3,
    scoring: str = 'average_precision'
) -> RFEResult:
    """
    Perform RFE feature selection.
    
    Args:
        X: Feature DataFrame
        y: Labels
        feature_columns: List of feature column names
        min_features: Minimum features to select
        max_features: Maximum features to select
        step: Number of features to remove at each iteration
        cv: Number of CV folds
        scoring: Scoring metric
        
    Returns:
        RFEResult with selected features
    """
    # Prepare data
    X_subset = X[feature_columns].copy()
    
    # Handle NaN/inf
    X_subset = X_subset.replace([np.inf, -np.inf], np.nan)
    X_subset = X_subset.fillna(X_subset.mean())
    
    # Create estimator with all warnings suppressed
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        
        if LIGHTGBM_AVAILABLE:
            estimator = LGBMClassifier(
                n_estimators=100,
                max_depth=4,
                random_state=42,
                verbose=-1,
                force_col_wise=True
            )
        else:
            estimator = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=4,
                random_state=42
            )
        
        # RFECV
        cv_splitter = TimeSeriesSplit(n_splits=cv)
        
        selector = RFECV(
            estimator=estimator,
            step=step,
            cv=cv_splitter,
            scoring=scoring,
            min_features_to_select=min_features
        )
        
        selector.fit(X_subset, y)
    
    # Get selected features
    selected_mask = selector.support_
    selected_features = [f for f, s in zip(feature_columns, selected_mask) if s]
    
    # Limit to max_features
    if len(selected_features) > max_features:
        # Sort by ranking and take top max_features
        rankings = selector.ranking_
        ranked = sorted(zip(feature_columns, rankings), key=lambda x: x[1])
        selected_features = [f for f, r in ranked[:max_features]]
    
    # Create ranking dictionary
    feature_ranking = {f: int(r) for f, r in zip(feature_columns, selector.ranking_)}
    
    return RFEResult(
        selected_features=selected_features,
        feature_ranking=feature_ranking,
        n_features_selected=len(selected_features),
        optimal_n_features=selector.n_features_,
        cv_scores=list(selector.cv_results_.get('mean_test_score', []))
    )


def get_consensus_features(
    rfe_results: List[RFEResult],
    min_occurrence_ratio: float = 0.5
) -> List[str]:
    """
    Get consensus features from multiple RFE runs.
    """
    from collections import Counter
    
    if not rfe_results:
        return []
    
    # Count feature occurrences
    feature_counts = Counter()
    for result in rfe_results:
        feature_counts.update(result.selected_features)
    
    # Filter by occurrence threshold
    threshold = len(rfe_results) * min_occurrence_ratio
    consensus = [f for f, c in feature_counts.items() if c >= threshold]
    
    # Sort by frequency
    consensus.sort(key=lambda x: feature_counts[x], reverse=True)
    
    return consensus
