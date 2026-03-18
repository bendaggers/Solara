"""
predictors/base_predictor.py — Abstract Base Predictor
=======================================================
All model strategy classes must inherit from this.
"""
from abc import ABC, abstractmethod
import pandas as pd


class BasePredictor(ABC):
    """Abstract base for all SAQ ML model predictors."""

    def __init__(self, entry) -> None:
        """
        Args:
            entry: ModelRegistryEntry — provides model path, magic,
                   min_confidence, comment, and all config.
        """
        self._entry = entry

    @abstractmethod
    def predict(self, featured_df: pd.DataFrame) -> list:
        """
        Run inference on the featured DataFrame.

        Args:
            featured_df: One row per symbol, all features computed.
                         This is a copy — safe to mutate.

        Returns:
            List of RawSignal objects. Empty list = no signals this bar.
        """
        ...

    @abstractmethod
    def get_feature_list(self) -> list[str]:
        """Return the list of feature column names this model requires."""
        ...

    def get_metadata(self) -> dict:
        """Return model metadata for logging and health tracking."""
        return {
            "name": self._entry.name,
            "magic": self._entry.magic,
            "model_type": self._entry.model_type,
            "timeframe": self._entry.timeframe,
            "feature_version": self._entry.feature_version,
            "min_confidence": self._entry.min_confidence,
        }
