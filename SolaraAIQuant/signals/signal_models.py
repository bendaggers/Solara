"""
Solara AI Quant - Signal Models

Data structures for trading signals through the pipeline.

Signal Flow:
1. RawSignal - Direct output from predictor
2. ValidatedSignal - After conflict checking
3. ApprovedSignal - After risk manager approval
4. ExecutedSignal - After trade execution
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum


class SignalDirection(Enum):
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class SignalStatus(Enum):
    """Signal processing status."""
    RAW = "RAW"                       # Just created
    VALIDATED = "VALIDATED"           # Passed conflict check
    CONFLICT = "CONFLICT"             # Rejected due to conflict
    APPROVED = "APPROVED"             # Passed risk check
    REJECTED = "REJECTED"             # Rejected by risk manager
    EXECUTED = "EXECUTED"             # Trade placed
    FAILED = "FAILED"                 # Execution failed


class RejectionReason(Enum):
    """Reasons for signal rejection."""
    # Conflict reasons
    OPPOSING_SIGNAL = "OPPOSING_SIGNAL"
    DUPLICATE_SIGNAL = "DUPLICATE_SIGNAL"
    SYMBOL_NOT_ALLOWED = "SYMBOL_NOT_ALLOWED"
    
    # Risk reasons
    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"
    DAILY_TRADE_LIMIT = "DAILY_TRADE_LIMIT"
    POSITION_LIMIT = "POSITION_LIMIT"
    INSUFFICIENT_MARGIN = "INSUFFICIENT_MARGIN"
    INVALID_LOT_SIZE = "INVALID_LOT_SIZE"
    
    # Execution reasons
    ORDER_FAILED = "ORDER_FAILED"
    TIMEOUT = "TIMEOUT"
    MARKET_CLOSED = "MARKET_CLOSED"


@dataclass
class RawSignal:
    """
    Raw signal directly from a predictor.
    
    This is the initial signal before any validation.
    """
    # Identity
    signal_id: str = ""
    model_name: str = ""
    magic: int = 0
    
    # Trade info
    symbol: str = ""
    direction: SignalDirection = SignalDirection.LONG
    confidence: float = 0.0
    entry_price: float = 0.0
    
    # Trade parameters
    tp_pips: int = 0
    sl_pips: int = 0
    
    # Metadata
    comment: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    features: Dict[str, float] = field(default_factory=dict)
    
    @classmethod
    def from_prediction(cls, pred: Dict, signal_id: str = None) -> 'RawSignal':
        """Create RawSignal from predictor output dict."""
        import uuid
        
        direction = SignalDirection(pred.get('direction', 'LONG'))
        
        return cls(
            signal_id=signal_id or str(uuid.uuid4())[:8],
            model_name=pred.get('model_name', ''),
            magic=pred.get('magic', 0),
            symbol=pred.get('symbol', ''),
            direction=direction,
            confidence=pred.get('confidence', 0.0),
            entry_price=pred.get('entry_price', 0.0),
            tp_pips=pred.get('tp_pips', 0),
            sl_pips=pred.get('sl_pips', 0),
            comment=pred.get('comment', ''),
            features=pred.get('features', {})
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'signal_id': self.signal_id,
            'model_name': self.model_name,
            'magic': self.magic,
            'symbol': self.symbol,
            'direction': self.direction.value,
            'confidence': self.confidence,
            'entry_price': self.entry_price,
            'tp_pips': self.tp_pips,
            'sl_pips': self.sl_pips,
            'comment': self.comment,
            'timestamp': self.timestamp.isoformat(),
            'features': self.features
        }


@dataclass
class AggregatedSignal:
    """
    Signal after conflict checking and aggregation.
    
    May include combined confidence from multiple models.
    """
    # Original signal
    raw_signal: RawSignal
    
    # Aggregation info
    status: SignalStatus = SignalStatus.VALIDATED
    rejection_reason: Optional[RejectionReason] = None
    
    # Combined metrics (if multiple models)
    combined_confidence: float = 0.0
    contributing_models: List[str] = field(default_factory=list)
    total_weight: float = 0.0
    
    @property
    def symbol(self) -> str:
        return self.raw_signal.symbol
    
    @property
    def direction(self) -> SignalDirection:
        return self.raw_signal.direction
    
    @property
    def magic(self) -> int:
        return self.raw_signal.magic
    
    @property
    def is_valid(self) -> bool:
        return self.status == SignalStatus.VALIDATED
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'signal': self.raw_signal.to_dict(),
            'status': self.status.value,
            'rejection_reason': self.rejection_reason.value if self.rejection_reason else None,
            'combined_confidence': self.combined_confidence,
            'contributing_models': self.contributing_models,
            'total_weight': self.total_weight
        }


@dataclass
class ApprovedSignal:
    """
    Signal approved by risk manager.
    
    Includes calculated lot size and actual SL/TP prices.
    """
    # Source signal
    aggregated_signal: AggregatedSignal
    
    # Risk-adjusted parameters
    lot_size: float = 0.0
    sl_price: float = 0.0
    tp_price: float = 0.0
    
    # Risk metrics
    risk_amount: float = 0.0      # Account currency
    risk_percent: float = 0.0     # Of equity
    margin_required: float = 0.0
    
    # Status
    status: SignalStatus = SignalStatus.APPROVED
    rejection_reason: Optional[RejectionReason] = None
    
    @property
    def raw_signal(self) -> RawSignal:
        return self.aggregated_signal.raw_signal
    
    @property
    def symbol(self) -> str:
        return self.raw_signal.symbol
    
    @property
    def direction(self) -> SignalDirection:
        return self.raw_signal.direction
    
    @property
    def magic(self) -> int:
        return self.raw_signal.magic
    
    @property
    def is_approved(self) -> bool:
        return self.status == SignalStatus.APPROVED
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'signal': self.aggregated_signal.to_dict(),
            'lot_size': self.lot_size,
            'sl_price': self.sl_price,
            'tp_price': self.tp_price,
            'risk_amount': self.risk_amount,
            'risk_percent': self.risk_percent,
            'margin_required': self.margin_required,
            'status': self.status.value,
            'rejection_reason': self.rejection_reason.value if self.rejection_reason else None
        }


@dataclass
class ExecutedSignal:
    """
    Signal after trade execution attempt.
    
    Contains MT5 ticket and execution details.
    """
    # Source signal
    approved_signal: ApprovedSignal
    
    # Execution result
    status: SignalStatus = SignalStatus.EXECUTED
    ticket: int = 0
    actual_entry_price: float = 0.0
    actual_lot_size: float = 0.0
    slippage_pips: float = 0.0
    
    # Error info
    error_code: int = 0
    error_message: str = ""
    rejection_reason: Optional[RejectionReason] = None
    
    # Timing
    executed_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def raw_signal(self) -> RawSignal:
        return self.approved_signal.raw_signal
    
    @property
    def symbol(self) -> str:
        return self.raw_signal.symbol
    
    @property
    def magic(self) -> int:
        return self.raw_signal.magic
    
    @property
    def is_success(self) -> bool:
        return self.status == SignalStatus.EXECUTED and self.ticket > 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'signal': self.approved_signal.to_dict(),
            'status': self.status.value,
            'ticket': self.ticket,
            'actual_entry_price': self.actual_entry_price,
            'actual_lot_size': self.actual_lot_size,
            'slippage_pips': self.slippage_pips,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'rejection_reason': self.rejection_reason.value if self.rejection_reason else None,
            'executed_at': self.executed_at.isoformat()
        }
