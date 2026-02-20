"""
config.py — Solara AI Quant Master Configuration
=================================================
Single source of truth for all system constants, paths, and parameters.

All sensitive values (credentials, paths) are loaded from environment
variables. Never hardcode credentials here.

Usage:
    from config import config
    print(config.MAX_CONCURRENT_MODELS)
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env file (dev only — prod uses OS env vars directly) ──────────────
load_dotenv()


# ── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).parent.resolve()
MODELS_DIR: Path = BASE_DIR / "Models"
STATE_DIR: Path = BASE_DIR / "state"
LOGS_DIR: Path = BASE_DIR / "logs"
REPORTS_DIR: Path = BASE_DIR / "reports"

# ── MT5 Terminal Path ────────────────────────────────────────────────────────
# Set MT5_TERMINAL_PATH in your .env or OS environment variables.
# Example: C:\Users\Ben\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075
MT5_TERMINAL_PATH: Path = Path(
    os.environ.get(
        "MT5_TERMINAL_PATH",
        r"C:\Users\[name]\AppData\Roaming\MetaQuotes\Terminal\[hash]",
    )
)
MT5_FILES_DIR: Path = MT5_TERMINAL_PATH / "MQL5" / "Files"

# ── MT5 Credentials (loaded from environment — never hardcoded) ──────────────
MT5_LOGIN: int = int(os.environ.get("MT5_LOGIN", "0"))
MT5_PASSWORD: str = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER: str = os.environ.get("MT5_SERVER", "")

# ── Environment ───────────────────────────────────────────────────────────────
SAQ_ENV: str = os.environ.get("SAQ_ENV", "development")
IS_PRODUCTION: bool = SAQ_ENV == "production"

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.environ.get("SAQ_LOG_LEVEL", "DEBUG" if not IS_PRODUCTION else "INFO")

# ── Watched CSV Files (one per supported timeframe) ──────────────────────────
WATCHED_FILES: dict[str, Path] = {
    "M5":  MT5_FILES_DIR / "marketdata_PERIOD_M5.csv",
    "M15": MT5_FILES_DIR / "marketdata_PERIOD_M15.csv",
    "H1":  MT5_FILES_DIR / "marketdata_PERIOD_H1.csv",
    "H4":  MT5_FILES_DIR / "marketdata_PERIOD_H4.csv",
}

SUPPORTED_TIMEFRAMES: list[str] = list(WATCHED_FILES.keys())

# ── Model Registry ───────────────────────────────────────────────────────────
MODEL_REGISTRY_PATH: Path = BASE_DIR / "model_registry.yaml"
FEATURE_VERSIONS_PATH: Path = BASE_DIR / "features" / "feature_versions.yaml"

# ── Model Execution Engine ────────────────────────────────────────────────────
# Maximum models running simultaneously within a single timeframe pipeline.
# 4 pipelines × 8 workers = up to 32 models system-wide at peak load.
MAX_CONCURRENT_MODELS: int = int(os.environ.get("SAQ_MAX_CONCURRENT_MODELS", "8"))

# ── Survivor Engine ───────────────────────────────────────────────────────────
# How often the Survivor Engine checks and updates open positions (seconds).
SURVIVOR_INTERVAL_SECONDS: int = int(
    os.environ.get("SAQ_SURVIVOR_INTERVAL_SECONDS", "60")
)
STAGE_DEFINITIONS_PATH: Path = BASE_DIR / "survivor" / "stage_definitions.yaml"

# ── Risk Management ───────────────────────────────────────────────────────────
# Maximum daily equity drawdown allowed before all trading halts.
MAX_DAILY_DRAWDOWN_PCT: float = 0.05        # 5% of starting equity

# Maximum trades per model (magic number) per calendar day.
MAX_DAILY_TRADES: int = 20 if IS_PRODUCTION else 999

# Risk per trade as a fraction of current account equity.
MAX_RISK_PER_TRADE: float = 0.02            # 2%

# Default stop loss / take profit in pips (overridable per model in registry).
DEFAULT_STOP_LOSS_PIPS: int = 30
DEFAULT_TAKE_PROFIT_PIPS: int = 40

# Maximum slippage accepted on order fill (in points).
MAX_SLIPPAGE_POINTS: int = 10

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_PATH: Path = STATE_DIR / "solara_aq.db"
DATABASE_URL: str = f"sqlite:///{DATABASE_PATH}"

# ── Feature Engineering ───────────────────────────────────────────────────────
# Minimum number of historical bars required per symbol to compute all features.
MIN_LOOKBACK_BARS: int = 30

# Bollinger Band parameters.
BB_PERIOD: int = 20
BB_STD_DEV: float = 2.0

# RSI period (Wilder's smoothing).
RSI_PERIOD: int = 14

# ── Model Health ─────────────────────────────────────────────────────────────
# Number of consecutive failures before a model is auto-disabled.
AUTO_DISABLE_AFTER_FAILURES: int = 3

# ── Ensure runtime directories exist ─────────────────────────────────────────
def ensure_dirs() -> None:
    """Create required runtime directories if they don't exist."""
    for d in [STATE_DIR, LOGS_DIR, REPORTS_DIR, REPORTS_DIR / "archive", REPORTS_DIR / "exports"]:
        d.mkdir(parents=True, exist_ok=True)


def validate() -> list[str]:
    """
    Validate critical config values at startup.
    Returns a list of error messages. Empty list = all good.
    """
    errors = []

    if MT5_LOGIN == 0:
        errors.append("MT5_LOGIN not set — add it to your .env file or OS environment")

    if not MT5_PASSWORD:
        errors.append("MT5_PASSWORD not set — add it to your .env file or OS environment")

    if not MT5_SERVER:
        errors.append("MT5_SERVER not set — add it to your .env file or OS environment")

    if "[name]" in str(MT5_TERMINAL_PATH) or "[hash]" in str(MT5_TERMINAL_PATH):
        errors.append(
            "MT5_TERMINAL_PATH still has placeholder values — "
            "set MT5_TERMINAL_PATH in your .env file"
        )

    if not MODEL_REGISTRY_PATH.exists():
        errors.append(f"model_registry.yaml not found at: {MODEL_REGISTRY_PATH}")

    if not MODELS_DIR.exists():
        errors.append(f"Models directory not found at: {MODELS_DIR}")

    if MAX_CONCURRENT_MODELS < 1 or MAX_CONCURRENT_MODELS > 64:
        errors.append(f"MAX_CONCURRENT_MODELS must be between 1 and 64, got: {MAX_CONCURRENT_MODELS}")

    return errors
