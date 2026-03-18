"""
Solara AI Quant - Predictors Module

ML model predictors that generate trading signals.

Available Predictors:
- StellaAlphaLongPredictor: MTF trend following LONG strategy

To add a new predictor:
1. Create new file in predictors/
2. Inherit from BasePredictor
3. Implement predict() and get_required_features()
4. Register in model_registry.yaml
"""

from .base_predictor import (
    BasePredictor,
    PredictionSignal
)

from .stella_alpha_long import StellaAlphaLongPredictor

__all__ = [
    'BasePredictor',
    'PredictionSignal',
    'StellaAlphaLongPredictor',
]
