"""
Logging utilities for ML Training System.

Provides structured, deterministic logging with:
- Console output (clean, readable)
- File output (detailed)
- Progress tracking
- Fold/config-scoped formatting
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


# =============================================================================
# DATA CLASSES FOR STRUCTURED LOGGING
# =============================================================================

@dataclass
class FoldMetricsLog:
    """Structured fold metrics for logging."""
    fold_number: int
    train_size: int
    cal_size: int
    thresh_size: int
    n_features_selected: int
    selected_features: List[str]
    best_hyperparams: Dict[str, Any]
    threshold: float
    precision: float
    recall: float
    f1_score: float
    auc_pr: float
    expected_value: float
    trade_count: int
    regime_breakdown: Dict[str, Dict[str, float]]


@dataclass 
class ConfigResultLog:
    """Structured config result for logging."""
    config_id: str
    bb_threshold: float
    rsi_threshold: int
    tp_pips: int
    max_holding_bars: int
    labels_generated: int
    labels_dropped: int
    signal_filtered_rows: int
    signal_pct: float
    fold_metrics: List[FoldMetricsLog]
    aggregate_precision: float
    aggregate_precision_std: float
    aggregate_f1: float
    aggregate_ev: float
    aggregate_ev_std: float
    total_trades: int
    status: str  # "PASSED" or "REJECTED"
    rejection_reason: Optional[str]


# =============================================================================
# CUSTOM FORMATTER
# =============================================================================

class CleanFormatter(logging.Formatter):
    """Clean formatter without noisy prefixes for console."""
    
    def format(self, record: logging.LogRecord) -> str:
        # For INFO level, just return the message (clean output)
        if record.levelno == logging.INFO:
            return record.getMessage()
        # For other levels, include level name
        return f"[{record.levelname}] {record.getMessage()}"


class DetailedFormatter(logging.Formatter):
    """Detailed formatter for file logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{timestamp} | {record.levelname:8} | {record.getMessage()}"


# =============================================================================
# LOGGER SETUP
# =============================================================================

def setup_logger(
    name: str = "ml_training",
    level: str = "INFO",
    log_to_file: bool = True,
    log_file: Optional[str] = None,
    logs_dir: str = "logs"
) -> logging.Logger:
    """
    Setup and configure the logger.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_to_file: Whether to log to file
        log_file: Path to log file
        logs_dir: Directory for log files
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler (clean output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(CleanFormatter())
    logger.addHandler(console_handler)
    
    # File handler (detailed output)
    if log_to_file:
        logs_path = Path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)
        
        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = logs_path / f"training_{timestamp}.log"
        else:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(DetailedFormatter())
        logger.addHandler(file_handler)
    
    return logger


# =============================================================================
# LOGGING FUNCTIONS
# =============================================================================

def log_header(logger: logging.Logger, title: str, width: int = 80) -> None:
    """Log a section header."""
    logger.info("=" * width)
    logger.info(title.center(width))
    logger.info("=" * width)


def log_subheader(logger: logging.Logger, title: str, width: int = 80) -> None:
    """Log a subsection header."""
    logger.info("-" * width)
    logger.info(title)
    logger.info("-" * width)


def log_separator(logger: logging.Logger, char: str = "-", width: int = 80) -> None:
    """Log a separator line."""
    logger.info(char * width)


def log_pipeline_start(
    logger: logging.Logger,
    n_rows: int,
    n_features: int,
    date_range: tuple,
    n_folds: int,
    n_configs: int,
    max_workers: int
) -> None:
    """Log pipeline start information."""
    log_header(logger, "TRAINING PIPELINE STARTED")
    logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info(f"Data: {n_rows:,} rows | Features: {n_features} | Date range: {date_range[0]} → {date_range[1]}")
    logger.info(f"Walk-forward folds: {n_folds} (60% train / 20% calibration / 20% threshold)")
    logger.info(f"Configuration space: {n_configs:,} combinations")
    logger.info(f"Concurrency: {max_workers} workers")
    log_separator(logger, "=")


def log_preprocessing_complete(
    logger: logging.Logger,
    rows_before: int,
    rows_after: int,
    dropped: int
) -> None:
    """Log preprocessing completion."""
    logger.info("")
    logger.info("PREPROCESSING COMPLETE")
    logger.info(f"  Rows after cleaning: {rows_after:,} ({dropped:,} dropped for NaN)")


def log_regime_tagging_complete(
    logger: logging.Logger,
    trending_count: int,
    ranging_count: int,
    volatile_count: int,
    total: int
) -> None:
    """Log regime tagging completion."""
    logger.info("")
    logger.info("REGIME TAGGING COMPLETE")
    logger.info(f"  Trending: {trending_count:,} rows ({trending_count/total*100:.1f}%)")
    logger.info(f"  Ranging:  {ranging_count:,} rows ({ranging_count/total*100:.1f}%)")
    logger.info(f"  Volatile: {volatile_count:,} rows ({volatile_count/total*100:.1f}%)")


def log_walk_forward_boundaries(
    logger: logging.Logger,
    fold_boundaries: List[Dict[str, Any]]
) -> None:
    """Log walk-forward fold boundaries."""
    logger.info("")
    logger.info("WALK-FORWARD BOUNDARIES DEFINED")
    for fold in fold_boundaries:
        logger.info(
            f"  Fold {fold['fold_number']}: "
            f"Train {fold['train_start']}→{fold['train_end']} | "
            f"Cal {fold['cal_start']}→{fold['cal_end']} | "
            f"Thresh {fold['thresh_start']}→{fold['thresh_end']}"
        )


def log_config_start(
    logger: logging.Logger,
    config_id: str,
    current: int,
    total: int,
    bb_threshold: float,
    rsi_threshold: int,
    tp_pips: int,
    max_holding_bars: int
) -> None:
    """Log configuration experiment start."""
    logger.info("")
    logger.info(
        f"[{config_id}] BB={bb_threshold:.2f} RSI={rsi_threshold} "
        f"TP={tp_pips} HOLD={max_holding_bars}"
    )


def log_config_labels(
    logger: logging.Logger,
    total_rows: int,
    labeled_rows: int,
    dropped: int
) -> None:
    """Log label generation results."""
    logger.info(f"  Labels generated: {labeled_rows:,} rows ({dropped:,} dropped for insufficient future data)")


def log_config_signals(
    logger: logging.Logger,
    before: int,
    after: int
) -> None:
    """Log signal filtering results."""
    pct = (after / before * 100) if before > 0 else 0
    logger.info(f"  Signal filter: {before:,} → {after:,} rows ({pct:.1f}%)")


def log_fold_result(
    logger: logging.Logger,
    fold: FoldMetricsLog
) -> None:
    """Log single fold result."""
    logger.info(f"  Fold {fold.fold_number}:")
    logger.info(f"    Split: Train={fold.train_size:,} | Cal={fold.cal_size:,} | Thresh={fold.thresh_size:,}")
    logger.info(f"    RFE: → {fold.n_features_selected} features {fold.selected_features[:5]}...")
    logger.info(f"    HP: {fold.best_hyperparams}")
    logger.info(f"    Threshold: {fold.threshold:.2f}")
    logger.info(
        f"    Metrics: P={fold.precision:.2f} | R={fold.recall:.2f} | "
        f"F1={fold.f1_score:.2f} | EV={fold.expected_value:+.1f} | n={fold.trade_count}"
    )
    
    # Regime breakdown
    regime_str = " | ".join([
        f"{regime} P={metrics.get('precision', 0):.2f} n={metrics.get('trade_count', 0)}"
        for regime, metrics in fold.regime_breakdown.items()
    ])
    logger.info(f"    Regime: {regime_str}")


def log_config_aggregate(
    logger: logging.Logger,
    result: ConfigResultLog
) -> None:
    """Log configuration aggregate results."""
    log_separator(logger, "-", 50)
    logger.info(
        f"  AGGREGATE: P={result.aggregate_precision:.2f}±{result.aggregate_precision_std:.2f} | "
        f"F1={result.aggregate_f1:.2f} | "
        f"EV={result.aggregate_ev:+.2f}±{result.aggregate_ev_std:.2f} | "
        f"Trades={result.total_trades}"
    )
    
    if result.status == "PASSED":
        logger.info(f"  STATUS: ✓ PASSED")
    else:
        logger.info(f"  STATUS: ✗ REJECTED ({result.rejection_reason})")


def log_progress(
    logger: logging.Logger,
    current: int,
    total: int,
    passed: int,
    rejected: int,
    elapsed_seconds: float
) -> None:
    """Log progress update."""
    pct = current / total * 100
    rate = current / elapsed_seconds if elapsed_seconds > 0 else 0
    eta_seconds = (total - current) / rate if rate > 0 else 0
    eta_hours = eta_seconds / 3600
    eta_mins = (eta_seconds % 3600) / 60
    
    logger.info("")
    logger.info(
        f"[PROGRESS] {current:,}/{total:,} complete ({pct:.1f}%) | "
        f"Passed: {passed:,} | Rejected: {rejected:,} | "
        f"ETA: {int(eta_hours)}h {int(eta_mins)}m"
    )


def log_experiments_complete(
    logger: logging.Logger,
    total: int,
    passed: int,
    rejected: int,
    rejection_reasons: Dict[str, int],
    duration_seconds: float
) -> None:
    """Log experiments completion."""
    duration_hours = duration_seconds / 3600
    duration_mins = (duration_seconds % 3600) / 60
    
    log_header(logger, "CONFIGURATION EXPERIMENTS COMPLETE")
    logger.info(f"Duration: {int(duration_hours)}h {int(duration_mins)}m")
    logger.info(f"Total: {total:,}")
    logger.info(f"Passed: {passed:,} ({passed/total*100:.1f}%)")
    logger.info(f"Rejected: {rejected:,} ({rejected/total*100:.1f}%)")
    
    for reason, count in rejection_reasons.items():
        logger.info(f"  - {reason}: {count:,}")


def log_best_config(
    logger: logging.Logger,
    config_id: str,
    bb_threshold: float,
    rsi_threshold: int,
    tp_pips: int,
    sl_pips: int,
    max_holding_bars: int,
    features: List[str],
    feature_importances: List[float],
    hyperparams: Dict[str, Any],
    threshold: float,
    precision: float,
    precision_std: float,
    recall: float,
    f1: float,
    auc_pr: float,
    ev: float,
    ev_std: float,
    total_trades: int,
    regime_breakdown: Dict[str, Dict[str, float]]
) -> None:
    """Log best configuration selection."""
    log_header(logger, "BEST CONFIGURATION SELECTED")
    logger.info(f"Config ID: {config_id}")
    logger.info(f"Parameters: BB={bb_threshold:.2f} | RSI={rsi_threshold} | TP={tp_pips} | SL={sl_pips} | HOLD={max_holding_bars}")
    logger.info("")
    logger.info(f"Features ({len(features)}):")
    for i, (feat, imp) in enumerate(zip(features, feature_importances), 1):
        logger.info(f"  {i}. {feat} (importance: {imp:.3f})")
    
    logger.info("")
    logger.info("Hyperparameters:")
    for key, value in hyperparams.items():
        logger.info(f"  {key}: {value}")
    
    logger.info("")
    logger.info(f"Threshold: {threshold:.2f}")
    logger.info("")
    logger.info("Aggregate Metrics:")
    logger.info(f"  Precision:      {precision:.2f} ± {precision_std:.2f}")
    logger.info(f"  Recall:         {recall:.2f}")
    logger.info(f"  F1 Score:       {f1:.2f}")
    logger.info(f"  AUC-PR:         {auc_pr:.2f}")
    logger.info(f"  Expected Value: {ev:+.2f} ± {ev_std:.2f}")
    logger.info(f"  Total Trades:   {total_trades:,}")
    
    logger.info("")
    logger.info("Regime Breakdown:")
    for regime, metrics in regime_breakdown.items():
        status = "✓" if metrics.get('expected_value', 0) > 0 else "⚠️"
        logger.info(
            f"  {regime.capitalize():10} P={metrics.get('precision', 0):.2f} | "
            f"n={metrics.get('trade_count', 0)} ({metrics.get('pct', 0):.0f}%) | "
            f"EV={metrics.get('expected_value', 0):+.1f} {status}"
        )


def log_final_training(
    logger: logging.Logger,
    combined_train_rows: int,
    combined_cal_rows: int
) -> None:
    """Log final model training."""
    log_header(logger, "FINAL MODEL TRAINING")
    logger.info(f"Combined training data: {combined_train_rows:,} rows")
    logger.info(f"Combined calibration data: {combined_cal_rows:,} rows")
    logger.info("Model trained with consensus features and hyperparameters")
    logger.info("Calibration applied (Platt scaling)")
    logger.info("Final model ready")


def log_artifacts_published(
    logger: logging.Logger,
    artifacts: Dict[str, str]
) -> None:
    """Log artifact publication."""
    log_header(logger, "ARTIFACTS PUBLISHED")
    for name, path in artifacts.items():
        logger.info(f"  → {path}")


def log_pipeline_complete(
    logger: logging.Logger,
    duration_seconds: float,
    best_config_id: str,
    best_params: Dict[str, Any],
    best_ev: float,
    recommendation: str
) -> None:
    """Log pipeline completion."""
    duration_hours = duration_seconds / 3600
    duration_mins = (duration_seconds % 3600) / 60
    
    log_header(logger, "TRAINING PIPELINE COMPLETE")
    logger.info(f"Total Duration: {int(duration_hours)}h {int(duration_mins)}m")
    logger.info(f"Status: SUCCESS")
    logger.info(
        f"Best Config: {best_config_id} "
        f"(BB={best_params['bb_threshold']:.2f}, RSI={best_params['rsi_threshold']}, "
        f"TP={best_params['tp_pips']}, HOLD={best_params['max_holding_bars']})"
    )
    logger.info(f"Expected Value: {best_ev:+.2f} pips per trade")
    logger.info(f"Recommendation: {recommendation}")
    log_separator(logger, "=")