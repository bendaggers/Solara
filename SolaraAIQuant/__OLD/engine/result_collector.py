"""
engine/result_collector.py — Model Result Types
=================================================
Data structures for model execution results.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED  = "FAILED"
    TIMEOUT = "TIMEOUT"
    EMPTY   = "EMPTY"


@dataclass
class ModelResult:
    model_name: str
    magic: int
    timeframe: str
    status: RunStatus
    signals: list = field(default_factory=list)   # list[RawSignal]
    elapsed_seconds: float = 0.0
    error_message: str | None = None
    batch_number: int = 0


@dataclass
class ModelResultSet:
    timeframe: str
    results: list[ModelResult] = field(default_factory=list)
    cycle_started_at: datetime = field(default_factory=datetime.utcnow)

    def successful(self) -> list[ModelResult]:
        return [r for r in self.results if r.status == RunStatus.SUCCESS]

    def all_signals(self) -> list:
        signals = []
        for r in self.successful():
            signals.extend(r.signals)
        return signals
