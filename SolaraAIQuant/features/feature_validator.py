"""
features/feature_validator.py — Feature Version Validator
===========================================================
Checks each model's declared feature_version against the columns
actually present in the computed DataFrame.
Runs before the worker pool is engaged — models with missing features
are excluded from the cycle before any inference is attempted.
"""
import yaml
import structlog
from pathlib import Path
import pandas as pd
import config

log = structlog.get_logger(__name__)


class FeatureValidationError(Exception):
    pass


class FeatureValidator:
    """Validates model feature version compatibility against computed features."""

    def __init__(self) -> None:
        self._versions: dict = {}
        self._load()

    def _load(self) -> None:
        path: Path = config.FEATURE_VERSIONS_PATH
        if not path.exists():
            raise FeatureValidationError(
                f"feature_versions.yaml not found at: {path}"
            )
        with open(path) as f:
            data = yaml.safe_load(f)
        self._versions = data.get("versions", {})

    def get_required_columns(self, feature_version: str) -> list[str]:
        """Return the required columns for a given feature version."""
        if feature_version not in self._versions:
            raise FeatureValidationError(
                f"Unknown feature_version: '{feature_version}'. "
                f"Valid versions: {list(self._versions.keys())}"
            )
        return self._versions[feature_version]["columns"]

    def validate_model(
        self,
        model_name: str,
        feature_version: str,
        featured_df: pd.DataFrame,
    ) -> tuple[bool, list[str]]:
        """
        Check if a model's required features are all present in featured_df.

        Returns:
            (is_valid, missing_columns)
        """
        try:
            required = self.get_required_columns(feature_version)
        except FeatureValidationError as e:
            log.error("feature_version_unknown", model=model_name, error=str(e))
            return False, []

        missing = [c for c in required if c not in featured_df.columns]
        if missing:
            log.error(
                "model_skipped_missing_features",
                model=model_name,
                feature_version=feature_version,
                missing_features=missing,
            )
            return False, missing

        return True, []
