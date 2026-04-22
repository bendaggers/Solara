"""
Solara AI Quant - Model Registry

Loads and validates model configurations from model_registry.yaml.

Key fields per model:
  timeframe                - The timeframe the model was TRAINED on
  trigger_timeframes       - Which CSV file changes FIRE this model
  merge_timeframes         - Additional TF CSVs to merge before prediction
  feature_engineering_class - Python class path for per-model feature engineering
  confidence_tiers         - Maps confidence ranges to fixed lot sizes
  timeframe_overrides      - Per-trigger-TF overrides for tp_pips, sl_pips,
                             max_holding_bars, and max_positions
"""

import yaml
import importlib
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

from config import PROJECT_ROOT, MODELS_DIR

logger = logging.getLogger(__name__)


class ModelType(Enum):
    LONG  = "LONG"
    SHORT = "SHORT"


class TimeframeEnum(Enum):
    M5  = "M5"
    M15 = "M15"
    H1  = "H1"
    H4  = "H4"
    D1  = "D1"


@dataclass
class ConfidenceTier:
    """
    Maps a confidence score range to a fixed lot size.
    First matching tier wins. Falls back to 0.01 if nothing matches.
    """
    min_confidence: float
    max_confidence: float
    fixed_lot: float

    def matches(self, confidence: float) -> bool:
        return self.min_confidence <= confidence <= self.max_confidence


@dataclass
class TimeframeOverride:
    """
    Per-trigger-timeframe overrides for trade parameters.

    Allows a single model to use different TP, SL, and holding bars
    depending on which timeframe CSV triggered the pipeline run.

    Only the fields you specify are overridden — unset fields fall
    back to the model-level defaults.

    Example (in model_registry.yaml):
        timeframe_overrides:
          M5:
            tp_pips: 15
            sl_pips: 40
            max_holding_bars: 24
          H4:
            tp_pips: 40
            sl_pips: 30
            max_holding_bars: 10
    """
    tp_pips:          Optional[int] = None
    sl_pips:          Optional[int] = None
    max_holding_bars: Optional[int] = None
    max_positions:    Optional[int] = None


@dataclass
class ModelConfig:
    """Configuration for a single model."""

    # ── Identity ──────────────────────────────────────────────────────────
    name: str
    description: str = ""
    class_path: str = ""
    model_file: str = ""
    feature_version: str = "v1"
    model_type: ModelType = ModelType.LONG
    timeframe: TimeframeEnum = TimeframeEnum.H4

    # ── Timeframe routing ─────────────────────────────────────────────────
    trigger_timeframes: List[TimeframeEnum] = field(default_factory=list)
    merge_timeframes:   List[TimeframeEnum] = field(default_factory=list)

    # ── Per-model feature engineering ─────────────────────────────────────
    feature_engineering_class: str = ""

    # ── Signal filtering ──────────────────────────────────────────────────
    min_confidence: float = 0.50
    threshold:      float = 0.50

    # ── Confidence-based fixed lot sizing ─────────────────────────────────
    confidence_tiers: List[ConfidenceTier] = field(default_factory=list)

    # ── Aggregation ───────────────────────────────────────────────────────
    weight:   float = 1.0
    priority: int   = 1

    # ── Execution ─────────────────────────────────────────────────────────
    timeout: int = 30
    magic:   int = 0
    comment: str = ""

    # ── Position management defaults ──────────────────────────────────────
    # These are the fallback values used when no timeframe_override matches.
    max_positions:    int = 3
    tp_pips:          int = 100
    sl_pips:          int = 50
    max_holding_bars: int = 72

    # ── Per-trigger-timeframe overrides ───────────────────────────────────
    # Dict keyed by timeframe string (e.g. "M5", "H4").
    # Each entry is a TimeframeOverride with optional field overrides.
    # Fields not set in the override fall back to the defaults above.
    timeframe_overrides: Dict[str, TimeframeOverride] = field(default_factory=dict)

    # ── Pull Back pipeline thresholds ────────────────────────────────────
    pb_exhaust_threshold: float = 0.55   # Gate 3: H4 pullback exhaustion prob

    # ── Reversal detection thresholds ─────────────────────────────────────
    rev_swing_window:      int   = 20    # H4 bars for swing high/low lookback
    rev_flip_lookback:     int   = 6     # bars — prior trend must exist within this window
    rev_break_buffer_pips: int   = 2     # pips — close must exceed swing level by this margin

    # ── Filters ───────────────────────────────────────────────────────────
    symbols: List[str] = field(default_factory=list)

    # ── Status ────────────────────────────────────────────────────────────
    enabled: bool = True

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def model_path(self) -> Path:
        return MODELS_DIR / self.model_file

    @property
    def model_exists(self) -> bool:
        return self.model_path.exists()

    @property
    def has_custom_feature_engineer(self) -> bool:
        return bool(self.feature_engineering_class)

    def is_triggered_by(self, timeframe: str) -> bool:
        try:
            tf = TimeframeEnum(timeframe)
        except ValueError:
            return False
        if self.trigger_timeframes:
            return tf in self.trigger_timeframes
        return tf == self.timeframe

    def get_merge_timeframe_strings(self) -> List[str]:
        return [tf.value for tf in self.merge_timeframes]

    # ── Timeframe-aware trade parameter getters ───────────────────────────

    def get_tp_pips(self, timeframe: str = "") -> int:
        """
        Return TP pips for the given trigger timeframe.
        Falls back to model-level tp_pips if no override exists.
        """
        override = self.timeframe_overrides.get(timeframe.upper())
        if override and override.tp_pips is not None:
            return override.tp_pips
        return self.tp_pips

    def get_sl_pips(self, timeframe: str = "") -> int:
        """
        Return SL pips for the given trigger timeframe.
        Falls back to model-level sl_pips if no override exists.
        """
        override = self.timeframe_overrides.get(timeframe.upper())
        if override and override.sl_pips is not None:
            return override.sl_pips
        return self.sl_pips

    def get_max_holding_bars(self, timeframe: str = "") -> int:
        """
        Return max holding bars for the given trigger timeframe.
        Falls back to model-level max_holding_bars if no override exists.
        """
        override = self.timeframe_overrides.get(timeframe.upper())
        if override and override.max_holding_bars is not None:
            return override.max_holding_bars
        return self.max_holding_bars

    def get_max_positions(self, timeframe: str = "") -> int:
        """
        Return max positions for the given trigger timeframe.
        Falls back to model-level max_positions if no override exists.
        """
        override = self.timeframe_overrides.get(timeframe.upper())
        if override and override.max_positions is not None:
            return override.max_positions
        return self.max_positions

    def get_fixed_lot(self, confidence: float) -> float | None:
        """
        Return the fixed lot size for a given confidence score.

        Returns None if confidence does not match any tier — the caller
        must treat None as a rejection (do not place the trade).

        Returns 0.01 only when no tiers are configured at all (legacy
        models without a confidence_tiers block).
        """
        if not self.confidence_tiers:
            return 0.01
        for tier in self.confidence_tiers:
            if tier.matches(confidence):
                return tier.fixed_lot
        logger.debug(
            f"'{self.name}': confidence {confidence:.4f} below all tiers "
            f"(min={min(t.min_confidence for t in self.confidence_tiers):.2f}) "
            f"— signal rejected"
        )
        return None
        return 0.01

    def load_feature_engineer(self):
        """Dynamically import and instantiate this model's feature engineering class.

        Passes self (ModelConfig) to the constructor so FEs can read registry
        thresholds (e.g. rev_swing_window) without needing a separate config path.
        FE constructors accept an optional config= kwarg; older FEs that don't
        declare it receive no argument (fallback via try/except).
        """
        if not self.feature_engineering_class:
            return None
        try:
            module_path, class_name = self.feature_engineering_class.rsplit('.', 1)
            module   = importlib.import_module(module_path)
            cls      = getattr(module, class_name)
            try:
                instance = cls(config=self)
            except TypeError:
                instance = cls()
            logger.debug(
                f"'{self.name}': loaded feature engineer "
                f"{self.feature_engineering_class}"
            )
            return instance
        except ImportError as e:
            logger.error(
                f"'{self.name}': cannot import feature engineer "
                f"'{self.feature_engineering_class}': {e}"
            )
        except AttributeError as e:
            logger.error(f"'{self.name}': feature engineer class not found: {e}")
        except Exception as e:
            logger.error(f"'{self.name}': error loading feature engineer: {e}")
        return None

    def to_dict(self) -> Dict:
        return {
            'name':                      self.name,
            'description':               self.description,
            'class_path':                self.class_path,
            'model_file':                self.model_file,
            'feature_version':           self.feature_version,
            'model_type':                self.model_type.value,
            'timeframe':                 self.timeframe.value,
            'trigger_timeframes':        [tf.value for tf in self.trigger_timeframes],
            'merge_timeframes':          [tf.value for tf in self.merge_timeframes],
            'feature_engineering_class': self.feature_engineering_class,
            'min_confidence':            self.min_confidence,
            'threshold':                 self.threshold,
            'confidence_tiers': [
                {
                    'min_confidence': t.min_confidence,
                    'max_confidence': t.max_confidence,
                    'fixed_lot':      t.fixed_lot,
                }
                for t in self.confidence_tiers
            ],
            'weight':            self.weight,
            'priority':          self.priority,
            'timeout':           self.timeout,
            'magic':             self.magic,
            'comment':           self.comment,
            'max_positions':     self.max_positions,
            'tp_pips':           self.tp_pips,
            'sl_pips':           self.sl_pips,
            'max_holding_bars':  self.max_holding_bars,
            'timeframe_overrides': {
                tf: {
                    k: v for k, v in {
                        'tp_pips':          o.tp_pips,
                        'sl_pips':          o.sl_pips,
                        'max_holding_bars': o.max_holding_bars,
                        'max_positions':    o.max_positions,
                    }.items() if v is not None
                }
                for tf, o in self.timeframe_overrides.items()
            },
            'pb_exhaust_threshold':  self.pb_exhaust_threshold,
            'rev_swing_window':      self.rev_swing_window,
            'rev_flip_lookback':     self.rev_flip_lookback,
            'rev_break_buffer_pips': self.rev_break_buffer_pips,
            'symbols': self.symbols,
            'enabled': self.enabled,
        }

    def get_min_confidence(self) -> float:
        """Derive minimum confidence from tiers, fallback to min_confidence field."""
        if self.confidence_tiers:
            return min(t.min_confidence for t in self.confidence_tiers)
        return self.min_confidence


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
        timeframe  = TimeframeEnum(data.get('timeframe', 'H4'))

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

        # Parse confidence tiers
        tiers = []
        for tier_data in data.get('confidence_tiers', []):
            try:
                tiers.append(ConfidenceTier(
                    min_confidence=float(tier_data['min_confidence']),
                    max_confidence=float(tier_data['max_confidence']),
                    fixed_lot=float(tier_data['fixed_lot']),
                ))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(
                    f"Invalid confidence tier in '{data.get('name', '?')}': "
                    f"{tier_data} — {e} — skipping tier"
                )

        # Parse timeframe overrides
        overrides: Dict[str, TimeframeOverride] = {}
        for tf_str, override_data in data.get('timeframe_overrides', {}).items():
            if not isinstance(override_data, dict):
                continue
            overrides[tf_str.upper()] = TimeframeOverride(
                tp_pips=          int(override_data['tp_pips'])          if 'tp_pips'          in override_data else None,
                sl_pips=          int(override_data['sl_pips'])          if 'sl_pips'          in override_data else None,
                max_holding_bars= int(override_data['max_holding_bars']) if 'max_holding_bars' in override_data else None,
                max_positions=    int(override_data['max_positions'])    if 'max_positions'    in override_data else None,
            )

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
            feature_engineering_class=data.get('feature_engineering_class', ''),
            min_confidence=float(data.get('min_confidence', 0.50)),
            threshold=float(data.get('threshold', 0.50)),
            confidence_tiers=tiers,
            weight=float(data.get('weight', 1.0)),
            priority=int(data.get('priority', 1)),
            timeout=int(data.get('timeout', 30)),
            magic=int(data.get('magic', 0)),
            comment=data.get('comment', ''),
            max_positions=int(data.get('max_positions', 3)),
            tp_pips=int(data.get('tp_pips', 100)),
            sl_pips=int(data.get('sl_pips', 50)),
            max_holding_bars=int(data.get('max_holding_bars', 72)),
            timeframe_overrides=overrides,
            pb_exhaust_threshold=float(data.get('pb_exhaust_threshold', 0.55)),
            rev_swing_window=int(data.get('rev_swing_window', 20)),
            rev_flip_lookback=int(data.get('rev_flip_lookback', 6)),
            rev_break_buffer_pips=int(data.get('rev_break_buffer_pips', 2)),
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

    # ── Query methods ─────────────────────────────────────────────────────

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
        """Get enabled models triggered by a given timeframe, sorted by priority."""
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
        enabled  = self.get_enabled_models()
        disabled = [m for m in self.models.values() if not m.enabled]
        print(f"  Total: {len(self.models)}  Enabled: {len(enabled)}  Disabled: {len(disabled)}")

        if enabled:
            print(f"\n  {'Name':<25} {'TF':<4} {'Triggers':<15} {'Merge':<12} {'Magic'}")
            print("  " + "-" * 65)
            for m in enabled:
                triggers = ",".join(tf.value for tf in m.trigger_timeframes) or m.timeframe.value
                merges   = ",".join(tf.value for tf in m.merge_timeframes) or "none"
                print(f"  {m.name:<25} {m.timeframe.value:<4} {triggers:<15} {merges:<12} {m.magic}")
                # Show per-TF TP/SL
                all_tfs = [tf.value for tf in m.trigger_timeframes] or [m.timeframe.value]
                for tf in all_tfs:
                    print(
                        f"    {tf}: TP={m.get_tp_pips(tf)} pips  "
                        f"SL={m.get_sl_pips(tf)} pips  "
                        f"max_bars={m.get_max_holding_bars(tf)}"
                    )

        missing = self.validate_model_files()
        if missing:
            print("\n  WARNING — MISSING MODEL FILES:")
            for m in missing:
                print(f"    {m}")
        print("=" * 70 + "\n")


# Global singleton
model_registry = ModelRegistry()
model_registry.load()
