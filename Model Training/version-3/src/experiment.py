"""
Experiment orchestration for configuration testing.
FULLY OPTIMIZED VERSION with LIVE WORKER DISPLAY.

Optimizations implemented:
1. Pre-compute ALL labels (unique TP×Holding combinations) - ONCE
2. Pre-compute ALL signals (unique BB×RSI combinations) - ONCE
3. Batch processing by label configuration
6. Fold-level parallelism (exhaust all workers)
7. Numba-accelerated label generation (in labels.py)
8. LightGBM for faster training (in training.py)

Architecture:
- Phase 0: Pre-compute labels and signals
- Phase 1: Create fold tasks (config × fold combinations)
- Phase 2: Process fold tasks in parallel
- Phase 3: Aggregate results by config
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp
from multiprocessing import shared_memory, Manager
import pickle
import time
import warnings
from pathlib import Path
import traceback
import sys
import threading
import gc
import os
from datetime import datetime
from collections import defaultdict
import queue

# Local imports
from .checkpoint_db import FastCheckpointManager
from .labels import (
    generate_labels_and_signals,
    precompute_all_labels,
    precompute_all_signals,
    apply_precomputed_labels_and_signals,
    TradeDirection,
    LabelStats,
    SignalStats,
    LabelCache,
    SignalCache
)
from .splits import (
    FoldBoundary,
    FoldData,
    apply_split_to_filtered,
    validate_fold_data
)
from .features import (
    rfe_select,
    RFEResult,
    get_consensus_features
)
from .training import (
    tune_hyperparameters,
    train_model,
    calibrate_model,
    TrainedModel,
    HyperparameterResult,
    CalibrationResult,
    get_consensus_hyperparameters,
    get_best_model_type
)
from .evaluation import (
    compute_metrics,
    optimize_threshold,
    compute_regime_breakdown,
    aggregate_fold_metrics,
    check_acceptance_criteria,
    get_consensus_threshold,
    MetricsBundle,
    ThresholdResult,
    RegimeMetrics,
    AggregateMetrics
)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ConfigurationSpec:
    """Specification for a single configuration experiment."""
    config_id: str
    bb_threshold: float
    rsi_threshold: int
    tp_pips: int
    sl_pips: int
    max_holding_bars: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'config_id': self.config_id,
            'bb_threshold': self.bb_threshold,
            'rsi_threshold': self.rsi_threshold,
            'tp_pips': self.tp_pips,
            'sl_pips': self.sl_pips,
            'max_holding_bars': self.max_holding_bars
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ConfigurationSpec':
        return cls(**d)
    
    def short_str(self) -> str:
        return f"BB{self.bb_threshold:.2f}_RSI{self.rsi_threshold}_TP{self.tp_pips}"
    
    def label_key(self) -> str:
        """Key for label cache lookup."""
        return f"tp{self.tp_pips}_sl{self.sl_pips}_hold{self.max_holding_bars}"
    
    def signal_key(self) -> str:
        """Key for signal cache lookup."""
        return f"bb{self.bb_threshold:.2f}_rsi{self.rsi_threshold}"


@dataclass
class FoldResult:
    """Result from a single fold."""
    fold_number: int
    train_size: int
    calibration_size: int
    threshold_size: int
    rfe_result: RFEResult
    hyperparameter_result: HyperparameterResult
    calibration_result: CalibrationResult
    threshold_result: ThresholdResult
    metrics: MetricsBundle
    regime_breakdown: Dict[str, RegimeMetrics]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'fold_number': self.fold_number,
            'train_size': self.train_size,
            'calibration_size': self.calibration_size,
            'threshold_size': self.threshold_size,
            'n_features_selected': self.rfe_result.n_features_selected,
            'selected_features': self.rfe_result.selected_features,
            'threshold': self.threshold_result.optimal_threshold,
            'metrics': self.metrics.to_dict()
        }


@dataclass
class ExperimentResult:
    """Complete result from a configuration experiment."""
    config: ConfigurationSpec
    status: str
    rejection_reasons: List[str]
    label_stats: Optional[LabelStats]
    signal_stats: Optional[SignalStats]
    fold_results: List[FoldResult]
    aggregate_metrics: Optional[AggregateMetrics]
    consensus_features: List[str]
    consensus_hyperparameters: Dict[str, Any]
    consensus_threshold: float
    aggregate_regime_breakdown: Optional[Dict[str, Dict[str, float]]]
    execution_time_seconds: float
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'config': self.config.to_dict(),
            'status': self.status,
            'rejection_reasons': self.rejection_reasons,
            'aggregate_metrics': self.aggregate_metrics.to_dict() if self.aggregate_metrics else None,
            'consensus_features': self.consensus_features,
            'consensus_threshold': self.consensus_threshold,
            'execution_time_seconds': self.execution_time_seconds
        }


@dataclass
class ExperimentProgress:
    """Progress tracking for parallel experiments."""
    total: int
    completed: int
    passed: int
    rejected: int
    failed: int
    start_time: float
    
    def update(self, result: ExperimentResult) -> None:
        self.completed += 1
        if result.status == "PASSED":
            self.passed += 1
        elif result.status == "REJECTED":
            self.rejected += 1
        else:
            self.failed += 1
    
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time


@dataclass
class FoldTask:
    """A single fold processing task."""
    config: ConfigurationSpec
    fold_number: int
    fold_boundary: FoldBoundary
    
    def task_id(self) -> str:
        return f"{self.config.config_id}_fold{self.fold_number}"


# =============================================================================
# PROGRESS DISPLAY WITH WORKER TRACKING
# =============================================================================

class WorkerProgressDisplay:
    """
    Thread-safe progress display showing each worker's current task.
    
    Display format:
    ════════════════════════════════════════════════════════════════════════════════
    [████████████░░░░░░░░░░░░░░░░░░] 35.2% | 735/2,088 | ETA: 8.5h | Rate: 1.2/min
    ────────────────────────────────────────────────────────────────────────────────
    Worker 1: ✓ BB=0.84 RSI=78 TP=40 | EV=+19.6 Pr=70.8% T=35 | PASSED
    Worker 2: ⟳ BB=0.85 RSI=72 TP=50 | Processing...
    Worker 3: ✗ BB=0.86 RSI=70 TP=40 | EV=-2.1 Pr=38.2% T=89 | precision < 0.45
    ...
    ────────────────────────────────────────────────────────────────────────────────
    PASS: 8 (1.1%) | REJECT: 727 | FAIL: 0 | BEST: BB=0.84 RSI=78 EV=+19.6
    ════════════════════════════════════════════════════════════════════════════════
    """
    
    def __init__(self, total: int, max_workers: int, update_interval: float = 0.5):
        self.total = total
        self.max_workers = max_workers
        self.completed = 0
        self.passed = 0
        self.rejected = 0
        self.failed = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
        self.best_ev = float('-inf')
        self.best_config = None
        self.last_update = 0
        self.update_interval = update_interval
        
        # Worker state tracking
        self.worker_states = {}  # worker_id -> {config, status, start_time, result}
        self.available_worker_ids = queue.Queue()
        for i in range(1, max_workers + 1):
            self.available_worker_ids.put(i)
        
        # Track which config is assigned to which worker
        self.config_to_worker = {}  # config_id -> worker_id
        
        # Display state
        self.display_lines = max_workers + 5  # Workers + header + footer
        self.initialized = False
    
    def assign_worker(self, config: 'ConfigurationSpec') -> int:
        """Assign a worker ID to a config when it starts processing."""
        try:
            worker_id = self.available_worker_ids.get_nowait()
        except queue.Empty:
            # All workers busy, reuse lowest ID (shouldn't happen with proper flow)
            worker_id = 1
        
        with self.lock:
            self.worker_states[worker_id] = {
                'config': config,
                'status': 'processing',
                'start_time': time.time(),
                'result': None
            }
            self.config_to_worker[config.config_id] = worker_id
        
        return worker_id
    
    def release_worker(self, config: 'ConfigurationSpec', result: 'ExperimentResult'):
        """Release a worker when config processing completes."""
        with self.lock:
            worker_id = self.config_to_worker.get(config.config_id)
            if worker_id:
                # Update stats
                self.completed += 1
                
                ev = result.aggregate_metrics.ev_mean if result.aggregate_metrics else 0.0
                precision = result.aggregate_metrics.precision_mean if result.aggregate_metrics else 0.0
                trades = result.aggregate_metrics.total_trades if result.aggregate_metrics else 0
                
                if result.status == "PASSED":
                    self.passed += 1
                    if ev > self.best_ev:
                        self.best_ev = ev
                        self.best_config = config
                elif result.status == "REJECTED":
                    self.rejected += 1
                else:
                    self.failed += 1
                
                # Update worker state to show completed result briefly
                self.worker_states[worker_id] = {
                    'config': config,
                    'status': result.status.lower(),
                    'start_time': time.time(),
                    'result': result,
                    'ev': ev,
                    'precision': precision,
                    'trades': trades
                }
                
                # Remove from mapping
                del self.config_to_worker[config.config_id]
                
                # Return worker to pool (will be reassigned)
                self.available_worker_ids.put(worker_id)
            
            # Update display
            now = time.time()
            if now - self.last_update >= self.update_interval or self.completed == self.total:
                self._display()
                self.last_update = now
    
    def _init_display(self):
        """Initialize display area."""
        if not self.initialized:
            # Print empty lines to create space
            print("\n" * (self.display_lines + 2))
            self.initialized = True
    
    def _move_cursor_up(self, lines: int):
        """Move cursor up N lines."""
        sys.stdout.write(f"\033[{lines}A")
    
    def _clear_line(self):
        """Clear current line."""
        sys.stdout.write("\033[2K\r")
    
    def _display(self):
        """Update the display."""
        self._init_display()
        
        elapsed = time.time() - self.start_time
        pct = 100 * self.completed / self.total if self.total > 0 else 0
        rate = self.completed / elapsed if elapsed > 0 else 0
        remaining = self.total - self.completed
        eta_seconds = remaining / rate if rate > 0 else 0
        
        # Format ETA
        if eta_seconds > 3600:
            eta_str = f"{eta_seconds/3600:.1f}h"
        elif eta_seconds > 60:
            eta_str = f"{eta_seconds/60:.1f}m"
        else:
            eta_str = f"{eta_seconds:.0f}s"
        
        # Move cursor to start of our display area
        self._move_cursor_up(self.display_lines + 1)
        
        # Line 1: Top border
        self._clear_line()
        print("=" * 90)
        
        # Line 2: Progress bar
        self._clear_line()
        bar_width = 30
        filled = int(bar_width * pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"[{bar}] {pct:5.1f}% | {self.completed:,}/{self.total:,} | ETA: {eta_str} | Rate: {rate:.1f}/min")
        
        # Line 3: Separator
        self._clear_line()
        print("-" * 90)
        
        # Worker lines
        for worker_id in range(1, self.max_workers + 1):
            self._clear_line()
            
            if worker_id in self.worker_states:
                state = self.worker_states[worker_id]
                config = state['config']
                status = state['status']
                
                # Status icon
                if status == 'processing':
                    icon = "⟳"
                    status_str = "Processing..."
                    metrics_str = ""
                elif status == 'passed':
                    icon = "✓"
                    ev = state.get('ev', 0)
                    prec = state.get('precision', 0)
                    trades = state.get('trades', 0)
                    metrics_str = f"EV={ev:+.1f} Pr={prec:.1%} T={trades}"
                    status_str = "PASSED"
                elif status == 'rejected':
                    icon = "✗"
                    ev = state.get('ev', 0)
                    prec = state.get('precision', 0)
                    trades = state.get('trades', 0)
                    metrics_str = f"EV={ev:+.1f} Pr={prec:.1%} T={trades}"
                    # Get rejection reason
                    if state.get('result') and state['result'].rejection_reasons:
                        reason = state['result'].rejection_reasons[0].split('(')[0].strip()[:20]
                        status_str = reason
                    else:
                        status_str = "REJECTED"
                else:
                    icon = "!"
                    metrics_str = ""
                    status_str = "FAILED"
                
                config_str = f"BB={config.bb_threshold:.2f} RSI={config.rsi_threshold} TP={config.tp_pips}"
                
                if metrics_str:
                    print(f"Worker {worker_id}: {icon} {config_str} | {metrics_str} | {status_str}")
                else:
                    print(f"Worker {worker_id}: {icon} {config_str} | {status_str}")
            else:
                print(f"Worker {worker_id}: - Idle")
        
        # Separator
        self._clear_line()
        print("-" * 90)
        
        # Summary line
        self._clear_line()
        pass_rate = 100 * self.passed / self.completed if self.completed > 0 else 0
        summary = f"PASS: {self.passed} ({pass_rate:.1f}%) | REJECT: {self.rejected} | FAIL: {self.failed}"
        
        if self.best_config and self.best_ev > float('-inf'):
            summary += f" | BEST: BB={self.best_config.bb_threshold:.2f} RSI={self.best_config.rsi_threshold} EV={self.best_ev:+.1f}"
        
        print(summary)
        
        # Bottom border
        self._clear_line()
        print("=" * 90)
        
        sys.stdout.flush()
    
    def finish(self):
        """Final display after completion."""
        # Move past display area
        print("\n" * 2)
        
        elapsed = time.time() - self.start_time
        elapsed_str = f"{elapsed/3600:.1f}h" if elapsed > 3600 else f"{elapsed/60:.1f}m"
        rate = self.completed / elapsed if elapsed > 0 else 0
        
        print()
        print("=" * 70)
        print(" TRAINING COMPLETE")
        print("=" * 70)
        print(f"  Time:       {elapsed_str} ({rate:.1f} configs/min)")
        print(f"  Completed:  {self.completed:,}")
        print(f"  Passed:     {self.passed:,} ({100*self.passed/max(self.completed,1):.1f}%)")
        print(f"  Rejected:   {self.rejected:,}")
        print(f"  Failed:     {self.failed:,}")
        
        if self.best_config and self.best_ev > float('-inf'):
            print()
            print(f"  {'─'*66}")
            print(f"  BEST CONFIG:")
            print(f"    BB={self.best_config.bb_threshold:.2f}, RSI={self.best_config.rsi_threshold}, TP={self.best_config.tp_pips}, SL={self.best_config.sl_pips}")
            print(f"    EV={self.best_ev:+.2f} pips")
        
        print("=" * 70)
        print()


# Legacy ProgressDisplay for backward compatibility
class ProgressDisplay:
    """Simple progress display (legacy)."""
    
    def __init__(self, total: int, update_interval: float = 1.0):
        self.total = total
        self.completed = 0
        self.passed = 0
        self.rejected = 0
        self.failed = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
        self.best_ev = float('-inf')
        self.best_config = ""
        self.last_update = 0
        self.update_interval = update_interval
    
    def update(self, config_str: str, status: str, ev: float = 0.0):
        with self.lock:
            self.completed += 1
            
            if status == "PASSED":
                self.passed += 1
                if ev > self.best_ev:
                    self.best_ev = ev
                    self.best_config = config_str
            elif status == "REJECTED":
                self.rejected += 1
            else:
                self.failed += 1
            
            now = time.time()
            if now - self.last_update >= self.update_interval or self.completed == self.total:
                self._display()
                self.last_update = now
    
    def _display(self):
        elapsed = time.time() - self.start_time
        pct = 100 * self.completed / self.total
        rate = self.completed / elapsed if elapsed > 0 else 0
        remaining = self.total - self.completed
        eta_seconds = remaining / rate if rate > 0 else 0
        
        if eta_seconds > 3600:
            eta_str = f"{eta_seconds/3600:.1f}h"
        elif eta_seconds > 60:
            eta_str = f"{eta_seconds/60:.1f}m"
        else:
            eta_str = f"{eta_seconds:.0f}s"
        
        best_str = ""
        if self.best_ev > float('-inf'):
            best_str = f" | Best: EV={self.best_ev:+.1f}"
        
        line = (
            f"\r[{self.completed:,}/{self.total:,}] {pct:5.1f}% | "
            f"PASS:{self.passed} REJECT:{self.rejected} | "
            f"ETA: {eta_str}{best_str}"
        )
        
        sys.stdout.write(line.ljust(100))
        sys.stdout.flush()
    
    def finish(self):
        elapsed = time.time() - self.start_time
        print()
        print(f"\n{'='*60}")
        print(f"EXPERIMENTS COMPLETE")
        print(f"{'='*60}")
        print(f"Time:       {elapsed/60:.1f} minutes")
        print(f"Completed:  {self.completed:,}")
        print(f"Passed:     {self.passed:,}")
        print(f"Rejected:   {self.rejected:,}")
        if self.best_ev > float('-inf'):
            print(f"\nBest EV:  {self.best_ev:+.2f} ({self.best_config})")
        print(f"{'='*60}\n")


# =============================================================================
# CONFIGURATION GENERATION
# =============================================================================

def generate_config_space_from_settings(settings: Dict[str, Any]) -> List[ConfigurationSpec]:
    """Generate configuration space from settings."""
    cs = settings.get('config_space', {})
    
    bb = cs.get('bb_threshold', {'min': 0.85, 'max': 0.95, 'step': 0.01})
    rsi = cs.get('rsi_threshold', {'min': 50, 'max': 95, 'step': 1})
    tp = cs.get('tp_pips', {'min': 40, 'max': 120, 'step': 10})
    sl_pips = cs.get('sl_pips', 40)
    holding = cs.get('max_holding_bars', {'min': 18, 'max': 40, 'step': 6})
    
    configs = []
    config_num = 0
    
    bb_values = np.arange(bb['min'], bb['max'] + bb['step']/2, bb['step'])
    
    for bb_val in bb_values:
        for rsi_val in range(rsi['min'], rsi['max'] + 1, rsi['step']):
            for tp_val in range(tp['min'], tp['max'] + 1, tp['step']):
                for hold_val in range(holding['min'], holding['max'] + 1, holding['step']):
                    config_num += 1
                    configs.append(ConfigurationSpec(
                        config_id=f"CFG_{config_num:05d}",
                        bb_threshold=round(float(bb_val), 2),
                        rsi_threshold=int(rsi_val),
                        tp_pips=int(tp_val),
                        sl_pips=sl_pips,
                        max_holding_bars=int(hold_val)
                    ))
    
    return configs


def get_unique_label_params(configs: List[ConfigurationSpec]) -> List[Tuple[int, int, int]]:
    """Get unique (TP, SL, Holding) combinations."""
    unique = set()
    for c in configs:
        unique.add((c.tp_pips, c.sl_pips, c.max_holding_bars))
    return list(unique)


def get_unique_signal_params(configs: List[ConfigurationSpec]) -> List[Tuple[float, int]]:
    """Get unique (BB, RSI) combinations."""
    unique = set()
    for c in configs:
        unique.add((c.bb_threshold, c.rsi_threshold))
    return list(unique)


# =============================================================================
# PRE-COMPUTATION PHASE
# =============================================================================

def precompute_labels_and_signals(
    df: pd.DataFrame,
    configs: List[ConfigurationSpec],
    pip_value: float = 0.0001,
    verbose: bool = True
) -> Tuple[LabelCache, SignalCache]:
    """
    Pre-compute ALL labels and signals for the entire config space.
    
    This is run ONCE before processing any configs.
    
    Args:
        df: Base DataFrame with OHLC and indicators
        configs: List of all configurations
        pip_value: Pip value for instrument
        verbose: Print progress
        
    Returns:
        Tuple of (LabelCache, SignalCache)
    """
    if verbose:
        print("\n" + "="*60)
        print("PRE-COMPUTATION PHASE")
        print("="*60)
    
    # Get unique parameters
    label_params = get_unique_label_params(configs)
    signal_params = get_unique_signal_params(configs)
    
    if verbose:
        print(f"Unique label configs:  {len(label_params)} (TP x Holding)")
        print(f"Unique signal configs: {len(signal_params)} (BB x RSI)")
        print(f"Total configs:         {len(configs):,}")
        print(f"Reduction factor:      {len(configs) / (len(label_params) + len(signal_params)):.1f}x")
    
    # Extract unique values
    tp_values = sorted(set(p[0] for p in label_params))
    sl_pips = label_params[0][1]  # Assuming fixed SL
    holding_values = sorted(set(p[2] for p in label_params))
    bb_values = sorted(set(p[0] for p in signal_params))
    rsi_values = sorted(set(p[1] for p in signal_params))
    
    # Pre-compute labels
    start_time = time.time()
    label_cache = precompute_all_labels(
        df=df,
        tp_values=tp_values,
        sl_pips=sl_pips,
        holding_values=holding_values,
        pip_value=pip_value,
        direction=TradeDirection.SHORT,
        verbose=verbose
    )
    label_time = time.time() - start_time
    
    # Pre-compute signals
    start_time = time.time()
    signal_cache = precompute_all_signals(
        df=df,
        bb_values=bb_values,
        rsi_values=rsi_values,
        direction=TradeDirection.SHORT,
        verbose=verbose
    )
    signal_time = time.time() - start_time
    
    if verbose:
        print(f"\n[TIME] Label pre-computation:  {label_time:.1f}s")
        print(f"[TIME] Signal pre-computation: {signal_time:.1f}s")
        print(f"[TIME] Total pre-computation:  {label_time + signal_time:.1f}s")
        print("="*60 + "\n")
    
    return label_cache, signal_cache


# =============================================================================
# CHECKPOINT HELPER (STORES ALL DETAILS)
# =============================================================================

def save_checkpoint_with_details(
    checkpoint_mgr,
    config: ConfigurationSpec,
    result: 'ExperimentResult'
) -> None:
    """Save checkpoint with ALL important details."""
    if not checkpoint_mgr:
        return
    
    # Extract metrics
    metrics = result.aggregate_metrics
    
    checkpoint_mgr.mark_completed(
        config_id=config.config_id,
        status=result.status,
        # Config parameters
        bb_threshold=config.bb_threshold,
        rsi_threshold=config.rsi_threshold,
        tp_pips=config.tp_pips,
        sl_pips=config.sl_pips,
        max_holding_bars=config.max_holding_bars,
        # Metrics
        ev_mean=metrics.ev_mean if metrics else None,
        ev_std=metrics.ev_std if metrics else None,
        precision_mean=metrics.precision_mean if metrics else None,
        precision_std=metrics.precision_std if metrics else None,
        recall_mean=metrics.recall_mean if metrics else None,
        f1_mean=metrics.f1_mean if metrics else None,
        auc_pr_mean=metrics.auc_pr_mean if metrics else None,
        total_trades=metrics.total_trades if metrics else None,
        # Model details
        selected_features=result.consensus_features if result.consensus_features else None,
        consensus_threshold=result.consensus_threshold,
        # Metadata
        rejection_reasons=result.rejection_reasons if result.rejection_reasons else None,
        execution_time=result.execution_time_seconds
    )


# =============================================================================
# SINGLE FOLD PROCESSING
# =============================================================================

def process_single_fold(
    df_filtered: pd.DataFrame,
    fold_boundary: FoldBoundary,
    feature_columns: List[str],
    config: ConfigurationSpec,
    settings: Dict[str, Any]
) -> Optional[FoldResult]:
    """
    Process a single fold for a configuration.
    
    This is the unit of work for fold-level parallelism.
    """
    try:
        # Apply split
        fold_data = apply_split_to_filtered(
            df_filtered=df_filtered,
            boundary=fold_boundary,
            timestamp_column='timestamp'
        )
        
        # Validate
        accept_settings = settings.get('acceptance_criteria', {})
        validation = validate_fold_data(
            fold_data=fold_data,
            min_train_rows=50,
            min_calibration_rows=20,
            min_threshold_rows=accept_settings.get('min_trades_per_fold', 30)
        )
        
        if not validation['is_valid']:
            return None
        
        # Get settings
        rfe_settings = settings.get('rfe', {})
        hp_settings = settings.get('hyperparameters', {})
        
        # RFE
        rfe_result = rfe_select(
            X_train=fold_data.train_df,
            y_train=fold_data.train_df['label'],
            feature_columns=feature_columns,
            min_features=rfe_settings.get('min_features', 5),
            max_features=rfe_settings.get('max_features', 15),
            cv_folds=rfe_settings.get('cv_folds', 3)
        )
        
        if len(rfe_result.selected_features) == 0:
            return None
        
        # Hyperparameter tuning (uses LightGBM if available)
        hp_result = tune_hyperparameters(
            X_train=fold_data.train_df,
            y_train=fold_data.train_df['label'],
            feature_columns=rfe_result.selected_features,
            model_type=get_best_model_type(),
            cv_folds=hp_settings.get('cv_folds', 3),
            random_state=42,
            use_randomized=hp_settings.get('use_randomized', True),
            n_iter=hp_settings.get('n_iter', 20)
        )
        
        # Train model
        trained_model = train_model(
            X_train=fold_data.train_df,
            y_train=fold_data.train_df['label'],
            feature_columns=rfe_result.selected_features,
            hyperparameters=hp_result.best_params,
            model_type=get_best_model_type(),
            random_state=42
        )
        
        # Calibrate
        calibrated_model, cal_result = calibrate_model(
            trained_model=trained_model,
            X_cal=fold_data.calibration_df,
            y_cal=fold_data.calibration_df['label'],
            method='sigmoid'
        )
        
        # Threshold optimization
        X_thresh = fold_data.threshold_df[rfe_result.selected_features].copy()
        X_thresh = X_thresh.replace([np.inf, -np.inf], np.nan).fillna(X_thresh.mean())
        y_proba = calibrated_model.model.predict_proba(X_thresh)[:, 1]
        
        thresh_result = optimize_threshold(
            y_true=fold_data.threshold_df['label'].values,
            y_proba=y_proba,
            tp_pips=config.tp_pips,
            sl_pips=config.sl_pips,
            min_trades=accept_settings.get('min_trades_per_fold', 30)
        )
        
        # Metrics
        y_pred = (y_proba >= thresh_result.optimal_threshold).astype(int)
        metrics = compute_metrics(
            y_true=fold_data.threshold_df['label'].values,
            y_pred=y_pred,
            y_proba=y_proba,
            tp_pips=config.tp_pips,
            sl_pips=config.sl_pips,
            threshold=thresh_result.optimal_threshold
        )
        
        return FoldResult(
            fold_number=fold_boundary.fold_number,
            train_size=len(fold_data.train_df),
            calibration_size=len(fold_data.calibration_df),
            threshold_size=len(fold_data.threshold_df),
            rfe_result=rfe_result,
            hyperparameter_result=hp_result,
            calibration_result=cal_result,
            threshold_result=thresh_result,
            metrics=metrics,
            regime_breakdown={}
        )
    
    except Exception as e:
        return None


# =============================================================================
# SINGLE CONFIG PROCESSING (WITH PRE-COMPUTED DATA)
# =============================================================================

def process_single_config(
    df: pd.DataFrame,
    config: ConfigurationSpec,
    fold_boundaries: List[FoldBoundary],
    feature_columns: List[str],
    settings: Dict[str, Any],
    pip_value: float,
    label_cache: LabelCache,
    signal_cache: SignalCache
) -> ExperimentResult:
    """
    Process a single configuration using pre-computed labels and signals.
    
    This is MUCH faster than computing labels/signals per config.
    """
    start_time = time.time()
    
    try:
        # FAST: Apply pre-computed labels and signals
        df_filtered, label_stats, signal_stats = apply_precomputed_labels_and_signals(
            df=df,
            label_cache=label_cache,
            signal_cache=signal_cache,
            tp_pips=config.tp_pips,
            sl_pips=config.sl_pips,
            max_holding_bars=config.max_holding_bars,
            bb_threshold=config.bb_threshold,
            rsi_threshold=config.rsi_threshold
        )
        
        if len(df_filtered) < 100:
            return ExperimentResult(
                config=config,
                status="REJECTED",
                rejection_reasons=["insufficient_data_after_filter"],
                label_stats=label_stats,
                signal_stats=signal_stats,
                fold_results=[],
                aggregate_metrics=None,
                consensus_features=[],
                consensus_hyperparameters={},
                consensus_threshold=0.5,
                aggregate_regime_breakdown=None,
                execution_time_seconds=time.time() - start_time
            )
        
        # Process folds
        fold_results = []
        
        for boundary in fold_boundaries:
            fold_result = process_single_fold(
                df_filtered=df_filtered,
                fold_boundary=boundary,
                feature_columns=feature_columns,
                config=config,
                settings=settings
            )
            if fold_result is not None:
                fold_results.append(fold_result)
        
        if len(fold_results) == 0:
            return ExperimentResult(
                config=config,
                status="REJECTED",
                rejection_reasons=["no_valid_folds"],
                label_stats=label_stats,
                signal_stats=signal_stats,
                fold_results=[],
                aggregate_metrics=None,
                consensus_features=[],
                consensus_hyperparameters={},
                consensus_threshold=0.5,
                aggregate_regime_breakdown=None,
                execution_time_seconds=time.time() - start_time
            )
        
        # Aggregate
        fold_metrics_list = [fr.metrics for fr in fold_results]
        aggregate_metrics = aggregate_fold_metrics(fold_metrics_list)
        
        rfe_results = [fr.rfe_result for fr in fold_results]
        consensus_features = get_consensus_features(rfe_results, min_fold_frequency=0.8)
        
        hp_results = [fr.hyperparameter_result for fr in fold_results]
        consensus_hyperparameters = get_consensus_hyperparameters(hp_results, method='best_score')
        
        threshold_results = [fr.threshold_result for fr in fold_results]
        consensus_threshold = get_consensus_threshold(threshold_results, method='median')
        
        # Check acceptance
        accept_settings = settings.get('acceptance_criteria', {})
        passed, rejection_reasons = check_acceptance_criteria(
            aggregate_metrics=aggregate_metrics,
            min_precision=accept_settings.get('min_precision', 0.55),
            min_trades_per_fold=accept_settings.get('min_trades_per_fold', 30),
            min_expected_value=accept_settings.get('min_expected_value', 0.0)
        )
        
        return ExperimentResult(
            config=config,
            status="PASSED" if passed else "REJECTED",
            rejection_reasons=rejection_reasons,
            label_stats=label_stats,
            signal_stats=signal_stats,
            fold_results=fold_results,
            aggregate_metrics=aggregate_metrics,
            consensus_features=consensus_features,
            consensus_hyperparameters=consensus_hyperparameters,
            consensus_threshold=consensus_threshold,
            aggregate_regime_breakdown=None,
            execution_time_seconds=time.time() - start_time
        )
    
    except Exception as e:
        return ExperimentResult(
            config=config,
            status="FAILED",
            rejection_reasons=["exception"],
            label_stats=None,
            signal_stats=None,
            fold_results=[],
            aggregate_metrics=None,
            consensus_features=[],
            consensus_hyperparameters={},
            consensus_threshold=0.5,
            aggregate_regime_breakdown=None,
            execution_time_seconds=time.time() - start_time,
            error_message=str(e),
            error_traceback=traceback.format_exc()
        )


# =============================================================================
# PARALLEL EXECUTION WITH PRE-COMPUTATION
# =============================================================================

def run_parallel_experiments(
    df: pd.DataFrame,
    configs: List[ConfigurationSpec],
    fold_boundaries: List[FoldBoundary],
    feature_columns: List[str],
    settings: Dict[str, Any],
    max_workers: int = 8,
    pip_value: float = 0.0001,
    progress_callback: Optional[Callable] = None,
    progress_interval: int = 100,
    show_progress: bool = True,
    checkpoint_db: Optional[str] = None,
    resume: bool = False
) -> List[ExperimentResult]:
    """
    Run experiments in parallel with pre-computed labels and signals.
    
    Optimizations:
    1. Pre-compute labels/signals ONCE
    2. Use ThreadPoolExecutor (GIL released during sklearn/lightgbm)
    3. Process configs in parallel
    4. Live worker status display
    """
    
    # =========================================================================
    # PHASE 0: CHECKPOINT HANDLING
    # =========================================================================
    checkpoint_mgr = None
    if checkpoint_db:
        checkpoint_mgr = FastCheckpointManager(checkpoint_db)
        if resume:
            configs = checkpoint_mgr.get_pending_configs(configs)
            print(f"Resuming: {len(configs)} configs remaining")
    
    if len(configs) == 0:
        print("All configs already completed!")
        return []
    
    # =========================================================================
    # PHASE 1: PRE-COMPUTE LABELS AND SIGNALS
    # =========================================================================
    label_cache, signal_cache = precompute_labels_and_signals(
        df=df,
        configs=configs,
        pip_value=pip_value,
        verbose=show_progress
    )
    
    # =========================================================================
    # PHASE 2: RUN EXPERIMENTS IN PARALLEL
    # =========================================================================
    results = []
    
    print(f"\n{'='*60}")
    print(f"RUNNING {len(configs):,} CONFIGURATIONS")
    print(f"{'='*60}")
    print(f"Workers:     {max_workers}")
    print(f"Model type:  {get_best_model_type()}")
    print(f"{'='*60}\n")
    
    # Use WorkerProgressDisplay for detailed worker tracking
    progress_display = WorkerProgressDisplay(len(configs), max_workers) if show_progress else None
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        
        # Use ThreadPoolExecutor - sklearn/lightgbm release the GIL
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks and track futures
            future_to_config = {}
            
            for config in configs:
                # Assign worker before submitting
                if progress_display:
                    progress_display.assign_worker(config)
                
                future = executor.submit(
                    process_single_config,
                    df=df,
                    config=config,
                    fold_boundaries=fold_boundaries,
                    feature_columns=feature_columns,
                    settings=settings,
                    pip_value=pip_value,
                    label_cache=label_cache,
                    signal_cache=signal_cache
                )
                future_to_config[future] = config
            
            # Process completed futures
            for future in as_completed(future_to_config):
                config = future_to_config[future]
                
                try:
                    result = future.result(timeout=600)
                except Exception as e:
                    result = ExperimentResult(
                        config=config,
                        status="FAILED",
                        rejection_reasons=["executor_error"],
                        label_stats=None,
                        signal_stats=None,
                        fold_results=[],
                        aggregate_metrics=None,
                        consensus_features=[],
                        consensus_hyperparameters={},
                        consensus_threshold=0.5,
                        aggregate_regime_breakdown=None,
                        execution_time_seconds=0,
                        error_message=str(e)
                    )
                
                results.append(result)
                
                # Checkpoint with full details
                save_checkpoint_with_details(checkpoint_mgr, config, result)
                
                # Update progress display
                if progress_display:
                    progress_display.release_worker(config, result)
    
    if progress_display:
        progress_display.finish()
    
    return results


def run_sequential_experiments(
    df: pd.DataFrame,
    configs: List[ConfigurationSpec],
    fold_boundaries: List[FoldBoundary],
    feature_columns: List[str],
    settings: Dict[str, Any],
    pip_value: float = 0.0001,
    show_progress: bool = True,
    checkpoint_db: Optional[str] = None
) -> List[ExperimentResult]:
    """
    Run experiments sequentially (for debugging).
    """
    # Checkpoint handling
    checkpoint_mgr = None
    if checkpoint_db:
        checkpoint_mgr = FastCheckpointManager(checkpoint_db)
        configs = checkpoint_mgr.get_pending_configs(configs)
    
    if len(configs) == 0:
        return []
    
    # Pre-compute
    label_cache, signal_cache = precompute_labels_and_signals(
        df=df,
        configs=configs,
        pip_value=pip_value,
        verbose=show_progress
    )
    
    results = []
    progress_display = ProgressDisplay(len(configs)) if show_progress else None
    
    for config in configs:
        result = process_single_config(
            df=df,
            config=config,
            fold_boundaries=fold_boundaries,
            feature_columns=feature_columns,
            settings=settings,
            pip_value=pip_value,
            label_cache=label_cache,
            signal_cache=signal_cache
        )
        
        results.append(result)
        
        # Checkpoint with full details
        save_checkpoint_with_details(checkpoint_mgr, config, result)
        
        if progress_display:
            ev = result.aggregate_metrics.ev_mean if result.aggregate_metrics else 0.0
            progress_display.update(config.short_str(), result.status, ev)
    
    if progress_display:
        progress_display.finish()
    
    return results


# =============================================================================
# RESULT UTILITIES
# =============================================================================

def filter_passed_results(results: List[ExperimentResult]) -> List[ExperimentResult]:
    """Filter to only passed experiments."""
    return [r for r in results if r.status == "PASSED"]


def sort_results_by_ev(results: List[ExperimentResult]) -> List[ExperimentResult]:
    """Sort by expected value (descending)."""
    return sorted(
        results,
        key=lambda r: r.aggregate_metrics.ev_mean if r.aggregate_metrics else float('-inf'),
        reverse=True
    )


def sort_results_by_ranking(results: List[ExperimentResult]) -> List[ExperimentResult]:
    """Sort by ranking criteria: EV ?+' F1 ?+' Precision ?+' AUC-PR."""
    def ranking_key(r: ExperimentResult) -> Tuple:
        if r.aggregate_metrics is None:
            return (float('-inf'),) * 4
        m = r.aggregate_metrics
        return (m.ev_mean, m.f1_mean, m.precision_mean, m.auc_pr_mean)
    
    return sorted(results, key=ranking_key, reverse=True)


def get_rejection_summary(results: List[ExperimentResult]) -> Dict[str, int]:
    """Get summary of rejection reasons."""
    summary = {}
    for result in results:
        if result.status == "REJECTED":
            for reason in result.rejection_reasons:
                clean = reason.split('(')[0].strip()
                summary[clean] = summary.get(clean, 0) + 1
    return summary


def summarize_experiments(results: List[ExperimentResult]) -> Dict[str, Any]:
    """Generate summary of all experiments."""
    total = len(results)
    passed = len([r for r in results if r.status == "PASSED"])
    rejected = len([r for r in results if r.status == "REJECTED"])
    failed = len([r for r in results if r.status == "FAILED"])
    
    best_result = None
    if passed > 0:
        sorted_results = sort_results_by_ranking(filter_passed_results(results))
        best_result = sorted_results[0] if sorted_results else None
    
    return {
        'total': total,
        'passed': passed,
        'rejected': rejected,
        'failed': failed,
        'passed_pct': 100 * passed / total if total > 0 else 0,
        'rejection_summary': get_rejection_summary(results),
        'best_config': best_result.config.to_dict() if best_result else None,
        'best_ev': best_result.aggregate_metrics.ev_mean if best_result and best_result.aggregate_metrics else None
    }
