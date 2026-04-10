"""
Solara AI Quant - Conflict Checker

Detects and resolves conflicts between signals.

Conflict Rules:
1. Same model, same symbol, LONG + SHORT -> Suppress both
2. Different models, same symbol, LONG + SHORT -> Allow both
3. Same model, same symbol, same direction -> Keep highest confidence
4. Symbol not in model's whitelist -> Discard

Strategy: INDEPENDENT_PASSTHROUGH
- Each model's signals are evaluated independently
- No cross-model voting or aggregation by default
"""

from typing import List, Dict, Tuple, Set
from collections import defaultdict
import logging

from .signal_models import (
    RawSignal,
    AggregatedSignal,
    SignalStatus,
    SignalDirection,
    RejectionReason
)
from engine.registry import ModelConfig

logger = logging.getLogger(__name__)


class ConflictChecker:
    """
    Checks for and resolves signal conflicts.
    
    Default strategy: INDEPENDENT_PASSTHROUGH
    - Signals from different models are independent
    - Same model cannot have opposing signals on same symbol
    """
    
    def __init__(self):
        pass
    
    def check_conflicts(
        self,
        raw_signals: List[RawSignal],
        model_configs: Dict[str, ModelConfig] = None
    ) -> List[AggregatedSignal]:
        """
        Check signals for conflicts and return validated signals.
        
        Args:
            raw_signals: List of raw signals from all models
            model_configs: Optional dict of model name -> ModelConfig
            
        Returns:
            List of AggregatedSignal (validated or rejected)
        """
        if not raw_signals:
            return []
        
        model_configs = model_configs or {}
        results: List[AggregatedSignal] = []
        
        # Group signals by model
        by_model: Dict[str, List[RawSignal]] = defaultdict(list)
        for signal in raw_signals:
            by_model[signal.model_name].append(signal)
        
        # Process each model's signals independently
        for model_name, signals in by_model.items():
            model_config = model_configs.get(model_name)
            
            # Check within-model conflicts
            validated = self._check_model_signals(signals, model_config)
            results.extend(validated)
        
        # Log summary
        valid_count = sum(1 for r in results if r.is_valid)
        rejected_count = len(results) - valid_count
        
        if rejected_count > 0:
            logger.info(
                f"Conflict check: {valid_count} valid, {rejected_count} rejected "
                f"from {len(raw_signals)} total"
            )
        
        return results
    
    def _check_model_signals(
        self,
        signals: List[RawSignal],
        model_config: ModelConfig = None
    ) -> List[AggregatedSignal]:
        """
        Check signals from a single model for conflicts.
        
        Rules:
        1. Symbol whitelist check
        2. Opposing direction on same symbol -> reject both
        3. Duplicate (same direction) -> keep highest confidence
        """
        results: List[AggregatedSignal] = []
        
        # Group by symbol
        by_symbol: Dict[str, List[RawSignal]] = defaultdict(list)
        for signal in signals:
            by_symbol[signal.symbol].append(signal)
        
        for symbol, symbol_signals in by_symbol.items():
            # 1. Check symbol whitelist
            if model_config and model_config.symbols:
                if symbol not in model_config.symbols:
                    for signal in symbol_signals:
                        results.append(AggregatedSignal(
                            raw_signal=signal,
                            status=SignalStatus.CONFLICT,
                            rejection_reason=RejectionReason.SYMBOL_NOT_ALLOWED
                        ))
                        logger.debug(
                            f"Symbol {symbol} not in whitelist for {signal.model_name}"
                        )
                    continue
            
            # 2. Check for opposing directions
            longs = [s for s in symbol_signals if s.direction == SignalDirection.LONG]
            shorts = [s for s in symbol_signals if s.direction == SignalDirection.SHORT]
            
            if longs and shorts:
                # Opposing signals from same model -> reject both
                logger.warning(
                    f"Opposing signals for {symbol} from {symbol_signals[0].model_name}: "
                    f"{len(longs)} LONG, {len(shorts)} SHORT - suppressing both"
                )
                
                for signal in symbol_signals:
                    results.append(AggregatedSignal(
                        raw_signal=signal,
                        status=SignalStatus.CONFLICT,
                        rejection_reason=RejectionReason.OPPOSING_SIGNAL
                    ))
                continue
            
            # 3. Handle duplicates (keep highest confidence)
            all_signals = longs + shorts
            
            if len(all_signals) > 1:
                # Sort by confidence descending
                all_signals.sort(key=lambda s: s.confidence, reverse=True)
                
                # Keep the best one
                best = all_signals[0]
                results.append(AggregatedSignal(
                    raw_signal=best,
                    status=SignalStatus.VALIDATED,
                    combined_confidence=best.confidence,
                    contributing_models=[best.model_name],
                    total_weight=1.0
                ))
                
                # Mark others as duplicates
                for signal in all_signals[1:]:
                    results.append(AggregatedSignal(
                        raw_signal=signal,
                        status=SignalStatus.CONFLICT,
                        rejection_reason=RejectionReason.DUPLICATE_SIGNAL
                    ))
                    logger.debug(
                        f"Duplicate signal for {symbol}: "
                        f"{signal.confidence:.3f} < {best.confidence:.3f}"
                    )
            else:
                # Single signal, valid
                signal = all_signals[0]
                results.append(AggregatedSignal(
                    raw_signal=signal,
                    status=SignalStatus.VALIDATED,
                    combined_confidence=signal.confidence,
                    contributing_models=[signal.model_name],
                    total_weight=1.0
                ))
        
        return results
    
    def get_valid_signals(
        self,
        aggregated: List[AggregatedSignal]
    ) -> List[AggregatedSignal]:
        """Filter to only validated signals."""
        return [s for s in aggregated if s.is_valid]


# Global instance
conflict_checker = ConflictChecker()
