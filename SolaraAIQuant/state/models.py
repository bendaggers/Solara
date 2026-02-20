"""
state/models.py — SQLAlchemy ORM Models
=========================================
All 6 SAQ database tables as defined in FS Section 10.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, ForeignKey
from state.database import Base


class PositionState(Base):
    """Current Survivor Engine stage and protection level for each open position."""
    __tablename__ = "position_state"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticket          = Column(Integer, nullable=False, unique=True)
    symbol          = Column(String, nullable=False)
    magic           = Column(Integer, nullable=False)
    model_name      = Column(String, nullable=False)
    timeframe       = Column(String, nullable=False)
    position_type   = Column(String, nullable=False)    # LONG | SHORT
    entry_price     = Column(Float, nullable=False)
    volume          = Column(Float, nullable=False)
    initial_sl      = Column(Float, nullable=False)
    initial_tp      = Column(Float)
    current_sl      = Column(Float, nullable=False)
    current_tp      = Column(Float)
    current_stage   = Column(String, nullable=False, default="STAGE_0")
    highest_price   = Column(Float, nullable=False)
    lowest_price    = Column(Float, nullable=False)
    opened_at       = Column(DateTime, nullable=False)
    last_updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    closed          = Column(Boolean, nullable=False, default=False)
    closed_at       = Column(DateTime)
    close_reason    = Column(String)                    # SL_HIT | TP_HIT | MANUAL | UNKNOWN


class StageTransitionLog(Base):
    """Immutable append-only log of every stage advancement."""
    __tablename__ = "stage_transition_log"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    ticket           = Column(Integer, nullable=False)
    symbol           = Column(String, nullable=False)
    magic            = Column(Integer, nullable=False)
    from_stage       = Column(String, nullable=False)
    to_stage         = Column(String, nullable=False)
    pips_in_profit   = Column(Float, nullable=False)
    protection_pct   = Column(Float, nullable=False)
    old_sl           = Column(Float, nullable=False)
    new_sl           = Column(Float, nullable=False)
    old_tp           = Column(Float)
    new_tp           = Column(Float)
    transitioned_at  = Column(DateTime, nullable=False, default=datetime.utcnow)
    mt5_confirmed    = Column(Boolean, nullable=False, default=False)


class ModelRun(Base):
    """Every model execution attempt — success, failure, or timeout."""
    __tablename__ = "model_run"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    model_name         = Column(String, nullable=False)
    timeframe          = Column(String, nullable=False)
    cycle_triggered_at = Column(DateTime)
    run_started_at     = Column(DateTime, nullable=False)
    run_completed_at   = Column(DateTime)
    elapsed_seconds    = Column(Float)
    status             = Column(String, nullable=False)    # SUCCESS|FAILED|TIMEOUT|EMPTY
    signals_generated  = Column(Integer, nullable=False, default=0)
    error_message      = Column(String)
    batch_number       = Column(Integer, nullable=False)
    worker_id          = Column(String)


class SignalLog(Base):
    """Every signal produced — whether acted on or not."""
    __tablename__ = "signal_log"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    model_name          = Column(String, nullable=False)
    magic               = Column(Integer, nullable=False)
    symbol              = Column(String, nullable=False)
    direction           = Column(String, nullable=False)   # LONG | SHORT
    confidence          = Column(Float, nullable=False)
    timeframe           = Column(String, nullable=False)
    price_at_signal     = Column(Float, nullable=False)
    signal_at           = Column(DateTime, nullable=False)
    aggregation_outcome = Column(String, nullable=False)   # PASSED|SUPPRESSED_CONFLICT|BELOW_THRESHOLD
    risk_outcome        = Column(String)                   # PASSED|REJECTED_*
    trade_ticket        = Column(Integer)
    trade_outcome       = Column(String)                   # PLACED|FAILED|REJECTED


class TradeLog(Base):
    """Every trade placement attempt."""
    __tablename__ = "trade_log"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    signal_log_id    = Column(Integer, ForeignKey("signal_log.id"))
    model_name       = Column(String, nullable=False)
    magic            = Column(Integer, nullable=False)
    symbol           = Column(String, nullable=False)
    direction        = Column(String, nullable=False)
    lot_size         = Column(Float, nullable=False)
    requested_price  = Column(Float, nullable=False)
    fill_price       = Column(Float)
    sl               = Column(Float, nullable=False)
    tp               = Column(Float)
    ticket           = Column(Integer)
    mt5_result_code  = Column(Integer)
    status           = Column(String, nullable=False)      # PLACED|FAILED|REJECTED
    failure_reason   = Column(String)
    attempts         = Column(Integer, nullable=False, default=1)
    attempted_at     = Column(DateTime, nullable=False)
    confirmed_at     = Column(DateTime)
    timeframe        = Column(String, nullable=False)


class ModelHealth(Base):
    """Per-model health record — one row per model, updated each cycle."""
    __tablename__ = "model_health"

    model_name             = Column(String, primary_key=True)
    timeframe              = Column(String, nullable=False)
    last_run_at            = Column(DateTime)
    last_run_status        = Column(String)
    consecutive_failures   = Column(Integer, nullable=False, default=0)
    total_runs             = Column(Integer, nullable=False, default=0)
    total_successes        = Column(Integer, nullable=False, default=0)
    total_failures         = Column(Integer, nullable=False, default=0)
    total_timeouts         = Column(Integer, nullable=False, default=0)
    avg_elapsed_seconds    = Column(Float, nullable=False, default=0.0)
    auto_disabled          = Column(Boolean, nullable=False, default=False)
    auto_disabled_at       = Column(DateTime)
    auto_disabled_reason   = Column(String)
