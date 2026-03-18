"""
Solara AI Quant - Configuration Module

Central configuration management for all SAQ components.
Loads settings from environment variables and provides defaults.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# PATH CONFIGURATION
# =============================================================================

# Project root (where this file is located)
PROJECT_ROOT = Path(__file__).parent.absolute()

# MT5 Terminal path (from env or default)
MT5_TERMINAL_PATH = Path(os.getenv(
    'MT5_TERMINAL_PATH',
    r'C:\Users\Default\AppData\Roaming\MetaQuotes\Terminal'
))

# MQL5 Files directory (where EA writes CSVs)
MQL5_FILES_DIR = MT5_TERMINAL_PATH / 'MQL5' / 'Files'

# Internal directories
MODELS_DIR = PROJECT_ROOT / os.getenv('SAQ_MODELS_DIR', 'Models')
LOGS_DIR = PROJECT_ROOT / os.getenv('SAQ_LOGS_DIR', 'logs')
STATE_DIR = PROJECT_ROOT / os.getenv('SAQ_STATE_DIR', 'state')
CONFIG_DIR = PROJECT_ROOT / 'config'

# Ensure directories exist
for dir_path in [MODELS_DIR, LOGS_DIR, STATE_DIR, CONFIG_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# MT5 CONNECTION
# =============================================================================

@dataclass
class MT5Config:
    """MT5 connection configuration."""
    login: int = field(default_factory=lambda: int(os.getenv('MT5_LOGIN', '0')))
    password: str = field(default_factory=lambda: os.getenv('MT5_PASSWORD', ''))
    server: str = field(default_factory=lambda: os.getenv('MT5_SERVER', ''))
    terminal_path: Path = field(default_factory=lambda: MT5_TERMINAL_PATH)
    timeout: int = 60000  # milliseconds
    portable: bool = False


# =============================================================================
# TIMEFRAME CONFIGURATION
# =============================================================================

@dataclass
class TimeframeConfig:
    """Configuration for watched timeframes."""
    name: str
    csv_filename: str
    mt5_timeframe: int  # MT5 TIMEFRAME constant value
    
    @property
    def csv_path(self) -> Path:
        return MQL5_FILES_DIR / self.csv_filename


# Standard timeframes
TIMEFRAMES = {
    'M5': TimeframeConfig('M5', 'marketdata_PERIOD_M5.csv', 5),
    'M15': TimeframeConfig('M15', 'marketdata_PERIOD_M15.csv', 15),
    'H1': TimeframeConfig('H1', 'marketdata_PERIOD_H1.csv', 60),
    'H4': TimeframeConfig('H4', 'marketdata_PERIOD_H4.csv', 240),
    'D1': TimeframeConfig('D1', 'marketdata_PERIOD_D1.csv', 1440),
}


# =============================================================================
# DATA INGESTION
# =============================================================================

@dataclass
class IngestionConfig:
    """Data ingestion configuration."""
    # Required columns in CSV
    required_columns: tuple = (
        'timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume'
    )
    
    # Minimum bars per symbol for processing
    min_bars_per_symbol: int = 2
    
    # Timestamp format from EA
    timestamp_format: str = '%Y.%m.%d %H:%M:%S'
    
    # Drop rows with these conditions
    drop_invalid_ohlc: bool = True  # high < low
    drop_null_symbol: bool = True


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

@dataclass
class FeatureConfig:
    """Feature engineering configuration."""
    # D1 merge settings
    d1_lookback_shift: int = 1  # Use previous day's D1 (no lookahead)
    
    # Feature computation
    rsi_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    
    # Feature version for compatibility checking
    current_version: str = 'v3'


# =============================================================================
# MODEL EXECUTION
# =============================================================================

@dataclass
class ExecutionConfig:
    """Model execution configuration."""
    # Worker pool
    max_concurrent_models: int = 8
    model_timeout_seconds: int = 30
    
    # Auto-disable after consecutive failures
    max_consecutive_failures: int = 3
    
    # Model registry file
    registry_file: Path = field(default_factory=lambda: PROJECT_ROOT / 'model_registry.yaml')


# =============================================================================
# RISK MANAGEMENT
# =============================================================================

@dataclass
class RiskConfig:
    """Risk management configuration."""
    # Daily limits
    max_daily_drawdown_pct: float = field(
        default_factory=lambda: float(os.getenv('MAX_DAILY_DRAWDOWN_PCT', '0.05'))
    )
    max_daily_trades: int = field(
        default_factory=lambda: int(os.getenv('MAX_DAILY_TRADES', '20'))
    )
    
    # Per-trade risk
    max_risk_per_trade: float = field(
        default_factory=lambda: float(os.getenv('MAX_RISK_PER_TRADE', '0.02'))
    )
    
    # Lot size limits
    min_lot: float = 0.01
    max_lot: float = 10.0
    
    # Slippage
    max_slippage_points: int = field(
        default_factory=lambda: int(os.getenv('MAX_SLIPPAGE_POINTS', '30'))
    )


# =============================================================================
# TRADE EXECUTION
# =============================================================================

@dataclass
class TradeConfig:
    """Trade execution configuration."""
    # Order retry
    retry_attempts: int = field(
        default_factory=lambda: int(os.getenv('ORDER_RETRY_ATTEMPTS', '3'))
    )
    retry_delay_ms: int = field(
        default_factory=lambda: int(os.getenv('ORDER_RETRY_DELAY_MS', '500'))
    )
    
    # Magic number base (models add their own offset)
    magic_base: int = 0
    
    # Comment prefix
    comment_prefix: str = 'SAQ_'


# =============================================================================
# SURVIVOR ENGINE
# =============================================================================

@dataclass
class SurvivorConfig:
    """Survivor engine configuration."""
    # Check interval
    check_interval_seconds: int = field(
        default_factory=lambda: int(os.getenv('SURVIVOR_CHECK_INTERVAL_SECONDS', '60'))
    )
    
    # Stage definitions file
    stage_definitions_file: Path = field(
        default_factory=lambda: PROJECT_ROOT / 'survivor' / 'stage_definitions.yaml'
    )
    
    # Position state tracking
    max_stages: int = 22


# =============================================================================
# WATCHDOG
# =============================================================================

@dataclass
class WatchdogConfig:
    """File watchdog configuration."""
    # Debounce delay to avoid duplicate triggers
    debounce_seconds: float = field(
        default_factory=lambda: float(os.getenv('WATCHDOG_DEBOUNCE_SECONDS', '2'))
    )
    
    # Watched files (built from TIMEFRAMES)
    @property
    def watched_files(self) -> list:
        return [tf.csv_path for tf in TIMEFRAMES.values()]


# =============================================================================
# DATABASE
# =============================================================================

@dataclass
class DatabaseConfig:
    """Database configuration."""
    # SQLite database file
    db_path: Path = field(default_factory=lambda: STATE_DIR / 'solara_aq.db')
    
    # Connection settings
    timeout: int = 30
    check_same_thread: bool = False  # Allow multi-threading with proper locks


# =============================================================================
# LOGGING
# =============================================================================

@dataclass
class LoggingConfig:
    """Logging configuration."""
    # Log file
    log_file: Path = field(default_factory=lambda: LOGS_DIR / 'saq.log')
    
    # Log levels
    console_level: str = 'INFO'
    file_level: str = 'DEBUG'
    
    # Format
    format: str = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    date_format: str = '%Y-%m-%d %H:%M:%S'
    
    # Rotation
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


# =============================================================================
# ENVIRONMENT
# =============================================================================

SAQ_ENV = os.getenv('SAQ_ENV', 'development')
IS_PRODUCTION = SAQ_ENV == 'production'
IS_DEVELOPMENT = SAQ_ENV == 'development'

# Windows compatibility
IS_WINDOWS = sys.platform.startswith('win')


# =============================================================================
# GLOBAL CONFIG INSTANCES
# =============================================================================

mt5_config = MT5Config()
ingestion_config = IngestionConfig()
feature_config = FeatureConfig()
execution_config = ExecutionConfig()
risk_config = RiskConfig()
trade_config = TradeConfig()
survivor_config = SurvivorConfig()
watchdog_config = WatchdogConfig()
database_config = DatabaseConfig()
logging_config = LoggingConfig()


# =============================================================================
# VALIDATION
# =============================================================================

def validate_config() -> bool:
    """Validate configuration on startup."""
    errors = []
    
    # Check MT5 credentials in production
    if IS_PRODUCTION:
        if not mt5_config.login:
            errors.append("MT5_LOGIN not set")
        if not mt5_config.password:
            errors.append("MT5_PASSWORD not set")
        if not mt5_config.server:
            errors.append("MT5_SERVER not set")
    
    # Check model registry exists
    if not execution_config.registry_file.exists():
        errors.append(f"Model registry not found: {execution_config.registry_file}")
    
    if errors:
        for error in errors:
            print(f"CONFIG ERROR: {error}")
        return False
    
    return True


def print_config():
    """Print current configuration (for debugging)."""
    print("\n" + "=" * 60)
    print("  SOLARA AI QUANT - CONFIGURATION")
    print("=" * 60)
    print(f"  Environment:      {SAQ_ENV}")
    print(f"  Project Root:     {PROJECT_ROOT}")
    print(f"  MT5 Terminal:     {MT5_TERMINAL_PATH}")
    print(f"  MQL5 Files:       {MQL5_FILES_DIR}")
    print(f"  Models Dir:       {MODELS_DIR}")
    print(f"  Database:         {database_config.db_path}")
    print(f"  Max Workers:      {execution_config.max_concurrent_models}")
    print(f"  Max Daily DD:     {risk_config.max_daily_drawdown_pct * 100}%")
    print(f"  Risk per Trade:   {risk_config.max_risk_per_trade * 100}%")
    print("=" * 60 + "\n")
