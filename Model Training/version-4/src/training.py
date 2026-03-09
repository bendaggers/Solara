"""
Training module - Standalone implementation for Pure ML pipeline.

This module handles:
1. Hyperparameter tuning with cross-validation
2. Model training with selected features
3. Probability calibration
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import warnings
import joblib
import time
from pathlib import Path

# Suppress warnings
warnings.filterwarnings('ignore')
os.environ['LIGHTGBM_VERBOSITY'] = '-1'

from sklearn.model_selection import RandomizedSearchCV, GridSearchCV, TimeSeriesSplit
from sklearn.calibration import CalibratedClassifierCV
from sklearn.base import BaseEstimator

# Try LightGBM
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
class HyperparameterResult:
    """Result of hyperparameter tuning."""
    best_params: Dict[str, Any]
    best_score: float
    all_params_tested: int = 0
    search_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'all_params_tested': self.all_params_tested,
            'search_time_seconds': self.search_time_seconds
        }


@dataclass
class TrainedModel:
    """Container for a trained model with metadata."""
    model: BaseEstimator
    feature_names: List[str]
    hyperparameters: Dict[str, Any]
    model_type: str = 'LGBMClassifier'
    is_calibrated: bool = False
    calibration_method: Optional[str] = None
    training_rows: int = 0
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_subset = self._prepare_features(X)
        return self.model.predict(X_subset)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_subset = self._prepare_features(X)
        return self.model.predict_proba(X_subset)
    
    def get_proba_positive(self, X: pd.DataFrame) -> np.ndarray:
        proba = self.predict_proba(X)
        return proba[:, 1]
    
    def _prepare_features(self, X: pd.DataFrame) -> pd.DataFrame:
        X_subset = X[self.feature_names].copy()
        X_subset = X_subset.replace([np.inf, -np.inf], np.nan)
        X_subset = X_subset.fillna(X_subset.mean())
        return X_subset


@dataclass
class CalibrationResult:
    """Result of probability calibration."""
    calibrated_model: BaseEstimator
    method: str
    brier_before: float
    brier_after: float
    improvement_pct: float
    calibration_rows: int


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_best_model_type() -> str:
    return 'LGBMClassifier' if LIGHTGBM_AVAILABLE else 'GradientBoostingClassifier'


def get_default_param_grid(model_type: str = None) -> Dict[str, List]:
    if model_type is None:
        model_type = get_best_model_type()
    
    if model_type == 'LGBMClassifier':
        return {
            'n_estimators': [100, 200, 300],
            'max_depth': [3, 4, 5, 6],
            'learning_rate': [0.05, 0.1],
            'num_leaves': [15, 31],
            'min_child_samples': [20, 50]
        }
    else:
        return {
            'n_estimators': [100, 200, 300],
            'max_depth': [3, 4, 5, 6],
            'learning_rate': [0.05, 0.1],
            'min_samples_leaf': [20, 50]
        }


# =============================================================================
# HYPERPARAMETER TUNING
# =============================================================================

def tune_hyperparameters(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    feature_columns: List[str],
    param_grid: Optional[Dict[str, List]] = None,
    method: str = 'randomized',
    n_iter: int = 30,
    cv: int = 3,
    scoring: str = 'average_precision'
) -> HyperparameterResult:
    """
    Tune hyperparameters using cross-validation.
    """
    start_time = time.time()
    
    # Prepare data
    X = X_train[feature_columns].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.mean())
    y = y_train.copy()
    
    # Create estimator
    if LIGHTGBM_AVAILABLE:
        estimator = LGBMClassifier(random_state=42, verbose=-1, force_col_wise=True)
    else:
        estimator = GradientBoostingClassifier(random_state=42)
    
    # Get param grid
    if param_grid is None:
        param_grid = get_default_param_grid()
    
    # Create CV splitter
    cv_splitter = TimeSeriesSplit(n_splits=cv)
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        
        if method == 'randomized':
            search = RandomizedSearchCV(
                estimator=estimator,
                param_distributions=param_grid,
                n_iter=n_iter,
                cv=cv_splitter,
                scoring=scoring,
                random_state=42,
                n_jobs=-1
            )
        else:
            search = GridSearchCV(
                estimator=estimator,
                param_grid=param_grid,
                cv=cv_splitter,
                scoring=scoring,
                n_jobs=-1
            )
        
        search.fit(X, y)
    
    return HyperparameterResult(
        best_params=search.best_params_,
        best_score=search.best_score_,
        all_params_tested=len(search.cv_results_['params']),
        search_time_seconds=time.time() - start_time
    )


# =============================================================================
# MODEL TRAINING
# =============================================================================

def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    feature_columns: List[str],
    hyperparameters: Optional[Dict[str, Any]] = None,
    model_type: str = None
) -> TrainedModel:
    """
    Train model with given hyperparameters.
    """
    if model_type is None:
        model_type = get_best_model_type()
    
    # Prepare data
    X = X_train[feature_columns].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.mean())
    y = y_train.copy()
    
    # Create and train model
    params = hyperparameters or {}
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        
        if model_type == 'LGBMClassifier' and LIGHTGBM_AVAILABLE:
            model = LGBMClassifier(
                random_state=42,
                verbose=-1,
                force_col_wise=True,
                **params
            )
        else:
            model = GradientBoostingClassifier(
                random_state=42,
                **params
            )
        
        model.fit(X, y)
    
    return TrainedModel(
        model=model,
        feature_names=feature_columns,
        hyperparameters=params,
        model_type=model_type,
        training_rows=len(X)
    )


# =============================================================================
# PROBABILITY CALIBRATION
# =============================================================================

def calibrate_model(
    trained_model: TrainedModel,
    X_cal: pd.DataFrame,
    y_cal: pd.Series,
    method: str = 'sigmoid'
) -> Tuple[TrainedModel, CalibrationResult]:
    """
    Calibrate model probabilities.
    """
    # Prepare features
    X = X_cal[trained_model.feature_names].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.mean())
    y = y_cal.copy()
    
    # Filter valid rows
    valid_mask = ~X.isna().any(axis=1) & ~y.isna()
    X = X[valid_mask]
    y = y[valid_mask]
    
    # Get pre-calibration probabilities
    try:
        proba_before = trained_model.model.predict_proba(X)[:, 1]
        brier_before = np.mean((proba_before - y.values) ** 2)
    except:
        brier_before = 1.0
    
    # Calibrate
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        
        calibrated = CalibratedClassifierCV(
            estimator=trained_model.model,
            method=method,
            cv='prefit'
        )
        calibrated.fit(X, y)
    
    # Get post-calibration probabilities
    try:
        proba_after = calibrated.predict_proba(X)[:, 1]
        brier_after = np.mean((proba_after - y.values) ** 2)
    except:
        brier_after = brier_before
    
    improvement_pct = (brier_before - brier_after) / brier_before * 100 if brier_before > 0 else 0
    
    # Create calibrated model container
    calibrated_model = TrainedModel(
        model=calibrated,
        feature_names=trained_model.feature_names,
        hyperparameters=trained_model.hyperparameters,
        model_type=trained_model.model_type,
        is_calibrated=True,
        calibration_method=method,
        training_rows=trained_model.training_rows
    )
    
    cal_result = CalibrationResult(
        calibrated_model=calibrated,
        method=method,
        brier_before=brier_before,
        brier_after=brier_after,
        improvement_pct=improvement_pct,
        calibration_rows=len(X)
    )
    
    return calibrated_model, cal_result


# =============================================================================
# CONSENSUS & PERSISTENCE
# =============================================================================

def get_consensus_hyperparameters(hp_results: List[HyperparameterResult]) -> Dict[str, Any]:
    """Get consensus hyperparameters from multiple results."""
    if not hp_results:
        return {}
    best_idx = np.argmax([r.best_score for r in hp_results])
    return hp_results[best_idx].best_params.copy()


def save_model(trained_model: TrainedModel, filepath: str) -> None:
    """Save trained model to file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(trained_model, filepath)


def load_model(filepath: str) -> TrainedModel:
    """Load trained model from file."""
    return joblib.load(filepath)


def get_feature_importance(trained_model: TrainedModel) -> pd.DataFrame:
    """Get feature importance from trained model."""
    model = trained_model.model
    
    # Handle calibrated models
    if hasattr(model, 'estimator'):
        model = model.estimator
    if hasattr(model, 'calibrated_classifiers_'):
        model = model.calibrated_classifiers_[0].estimator
    
    # Get importances
    try:
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
        else:
            importances = np.ones(len(trained_model.feature_names))
    except:
        importances = np.ones(len(trained_model.feature_names))
    
    # Normalize
    total = importances.sum()
    if total > 0:
        importances = importances / total
    
    df = pd.DataFrame({
        'feature_name': trained_model.feature_names,
        'importance': importances
    })
    
    return df.sort_values('importance', ascending=False).reset_index(drop=True)
