"""
signals/signal_models.py — Signal Data Contracts
=================================================
Typed dataclasses for RawSignal and AggregatedSignal.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawSignal:
    symbol: str
    direction: str          # LONG | SHORT
    confidence: float
    model_name: str
    model_type: str         # LONG | SHORT
    timeframe: str
    magic: int
    weight: float
    price: float
    comment: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AggregatedSignal:
    symbol: str
    direction: str
    confidence: float
    model_name: str
    magic: int
    weight: float
    price: float
    comment: str
    timeframe: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "AGGREGATED"
