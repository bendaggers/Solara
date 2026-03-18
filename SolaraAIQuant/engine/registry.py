"""
Solara AI Quant - Model Registry

Loads and validates model configurations from model_registry.yaml.
Provides access to enabled models filtered by timeframe.
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
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class TimeframeEnum(Enum):
    """Supported timeframes."""
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
        """Full path to model file."""
        return MODELS_DIR / self.model_file
    
    @property
    def model_exists(self) -> bool:
        """Check if model file exists."""
        return self.model_path.exists()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'class_path': self.class_path,
            'model_file': self.model_file,
            'feature_version': self.feature_version,
            'model_type': self.model_type.value,
            'timeframe': self.timeframe.value,
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
    """
    Manages model configurations loaded from YAML.
    
    Features:
    - Load and validate model configs
    - Filter models by timeframe, enabled status
    - Check for duplicate magic numbers
    - Validate model files exist
    """
    
    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or (PROJECT_ROOT / "model_registry.yaml")
        self.models: Dict[str, ModelConfig] = {}
        self._loaded = False
    
    def load(self) -> bool:
        """
        Load models from registry YAML.
        
        Returns:
            True if loaded successfully, False on error
        """
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
                    
                    # Check for duplicate names
                    if config.name in self.models:
                        errors.append(f"Duplicate model name: {config.name}")
                        continue
                    
                    self.models[config.name] = config
                    
                except Exception as e:
                    errors.append(f"Error parsing model: {e}")
            
            # Validate magic numbers are unique
            magic_errors = self._validate_magic_numbers()
            errors.extend(magic_errors)
            
            if errors:
                for error in errors:
                    logger.error(f"Registry error: {error}")
                return False
            
            self._loaded = True
            logger.info(f"Loaded {len(self.models)} models from registry")
            
            return True
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading registry: {e}")
            return False
    
    def _parse_model_config(self, data: Dict) -> ModelConfig:
        """Parse a single model configuration."""
        # Parse enums
        model_type = ModelType(data.get('model_type', 'LONG'))
        timeframe = TimeframeEnum(data.get('timeframe', 'H4'))
        
        return ModelConfig(
            name=data['name'],
            description=data.get('description', ''),
            class_path=data.get('class_path', ''),
            model_file=data.get('model_file', ''),
            feature_version=data.get('feature_version', 'v1'),
            model_type=model_type,
            timeframe=timeframe,
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
        """Validate magic numbers are unique."""
        errors = []
        seen_magic: Dict[int, str] = {}
        
        for name, config in self.models.items():
            if config.magic == 0:
                errors.append(f"Model '{name}' has no magic number")
            elif config.magic in seen_magic:
                errors.append(
                    f"Duplicate magic {config.magic}: '{name}' and '{seen_magic[config.magic]}'"
                )
            else:
                seen_magic[config.magic] = name
        
        return errors
    
    def get_model(self, name: str) -> Optional[ModelConfig]:
        """Get model by name."""
        return self.models.get(name)
    
    def get_model_by_magic(self, magic: int) -> Optional[ModelConfig]:
        """Get model by magic number."""
        for config in self.models.values():
            if config.magic == magic:
                return config
        return None
    
    def get_enabled_models(self) -> List[ModelConfig]:
        """Get all enabled models."""
        return [m for m in self.models.values() if m.enabled]
    
    def get_models_for_timeframe(self, timeframe: str) -> List[ModelConfig]:
        """
        Get enabled models for a specific timeframe.
        
        Args:
            timeframe: Timeframe string (e.g., "H4")
            
        Returns:
            List of enabled models for this timeframe, sorted by priority
        """
        try:
            tf = TimeframeEnum(timeframe)
        except ValueError:
            logger.warning(f"Unknown timeframe: {timeframe}")
            return []
        
        models = [
            m for m in self.models.values()
            if m.enabled and m.timeframe == tf
        ]
        
        # Sort by priority (lower first)
        models.sort(key=lambda m: m.priority)
        
        return models
    
    def get_all_magic_numbers(self) -> Set[int]:
        """Get all magic numbers in use."""
        return {m.magic for m in self.models.values() if m.magic > 0}
    
    def validate_model_files(self) -> List[str]:
        """
        Check that all enabled models have their .pkl files.
        
        Returns:
            List of missing model files
        """
        missing = []
        
        for config in self.get_enabled_models():
            if not config.model_exists:
                missing.append(f"{config.name}: {config.model_file}")
        
        return missing
    
    def print_summary(self):
        """Print registry summary."""
        print("\n" + "=" * 60)
        print("  MODEL REGISTRY")
        print("=" * 60)
        
        enabled = self.get_enabled_models()
        disabled = [m for m in self.models.values() if not m.enabled]
        
        print(f"  Total models: {len(self.models)}")
        print(f"  Enabled: {len(enabled)}")
        print(f"  Disabled: {len(disabled)}")
        
        if enabled:
            print("\n  ENABLED MODELS:")
            print(f"  {'Name':<25} {'Type':<6} {'TF':<4} {'Magic':<8} {'File':<20}")
            print("  " + "-" * 65)
            
            for m in enabled:
                exists = "✓" if m.model_exists else "✗"
                print(f"  {m.name:<25} {m.model_type.value:<6} {m.timeframe.value:<4} {m.magic:<8} {exists} {m.model_file}")
        
        # Check for missing files
        missing = self.validate_model_files()
        if missing:
            print("\n  ⚠️ MISSING MODEL FILES:")
            for m in missing:
                print(f"     {m}")
        
        print("=" * 60 + "\n")


# Global instance
model_registry = ModelRegistry()
