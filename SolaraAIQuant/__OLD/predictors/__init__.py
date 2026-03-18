"""Predictor modules for Solara AI Quant."""

from predictors.base_predictor import BasePredictor
from predictors.bb_reversal_long import BBReversalLongPredictor
from predictors.bb_reversal_short import BBReversalShortPredictor
from predictors.dummy_predictor import DummyRandomPredictor

__all__ = [
    "BasePredictor",
    "BBReversalLongPredictor",
    "BBReversalShortPredictor",
    "DummyRandomPredictor",
]