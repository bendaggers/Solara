"""
engine/model_registry.py — Model Registry Loader
==================================================
Loads model_registry.yaml, validates every entry with Pydantic v2,
and provides query methods to the execution engine.
Fatal on any validation error — system will not start with a broken registry.
"""
import yaml
import importlib
import structlog
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator
import config

log = structlog.get_logger(__name__)

VALID_TIMEFRAMES = {"M5", "M15", "H1", "H4"}
VALID_MODEL_TYPES = {"LONG", "SHORT"}


class ModelRegistryEntry(BaseModel):
    name: str
    class_path: str
    model_file: str
    feature_version: str
    model_type: str
    timeframe: str
    min_confidence: float = Field(ge=0.01, le=1.0)
    weight: float = Field(ge=0.1, le=2.0)
    priority: int = Field(ge=1, le=100)
    timeout: int = Field(ge=5, le=300)
    magic: int
    comment: str
    enabled: bool
    max_positions: int = Field(ge=1, le=20)
    symbols: list[str] = []

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        if v not in VALID_TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {VALID_TIMEFRAMES}, got: {v}")
        return v

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, v: str) -> str:
        if v not in VALID_MODEL_TYPES:
            raise ValueError(f"model_type must be LONG or SHORT, got: {v}")
        return v

    @property
    def model_path(self) -> Path:
        return config.MODELS_DIR / self.model_file


class ModelRegistry:
    """Loads, validates, and queries the model registry."""

    def __init__(self) -> None:
        self._entries: list[ModelRegistryEntry] = []
        self._loaded = False

    def load(self) -> None:
        """
        Load and validate model_registry.yaml.
        Raises SystemExit on any fatal validation error.
        """
        path = config.MODEL_REGISTRY_PATH
        if not path.exists():
            log.critical("registry_not_found", path=str(path))
            raise SystemExit(1)

        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)

        raw_entries = data.get("models", [])
        entries: list[ModelRegistryEntry] = []
        fatal_errors: list[str] = []

        # Validate each entry
        for raw in raw_entries:
            name = raw.get("name", "<unnamed>")
            try:
                entry = ModelRegistryEntry(**raw)
            except Exception as e:
                fatal_errors.append(f"Model '{name}': {e}")
                continue

            # Check model file exists (only if enabled and model_file is not empty)
            if entry.enabled and entry.model_file and not entry.model_path.exists():
                fatal_errors.append(
                    f"Model '{entry.name}': model_file not found at {entry.model_path}"
                )
                continue

            # Validate class_path is importable
            try:
                module_path, class_name = entry.class_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                getattr(module, class_name)
            except Exception as e:
                fatal_errors.append(
                    f"Model '{entry.name}': class_path '{entry.class_path}' import failed: {e}"
                )
                continue

            entries.append(entry)

        # Check for duplicate names
        names = [e.name for e in entries]
        dupes = [n for n in names if names.count(n) > 1]
        if dupes:
            fatal_errors.append(f"Duplicate model names: {list(set(dupes))}")

        # Check for duplicate magic numbers
        magics = [e.magic for e in entries]
        dupe_magics = [m for m in magics if magics.count(m) > 1]
        if dupe_magics:
            fatal_errors.append(f"Duplicate magic numbers: {list(set(dupe_magics))}")

        if fatal_errors:
            for err in fatal_errors:
                log.critical("registry_validation_error", error=err)
            raise SystemExit(1)

        self._entries = entries
        self._loaded = True
        log.info(
            "registry_loaded",
            total=len(entries),
            enabled=sum(1 for e in entries if e.enabled),
        )

    # ── Query methods ─────────────────────────────────────────────────────────

    def get_all_models(self) -> list[ModelRegistryEntry]:
        """Return all registered models regardless of enabled status."""
        return list(self._entries)

    def get_enabled(self, timeframe: str) -> list[ModelRegistryEntry]:
        """Return all enabled entries for a given timeframe, sorted by priority."""
        return sorted(
            [e for e in self._entries if e.enabled and e.timeframe == timeframe],
            key=lambda e: e.priority,
        )

    def get_by_magic(self, magic: int) -> ModelRegistryEntry | None:
        return next((e for e in self._entries if e.magic == magic), None)

    def count(self) -> int:
        return len(self._entries)

    def count_enabled(self) -> int:
        return sum(1 for e in self._entries if e.enabled)

    def timeframes_active(self) -> list[str]:
        return sorted(set(e.timeframe for e in self._entries if e.enabled))

    def disable(self, name: str, reason: str) -> None:
        """Auto-disable a model in memory (does not modify YAML)."""
        for entry in self._entries:
            if entry.name == name:
                entry.enabled = False
                log.critical(
                    "model_auto_disabled",
                    model=name,
                    reason=reason,
                )
                return
