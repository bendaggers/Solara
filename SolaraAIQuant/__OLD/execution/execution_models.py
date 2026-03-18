"""
execution/execution_models.py — Execution Data Contracts
==========================================================
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TradeStatus(str, Enum):
    PLACED   = "PLACED"
    FAILED   = "FAILED"
    REJECTED = "REJECTED"


@dataclass
class TradeOrder:
    symbol: str
    direction: str      # LONG | SHORT
    lot_size: float
    sl: float
    tp: float | None
    magic: int
    comment: str
    price: float        # requested price


@dataclass
class ExecutionResult:
    order: TradeOrder
    status: TradeStatus
    ticket: int | None = None
    fill_price: float | None = None
    mt5_result_code: int | None = None
    failure_reason: str | None = None
    attempts: int = 1
    attempted_at: datetime = field(default_factory=datetime.utcnow)
    confirmed_at: datetime | None = None
