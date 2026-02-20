"""
state/database.py — SQLite Database Engine
============================================
SQLAlchemy engine, session factory, and init function.
All writes are atomic. Row-level locking via SQLAlchemy sessions.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import structlog
import config

log = structlog.get_logger(__name__)

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False},   # required for SQLite + threads
    echo=False,
)

# Enable WAL mode for better concurrent read/write performance
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    from state import models  # import here to avoid circular imports
    Base.metadata.create_all(bind=engine)
    log.info("database_tables_created_or_verified", path=str(config.DATABASE_PATH))


def get_session():
    """Context manager for database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
