"""Probability Calibration — Platt scaling wrapper for trend models."""

import numpy as np
import pandas as pd
import joblib
import logging
from pathlib import Path
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)

LABEL_MAP     = {-1: 0, 0: 1, 1: 2}
LABEL_INVERSE = {0: -1, 1: 0, 2: 1}


class TrendModelCalibrator:
    """
    Wraps any fitted trend model with Platt scaling calibration.
    predict_proba() returns calibrated 3-class probabilities: [down, sideways, up].
    """

    def __init__(self, base_model, method: str = 'sigmoid'):
        self.base_model       = base_model
        self.method           = method
        self.calibrated_model = None
        self.is_calibrated    = False

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        feature_cols = self.base_model.feature_cols
        n = len(X)

        try:
            raw_probs = self.base_model.predict_proba(X[feature_cols])
        except Exception as exc:
            logger.error(
                f"TrendModelCalibrator: base_model.predict_proba failed: "
                f"{type(exc).__name__}: {exc} — returning uniform probs"
            )
            return np.full((n, 3), 1.0 / 3.0)

        if not self.is_calibrated:
            logger.warning("Model not calibrated — returning raw probabilities.")
            return raw_probs

        try:
            return self.calibrated_model.predict_proba(raw_probs)
        except Exception as exc:
            logger.warning(f"Calibrated predict_proba failed: {exc} — returning raw probs")
            return raw_probs

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        probs  = self.predict_proba(X)
        mapped = np.argmax(probs, axis=1)
        return np.vectorize(LABEL_INVERSE.get)(mapped)

    def calibrate(self, X_val, y_val):
        feature_cols = self.base_model.feature_cols
        y_v      = np.vectorize(LABEL_MAP.get)(y_val)
        raw_probs = self.base_model.predict_proba(X_val[feature_cols])
        self.calibrated_model = LogisticRegression(
            multi_class='multinomial', solver='lbfgs', max_iter=1000, C=1.0, random_state=42,
        )
        self.calibrated_model.fit(raw_probs, y_v)
        self.is_calibrated = True
        return self

    def save(self, path) -> None:
        joblib.dump(self, Path(path))

    @classmethod
    def load(cls, path) -> 'TrendModelCalibrator':
        return joblib.load(path)
