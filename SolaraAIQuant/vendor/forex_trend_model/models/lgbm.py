"""
LightGBM Model Wrapper — inference only (SAQ vendored copy).
ForexTrendLGBM kept for joblib deserialization compatibility.
Training helpers and optuna dependency removed.
"""

import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LABEL_MAP     = {-1: 0, 0: 1, 1: 2}
LABEL_INVERSE = {0: -1, 1: 0, 2: 1}


class ForexTrendLGBM:
    """LightGBM wrapper for 3-class trend classification."""

    DEFAULT_PARAMS = {
        'n_estimators':      500,
        'max_depth':         6,
        'learning_rate':     0.05,
        'num_leaves':        31,
        'min_child_samples': 20,
        'reg_alpha':         0.1,
        'reg_lambda':        0.1,
        'class_weight':      'balanced',
        'random_state':      42,
        'n_jobs':            -1,
        'verbose':           -1,
    }

    def __init__(self, params: dict = None):
        self.params       = {**self.DEFAULT_PARAMS, **(params or {})}
        self.model        = None
        self.feature_cols = None
        self.is_fitted    = False

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        mapped = self.model.predict(X[self.feature_cols])
        return np.vectorize(LABEL_INVERSE.get)(mapped)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        data = X[self.feature_cols]
        try:
            return self.model.predict_proba(data)
        except (AttributeError, TypeError):
            try:
                raw = self.model.booster_.predict(
                    data.values if hasattr(data, 'values') else data
                )
                if raw.ndim == 1:
                    raw = raw.reshape(1, -1)
                return raw
            except Exception:
                return self.model.predict_proba(data.values)

    def save(self, path) -> None:
        joblib.dump(self, Path(path))

    @classmethod
    def load(cls, path) -> 'ForexTrendLGBM':
        return joblib.load(Path(path))
