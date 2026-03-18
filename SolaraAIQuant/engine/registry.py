"""
Solara AI Quant - Model Registry

Loads and validates model configurations from model_registry.yaml.

Key fields per model:
  timeframe          - The timeframe the model was TRAINED on
  trigger_timeframes - Which CSV file changes FIRE this model
  merge_timeframes   - Additional TF CSVs to merge into base data before prediction
"""

import yaml
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

from config import PROJECT_ROOT, MODELS_DIR

logger = logging.getLogger(__name__)


class ModelType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TimeframeEnum(Enum):
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    # Identity
    name: str
    description: str = ""
    class_path: str = ""
    model_file: str = ""
    feature_version: str = "v1"
    model_type: ModelType = ModelType.LONG
    timeframe: TimeframeEnum = TimeframeEnum.H4

    # Which CSV file changes trigger this model to run.
    # Empty = only triggered by its own trained timeframe.
    trigger_timeframes: List[TimeframeEnum] = field(default_factory=list)

    # Additional timeframes to merge INTO the base (trigger) data.
    # The trigger TF is always the base — list only extra TFs here.
    # Merged columns are prefixed: D1 → d1_close, H4 → h4_close, etc.
    merge_timeframes: List[TimeframeEnum] = field(default_factory=list)

    # Prediction
    min_confidence: float = 0.50
    threshold: float = 0.50

    # Aggregation
    weight: float = 1.0
    priority: int = 1

    # Execution
    timeout: int = 30
    magic: int = 0
    comment: str = ""

    # Position management
    max_positions: int = 3
    tp_pips: int = 100
    sl_pips: int = 50
    max_holding_bars: int = 72

    # Filters
    symbols: List[str] = field(default_factory=list)

    # Status
    enabled: bool = True

    @property
    def model_path(self) -> Path:
        return MODELS_DIR / self.model_file

    @property
    def model_exists(self) -> bool:
        return self.model_path.exists()

    def is_triggered_by(self, timeframe: str) -> bool:
        """Check if this model should run when a given timeframe CSV is updated."""
        try:
            tf = TimeframeEnum(timeframe)
        except ValueError:
            return False

        if self.trigger_timeframes:
            return tf in self.trigger_timeframes

        # Default: only trigger on own trained timeframe
        return tf == self.timeframe

    def get_merge_timeframe_strings(self) -> List[str]:
        """Return merge_timeframes as plain strings (e.g. ['D1', 'H4'])."""
        return [tf.value for tf in self.merge_timeframes]

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'description': self.description,
            'class_path': self.class_path,
            'model_file': self.model_file,
            'feature_version': self.feature_version,
            'model_type': self.model_type.value,
            'timeframe': self.timeframe.value,
            'trigger_timeframes': [tf.value for tf in self.trigger_timeframes],
            'merge_timeframes': [tf.value for tf in self.merge_timeframes],
            'min_confidence': self.min_confidence,
            'threshold': self.threshold,
            'weight': self.weight,
            'priority': self.priority,
            'timeout': self.timeout,
            'magic': self.magic,
            'comment': self.comment,
            'max_positions': self.max_positions,
            'tp_pips': self.tp_pips,
            'sl_pips': self.sl_pips,
            'max_holding_bars': self.max_holding_bars,
            'symbols': self.symbols,
            'enabled': self.enabled,
        }


class ModelRegistry:
    """Manages model configurations loaded from YAML."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or (PROJECT_ROOT / "model_registry.yaml")
        self.models: Dict[str, ModelConfig] = {}
        self._loaded = False

    def load(self) -> bool:
        if not self.registry_path.exists():
            logger.error(f"Registry file not found: {self.registry_path}")
            return False

        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not data or 'models' not in data:
                logger.warning("No models defined in registry")
                return True

            self.models = {}
            errors = []

            for model_data in data.get('models', []):
                try:
                    config = self._parse_model_config(model_data)
                    if config.name in self.models:
                        errors.append(f"Duplicate model name: {config.name}")
                        continue
                    self.models[config.name] = config
                except Exception as e:
                    errors.append(
                        f"Error parsing model '{model_data.get('name', '?')}': {e}"
                    )

            errors.extend(self._validate_magic_numbers())

            if errors:
                for error in errors:
                    logger.error(f"Registry error: {error}")
                return False

            self._loaded = True
            enabled = len(self.get_enabled_models())
            logger.info(
                f"Loaded {len(self.models)} models from registry ({enabled} enabled)"
            )
            return True

        except yaml.YAMLError as e:
            logger.error(f"YAML parse error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading registry: {e}")
            return False

    def _parse_model_config(self, data: Dict) -> ModelConfig:
        model_type = ModelType(data.get('model_type', 'LONG'))
        timeframe = TimeframeEnum(data.get('timeframe', 'H4'))

        def parse_tf_list(key: str) -> List[TimeframeEnum]:
            result = []
            for tf_str in data.get(key, []):
                try:
                    result.append(TimeframeEnum(tf_str))
                except ValueError:
                    logger.warning(
                        f"Unknown timeframe '{tf_str}' in '{key}' "
                        f"for model '{data.get('name', '?')}' — skipping"
                    )
            return result

        return ModelConfig(
            name=data['name'],
            description=data.get('description', ''),
            class_path=data.get('class_path', ''),
            model_file=data.get('model_file', ''),
            feature_version=data.get('feature_version', 'v1'),
            model_type=model_type,
            timeframe=timeframe,
            trigger_timeframes=parse_tf_list('trigger_timeframes'),
            merge_timeframes=parse_tf_list('merge_timeframes'),
            min_confidence=float(data.get('min_confidence', 0.50)),
            threshold=float(data.get('threshold', 0.50)),
            weight=float(data.get('weight', 1.0)),
            priority=int(data.get('priority', 1)),
            timeout=int(data.get('timeout', 30)),
            magic=int(data.get('magic', 0)),
            comment=data.get('comment', ''),
            max_positions=int(data.get('max_positions', 3)),
            tp_pips=int(data.get('tp_pips', 100)),
            sl_pips=int(data.get('sl_pips', 50)),
            max_holding_bars=int(data.get('max_holding_bars', 72)),
            symbols=data.get('symbols', []),
            enabled=bool(data.get('enabled', True)),
        )

    def _validate_magic_numbers(self) -> List[str]:
        errors = []
        seen: Dict[int, str] = {}
        for name, config in self.models.items():
            if config.magic == 0:
                errors.append(f"Model '{name}' has no magic number")
            elif config.magic in seen:
                errors.append(
                    f"Duplicate magic {config.magic}: '{name}' and '{seen[config.magic]}'"
                )
            else:
                seen[config.magic] = name
        return errors

    # ── Query methods ─────────────────────────────────────────────────────────

    def get_all_models(self) -> List[ModelConfig]:
        return list(self.models.values())

    def get_model(self, name: str) -> Optional[ModelConfig]:
        return self.models.get(name)

    def get_model_by_magic(self, magic: int) -> Optional[ModelConfig]:
        for config in self.models.values():
            if config.magic == magic:
                return config
        return None

    def get_enabled_models(self) -> List[ModelConfig]:
        return [m for m in self.models.values() if m.enabled]

    def get_models_for_timeframe(self, timeframe: str) -> List[ModelConfig]:
        """
        Get enabled models triggered by a given timeframe CSV update,
        sorted by priority.
        """
        models = [
            m for m in self.models.values()
            if m.enabled and m.is_triggered_by(timeframe)
        ]
        models.sort(key=lambda m: m.priority)

        if models:
            logger.debug(
                f"Timeframe {timeframe} triggers {len(models)} model(s): "
                f"{[m.name for m in models]}"
            )
        return models

    def get_all_magic_numbers(self) -> Set[int]:
        return {m.magic for m in self.models.values() if m.magic > 0}

    def validate_model_files(self) -> List[str]:
        return [
            f"{c.name}: {c.model_file}"
            for c in self.get_enabled_models()
            if not c.model_exists
        ]

    def print_summary(self):
        print("\n" + "=" * 70)
        print("  MODEL REGISTRY")
        print("=" * 70)
        enabled = self.get_enabled_models()
        disabled = [m for m in self.models.values() if not m.enabled]
        print(f"  Total: {len(self.models)}  Enabled: {len(enabled)}  Disabled: {len(disabled)}")

        if enabled:
            print(f"\n  {'Name':<25} {'TF':<4} {'Triggers':<15} {'Merge':<12} {'Magic'}")
            print("  " + "-" * 65)
            for m in enabled:
                triggers = ",".join(tf.value for tf in m.trigger_timeframes) or m.timeframe.value
                merges = ",".join(tf.value for tf in m.merge_timeframes) or "none"
                print(f"  {m.name:<25} {m.timeframe.value:<4} {triggers:<15} {merges:<12} {m.magic}")

        missing = self.validate_model_files()
        if missing:
            print("\n  WARNING — MISSING MODEL FILES:")
            for m in missing:
                print(f"    {m}")
        print("=" * 70 + "\n")


# Global singleton
model_registry = ModelRegistry()
model_registry.load()
