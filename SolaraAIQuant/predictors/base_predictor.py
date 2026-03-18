"""
Solara AI Quant - Base Predictor

Abstract base class for all ML predictors.
All model predictors must inherit from this class.

To create a new predictor:
1. Inherit from BasePredictor
2. Implement predict() method
3. Implement get_required_features() method
4. Register in model_registry.yaml
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import pickle
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PredictionSignal:
    """
    A single prediction/signal from a model.
    
    Attributes:
        symbol: Trading symbol (e.g., "EURUSD")
        direction: "LONG" or "SHORT"
        confidence: Model probability (0.0 - 1.0)
        entry_price: Current price at signal time
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        model_name: Name of the model
        magic: MT5 magic number
        comment: Trade comment
        features: Key features at signal time (for logging)
    """
    symbol: str
    direction: str
    confidence: float
    entry_price: float
    tp_pips: int
    sl_pips: int
    model_name: str
    magic: int
    comment: str
    features: Dict[str, float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'confidence': self.confidence,
            'entry_price': self.entry_price,
            'tp_pips': self.tp_pips,
            'sl_pips': self.sl_pips,
            'model_name': self.model_name,
            'magic': self.magic,
            'comment': self.comment,
            'features': self.features or {}
        }


class BasePredictor(ABC):
    """
    Abstract base class for all predictors.
    
    Subclasses must implement:
    - predict(): Generate predictions from features
    - get_required_features(): List features needed by model
    
    Optional overrides:
    - load_model(): Custom model loading logic
    - validate_features(): Custom feature validation
    """
    
    def __init__(self, config):
        """
        Initialize predictor with configuration.
        
        Args:
            config: ModelConfig from registry
        """
        self.config = config
        self.model = None
        self.model_loaded = False
        
        # Load model on init
        self._load_model()
    
    def _load_model(self):
        """Load the ML model from disk."""
        model_path = self.config.model_path
        
        if not model_path.exists():
            logger.warning(f"Model file not found: {model_path}")
            return
        
        try:
            self.model = self.load_model(model_path)
            self.model_loaded = True
            logger.info(f"Loaded model: {self.config.name} from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model {self.config.name}: {e}")
            self.model = None
            self.model_loaded = False
    
    def load_model(self, model_path: Path) -> Any:
        """
        Load model from file.
        
        Override for custom loading (e.g., ONNX, TensorFlow).
        Default implementation uses pickle.
        
        Args:
            model_path: Path to model file
            
        Returns:
            Loaded model object
        """
        with open(model_path, 'rb') as f:
            return pickle.load(f)
    
    @abstractmethod
    def get_required_features(self) -> List[str]:
        """
        Return list of feature names required by this model.
        
        Returns:
            List of feature column names
        """
        pass
    
    @abstractmethod
    def predict(
        self,
        df_features: pd.DataFrame,
        config
    ) -> List[Dict]:
        """
        Generate predictions from feature DataFrame.
        
        Args:
            df_features: DataFrame with computed features
                        (one row per symbol, latest bar only)
            config: ModelConfig with trading parameters
            
        Returns:
            List of prediction dictionaries (can be empty)
            Each dict should have: symbol, direction, confidence,
            entry_price, tp_pips, sl_pips, etc.
        """
        pass
    
    def validate_features(
        self,
        df: pd.DataFrame,
        required: List[str]
    ) -> bool:
        """
        Validate that required features exist in DataFrame.
        
        Args:
            df: Feature DataFrame
            required: List of required column names
            
        Returns:
            True if all features present, False otherwise
        """
        missing = set(required) - set(df.columns)
        
        if missing:
            logger.warning(
                f"Model '{self.config.name}' missing features: {missing}"
            )
            return False
        
        return True
    
    def filter_by_symbols(
        self,
        df: pd.DataFrame,
        symbol_column: str = 'symbol'
    ) -> pd.DataFrame:
        """
        Filter DataFrame to allowed symbols.
        
        Args:
            df: DataFrame with symbol column
            symbol_column: Name of symbol column
            
        Returns:
            Filtered DataFrame
        """
        allowed = self.config.symbols
        
        if not allowed:
            # Empty list = all symbols allowed
            return df
        
        return df[df[symbol_column].isin(allowed)]
    
    def create_signal(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        entry_price: float,
        features: Dict[str, float] = None
    ) -> PredictionSignal:
        """
        Create a prediction signal with model config values.
        
        Args:
            symbol: Trading symbol
            direction: "LONG" or "SHORT"
            confidence: Model probability
            entry_price: Current price
            features: Optional key features for logging
            
        Returns:
            PredictionSignal object
        """
        return PredictionSignal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            tp_pips=self.config.tp_pips,
            sl_pips=self.config.sl_pips,
            model_name=self.config.name,
            magic=self.config.magic,
            comment=self.config.comment,
            features=features
        )
    
    def get_metadata(self) -> Dict:
        """
        Get predictor metadata for logging/debugging.
        
        Returns:
            Dictionary with predictor info
        """
        return {
            'name': self.config.name,
            'model_type': self.config.model_type.value,
            'timeframe': self.config.timeframe.value,
            'feature_version': self.config.feature_version,
            'threshold': self.config.threshold,
            'min_confidence': self.config.min_confidence,
            'model_loaded': self.model_loaded,
            'required_features': self.get_required_features()
        }
