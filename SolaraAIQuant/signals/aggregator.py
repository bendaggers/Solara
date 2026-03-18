"""
Solara AI Quant - Signal Aggregator

Aggregates and processes signals from multiple models.

Flow:
1. Collect predictions from all models
2. Convert to RawSignals
3. Run conflict checker
4. Output validated AggregatedSignals

Strategy: INDEPENDENT_PASSTHROUGH
- Each model's signals are independent
- No voting or consensus required
- All valid signals go to risk manager
"""

from typing import List, Dict, Optional
from datetime import datetime
import logging
import uuid

from .signal_models import (
    RawSignal,
    AggregatedSignal,
    SignalDirection,
    SignalStatus
)
from .conflict_checker import ConflictChecker, conflict_checker
from engine.registry import ModelConfig, model_registry
from engine.execution_engine import ModelResultSet

logger = logging.getLogger(__name__)


class SignalAggregator:
    """
    Aggregates signals from model results.
    
    Responsibilities:
    - Convert model predictions to RawSignals
    - Run conflict checking
    - Filter to valid signals only
    - Maintain signal statistics
    """
    
    def __init__(self, checker: ConflictChecker = None):
        self.checker = checker or conflict_checker
        
        # Statistics
        self.total_predictions = 0
        self.total_signals = 0
        self.rejected_signals = 0
    
    def aggregate(
        self,
        result_set: ModelResultSet
    ) -> List[AggregatedSignal]:
        """
        Aggregate all model results into validated signals.
        
        Args:
            result_set: Results from execution engine
            
        Returns:
            List of AggregatedSignal (validated only)
        """
        # 1. Collect all predictions
        all_predictions = result_set.get_all_predictions()
        self.total_predictions += len(all_predictions)
        
        if not all_predictions:
            logger.debug("No predictions to aggregate")
            return []
        
        # 2. Convert to RawSignals
        raw_signals = []
        for pred in all_predictions:
            try:
                signal_id = f"{result_set.timeframe}_{uuid.uuid4().hex[:8]}"
                signal = RawSignal.from_prediction(pred, signal_id)
                raw_signals.append(signal)
            except Exception as e:
                logger.error(f"Error converting prediction to signal: {e}")
        
        if not raw_signals:
            return []
        
        # 3. Get model configs for conflict checking
        model_configs = {}
        for signal in raw_signals:
            config = model_registry.get_model(signal.model_name)
            if config:
                model_configs[signal.model_name] = config
        
        # 4. Run conflict checker
        aggregated = self.checker.check_conflicts(raw_signals, model_configs)
        
        # 5. Filter to valid signals
        valid_signals = self.checker.get_valid_signals(aggregated)
        
        # Update stats
        self.total_signals += len(aggregated)
        self.rejected_signals += len(aggregated) - len(valid_signals)
        
        # Log summary
        if valid_signals:
            symbols = set(s.symbol for s in valid_signals)
            logger.info(
                f"Aggregated {len(valid_signals)} valid signals "
                f"for symbols: {symbols}"
            )
        
        return valid_signals
    
    def aggregate_from_predictions(
        self,
        predictions: List[Dict]
    ) -> List[AggregatedSignal]:
        """
        Aggregate from raw prediction dictionaries.
        
        Args:
            predictions: List of prediction dicts from models
            
        Returns:
            List of validated AggregatedSignal
        """
        if not predictions:
            return []
        
        # Convert to RawSignals
        raw_signals = []
        for pred in predictions:
            try:
                signal_id = uuid.uuid4().hex[:8]
                signal = RawSignal.from_prediction(pred, signal_id)
                raw_signals.append(signal)
            except Exception as e:
                logger.error(f"Error converting prediction: {e}")
        
        # Get model configs
        model_configs = {}
        for signal in raw_signals:
            config = model_registry.get_model(signal.model_name)
            if config:
                model_configs[signal.model_name] = config
        
        # Check conflicts
        aggregated = self.checker.check_conflicts(raw_signals, model_configs)
        
        return self.checker.get_valid_signals(aggregated)
    
    def get_statistics(self) -> Dict:
        """Get aggregation statistics."""
        return {
            'total_predictions': self.total_predictions,
            'total_signals': self.total_signals,
            'rejected_signals': self.rejected_signals,
            'valid_signals': self.total_signals - self.rejected_signals,
            'rejection_rate': (
                self.rejected_signals / self.total_signals
                if self.total_signals > 0 else 0.0
            )
        }
    
    def reset_statistics(self):
        """Reset counters."""
        self.total_predictions = 0
        self.total_signals = 0
        self.rejected_signals = 0


# Global instance
signal_aggregator = SignalAggregator()
