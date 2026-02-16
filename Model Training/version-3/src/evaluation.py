"""
Model evaluation, metrics computation, and threshold optimization.

This module handles:
1. Computing classification metrics (Precision, Recall, F1, AUC-PR)
2. Computing trading metrics (Expected Value, Win Rate)
3. Optimizing probability threshold for maximum EV
4. Breaking down metrics by regime

Critical rules:
- Threshold optimization uses THRESHOLD data only
- EV calculation uses actual TP/SL pip values
- Regime breakdown is for diagnostics only
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import warnings

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    precision_recall_curve,
    average_precision_score,
    roc_auc_score,
    confusion_matrix,
    classification_report
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
    
    # Optional additional metrics
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
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
            'threshold': self.threshold,
            'true_positives': self.true_positives,
            'false_positives': self.false_positives,
            'true_negatives': self.true_negatives,
            'false_negatives': self.false_negatives
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
    
    # All thresholds evaluated
    threshold_analysis: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
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
        """Convert to dictionary."""
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
    """Aggregated metrics across multiple folds."""
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
    
    # Per-fold data
    fold_metrics: List[MetricsBundle] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
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
# BASIC METRICS COMPUTATION
# =============================================================================

def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None
) -> Dict[str, float]:
    """
    Compute basic classification metrics.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels (binary)
        y_proba: Predicted probabilities for positive class
        
    Returns:
        Dictionary of metrics
    """
    metrics = {}
    
    # Handle edge cases
    if len(y_true) == 0 or len(y_pred) == 0:
        return {
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0,
            'auc_pr': 0.0,
            'roc_auc': None
        }
    
    # Precision, Recall, F1
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        
        metrics['precision'] = precision_score(y_true, y_pred, zero_division=0)
        metrics['recall'] = recall_score(y_true, y_pred, zero_division=0)
        metrics['f1_score'] = f1_score(y_true, y_pred, zero_division=0)
    
    # AUC-PR (requires probabilities)
    if y_proba is not None and len(np.unique(y_true)) > 1:
        try:
            metrics['auc_pr'] = average_precision_score(y_true, y_proba)
        except Exception:
            metrics['auc_pr'] = 0.0
        
        try:
            metrics['roc_auc'] = roc_auc_score(y_true, y_proba)
        except Exception:
            metrics['roc_auc'] = None
    else:
        metrics['auc_pr'] = 0.0
        metrics['roc_auc'] = None
    
    return metrics


def compute_confusion_matrix_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray
) -> Dict[str, int]:
    """
    Compute confusion matrix components.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        
    Returns:
        Dictionary with TP, FP, TN, FN
    """
    if len(y_true) == 0:
        return {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0}
    
    # Handle case where only one class is present
    try:
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
    except ValueError:
        # Only one class present
        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        tn = int(((y_true == 0) & (y_pred == 0)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
    
    return {
        'tp': int(tp),
        'fp': int(fp),
        'tn': int(tn),
        'fn': int(fn)
    }


# =============================================================================
# TRADING METRICS
# =============================================================================

def compute_expected_value(
    precision: float,
    tp_pips: float,
    sl_pips: float
) -> float:
    """
    Compute Expected Value per trade.
    
    EV = (precision × TP) - ((1 - precision) × SL)
    
    Args:
        precision: Win rate (0-1)
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        
    Returns:
        Expected value in pips
    """
    return (precision * tp_pips) - ((1 - precision) * sl_pips)


def compute_trading_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    tp_pips: float,
    sl_pips: float
) -> Dict[str, Any]:
    """
    Compute trading-specific metrics.
    
    Args:
        y_true: True labels (1=win, 0=loss)
        y_pred: Predicted labels (1=take trade, 0=skip)
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        
    Returns:
        Dictionary of trading metrics
    """
    # Trades taken = predicted positive
    trades_taken = (y_pred == 1)
    trade_count = int(trades_taken.sum())
    
    if trade_count == 0:
        return {
            'trade_count': 0,
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0.0,
            'expected_value': 0.0,
            'total_pnl': 0.0
        }
    
    # Among trades taken, count wins and losses
    wins = ((y_pred == 1) & (y_true == 1))
    losses = ((y_pred == 1) & (y_true == 0))
    
    win_count = int(wins.sum())
    loss_count = int(losses.sum())
    
    win_rate = win_count / trade_count if trade_count > 0 else 0.0
    
    # Expected value
    ev = compute_expected_value(win_rate, tp_pips, sl_pips)
    
    # Total PnL
    total_pnl = (win_count * tp_pips) - (loss_count * sl_pips)
    
    return {
        'trade_count': trade_count,
        'win_count': win_count,
        'loss_count': loss_count,
        'win_rate': win_rate,
        'expected_value': ev,
        'total_pnl': total_pnl
    }


# =============================================================================
# COMPLETE METRICS COMPUTATION
# =============================================================================

def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    tp_pips: float,
    sl_pips: float,
    threshold: float
) -> MetricsBundle:
    """
    Compute all metrics for a model evaluation.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels (binary)
        y_proba: Predicted probabilities for positive class
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        threshold: Probability threshold used for predictions
        
    Returns:
        MetricsBundle with all metrics
    """
    # Classification metrics
    clf_metrics = compute_classification_metrics(y_true, y_pred, y_proba)
    
    # Confusion matrix
    cm_metrics = compute_confusion_matrix_metrics(y_true, y_pred)
    
    # Trading metrics
    trading_metrics = compute_trading_metrics(y_true, y_pred, tp_pips, sl_pips)
    
    return MetricsBundle(
        precision=clf_metrics['precision'],
        recall=clf_metrics['recall'],
        f1_score=clf_metrics['f1_score'],
        auc_pr=clf_metrics['auc_pr'],
        roc_auc=clf_metrics.get('roc_auc'),
        expected_value=trading_metrics['expected_value'],
        trade_count=trading_metrics['trade_count'],
        win_count=trading_metrics['win_count'],
        loss_count=trading_metrics['loss_count'],
        win_rate=trading_metrics['win_rate'],
        threshold=threshold,
        true_positives=cm_metrics['tp'],
        false_positives=cm_metrics['fp'],
        true_negatives=cm_metrics['tn'],
        false_negatives=cm_metrics['fn']
    )


def compute_metrics_from_proba(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    threshold: float,
    tp_pips: float,
    sl_pips: float
) -> MetricsBundle:
    """
    Compute metrics from probabilities using given threshold.
    
    Args:
        y_true: True labels
        y_proba: Predicted probabilities
        threshold: Probability threshold
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        
    Returns:
        MetricsBundle
    """
    y_pred = (y_proba >= threshold).astype(int)
    return compute_metrics(y_true, y_pred, y_proba, tp_pips, sl_pips, threshold)


# =============================================================================
# THRESHOLD OPTIMIZATION
# =============================================================================

def optimize_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    tp_pips: float,
    sl_pips: float,
    min_threshold: float = 0.50,
    max_threshold: float = 0.90,
    step: float = 0.01,
    min_trades: int = 30,
    optimize_for: str = 'ev'
) -> ThresholdResult:
    """
    Find optimal probability threshold that maximizes Expected Value.
    
    Args:
        y_true: True labels
        y_proba: Predicted probabilities for positive class
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        min_threshold: Minimum threshold to test
        max_threshold: Maximum threshold to test
        step: Step size for threshold sweep
        min_trades: Minimum trades required for valid threshold
        optimize_for: 'ev' (expected value) or 'f1'
        
    Returns:
        ThresholdResult with optimal threshold and metrics
    """
    thresholds = np.arange(min_threshold, max_threshold + step, step)
    
    results = []
    best_result = None
    best_score = float('-inf')
    
    for thresh in thresholds:
        y_pred = (y_proba >= thresh).astype(int)
        trade_count = int(y_pred.sum())
        
        # Skip if insufficient trades
        if trade_count < min_trades:
            results.append({
                'threshold': float(thresh),
                'trade_count': trade_count,
                'precision': 0.0,
                'recall': 0.0,
                'f1_score': 0.0,
                'expected_value': float('-inf'),
                'valid': False,
                'reason': 'insufficient_trades'
            })
            continue
        
        # Compute metrics
        trading = compute_trading_metrics(y_true, y_pred, tp_pips, sl_pips)
        clf = compute_classification_metrics(y_true, y_pred, y_proba)
        
        ev = trading['expected_value']
        precision = clf['precision']
        recall = clf['recall']
        f1 = clf['f1_score']
        
        result_entry = {
            'threshold': float(thresh),
            'trade_count': trade_count,
            'win_count': trading['win_count'],
            'loss_count': trading['loss_count'],
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'expected_value': ev,
            'valid': ev > 0,
            'reason': 'valid' if ev > 0 else 'negative_ev'
        }
        results.append(result_entry)
        
        # Determine score based on optimization target
        if optimize_for == 'ev':
            score = ev
        elif optimize_for == 'f1':
            score = f1 if ev > 0 else float('-inf')
        else:
            score = ev
        
        # Update best if valid and better score
        if ev > 0 and score > best_score:
            best_score = score
            best_result = result_entry
    
    # Handle case where no valid threshold found
    if best_result is None:
        # Return the threshold with highest trade count as fallback
        if results:
            fallback = max(results, key=lambda x: x['trade_count'])
            return ThresholdResult(
                optimal_threshold=fallback['threshold'],
                expected_value=fallback['expected_value'],
                precision=fallback['precision'],
                recall=fallback['recall'],
                f1_score=fallback['f1_score'],
                trade_count=fallback['trade_count'],
                win_count=fallback.get('win_count', 0),
                loss_count=fallback.get('loss_count', 0),
                threshold_analysis=results
            )
        else:
            return ThresholdResult(
                optimal_threshold=0.5,
                expected_value=0.0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
                trade_count=0,
                win_count=0,
                loss_count=0,
                threshold_analysis=[]
            )
    
    return ThresholdResult(
        optimal_threshold=best_result['threshold'],
        expected_value=best_result['expected_value'],
        precision=best_result['precision'],
        recall=best_result['recall'],
        f1_score=best_result['f1_score'],
        trade_count=best_result['trade_count'],
        win_count=best_result['win_count'],
        loss_count=best_result['loss_count'],
        threshold_analysis=results
    )


def optimize_threshold_simple(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    tp_pips: float,
    sl_pips: float,
    min_trades: int = 30
) -> Tuple[float, float, float]:
    """
    Simple threshold optimization returning just the essentials.
    
    Args:
        y_true: True labels
        y_proba: Predicted probabilities
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        min_trades: Minimum trades required
        
    Returns:
        Tuple of (optimal_threshold, precision, expected_value)
    """
    result = optimize_threshold(
        y_true=y_true,
        y_proba=y_proba,
        tp_pips=tp_pips,
        sl_pips=sl_pips,
        min_trades=min_trades
    )
    return result.optimal_threshold, result.precision, result.expected_value


# =============================================================================
# REGIME BREAKDOWN
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
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        regime: Regime labels for each sample
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        
    Returns:
        Dictionary mapping regime name to RegimeMetrics
    """
    total_trades = int((y_pred == 1).sum())
    
    breakdown = {}
    
    for regime_name in np.unique(regime):
        mask = regime == regime_name
        
        y_true_regime = y_true[mask]
        y_pred_regime = y_pred[mask]
        
        # Trading metrics for this regime
        trades_taken = (y_pred_regime == 1)
        trade_count = int(trades_taken.sum())
        
        if trade_count == 0:
            breakdown[regime_name] = RegimeMetrics(
                regime=str(regime_name),
                precision=0.0,
                recall=0.0,
                expected_value=0.0,
                trade_count=0,
                win_count=0,
                loss_count=0,
                pct_of_total=0.0
            )
            continue
        
        wins = ((y_pred_regime == 1) & (y_true_regime == 1))
        losses = ((y_pred_regime == 1) & (y_true_regime == 0))
        
        win_count = int(wins.sum())
        loss_count = int(losses.sum())
        precision = win_count / trade_count if trade_count > 0 else 0.0
        
        # Recall for this regime
        actual_positives = (y_true_regime == 1).sum()
        recall = win_count / actual_positives if actual_positives > 0 else 0.0
        
        ev = compute_expected_value(precision, tp_pips, sl_pips)
        
        pct_of_total = (trade_count / total_trades * 100) if total_trades > 0 else 0.0
        
        breakdown[regime_name] = RegimeMetrics(
            regime=str(regime_name),
            precision=precision,
            recall=recall,
            expected_value=ev,
            trade_count=trade_count,
            win_count=win_count,
            loss_count=loss_count,
            pct_of_total=pct_of_total
        )
    
    return breakdown


def regime_breakdown_to_dict(breakdown: Dict[str, RegimeMetrics]) -> Dict[str, Dict[str, Any]]:
    """
    Convert regime breakdown to nested dictionary.
    
    Args:
        breakdown: Dictionary of RegimeMetrics
        
    Returns:
        Nested dictionary for JSON serialization
    """
    return {name: metrics.to_dict() for name, metrics in breakdown.items()}


# =============================================================================
# AGGREGATE METRICS ACROSS FOLDS
# =============================================================================

def aggregate_fold_metrics(
    fold_metrics: List[MetricsBundle]
) -> AggregateMetrics:
    """
    Aggregate metrics across multiple folds.
    
    Args:
        fold_metrics: List of MetricsBundle from each fold
        
    Returns:
        AggregateMetrics with mean and std
    """
    if not fold_metrics:
        return AggregateMetrics(
            precision_mean=0.0, precision_std=0.0,
            recall_mean=0.0, recall_std=0.0,
            f1_mean=0.0, f1_std=0.0,
            auc_pr_mean=0.0, auc_pr_std=0.0,
            ev_mean=0.0, ev_std=0.0,
            total_trades=0,
            n_folds=0,
            fold_metrics=[]
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
        n_folds=len(fold_metrics),
        fold_metrics=fold_metrics
    )


def get_consensus_threshold(
    fold_results: List[ThresholdResult],
    method: str = 'median'
) -> float:
    """
    Get consensus threshold from multiple folds.
    
    Args:
        fold_results: List of ThresholdResult from each fold
        method: 'median', 'mean', or 'best_ev'
        
    Returns:
        Consensus threshold value
    """
    if not fold_results:
        return 0.5
    
    thresholds = [r.optimal_threshold for r in fold_results]
    
    if method == 'median':
        return float(np.median(thresholds))
    elif method == 'mean':
        return float(np.mean(thresholds))
    elif method == 'best_ev':
        best = max(fold_results, key=lambda x: x.expected_value)
        return best.optimal_threshold
    else:
        return float(np.median(thresholds))


# =============================================================================
# ACCEPTANCE CRITERIA VALIDATION
# =============================================================================

def check_acceptance_criteria(
    aggregate_metrics: AggregateMetrics,
    min_precision: float = 0.55,
    min_trades_per_fold: int = 30,
    min_expected_value: float = 0.0,
    max_metric_cv: float = 0.30
) -> Tuple[bool, List[str]]:
    """
    Check if model meets minimum acceptance criteria.
    
    Args:
        aggregate_metrics: Aggregated metrics
        min_precision: Minimum required precision
        min_trades_per_fold: Minimum trades per fold
        min_expected_value: Minimum expected value
        max_metric_cv: Maximum coefficient of variation
        
    Returns:
        Tuple of (passed: bool, rejection_reasons: List[str])
    """
    passed = True
    reasons = []
    
    # Check precision
    if aggregate_metrics.precision_mean < min_precision:
        passed = False
        reasons.append(f"precision < {min_precision} ({aggregate_metrics.precision_mean:.3f})")
    
    # Check expected value
    if aggregate_metrics.ev_mean <= min_expected_value:
        passed = False
        reasons.append(f"EV <= {min_expected_value} ({aggregate_metrics.ev_mean:.3f})")
    
    # Check trades per fold
    avg_trades_per_fold = aggregate_metrics.total_trades / max(aggregate_metrics.n_folds, 1)
    if avg_trades_per_fold < min_trades_per_fold:
        passed = False
        reasons.append(f"trades_per_fold < {min_trades_per_fold} ({avg_trades_per_fold:.1f})")
    
    # Check stability (coefficient of variation)
    if aggregate_metrics.precision_mean > 0:
        precision_cv = aggregate_metrics.precision_std / aggregate_metrics.precision_mean
        if precision_cv > max_metric_cv:
            passed = False
            reasons.append(f"precision_cv > {max_metric_cv} ({precision_cv:.3f})")
    
    if aggregate_metrics.ev_mean > 0:
        ev_cv = aggregate_metrics.ev_std / aggregate_metrics.ev_mean
        if ev_cv > max_metric_cv:
            # This is a warning, not a hard failure
            reasons.append(f"warning: ev_cv > {max_metric_cv} ({ev_cv:.3f})")
    
    return passed, reasons


# =============================================================================
# EVALUATION UTILITIES
# =============================================================================

def evaluate_model(
    model,
    X: pd.DataFrame,
    y: pd.Series,
    feature_columns: List[str],
    threshold: float,
    tp_pips: float,
    sl_pips: float,
    regime: Optional[pd.Series] = None
) -> Tuple[MetricsBundle, Optional[Dict[str, RegimeMetrics]]]:
    """
    Complete model evaluation.
    
    Args:
        model: Trained model with predict_proba method
        X: Feature DataFrame
        y: True labels
        feature_columns: Feature column names
        threshold: Probability threshold
        tp_pips: Take profit in pips
        sl_pips: Stop loss in pips
        regime: Optional regime labels for breakdown
        
    Returns:
        Tuple of (MetricsBundle, optional RegimeMetrics breakdown)
    """
    # Prepare features
    X_subset = X[feature_columns].copy()
    
    # Handle NaN
    valid_mask = ~X_subset.isna().any(axis=1)
    X_clean = X_subset[valid_mask]
    y_clean = y[valid_mask].values
    
    # Handle infinite
    X_clean = X_clean.replace([np.inf, -np.inf], np.nan)
    X_clean = X_clean.fillna(X_clean.mean())
    
    # Get predictions
    y_proba = model.predict_proba(X_clean)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)
    
    # Compute main metrics
    metrics = compute_metrics(
        y_true=y_clean,
        y_pred=y_pred,
        y_proba=y_proba,
        tp_pips=tp_pips,
        sl_pips=sl_pips,
        threshold=threshold
    )
    
    # Compute regime breakdown if provided
    regime_breakdown = None
    if regime is not None:
        regime_clean = regime[valid_mask].values
        regime_breakdown = compute_regime_breakdown(
            y_true=y_clean,
            y_pred=y_pred,
            regime=regime_clean,
            tp_pips=tp_pips,
            sl_pips=sl_pips
        )
    
    return metrics, regime_breakdown


def get_classification_report(
    y_true: np.ndarray,
    y_pred: np.ndarray
) -> str:
    """
    Get sklearn classification report as string.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        
    Returns:
        Classification report string
    """
    return classification_report(
        y_true, y_pred,
        target_names=['Loss (0)', 'Win (1)'],
        zero_division=0
    )


def metrics_to_log_string(metrics: MetricsBundle) -> str:
    """
    Format metrics as log string.
    
    Args:
        metrics: MetricsBundle to format
        
    Returns:
        Formatted string
    """
    return (
        f"P={metrics.precision:.2f} | "
        f"R={metrics.recall:.2f} | "
        f"F1={metrics.f1_score:.2f} | "
        f"EV={metrics.expected_value:+.1f} | "
        f"n={metrics.trade_count}"
    )


def aggregate_to_log_string(agg: AggregateMetrics) -> str:
    """
    Format aggregate metrics as log string.
    
    Args:
        agg: AggregateMetrics to format
        
    Returns:
        Formatted string
    """
    return (
        f"P={agg.precision_mean:.2f}±{agg.precision_std:.2f} | "
        f"F1={agg.f1_mean:.2f}±{agg.f1_std:.2f} | "
        f"EV={agg.ev_mean:+.2f}±{agg.ev_std:.2f} | "
        f"Trades={agg.total_trades}"
    )
