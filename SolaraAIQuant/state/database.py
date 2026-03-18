"""
Solara AI Quant - Database Manager

SQLite database connection and session management.
Thread-safe with WAL mode for concurrent access.
"""

import threading
import logging
from datetime import datetime
from typing import Optional, Generator, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from config import database_config
from .models import (
    Base, PositionState, StageTransitionLog, ModelRun,
    SignalLog, TradeLog, ModelHealth, DailyStats
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Thread-safe SQLite database manager.
    
    Features:
    - WAL mode for concurrent read/write
    - Thread-local sessions
    - Automatic table creation
    """
    
    _instance: Optional['DatabaseManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize database connection."""
        if self._initialized:
            return
        
        db_path = database_config.db_path
        
        # Create SQLite URL
        db_url = f"sqlite:///{db_path}"
        
        # Create engine with thread-safe settings
        self.engine = create_engine(
            db_url,
            echo=False,  # Set to True for SQL debugging
            connect_args={
                "check_same_thread": False,
                "timeout": database_config.timeout
            },
            poolclass=StaticPool  # Single connection pool for thread safety
        )
        
        # Enable WAL mode for better concurrency
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )
        
        # Thread-local storage for sessions
        self._local = threading.local()
        
        # Create tables
        self._create_tables()
        
        self._initialized = True
        logger.info(f"Database initialized: {db_path}")
    
    def _create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(self.engine)
        logger.debug("Database tables created/verified")
    
    def get_session(self) -> Session:
        """
        Get thread-local session.
        
        Returns:
            SQLAlchemy Session
        """
        if not hasattr(self._local, 'session') or self._local.session is None:
            self._local.session = self.SessionLocal()
        return self._local.session
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around operations.
        
        Usage:
            with db.session_scope() as session:
                session.add(obj)
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    def close_session(self):
        """Close thread-local session."""
        if hasattr(self._local, 'session') and self._local.session is not None:
            self._local.session.close()
            self._local.session = None
    
    # =========================================================================
    # Position State Operations
    # =========================================================================
    
    def get_position_state(self, ticket: int) -> Optional[PositionState]:
        """Get position state by ticket."""
        with self.session_scope() as session:
            return session.query(PositionState).filter_by(ticket=ticket).first()
    
    def upsert_position_state(
        self,
        ticket: int,
        symbol: str,
        magic: int,
        direction: str,
        entry_price: float,
        volume: float,
        current_sl: Optional[float] = None,
        current_tp: Optional[float] = None,
        opened_at: Optional[datetime] = None
    ) -> PositionState:
        """Create or update position state."""
        with self.session_scope() as session:
            state = session.query(PositionState).filter_by(ticket=ticket).first()
            
            if state is None:
                state = PositionState(
                    ticket=ticket,
                    symbol=symbol,
                    magic=magic,
                    direction=direction,
                    entry_price=entry_price,
                    volume=volume,
                    current_sl=current_sl,
                    current_tp=current_tp,
                    current_stage=0,
                    opened_at=opened_at or datetime.utcnow()
                )
                
                # Initialize high/low price
                if direction == 'LONG':
                    state.highest_price = entry_price
                else:
                    state.lowest_price = entry_price
                
                session.add(state)
            else:
                state.current_sl = current_sl
                state.current_tp = current_tp
            
            session.commit()
            return state
    
    def update_position_stage(
        self,
        ticket: int,
        new_stage: int,
        new_sl: float,
        new_tp: Optional[float],
        trigger_pips: float,
        protection_pct: float
    ):
        """Update position to new stage and log transition."""
        with self.session_scope() as session:
            state = session.query(PositionState).filter_by(ticket=ticket).first()
            if state is None:
                logger.warning(f"Position {ticket} not found for stage update")
                return
            
            old_stage = state.current_stage
            
            # Update state
            state.current_stage = new_stage
            state.current_sl = new_sl
            state.current_tp = new_tp
            state.max_profit_pips = max(state.max_profit_pips or 0, trigger_pips)
            
            # Log transition
            transition = StageTransitionLog(
                position_id=state.id,
                ticket=ticket,
                from_stage=old_stage,
                to_stage=new_stage,
                trigger_pips=trigger_pips,
                new_sl=new_sl,
                new_tp=new_tp,
                protection_pct=protection_pct
            )
            session.add(transition)
            
            session.commit()
            logger.info(f"Position {ticket}: Stage {old_stage} → {new_stage}")
    
    def delete_position_state(self, ticket: int):
        """Delete closed position state."""
        with self.session_scope() as session:
            state = session.query(PositionState).filter_by(ticket=ticket).first()
            if state:
                session.delete(state)
                session.commit()
    
    def get_all_position_states(self) -> list:
        """Get all open position states."""
        with self.session_scope() as session:
            return session.query(PositionState).all()
    
    # =========================================================================
    # Model Health Operations
    # =========================================================================
    
    def get_model_health(self, model_name: str) -> Optional[ModelHealth]:
        """Get model health record."""
        with self.session_scope() as session:
            return session.query(ModelHealth).filter_by(model_name=model_name).first()
    
    def update_model_health(
        self,
        model_name: str,
        status: str,
        execution_time_ms: Optional[int] = None,
        signals: int = 0,
        trades: int = 0
    ):
        """Update model health after a run."""
        with self.session_scope() as session:
            health = session.query(ModelHealth).filter_by(model_name=model_name).first()
            
            if health is None:
                health = ModelHealth(
                    model_name=model_name,
                    first_run_at=datetime.utcnow()
                )
                session.add(health)
            
            # Update counters
            health.total_runs += 1
            health.last_run_at = datetime.utcnow()
            health.last_run_status = status
            
            if status == 'SUCCESS':
                health.successful_runs += 1
                health.consecutive_failures = 0
            elif status == 'FAILED':
                health.failed_runs += 1
                health.consecutive_failures += 1
            elif status == 'TIMEOUT':
                health.timeout_runs += 1
                health.consecutive_failures += 1
            elif status == 'EMPTY':
                health.empty_runs += 1
                # Empty doesn't count as failure
            
            # Update averages
            if execution_time_ms:
                if health.avg_execution_time_ms:
                    health.avg_execution_time_ms = (
                        health.avg_execution_time_ms * 0.9 + execution_time_ms * 0.1
                    )
                else:
                    health.avg_execution_time_ms = execution_time_ms
            
            health.total_signals += signals
            health.total_trades += trades
            
            # Auto-disable check
            if health.consecutive_failures >= 3:
                health.auto_disabled = True
                health.auto_disabled_reason = f"3+ consecutive failures"
                health.disabled_at = datetime.utcnow()
                logger.warning(f"Model {model_name} auto-disabled: consecutive failures")
            
            session.commit()
    
    def is_model_enabled(self, model_name: str) -> bool:
        """Check if model is enabled (not auto-disabled)."""
        health = self.get_model_health(model_name)
        if health is None:
            return True  # New model, enabled by default
        return health.is_enabled and not health.auto_disabled
    
    # =========================================================================
    # Signal & Trade Logging
    # =========================================================================
    
    def log_signal(
        self,
        model_name: str,
        symbol: str,
        direction: str,
        confidence: float,
        weight: float = 1.0,
        aggregation_status: Optional[str] = None,
        risk_status: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        trade_ticket: Optional[int] = None
    ):
        """Log a signal."""
        with self.session_scope() as session:
            signal = SignalLog(
                model_name=model_name,
                symbol=symbol,
                direction=direction,
                confidence=confidence,
                weight=weight,
                aggregation_status=aggregation_status,
                risk_status=risk_status,
                rejection_reason=rejection_reason,
                trade_ticket=trade_ticket
            )
            session.add(signal)
            session.commit()
    
    def log_trade(
        self,
        symbol: str,
        direction: str,
        magic: int,
        volume: float,
        status: str,
        model_name: Optional[str] = None,
        ticket: Optional[int] = None,
        entry_price: Optional[float] = None,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        mt5_retcode: Optional[int] = None,
        mt5_comment: Optional[str] = None
    ):
        """Log a trade attempt."""
        with self.session_scope() as session:
            trade = TradeLog(
                ticket=ticket,
                symbol=symbol,
                direction=direction,
                magic=magic,
                model_name=model_name,
                volume=volume,
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
                status=status,
                mt5_retcode=mt5_retcode,
                mt5_comment=mt5_comment,
                filled_at=datetime.utcnow() if status == 'FILLED' else None
            )
            session.add(trade)
            session.commit()
    
    def log_model_run(
        self,
        model_name: str,
        timeframe: str,
        status: str,
        batch_id: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        signals_generated: int = 0,
        signals_passed: int = 0
    ):
        """Log a model execution run."""
        with self.session_scope() as session:
            run = ModelRun(
                model_name=model_name,
                timeframe=timeframe,
                status=status,
                batch_id=batch_id,
                execution_time_ms=execution_time_ms,
                error_message=error_message,
                signals_generated=signals_generated,
                signals_passed=signals_passed
            )
            session.add(run)
            session.commit()


# Global instance
db_manager = DatabaseManager()
