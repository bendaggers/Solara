"""
Pure ML Experiment Runner - With Parallel Processing and Live Display

Features:
- Multi-worker parallel processing
- Live terminal display showing worker status
- Progress bar with ETA
- Checkpoint saving for resumable runs
- Clean output without LightGBM spam
"""

import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed, Future
import multiprocessing as mp
import time
import warnings
from pathlib import Path
import threading
from datetime import datetime
from collections import defaultdict

# Suppress warnings
warnings.filterwarnings('ignore')
os.environ['LIGHTGBM_VERBOSITY'] = '-1'

# Local imports
try:
    from pure_ml_labels import (
        apply_precomputed_labels,
        precompute_all_labels,
        get_unique_label_configs,
        estimate_class_imbalance,
        LabelCache,
        LabelStats,
        TradeDirection
    )
    from checkpoint_db import PureMLCheckpointManager
except ImportError:
    from src.pure_ml_labels import (
        apply_precomputed_labels,
        precompute_all_labels,
        get_unique_label_configs,
        estimate_class_imbalance,
        LabelCache,
        LabelStats,
        TradeDirection
    )
    from src.checkpoint_db import PureMLCheckpointManager


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ConfigurationSpec:
    """Specification for a single configuration to test."""
    config_id: str
    tp_pips: int
    sl_pips: int
    max_holding_bars: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'config_id': self.config_id,
            'tp_pips': self.tp_pips,
            'sl_pips': self.sl_pips,
            'max_holding_bars': self.max_holding_bars
        }
    
    def short_str(self) -> str:
        return f"TP={self.tp_pips} SL={self.sl_pips} H={self.max_holding_bars}"
    
    def __hash__(self):
        return hash(self.config_id)
    
    def __eq__(self, other):
        if not isinstance(other, ConfigurationSpec):
            return False
        return self.config_id == other.config_id


@dataclass
class FoldResult:
    """Results from a single fold."""
    fold_number: int
    config_id: str
    train_rows: int
    calibration_rows: int
    threshold_rows: int
    train_win_rate: float
    selected_features: List[str]
    feature_importances: Dict[str, float]
    hyperparameters: Dict[str, Any]
    precision: float
    recall: float
    f1_score: float
    auc_pr: float
    expected_value: float
    trade_count: int
    win_count: int
    loss_count: int
    threshold: float
    training_time_seconds: float
    status: str = "success"
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'fold_number': self.fold_number,
            'config_id': self.config_id,
            'train_rows': self.train_rows,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'expected_value': self.expected_value,
            'trade_count': self.trade_count,
            'threshold': self.threshold,
            'status': self.status
        }


@dataclass
class AggregateMetrics:
    """Aggregated metrics across folds."""
    precision_mean: float
    precision_std: float
    recall_mean: float
    recall_std: float
    f1_mean: float
    f1_std: float
    auc_pr_mean: float
    auc_pr_std: float
    ev_mean: float
    ev_std: float
    total_trades: int
    n_folds: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'precision': {'mean': self.precision_mean, 'std': self.precision_std},
            'recall': {'mean': self.recall_mean, 'std': self.recall_std},
            'f1_score': {'mean': self.f1_mean, 'std': self.f1_std},
            'auc_pr': {'mean': self.auc_pr_mean, 'std': self.auc_pr_std},
            'expected_value': {'mean': self.ev_mean, 'std': self.ev_std},
            'total_trades': self.total_trades,
            'n_folds': self.n_folds
        }


@dataclass
class ExperimentResult:
    """Complete results for a configuration across all folds."""
    config: ConfigurationSpec
    fold_results: List[FoldResult]
    aggregate_metrics: Optional[AggregateMetrics]
    consensus_features: List[str]
    consensus_hyperparameters: Dict[str, Any]
    consensus_threshold: float
    passed: bool
    rejection_reasons: List[str]
    total_time_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'config': self.config.to_dict(),
            'aggregate_metrics': self.aggregate_metrics.to_dict() if self.aggregate_metrics else None,
            'passed': self.passed,
            'rejection_reasons': self.rejection_reasons,
            'total_time_seconds': self.total_time_seconds
        }


@dataclass
class WorkerStatus:
    """Status of a single worker."""
    worker_id: int
    current_config: Optional[str] = None
    start_time: Optional[float] = None
    last_config: Optional[str] = None
    last_result: Optional[str] = None  # "✓" or "✗"
    last_duration: float = 0.0


# =============================================================================
# CONFIGURATION GENERATION
# =============================================================================

def generate_config_space(settings: Dict[str, Any]) -> List[ConfigurationSpec]:
    """Generate all configurations to test."""
    config_space = settings.get('config_space', {})
    
    tp_cfg = config_space.get('tp_pips', {'min': 30, 'max': 80, 'step': 10})
    sl_cfg = config_space.get('sl_pips', 40)
    hold_cfg = config_space.get('max_holding_bars', {'min': 12, 'max': 30, 'step': 6})
    
    if isinstance(tp_cfg, dict):
        tp_values = list(range(tp_cfg['min'], tp_cfg['max'] + 1, tp_cfg['step']))
    else:
        tp_values = [tp_cfg]
    
    if isinstance(sl_cfg, dict):
        sl_values = list(range(sl_cfg['min'], sl_cfg['max'] + 1, sl_cfg['step']))
    else:
        sl_values = [sl_cfg]
    
    if isinstance(hold_cfg, dict):
        hold_values = list(range(hold_cfg['min'], hold_cfg['max'] + 1, hold_cfg['step']))
    else:
        hold_values = [hold_cfg]
    
    configs = []
    config_id = 1
    
    for tp in tp_values:
        for sl in sl_values:
            for hold in hold_values:
                spec = ConfigurationSpec(
                    config_id=f"cfg_{config_id:04d}",
                    tp_pips=tp,
                    sl_pips=sl,
                    max_holding_bars=hold
                )
                configs.append(spec)
                config_id += 1
    
    return configs


# =============================================================================
# SINGLE CONFIG PROCESSING (runs in worker process)
# =============================================================================

def process_single_config(args: Tuple) -> ExperimentResult:
    """
    Process a single configuration - runs in worker process.
    
    Args is a tuple of: (config_dict, df_bytes, label_cache_bytes, fold_boundaries, 
                         feature_columns, settings, pip_value)
    """
    import pickle
    import io
    
    # Suppress all warnings in worker
    import warnings
    import os
    warnings.filterwarnings('ignore')
    os.environ['LIGHTGBM_VERBOSITY'] = '-1'
    
    # Unpack arguments
    config_dict, df_pickle, labels_pickle, fold_boundaries, feature_columns, settings, pip_value = args
    
    # Reconstruct objects
    config = ConfigurationSpec(**config_dict)
    df = pickle.loads(df_pickle)
    label_cache = pickle.loads(labels_pickle)
    
    start_time = time.time()
    
    try:
        # Import here to avoid issues
        from features import rfe_select
        from training import tune_hyperparameters, train_model, calibrate_model, get_best_model_type
        from evaluation import compute_metrics, optimize_threshold
        
        # Apply labels
        df_labeled, label_stats = apply_precomputed_labels(
            df=df,
            label_cache=label_cache,
            tp_pips=config.tp_pips,
            sl_pips=config.sl_pips,
            max_holding_bars=config.max_holding_bars
        )
        
        fold_results = []
        
        for boundary in fold_boundaries:
            fold_start = time.time()
            fold_number = boundary['fold_number']
            
            # Split data
            train_df = df_labeled[
                (df_labeled.index >= boundary['train_start_idx']) &
                (df_labeled.index <= boundary['train_end_idx'])
            ].copy()
            
            cal_df = df_labeled[
                (df_labeled.index >= boundary['cal_start_idx']) &
                (df_labeled.index <= boundary['cal_end_idx'])
            ].copy()
            
            thresh_df = df_labeled[
                (df_labeled.index >= boundary['thresh_start_idx']) &
                (df_labeled.index <= boundary['thresh_end_idx'])
            ].copy()
            
            # Skip if insufficient data
            if len(train_df) < 100 or len(thresh_df) < 30:
                fold_results.append(FoldResult(
                    fold_number=fold_number, config_id=config.config_id,
                    train_rows=len(train_df), calibration_rows=len(cal_df),
                    threshold_rows=len(thresh_df), train_win_rate=0.0,
                    selected_features=[], feature_importances={},
                    hyperparameters={}, precision=0.0, recall=0.0,
                    f1_score=0.0, auc_pr=0.0, expected_value=0.0,
                    trade_count=0, win_count=0, loss_count=0,
                    threshold=0.5, training_time_seconds=0.0,
                    status="skipped", error_message="Insufficient data"
                ))
                continue
            
            y_train = train_df['label']
            y_cal = cal_df['label']
            y_thresh = thresh_df['label']
            
            X_train = train_df[feature_columns]
            X_cal = cal_df[feature_columns]
            X_thresh = thresh_df[feature_columns]
            
            train_win_rate = float(y_train.mean())
            
            # RFE
            rfe_settings = settings.get('rfe', {})
            if rfe_settings.get('enabled', True):
                rfe_result = rfe_select(
                    X=X_train, y=y_train, feature_columns=feature_columns,
                    min_features=rfe_settings.get('min_features', 5),
                    max_features=rfe_settings.get('max_features', 20)
                )
                selected_features = rfe_result.selected_features
            else:
                selected_features = feature_columns
            
            X_train_sel = X_train[selected_features]
            X_cal_sel = X_cal[selected_features]
            X_thresh_sel = X_thresh[selected_features]
            
            # Hyperparameter tuning
            hp_settings = settings.get('hyperparameter_tuning', {})
            if hp_settings.get('enabled', True):
                hp_result = tune_hyperparameters(
                    X_train=X_train_sel, y_train=y_train,
                    feature_columns=selected_features,
                    n_iter=hp_settings.get('n_iter', 20)
                )
                best_params = hp_result.best_params
            else:
                best_params = {}
            
            # Train
            trained_model = train_model(
                X_train=X_train_sel, y_train=y_train,
                feature_columns=selected_features,
                hyperparameters=best_params
            )
            
            # Calibrate
            cal_settings = settings.get('calibration', {})
            if cal_settings.get('enabled', True) and len(cal_df) > 20:
                calibrated_model, _ = calibrate_model(
                    trained_model=trained_model,
                    X_cal=X_cal_sel, y_cal=y_cal
                )
                model_for_eval = calibrated_model
            else:
                model_for_eval = trained_model
            
            # Threshold optimization
            thresh_settings = settings.get('threshold', {})
            y_proba = model_for_eval.get_proba_positive(X_thresh_sel)
            
            thresh_result = optimize_threshold(
                y_true=y_thresh.values, y_proba=y_proba,
                tp_pips=config.tp_pips, sl_pips=config.sl_pips,
                min_threshold=thresh_settings.get('min_threshold', 0.40),
                max_threshold=thresh_settings.get('max_threshold', 0.80)
            )
            
            # Compute metrics
            y_pred = (y_proba >= thresh_result.optimal_threshold).astype(int)
            metrics = compute_metrics(
                y_true=y_thresh.values, y_pred=y_pred, y_proba=y_proba,
                tp_pips=config.tp_pips, sl_pips=config.sl_pips,
                threshold=thresh_result.optimal_threshold
            )
            
            fold_results.append(FoldResult(
                fold_number=fold_number, config_id=config.config_id,
                train_rows=len(train_df), calibration_rows=len(cal_df),
                threshold_rows=len(thresh_df), train_win_rate=train_win_rate,
                selected_features=selected_features, feature_importances={},
                hyperparameters=best_params, precision=metrics.precision,
                recall=metrics.recall, f1_score=metrics.f1_score,
                auc_pr=metrics.auc_pr, expected_value=metrics.expected_value,
                trade_count=metrics.trade_count, win_count=metrics.win_count,
                loss_count=metrics.loss_count, threshold=thresh_result.optimal_threshold,
                training_time_seconds=time.time() - fold_start, status="success"
            ))
        
        # Aggregate
        successful = [fr for fr in fold_results if fr.status == "success"]
        
        if successful:
            agg = AggregateMetrics(
                precision_mean=float(np.mean([f.precision for f in successful])),
                precision_std=float(np.std([f.precision for f in successful])),
                recall_mean=float(np.mean([f.recall for f in successful])),
                recall_std=float(np.std([f.recall for f in successful])),
                f1_mean=float(np.mean([f.f1_score for f in successful])),
                f1_std=float(np.std([f.f1_score for f in successful])),
                auc_pr_mean=float(np.mean([f.auc_pr for f in successful])),
                auc_pr_std=float(np.std([f.auc_pr for f in successful])),
                ev_mean=float(np.mean([f.expected_value for f in successful])),
                ev_std=float(np.std([f.expected_value for f in successful])),
                total_trades=sum(f.trade_count for f in successful),
                n_folds=len(successful)
            )
            
            # Consensus
            from collections import Counter
            feat_counts = Counter()
            for f in successful:
                feat_counts.update(f.selected_features)
            consensus_features = [f for f, c in feat_counts.items() if c > len(successful)/2]
            consensus_threshold = float(np.median([f.threshold for f in successful]))
            consensus_hp = successful[0].hyperparameters if successful else {}
        else:
            agg = None
            consensus_features = []
            consensus_threshold = 0.5
            consensus_hp = {}
        
        # Check acceptance
        criteria = settings.get('acceptance_criteria', {})
        passed = True
        reasons = []
        
        if agg:
            if agg.precision_mean < criteria.get('min_precision', 0.55):
                passed = False
                reasons.append(f"precision < {criteria.get('min_precision', 0.55)}")
            if agg.ev_mean <= criteria.get('min_expected_value', 0.0):
                passed = False
                reasons.append(f"EV <= 0")
            if agg.n_folds > 0:
                avg_trades = agg.total_trades / agg.n_folds
                if avg_trades < criteria.get('min_trades_per_fold', 30):
                    passed = False
                    reasons.append(f"trades < {criteria.get('min_trades_per_fold', 30)}")
        else:
            passed = False
            reasons.append("No successful folds")
        
        return ExperimentResult(
            config=config, fold_results=fold_results,
            aggregate_metrics=agg, consensus_features=consensus_features,
            consensus_hyperparameters=consensus_hp,
            consensus_threshold=consensus_threshold,
            passed=passed, rejection_reasons=reasons,
            total_time_seconds=time.time() - start_time
        )
    
    except Exception as e:
        return ExperimentResult(
            config=config, fold_results=[],
            aggregate_metrics=None, consensus_features=[],
            consensus_hyperparameters={}, consensus_threshold=0.5,
            passed=False, rejection_reasons=[str(e)],
            total_time_seconds=time.time() - start_time
        )


# =============================================================================
# LIVE DISPLAY
# =============================================================================

def format_time(seconds: float) -> str:
    """Format seconds to human readable."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}min"
    else:
        return f"{seconds/3600:.1f}h"


def create_progress_bar(pct: float, width: int = 25) -> str:
    """Create a progress bar string."""
    filled = int(width * pct / 100)
    bar = '█' * filled + '░' * (width - filled)
    return f"[{bar}]"


def print_live_status(
    completed: int,
    total: int,
    passed: int,
    failed: int,
    worker_status: Dict[int, WorkerStatus],
    start_time: float,
    n_workers: int
):
    """Print live status display."""
    elapsed = time.time() - start_time
    pct = 100.0 * completed / total if total > 0 else 0
    
    # Calculate ETA
    if completed > 0:
        rate = completed / elapsed
        remaining = total - completed
        eta = remaining / rate if rate > 0 else 0
        avg_time = elapsed / completed
    else:
        eta = 0
        avg_time = 0
    
    # Clear screen and move cursor up
    lines_to_clear = n_workers + 4
    sys.stdout.write(f"\033[{lines_to_clear}A\033[J")
    
    # Progress bar
    bar = create_progress_bar(pct)
    print(f"{'='*80}")
    print(f"{bar} {pct:5.1f}% | {completed:,}/{total:,} | "
          f"ETA: {format_time(eta)} | Avg: {format_time(avg_time)}/cfg | "
          f"✓:{passed} ✗:{failed}")
    print(f"{'-'*80}")
    
    # Worker status
    for i in range(1, n_workers + 1):
        ws = worker_status.get(i, WorkerStatus(worker_id=i))
        
        if ws.current_config and ws.start_time:
            elapsed_w = time.time() - ws.start_time
            current = f"⟳ {ws.current_config} ({format_time(elapsed_w)})"
        else:
            current = "idle"
        
        if ws.last_config:
            last = f"{ws.last_result} {ws.last_config} ({format_time(ws.last_duration)})"
        else:
            last = "-"
        
        print(f"W{i}: {current:40} | Last: {last}")
    
    sys.stdout.flush()


# =============================================================================
# PARALLEL EXPERIMENT RUNNER
# =============================================================================

def run_parallel_experiments(
    df: pd.DataFrame,
    label_cache: LabelCache,
    configs: List[ConfigurationSpec],
    fold_boundaries: List[Dict[str, Any]],
    feature_columns: List[str],
    settings: Dict[str, Any],
    pip_value: float,
    n_workers: int = 8,
    db_path: str = "pure_ml.db"
) -> List[ExperimentResult]:
    """
    Run all experiments in parallel with live display and checkpointing.
    """
    import pickle
    
    # Initialize checkpoint manager
    checkpoint = PureMLCheckpointManager(db_path)
    
    # Filter out already completed configs
    pending_configs = checkpoint.get_pending_configs(configs)
    already_done = len(configs) - len(pending_configs)
    
    if already_done > 0:
        print(f"\n✓ Resuming: {already_done} configs already completed, {len(pending_configs)} remaining")
    
    if not pending_configs:
        print("All configurations already completed!")
        # Return results from database
        return _load_results_from_db(checkpoint, configs)
    
    # Serialize data for workers
    df_pickle = pickle.dumps(df)
    labels_pickle = pickle.dumps(label_cache)
    
    # Prepare arguments for each config
    args_list = [
        (
            config.to_dict(),
            df_pickle,
            labels_pickle,
            fold_boundaries,
            feature_columns,
            settings,
            pip_value
        )
        for config in pending_configs
    ]
    
    results = []
    completed = already_done
    passed = checkpoint.get_passed_count()
    failed = already_done - passed
    total = len(configs)
    start_time = time.time()
    
    worker_status: Dict[int, WorkerStatus] = {
        i: WorkerStatus(worker_id=i) for i in range(1, n_workers + 1)
    }
    
    # Print header
    print(f"\n{'='*80}")
    print(f"RUNNING {len(pending_configs):,} CONFIGURATIONS ({already_done} already done)")
    print(f"{'='*80}")
    print(f"Workers:     {n_workers}")
    print(f"Model type:  LGBMClassifier")
    print(f"Checkpoint:  {db_path}")
    print(f"{'='*80}")
    print(f"Starting workers...")
    print(f"{'-'*80}")
    
    # Print initial empty status lines
    for i in range(n_workers + 4):
        print()
    
    # Track which worker is processing what
    future_to_worker: Dict[Future, int] = {}
    worker_to_config: Dict[int, ConfigurationSpec] = {}
    available_workers = list(range(1, n_workers + 1))
    config_queue = list(enumerate(args_list))
    last_display_time = 0
    
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        # Submit initial batch
        while available_workers and config_queue:
            worker_id = available_workers.pop(0)
            idx, args = config_queue.pop(0)
            config = pending_configs[idx]
            
            future = executor.submit(process_single_config, args)
            future_to_worker[future] = worker_id
            worker_to_config[worker_id] = config
            
            # Update worker status
            worker_status[worker_id].current_config = config.short_str()
            worker_status[worker_id].start_time = time.time()
        
        # Print initial status
        print_live_status(completed, total, passed, failed, 
                         worker_status, start_time, n_workers)
        
        # Process completions
        while future_to_worker:
            # Wait for any future to complete
            done_futures = []
            for future in list(future_to_worker.keys()):
                if future.done():
                    done_futures.append(future)
            
            if not done_futures:
                time.sleep(0.5)
                # Update display every 5 seconds
                current_time = time.time()
                if current_time - last_display_time >= 5:
                    print_live_status(completed, total, passed, failed,
                                     worker_status, start_time, n_workers)
                    last_display_time = current_time
                continue
            
            for future in done_futures:
                worker_id = future_to_worker.pop(future)
                config = worker_to_config.pop(worker_id, None)
                
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # Save to checkpoint
                    _save_result_to_checkpoint(checkpoint, result)
                    
                    if result.passed:
                        passed += 1
                        result_symbol = "✓"
                    else:
                        failed += 1
                        result_symbol = "✗"
                    
                    # Update worker status
                    duration = time.time() - (worker_status[worker_id].start_time or time.time())
                    worker_status[worker_id].last_config = config.short_str() if config else "?"
                    worker_status[worker_id].last_result = result_symbol
                    worker_status[worker_id].last_duration = duration
                    worker_status[worker_id].current_config = None
                    worker_status[worker_id].start_time = None
                    
                except Exception as e:
                    completed += 1
                    failed += 1
                    worker_status[worker_id].last_result = "✗"
                    worker_status[worker_id].current_config = None
                
                # Submit next config if available
                if config_queue:
                    idx, args = config_queue.pop(0)
                    next_config = pending_configs[idx]
                    
                    new_future = executor.submit(process_single_config, args)
                    future_to_worker[new_future] = worker_id
                    worker_to_config[worker_id] = next_config
                    
                    worker_status[worker_id].current_config = next_config.short_str()
                    worker_status[worker_id].start_time = time.time()
                else:
                    available_workers.append(worker_id)
            
            # Update display
            print_live_status(completed, total, passed, failed,
                             worker_status, start_time, n_workers)
            last_display_time = time.time()
    
    # Final display
    print_live_status(completed, total, passed, failed,
                     worker_status, start_time, n_workers)
    
    total_time = time.time() - start_time
    print(f"\n{'='*80}")
    print(f"COMPLETED in {format_time(total_time)}")
    print(f"Passed: {passed}/{total} ({100*passed/total:.1f}%)")
    print(f"Results saved to: {db_path}")
    print(f"{'='*80}\n")
    
    return results


def _save_result_to_checkpoint(checkpoint: PureMLCheckpointManager, result: ExperimentResult):
    """Save an experiment result to the checkpoint database."""
    checkpoint.mark_completed(
        config_id=result.config.config_id,
        status='passed' if result.passed else 'failed',
        tp_pips=result.config.tp_pips,
        sl_pips=result.config.sl_pips,
        max_holding_bars=result.config.max_holding_bars,
        ev_mean=result.aggregate_metrics.ev_mean if result.aggregate_metrics else None,
        ev_std=result.aggregate_metrics.ev_std if result.aggregate_metrics else None,
        precision_mean=result.aggregate_metrics.precision_mean if result.aggregate_metrics else None,
        precision_std=result.aggregate_metrics.precision_std if result.aggregate_metrics else None,
        recall_mean=result.aggregate_metrics.recall_mean if result.aggregate_metrics else None,
        f1_mean=result.aggregate_metrics.f1_mean if result.aggregate_metrics else None,
        auc_pr_mean=result.aggregate_metrics.auc_pr_mean if result.aggregate_metrics else None,
        total_trades=result.aggregate_metrics.total_trades if result.aggregate_metrics else None,
        selected_features=result.consensus_features,
        consensus_threshold=result.consensus_threshold,
        rejection_reasons=result.rejection_reasons,
        execution_time=result.total_time_seconds
    )


def _load_results_from_db(checkpoint: PureMLCheckpointManager, configs: List[ConfigurationSpec]) -> List[ExperimentResult]:
    """Load results from checkpoint database."""
    import json
    
    results = []
    conn = checkpoint._get_conn()
    
    for config in configs:
        cursor = conn.execute("""
            SELECT status, ev_mean, ev_std, precision_mean, precision_std,
                   recall_mean, f1_mean, auc_pr_mean, total_trades,
                   selected_features, consensus_threshold, rejection_reasons
            FROM completed
            WHERE tp_pips = ? AND sl_pips = ? AND max_holding_bars = ?
        """, (config.tp_pips, config.sl_pips, config.max_holding_bars))
        
        row = cursor.fetchone()
        
        if row:
            status = row[0]
            passed = status == 'PASSED'
            
            # Parse JSON fields
            features = json.loads(row[9]) if row[9] else []
            rejection_reasons = json.loads(row[11]) if row[11] else []
            
            # Create aggregate metrics if we have data
            if row[1] is not None:  # ev_mean
                agg_metrics = AggregateMetrics(
                    precision_mean=row[3] or 0.0,
                    precision_std=row[4] or 0.0,
                    recall_mean=row[5] or 0.0,
                    recall_std=0.0,
                    f1_mean=row[6] or 0.0,
                    f1_std=0.0,
                    auc_pr_mean=row[7] or 0.0,
                    auc_pr_std=0.0,
                    ev_mean=row[1] or 0.0,
                    ev_std=row[2] or 0.0,
                    total_trades=row[8] or 0,
                    n_folds=5
                )
            else:
                agg_metrics = None
            
            results.append(ExperimentResult(
                config=config,
                fold_results=[],
                aggregate_metrics=agg_metrics,
                consensus_features=features,
                consensus_hyperparameters={},
                consensus_threshold=row[10] or 0.5,
                passed=passed,
                rejection_reasons=rejection_reasons,
                total_time_seconds=0
            ))
        else:
            # Not found in DB - should not happen
            results.append(ExperimentResult(
                config=config,
                fold_results=[],
                aggregate_metrics=None,
                consensus_features=[],
                consensus_hyperparameters={},
                consensus_threshold=0.5,
                passed=False,
                rejection_reasons=["Not found in checkpoint"],
                total_time_seconds=0
            ))
    
    return results


# =============================================================================
# SEQUENTIAL FALLBACK
# =============================================================================

def run_all_experiments(
    df: pd.DataFrame,
    label_cache: LabelCache,
    configs: List[ConfigurationSpec],
    fold_boundaries: List[Dict[str, Any]],
    feature_columns: List[str],
    settings: Dict[str, Any],
    pip_value: float,
    progress_callback: Optional[Callable] = None,
    max_workers: int = 8,
    db_path: str = "pure_ml.db"
) -> List[ExperimentResult]:
    """
    Run all experiments - uses parallel if workers > 1.
    """
    if max_workers > 1:
        return run_parallel_experiments(
            df=df,
            label_cache=label_cache,
            configs=configs,
            fold_boundaries=fold_boundaries,
            feature_columns=feature_columns,
            settings=settings,
            pip_value=pip_value,
            n_workers=max_workers,
            db_path=db_path
        )
    else:
        # Sequential fallback
        import pickle
        checkpoint = PureMLCheckpointManager(db_path)
        pending_configs = checkpoint.get_pending_configs(configs)
        
        results = []
        df_pickle = pickle.dumps(df)
        labels_pickle = pickle.dumps(label_cache)
        
        for i, config in enumerate(pending_configs):
            args = (
                config.to_dict(),
                df_pickle,
                labels_pickle,
                fold_boundaries,
                feature_columns,
                settings,
                pip_value
            )
            result = process_single_config(args)
            results.append(result)
            _save_result_to_checkpoint(checkpoint, result)
            
            if progress_callback:
                progress_callback(i + 1, len(pending_configs), result.passed)
        
        return results


# =============================================================================
# RESULT FILTERING
# =============================================================================

def filter_passed_results(results: List[ExperimentResult]) -> List[ExperimentResult]:
    return [r for r in results if r.passed]


def sort_results_by_ranking(results: List[ExperimentResult]) -> List[ExperimentResult]:
    return sorted(
        results,
        key=lambda r: (
            r.aggregate_metrics.ev_mean if r.aggregate_metrics else 0,
            r.aggregate_metrics.f1_mean if r.aggregate_metrics else 0,
            r.aggregate_metrics.precision_mean if r.aggregate_metrics else 0
        ),
        reverse=True
    )


def select_best_result(results: List[ExperimentResult]) -> Optional[ExperimentResult]:
    passed = filter_passed_results(results)
    if not passed:
        return None
    sorted_results = sort_results_by_ranking(passed)
    return sorted_results[0]
