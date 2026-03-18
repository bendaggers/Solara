"""
Solara AI Quant - Signals Module

Signal processing and aggregation.

Components:
- Signal Models: Data structures for signals through pipeline
- Conflict Checker: Detect/resolve opposing signals
- Aggregator: Combine signals from multiple models

Signal Flow:
RawSignal -> ConflictChecker -> AggregatedSignal -> RiskManager -> ApprovedSignal
"""

from .signal_models import (
    SignalDirection,
    SignalStatus,
    RejectionReason,
    RawSignal,
    AggregatedSignal,
    ApprovedSignal,
    ExecutedSignal
)

from .conflict_checker import (
    ConflictChecker,
    conflict_checker
)

from .aggregator import (
    SignalAggregator,
    signal_aggregator
)

__all__ = [
    # Enums
    'SignalDirection',
    'SignalStatus',
    'RejectionReason',
    
    # Signal types
    'RawSignal',
    'AggregatedSignal',
    'ApprovedSignal',
    'ExecutedSignal',
    
    # Conflict checker
    'ConflictChecker',
    'conflict_checker',
    
    # Aggregator
    'SignalAggregator',
    'signal_aggregator',
]
