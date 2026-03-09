"""
Model training, hyperparameter tuning, and probability calibration.
OPTIMIZED VERSION with LightGBM support.

Optimizations implemented:
- LightGBM as primary model (5-10x faster than sklearn GradientBoosting)
- Fallback to sklearn if LightGBM not available

This module handles:
1. Hyperparameter tuning with cross-validation
2. Model training with selected features
3. Probability calibration (Platt scaling / Isotonic)

Critical rules:
- Hyperparameter tuning uses TRAINING data only (inner CV)
- Calibration uses CALIBRATION data only (separate from training)
- No leakage from threshold/validation sets
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
import warnings
import joblib
from pathlib import Path
import time

from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, StratifiedKFold, TimeSeriesSplit
from sklearn.calibration import CalibratedClassifierCV
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning

# Try to import LightGBM
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    warnings.warn("LightGBM not installed. Using slower sklearn GradientBoosting. "
                  "Install with: pip install lightgbm")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class HyperparameterResult:
    """Result of hyperparameter tuning."""
    best_params: Dict[str, Any]
    best_score: float
    cv_results: Optional[Dict[str, Any]] = None
    all_params_tested: int = 0
    search_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
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
    training_class_balance: Optional[Dict[int, int]] = None
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions."""
        X_subset = self._prepare_features(X)
        return self.model.predict(X_subset)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get probability predictions."""
        X_subset = self._prepare_features(X)
        return self.model.predict_proba(X_subset)
    
    def get_proba_positive(self, X: pd.DataFrame) -> np.ndarray:
        """Get probability of positive class (label=1)."""
        proba = self.predict_proba(X)
        return proba[:, 1]
    
    def _prepare_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Prepare feature DataFrame for prediction."""
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
# MODEL TYPE DETECTION
# =============================================================================

def get_best_model_type() -> str:
    """Get the best available model type."""
    if LIGHTGBM_AVAILABLE:
        return 'LGBMClassifier'
    else:
        return 'GradientBoostingClassifier'


def is_lightgbm_available() -> bool:
    """Check if LightGBM is available."""
    return LIGHTGBM_AVAILABLE


# =============================================================================
# HYPERPARAMETER GRIDS
# =============================================================================

def get_default_param_grid(model_type: str = None) -> Dict[str, List]:
    """
    Get default hyperparameter grid for model type.
    
    Args:
        model_type: Type of model (auto-detects best if None)
        
    Returns:
        Parameter grid dictionary
    """
    if model_type is None:
        model_type = get_best_model_type()
    
    if model_type == 'LGBMClassifier':
        return {
            'n_estimators': [100, 200, 300, 500],
            'max_depth': [3, 4, 5, 6, 8],
            'learning_rate': [0.01, 0.05, 0.1],
            'num_leaves': [15, 31, 63],
            'min_child_samples': [10, 20, 50],
            'subsample': [0.8, 1.0]
        }
    elif model_type == 'GradientBoostingClassifier':
        return {
            'n_estimators': [100, 200, 300, 500],
            'max_depth': [3, 4, 5, 6, 8],
            'learning_rate': [0.01, 0.05, 0.1],
            'min_samples_leaf': [10, 20, 50],
            'subsample': [0.8, 1.0]
        }
    elif model_type == 'RandomForestClassifier':
        return {
            'n_estimators': [100, 200, 300, 500],
            'max_depth': [4, 6, 8, 10, None],
            'min_samples_leaf': [10, 20, 50],
            'max_features': ['sqrt', 'log2', 0.5]
        }
    else:
        return {}


def get_reduced_param_grid(model_type: str = None) -> Dict[str, List]:
    """
    Get reduced hyperparameter grid for faster tuning.
    
    Args:
        model_type: Type of model
        
    Returns:
        Reduced parameter grid dictionary
    """
    if model_type is None:
        model_type = get_best_model_type()
    
    if model_type == 'LGBMClassifier':
        return {
            'n_estimators': [100, 200, 300],
            'max_depth': [4, 5, 6],
            'learning_rate': [0.05, 0.1],
            'num_leaves': [31],
            'min_child_samples': [20, 50]
        }
    elif model_type == 'GradientBoostingClassifier':
        return {
            'n_estimators': [100, 200, 300],
            'max_depth': [4, 5, 6],
            'learning_rate': [0.05, 0.1],
            'min_samples_leaf': [20, 50]
        }
    elif model_type == 'RandomForestClassifier':
        return {
            'n_estimators': [100, 200, 300],
            'max_depth': [6, 8, 10],
            'min_samples_leaf': [20, 50]
        }
    else:
        return {}


# =============================================================================
# MODEL CREATION
# =============================================================================

def create_estimator(
    model_type: str = None,
    random_state: int = 42,
    n_jobs: int = 1,
    **kwargs
) -> BaseEstimator:
    """
    Create a model estimator.
    
    Args:
        model_type: Type of model to create (auto-detects best if None)
        random_state: Random state for reproducibility
        n_jobs: Number of parallel jobs (for LightGBM)
        **kwargs: Additional parameters for the model
        
    Returns:
        Model estimator instance
    """
    if model_type is None:
        model_type = get_best_model_type()
    
    if model_type == 'LGBMClassifier':
        if not LIGHTGBM_AVAILABLE:
            warnings.warn("LightGBM not available, falling back to GradientBoosting")
            model_type = 'GradientBoostingClassifier'
        else:
            default_params = {
                'n_estimators': 200,
                'max_depth': 5,
                'learning_rate': 0.1,
                'num_leaves': 31,
                'min_child_samples': 20,
                'subsample': 0.8,
                'random_state': random_state,
                'n_jobs': n_jobs,
                'verbose': -1,  # Suppress LightGBM output
                'force_col_wise': True  # Better for small datasets
            }
            default_params.update(kwargs)
            return lgb.LGBMClassifier(**default_params)
    
    if model_type == 'GradientBoostingClassifier':
        default_params = {
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.1,
            'min_samples_leaf': 20,
            'subsample': 0.8,
            'random_state': random_state,
            'validation_fraction': 0.1,
            'n_iter_no_change': 10
        }
        default_params.update(kwargs)
        return GradientBoostingClassifier(**default_params)
    
    elif model_type == 'RandomForestClassifier':
        default_params = {
            'n_estimators': 200,
            'max_depth': 8,
            'min_samples_leaf': 20,
            'random_state': random_state,
            'n_jobs': n_jobs
        }
        default_params.update(kwargs)
        return RandomForestClassifier(**default_params)
    
    else:
        raise ValueError(f"Unknown model type: {model_type}")


# =============================================================================
# HYPERPARAMETER TUNING
# =============================================================================

def tune_hyperparameters(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    feature_columns: List[str],
    param_grid: Optional[Dict[str, List]] = None,
    model_type: str = None,
    cv_folds: int = 3,
    scoring: str = 'average_precision',
    n_jobs: int = -1,
    random_state: int = 42,
    use_randomized: bool = False,
    n_iter: int = 50
) -> HyperparameterResult:
    """
    Perform hyperparameter tuning using grid search or randomized search.
    
    Args:
        X_train: Training features DataFrame
        y_train: Training labels Series
        feature_columns: List of feature column names to use
        param_grid: Hyperparameter grid (uses default if None)
        model_type: Type of model (auto-detects best if None)
        cv_folds: Number of cross-validation folds
        scoring: Scoring metric
        n_jobs: Number of parallel jobs
        random_state: Random state for reproducibility
        use_randomized: Use RandomizedSearchCV instead of GridSearchCV
        n_iter: Number of iterations for randomized search
        
    Returns:
        HyperparameterResult with best parameters
    """
    start_time = time.time()
    
    if model_type is None:
        model_type = get_best_model_type()
    
    # Prepare features
    available_features = [col for col in feature_columns if col in X_train.columns]
    X = X_train[available_features].copy()
    y = y_train.copy()
    
    # Handle NaN
    valid_mask = ~(X.isna().any(axis=1) | y.isna())
    X = X[valid_mask]
    y = y[valid_mask]
    
    # Handle infinite values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.mean())
    
    if len(X) < 50:
        warnings.warn(f"Very small training set for hyperparameter tuning: {len(X)} rows")
    
    # Get param grid
    if param_grid is None:
        param_grid = get_reduced_param_grid(model_type)
    
    # Create base estimator
    base_estimator = create_estimator(model_type=model_type, random_state=random_state, n_jobs=1)
    
    # Create cross-validation splitter
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    
    # Suppress warnings during search
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        
        if use_randomized:
            search = RandomizedSearchCV(
                estimator=base_estimator,
                param_distributions=param_grid,
                n_iter=n_iter,
                cv=cv,
                scoring=scoring,
                n_jobs=n_jobs,
                random_state=random_state,
                refit=True
            )
        else:
            search = GridSearchCV(
                estimator=base_estimator,
                param_grid=param_grid,
                cv=cv,
                scoring=scoring,
                n_jobs=n_jobs,
                refit=True
            )
        
        try:
            search.fit(X, y)
            
            return HyperparameterResult(
                best_params=search.best_params_,
                best_score=search.best_score_,
                cv_results=None,  # Don't store full results to save memory
                all_params_tested=len(search.cv_results_['params']),
                search_time_seconds=time.time() - start_time
            )
        
        except Exception as e:
            warnings.warn(f"Hyperparameter search failed: {e}. Using defaults.")
            return HyperparameterResult(
                best_params={},
                best_score=0.0,
                cv_results=None,
                all_params_tested=0,
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
    model_type: str = None,
    random_state: int = 42
) -> TrainedModel:
    """
    Train a model with specified hyperparameters.
    
    Args:
        X_train: Training features DataFrame
        y_train: Training labels Series
        feature_columns: List of feature column names
        hyperparameters: Model hyperparameters (uses defaults if None)
        model_type: Type of model (auto-detects best if None)
        random_state: Random state for reproducibility
        
    Returns:
        TrainedModel instance
    """
    if model_type is None:
        model_type = get_best_model_type()
    
    # Prepare features
    available_features = [col for col in feature_columns if col in X_train.columns]
    X = X_train[available_features].copy()
    y = y_train.copy()
    
    # Handle NaN and infinite values
    valid_mask = ~(X.isna().any(axis=1) | y.isna())
    X = X[valid_mask]
    y = y[valid_mask]
    
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.mean())
    
    # Create model with hyperparameters
    params = hyperparameters or {}
    model = create_estimator(model_type=model_type, random_state=random_state, **params)
    
    # Train
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        model.fit(X, y)
    
    # Class balance
    class_balance = {
        0: int((y == 0).sum()),
        1: int((y == 1).sum())
    }
    
    return TrainedModel(
        model=model,
        feature_names=available_features,
        hyperparameters=params,
        model_type=model_type,
        is_calibrated=False,
        calibration_method=None,
        training_rows=len(X),
        training_class_balance=class_balance
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
    Calibrate model probabilities using Platt scaling or isotonic regression.
    
    Args:
        trained_model: Already trained model
        X_cal: Calibration features DataFrame
        y_cal: Calibration labels Series
        method: 'sigmoid' (Platt scaling) or 'isotonic'
        
    Returns:
        Tuple of (calibrated TrainedModel, CalibrationResult)
    """
    # Prepare features
    X = X_cal[trained_model.feature_names].copy()
    y = y_cal.copy()
    
    # Handle NaN and infinite values
    valid_mask = ~(X.isna().any(axis=1) | y.isna())
    X = X[valid_mask]
    y = y[valid_mask]
    
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.mean())
    
    if len(X) < 20:
        warnings.warn(f"Very small calibration set: {len(X)} rows")
    
    # Get probabilities before calibration
    try:
        proba_before = trained_model.model.predict_proba(X)[:, 1]
        brier_before = np.mean((proba_before - y.values) ** 2)
    except Exception:
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
    
    # Get probabilities after calibration
    try:
        proba_after = calibrated.predict_proba(X)[:, 1]
        brier_after = np.mean((proba_after - y.values) ** 2)
    except Exception:
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
        training_rows=trained_model.training_rows,
        training_class_balance=trained_model.training_class_balance
    )
    
    calibration_result = CalibrationResult(
        calibrated_model=calibrated,
        method=method,
        brier_before=brier_before,
        brier_after=brier_after,
        improvement_pct=improvement_pct,
        calibration_rows=len(X)
    )
    
    return calibrated_model, calibration_result


# =============================================================================
# CONSENSUS HYPERPARAMETERS
# =============================================================================

def get_consensus_hyperparameters(
    hp_results: List[HyperparameterResult],
    method: str = 'best_score'
) -> Dict[str, Any]:
    """
    Get consensus hyperparameters from multiple fold results.
    
    Args:
        hp_results: List of HyperparameterResult from each fold
        method: 'best_score' (use params from best scoring fold) or
                'mode' (use most common value for each param)
        
    Returns:
        Consensus hyperparameters dictionary
    """
    if not hp_results:
        return {}
    
    if method == 'best_score':
        # Use params from the best scoring fold
        best_idx = np.argmax([r.best_score for r in hp_results])
        return hp_results[best_idx].best_params.copy()
    
    elif method == 'mode':
        # Use most common value for each parameter
        all_params = [r.best_params for r in hp_results]
        
        # Get all parameter names
        param_names = set()
        for params in all_params:
            param_names.update(params.keys())
        
        consensus = {}
        for param in param_names:
            values = [p.get(param) for p in all_params if param in p]
            if values:
                # Use most common value
                from collections import Counter
                consensus[param] = Counter(values).most_common(1)[0][0]
        
        return consensus
    
    else:
        return hp_results[0].best_params.copy()


# =============================================================================
# MODEL PERSISTENCE
# =============================================================================

def save_model(
    trained_model: TrainedModel,
    filepath: str
) -> None:
    """
    Save trained model to file.
    
    Args:
        trained_model: TrainedModel to save
        filepath: Path to output file
    """
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(trained_model, filepath)


def load_model(filepath: str) -> TrainedModel:
    """
    Load trained model from file.
    
    Args:
        filepath: Path to model file
        
    Returns:
        TrainedModel instance
    """
    return joblib.load(filepath)


# =============================================================================
# FEATURE IMPORTANCE
# =============================================================================

def get_feature_importance(
    trained_model: TrainedModel
) -> pd.DataFrame:
    """
    Get feature importance from trained model.
    
    Args:
        trained_model: Trained model
        
    Returns:
        DataFrame with feature names and importance scores
    """
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
        elif hasattr(model, 'coef_'):
            importances = np.abs(model.coef_).flatten()
        else:
            importances = np.ones(len(trained_model.feature_names))
    except Exception:
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


# =============================================================================
# QUICK TRAIN (FOR SPEED)
# =============================================================================

def quick_train(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    feature_columns: List[str],
    random_state: int = 42
) -> TrainedModel:
    """
    Quick training with default hyperparameters.
    
    Uses LightGBM if available for maximum speed.
    No hyperparameter tuning.
    
    Args:
        X_train: Training features
        y_train: Training labels
        feature_columns: Feature column names
        random_state: Random state
        
    Returns:
        TrainedModel
    """
    return train_model(
        X_train=X_train,
        y_train=y_train,
        feature_columns=feature_columns,
        hyperparameters=None,  # Use defaults
        model_type=get_best_model_type(),
        random_state=random_state
    )