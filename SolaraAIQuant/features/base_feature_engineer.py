"""
Solara AI Quant - Base Feature Engineer

Abstract base class for all per-model feature engineering classes.

Each model defines its own feature engineering class that inherits
from BaseFeatureEngineer. The class is responsible for transforming
the merged base DataFrame into the exact feature set that model
was trained on.

To create a new feature engineer:
    1. Inherit from BaseFeatureEngineer
    2. Implement compute() — transform merged df into featured df
    3. Implement get_required_input_columns() — columns needed from CSV/merge
    4. Implement get_output_features() — feature columns the model consumes
    5. Register class_path in model_registry.yaml under feature_engineering_class
"""

from abc import ABC, abstractmethod
from typing import List
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class BaseFeatureEngineer(ABC):
    """
    Abstract base for all model-specific feature engineers.

    Each model has its own concrete subclass. The execution engine
    instantiates the class via dynamic import and calls compute()
    before passing data to the predictor.

    Design principles:
    - compute() receives the merged base DataFrame (after tf_merger)
    - compute() returns a new DataFrame with all required features added
    - Never modify the input DataFrame in-place — always work on a copy
    - Never assume columns are present beyond get_required_input_columns()
    - Handle NaN/inf values — models should never receive them
    """

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all features required by this model.

        Args:
            df: Merged base DataFrame (output of tf_merger Stage 3).
                Contains raw OHLCV + any merged secondary TF columns.

        Returns:
            DataFrame with all model-specific features added.
            Must contain every column in get_output_features().
        """
        pass

    @abstractmethod
    def get_required_input_columns(self) -> List[str]:
        """
        Columns that must exist in the input df before compute() runs.

        Used by the execution engine to validate the merged DataFrame
        before calling compute(). If any are missing, the model is
        skipped with a clear error message.

        Returns:
            List of column names (e.g. ['close', 'high', 'low', 'd1_close'])
        """
        pass

    @abstractmethod
    def get_output_features(self) -> List[str]:
        """
        Feature column names that compute() guarantees to produce.

        Must match exactly what the model was trained on (the 
        SELECTED_FEATURES list in the predictor class).

        Returns:
            List of feature column names
        """
        pass

    def validate_input(self, df: pd.DataFrame) -> tuple[bool, List[str]]:
        """
        Validate input DataFrame has all required columns.

        Returns:
            (is_valid, list_of_missing_columns)
        """
        required = set(self.get_required_input_columns())
        available = set(df.columns)
        missing = list(required - available)
        return len(missing) == 0, missing

    def validate_output(self, df: pd.DataFrame) -> tuple[bool, List[str]]:
        """
        Validate output DataFrame has all expected feature columns.

        Returns:
            (is_valid, list_of_missing_features)
        """
        expected = set(self.get_output_features())
        available = set(df.columns)
        missing = list(expected - available)
        return len(missing) == 0, missing

    def safe_compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        compute() with input/output validation and error handling.

        Called by the execution engine instead of compute() directly.
        Logs clear errors if validation fails.

        Returns:
            Featured DataFrame, or None if validation/compute fails
        """
        # Validate input
        ok, missing_input = self.validate_input(df)
        if not ok:
            logger.error(
                f"{self.__class__.__name__}: missing input columns: {missing_input}"
            )
            return None

        # Run computation
        try:
            featured_df = self.compute(df)
        except Exception as e:
            logger.error(f"{self.__class__.__name__}: compute() failed: {e}")
            return None

        # Validate output
        ok, missing_output = self.validate_output(featured_df)
        if not ok:
            logger.error(
                f"{self.__class__.__name__}: compute() did not produce "
                f"expected features: {missing_output}"
            )
            return None

        return featured_df
