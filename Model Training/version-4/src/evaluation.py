"""
Evaluation module - Standalone implementation.

This module handles:
1. Computing classification metrics
2. Computing trading metrics (Expected Value)
3. Threshold optimization
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import warnings

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    average_precision_score,
    roc_auc_score
)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MetricsBundle:
    """Complete metrics for a model evaluation."""
    precision: float
    recall: float
    f1_score: float
    auc_pr: float
    roc_auc: Optional[float]
    expected_value: float
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    threshold: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'auc_pr': self.auc_pr,
            'roc_auc': self.roc_auc,
            'expected_value': self.expected_value,
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'win_rate': self.win_rate,
            'threshold': self.threshold
        }


@dataclass
class ThresholdResult:
    """Result of threshold optimization."""
    optimal_threshold: float
    expected_value: float
    precision: float
    recall: float
    f1_score: float
    trade_count: int
    win_count: int
    loss_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'optimal_threshold': self.optimal_threshold,
            'expected_value': self.expected_value,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'loss_count': self.loss_count
        }


@dataclass
class RegimeMetrics:
    """Metrics broken down by regime."""
    regime: str
    precision: float
    recall: float
    expected_value: float
    trade_count: int
    win_count: int
    loss_count: int
    pct_of_total: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'regime': self.regime,
            'precision': self.precision,
            'recall': self.recall,
            'expected_value': self.expected_value,
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'pct_of_total': self.pct_of_total
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


# =============================================================================
# METRICS COMPUTATION
# =============================================================================

def compute_expected_value(
    precision: float,
    tp_pips: float,
    sl_pips: float
) -> float:
    """
    Compute expected value per trade.
    
    EV = (win_rate * avg_win) - (loss_rate * avg_loss)
    """
    win_rate = precision
    loss_rate = 1 - precision
    
    ev = (win_rate * tp_pips) - (loss_rate * sl_pips)
    return ev


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    tp_pips: float,
    sl_pips: float,
    threshold: float
) -> MetricsBundle:
    """
    Compute all metrics for a prediction set.
    """
    # Handle edge cases
    if len(y_true) == 0 or len(y_pred) == 0:
        return MetricsBundle(
            precision=0.0, recall=0.0, f1_score=0.0,
            auc_pr=0.0, roc_auc=None,
            expected_value=0.0, trade_count=0,
            win_count=0, loss_count=0,
            win_rate=0.0, threshold=threshold
        )
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        
        # Classification metrics
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        
        # AUC metrics
        try:
            auc_pr = average_precision_score(y_true, y_proba)
        except:
            auc_pr = 0.0
        
        try:
            roc_auc = roc_auc_score(y_true, y_proba)
        except:
            roc_auc = None
    
    # Trading metrics
    trade_count = int(y_pred.sum())
    win_count = int(((y_pred == 1) & (y_true == 1)).sum())
    loss_count = int(((y_pred == 1) & (y_true == 0)).sum())
    win_rate = win_count / trade_count if trade_count > 0 else 0.0
    
    ev = compute_expected_value(prec, tp_pips, sl_pips)
    
    return MetricsBundle(
        precision=float(prec),
        recall=float(rec),
        f1_score=float(f1),
        auc_pr=float(auc_pr),
        roc_auc=float(roc_auc) if roc_auc is not None else None,
        expected_value=float(ev),
        trade_count=trade_count,
        win_count=win_count,
        loss_count=loss_count,
        win_rate=float(win_rate),
        threshold=threshold
    )


# =============================================================================
# THRESHOLD OPTIMIZATION
# =============================================================================

def optimize_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    tp_pips: float,
    sl_pips: float,
    min_threshold: float = 0.40,
    max_threshold: float = 0.80,
    step: float = 0.05,
    min_trades: int = 20
) -> ThresholdResult:
    """
    Optimize probability threshold to maximize Expected Value.
    """
    best_result = None
    best_ev = float('-inf')
    
    thresholds = np.arange(min_threshold, max_threshold + step/2, step)
    
    for threshold in thresholds:
        y_pred = (y_proba >= threshold).astype(int)
        
        trade_count = int(y_pred.sum())
        if trade_count < min_trades:
            continue
        
        win_count = int(((y_pred == 1) & (y_true == 1)).sum())
        loss_count = int(((y_pred == 1) & (y_true == 0)).sum())
        
        precision = win_count / trade_count if trade_count > 0 else 0.0
        
        ev = compute_expected_value(precision, tp_pips, sl_pips)
        
        if ev > best_ev:
            best_ev = ev
            
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore')
                rec = recall_score(y_true, y_pred, zero_division=0)
                f1 = f1_score(y_true, y_pred, zero_division=0)
            
            best_result = ThresholdResult(
                optimal_threshold=float(threshold),
                expected_value=float(ev),
                precision=float(precision),
                recall=float(rec),
                f1_score=float(f1),
                trade_count=trade_count,
                win_count=win_count,
                loss_count=loss_count
            )
    
    # Return default if no valid threshold found
    if best_result is None:
        return ThresholdResult(
            optimal_threshold=0.50,
            expected_value=0.0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            trade_count=0,
            win_count=0,
            loss_count=0
        )
    
    return best_result


# =============================================================================
# AGGREGATION
# =============================================================================

def compute_regime_breakdown(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    regime: np.ndarray,
    tp_pips: float,
    sl_pips: float
) -> Dict[str, RegimeMetrics]:
    """
    Compute metrics broken down by regime.
    """
    results = {}
    total_trades = int(y_pred.sum())
    
    for r in np.unique(regime):
        mask = regime == r
        y_true_r = y_true[mask]
        y_pred_r = y_pred[mask]
        
        trade_count = int(y_pred_r.sum())
        if trade_count == 0:
            continue
        
        win_count = int(((y_pred_r == 1) & (y_true_r == 1)).sum())
        loss_count = int(((y_pred_r == 1) & (y_true_r == 0)).sum())
        
        precision = win_count / trade_count if trade_count > 0 else 0.0
        
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore')
            rec = recall_score(y_true_r, y_pred_r, zero_division=0)
        
        ev = compute_expected_value(precision, tp_pips, sl_pips)
        
        results[str(r)] = RegimeMetrics(
            regime=str(r),
            precision=float(precision),
            recall=float(rec),
            expected_value=float(ev),
            trade_count=trade_count,
            win_count=win_count,
            loss_count=loss_count,
            pct_of_total=100.0 * trade_count / total_trades if total_trades > 0 else 0.0
        )
    
    return results


def aggregate_fold_metrics(fold_metrics: List[MetricsBundle]) -> AggregateMetrics:
    """Aggregate metrics across folds."""
    if not fold_metrics:
        return AggregateMetrics(
            precision_mean=0.0, precision_std=0.0,
            recall_mean=0.0, recall_std=0.0,
            f1_mean=0.0, f1_std=0.0,
            auc_pr_mean=0.0, auc_pr_std=0.0,
            ev_mean=0.0, ev_std=0.0,
            total_trades=0, n_folds=0
        )
    
    precisions = [m.precision for m in fold_metrics]
    recalls = [m.recall for m in fold_metrics]
    f1s = [m.f1_score for m in fold_metrics]
    auc_prs = [m.auc_pr for m in fold_metrics]
    evs = [m.expected_value for m in fold_metrics]
    total_trades = sum(m.trade_count for m in fold_metrics)
    
    return AggregateMetrics(
        precision_mean=float(np.mean(precisions)),
        precision_std=float(np.std(precisions)),
        recall_mean=float(np.mean(recalls)),
        recall_std=float(np.std(recalls)),
        f1_mean=float(np.mean(f1s)),
        f1_std=float(np.std(f1s)),
        auc_pr_mean=float(np.mean(auc_prs)),
        auc_pr_std=float(np.std(auc_prs)),
        ev_mean=float(np.mean(evs)),
        ev_std=float(np.std(evs)),
        total_trades=total_trades,
        n_folds=len(fold_metrics)
    )


def check_acceptance_criteria(
    aggregate_metrics: AggregateMetrics,
    min_precision: float = 0.55,
    min_trades_per_fold: int = 30,
    min_expected_value: float = 0.0,
    max_metric_cv: float = 0.30
) -> Tuple[bool, List[str]]:
    """Check if model meets acceptance criteria."""
    passed = True
    reasons = []
    
    if aggregate_metrics.precision_mean < min_precision:
        passed = False
        reasons.append(f"precision < {min_precision}")
    
    if aggregate_metrics.ev_mean <= min_expected_value:
        passed = False
        reasons.append(f"EV <= {min_expected_value}")
    
    avg_trades = aggregate_metrics.total_trades / max(aggregate_metrics.n_folds, 1)
    if avg_trades < min_trades_per_fold:
        passed = False
        reasons.append(f"trades_per_fold < {min_trades_per_fold}")
    
    if aggregate_metrics.precision_mean > 0:
        cv = aggregate_metrics.precision_std / aggregate_metrics.precision_mean
        if cv > max_metric_cv:
            passed = False
            reasons.append(f"precision_cv > {max_metric_cv}")
    
    return passed, reasons


def get_consensus_threshold(fold_results: List[ThresholdResult], method: str = 'median') -> float:
    """Get consensus threshold from multiple folds."""
    if not fold_results:
        return 0.5
    
    thresholds = [r.optimal_threshold for r in fold_results]
    
    if method == 'median':
        return float(np.median(thresholds))
    elif method == 'mean':
        return float(np.mean(thresholds))
    else:
        return float(np.median(thresholds))
