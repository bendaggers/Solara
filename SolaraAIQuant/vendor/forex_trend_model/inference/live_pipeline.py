"""
Live Trend Predictor — inference only (SAQ vendored copy).
Stripped to the from_package() loader; full predict() pipeline removed.
"""

import logging
from pathlib import Path

import joblib

from .post_process import DEFAULT_THRESHOLDS

logger = logging.getLogger(__name__)


class LiveTrendPredictor:
    """
    Stateful live inference engine for one or multiple pairs.
    SAQ uses only from_package() to load a model, then accesses
    predictor.model and predictor.feature_cols directly.
    """

    def __init__(
        self,
        model,
        training_stats: dict,
        feature_cols: list,
        thresholds: dict = None,
        model_version: str = 'unknown',
    ):
        self.model          = model
        self.training_stats = training_stats
        self.feature_cols   = feature_cols
        self.thresholds     = thresholds or DEFAULT_THRESHOLDS.copy()
        self.model_version  = model_version
        self.prior_states: dict = {}

    @classmethod
    def from_package(
        cls,
        package_path,
        thresholds: dict = None,
    ) -> 'LiveTrendPredictor':
        """Load a saved model package (.joblib) and return a predictor."""
        package = joblib.load(package_path)
        logger.info(
            f"Loaded model package: "
            f"pair={package.get('pair')} | "
            f"tf={package.get('timeframe')} | "
            f"version={package.get('version')}"
        )
        return cls(
            model=package['model'],
            training_stats=package['training_stats'],
            feature_cols=package['feature_cols'],
            thresholds=thresholds,
            model_version=package.get('version', 'unknown'),
        )
