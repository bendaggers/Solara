"""
Best model selection and final model training.

This module handles:
1. Selecting the best configuration from experiments
2. Training the final production model
3. Preparing model for deployment

Critical rules:
- Only ONE best configuration is selected
- Final model trained on ALL available training data
- Calibration on ALL available calibration data
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import warnings
from pathlib import Path

# Local imports
from .experiment import (
    ExperimentResult,
    ConfigurationSpec,
    filter_passed_results,
    sort_results_by_ranking
)
from .labels import (
    generate_labels_and_signals,
    TradeDirection
)
from .splits import (
    FoldBoundary,
    apply_split_to_filtered,
    combine_train_data,
    combine_calibration_data
)
from .features import (
    get_consensus_features,
    RFEResult
)
from .training import (
    train_model,
    calibrate_model,
    TrainedModel,
    get_consensus_hyperparameters,
    save_model,
    get_feature_importance,
    get_best_model_type
)
from .evaluation import (
    AggregateMetrics,
    RegimeMetrics
)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BestConfiguration:
    """The selected best configuration with all details."""
    config: ConfigurationSpec
    experiment_result: ExperimentResult
    
    # Aggregated metrics
    aggregate_metrics: AggregateMetrics
    
    # Consensus values from folds
    features: List[str]
    feature_importances: Dict[str, float]
    hyperparameters: Dict[str, Any]
    threshold: float
    
    # Regime breakdown
    regime_breakdown: Dict[str, Dict[str, float]]
    
    # Ranking info
    rank: int
    total_passed: int
    total_tested: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'config': self.config.to_dict(),
            'rank': self.rank,
            'total_passed': self.total_passed,
            'total_tested': self.total_tested,
            'features': self.features,
            'feature_importances': self.feature_importances,
            'hyperparameters': self.hyperparameters,
            'threshold': self.threshold,
            'metrics': self.aggregate_metrics.to_dict() if self.aggregate_metrics else None,
            'regime_breakdown': self.regime_breakdown
        }


@dataclass
class FinalModel:
    """The final production-ready model."""
    trained_model: TrainedModel
    config: ConfigurationSpec
    features: List[str]
    feature_importances: Dict[str, float]
    hyperparameters: Dict[str, Any]
    threshold: float
    
    # Training info
    total_training_rows: int
    total_calibration_rows: int
    
    # Expected performance
    expected_precision: float
    expected_ev: float
    
    # Regime info
    regime_breakdown: Dict[str, Dict[str, float]]
    regime_recommendation: str
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get probability predictions."""
        return self.trained_model.get_proba_positive(X)
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Get binary predictions using threshold."""
        proba = self.predict_proba(X)
        return (proba >= self.threshold).astype(int)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding model object)."""
        return {
            'config': self.config.to_dict(),
            'features': self.features,
            'feature_importances': self.feature_importances,
            'hyperparameters': self.hyperparameters,
            'threshold': self.threshold,
            'total_training_rows': self.total_training_rows,
            'total_calibration_rows': self.total_calibration_rows,
            'expected_precision': self.expected_precision,
            'expected_ev': self.expected_ev,
            'regime_breakdown': self.regime_breakdown,
            'regime_recommendation': self.regime_recommendation
        }


# =============================================================================
# BEST CONFIGURATION SELECTION
# =============================================================================

def select_best_config(
    results: List[ExperimentResult],
    selection_criteria: str = 'ev'
) -> Optional[BestConfiguration]:
    """
    Select the best configuration from experiment results.
    
    Ranking criteria:
    1. Primary: Expected Value (descending)
    2. Tiebreaker 1: F1 Score (descending)
    3. Tiebreaker 2: Precision (descending)
    4. Tiebreaker 3: AUC-PR (descending)
    
    Args:
        results: List of all experiment results
        selection_criteria: 'ev', 'f1', 'precision' (primary sort)
        
    Returns:
        BestConfiguration or None if no passed experiments
    """
    # Filter to passed only
    passed_results = filter_passed_results(results)
    
    if not passed_results:
        return None
    
    # Sort by ranking
    sorted_results = sort_results_by_ranking(passed_results)
    
    # Get best result
    best_result = sorted_results[0]
    
    # Extract feature importances
    feature_importances = _extract_feature_importances(best_result)
    
    return BestConfiguration(
        config=best_result.config,
        experiment_result=best_result,
        aggregate_metrics=best_result.aggregate_metrics,
        features=best_result.consensus_features,
        feature_importances=feature_importances,
        hyperparameters=best_result.consensus_hyperparameters,
        threshold=best_result.consensus_threshold,
        regime_breakdown=best_result.aggregate_regime_breakdown or {},
        rank=1,
        total_passed=len(passed_results),
        total_tested=len(results)
    )


def select_top_n_configs(
    results: List[ExperimentResult],
    n: int = 5
) -> List[BestConfiguration]:
    """
    Select top N configurations.
    
    Args:
        results: List of all experiment results
        n: Number of top configs to return
        
    Returns:
        List of top N BestConfiguration objects
    """
    passed_results = filter_passed_results(results)
    
    if not passed_results:
        return []
    
    sorted_results = sort_results_by_ranking(passed_results)
    top_n = sorted_results[:n]
    
    best_configs = []
    for rank, result in enumerate(top_n, 1):
        feature_importances = _extract_feature_importances(result)
        
        best_configs.append(BestConfiguration(
            config=result.config,
            experiment_result=result,
            aggregate_metrics=result.aggregate_metrics,
            features=result.consensus_features,
            feature_importances=feature_importances,
            hyperparameters=result.consensus_hyperparameters,
            threshold=result.consensus_threshold,
            regime_breakdown=result.aggregate_regime_breakdown or {},
            rank=rank,
            total_passed=len(passed_results),
            total_tested=len(results)
        ))
    
    return best_configs


def _extract_feature_importances(result: ExperimentResult) -> Dict[str, float]:
    """
    Extract feature importances from experiment result.
    
    Args:
        result: Experiment result
        
    Returns:
        Dictionary mapping feature name to importance
    """
    importances = {}
    
    if not result.fold_results:
        return importances
    
    # Aggregate importances across folds
    for fold_result in result.fold_results:
        for ranking in fold_result.rfe_result.feature_rankings:
            if ranking.selected:
                name = ranking.feature_name
                if name not in importances:
                    importances[name] = []
                importances[name].append(ranking.importance)
    
    # Average importances
    avg_importances = {
        name: float(np.mean(values))
        for name, values in importances.items()
    }
    
    # Normalize
    total = sum(avg_importances.values())
    if total > 0:
        avg_importances = {
            name: value / total
            for name, value in avg_importances.items()
        }
    
    # Sort by importance
    sorted_importances = dict(
        sorted(avg_importances.items(), key=lambda x: x[1], reverse=True)
    )
    
    return sorted_importances


# =============================================================================
# FINAL MODEL TRAINING
# =============================================================================

def train_final_model(
    df: pd.DataFrame,
    best_config: BestConfiguration,
    fold_boundaries: List[FoldBoundary],
    settings: Dict[str, Any],
    pip_value: float = 0.0001
) -> FinalModel:
    """
    Train the final production model using best configuration.
    
    Steps:
    1. Regenerate labels/signals with best config parameters
    2. Combine all training data from all folds
    3. Combine all calibration data from all folds
    4. Train model on combined training data
    5. Calibrate on combined calibration data
    
    Args:
        df: Base DataFrame with regime tags
        best_config: Selected best configuration
        fold_boundaries: Fold boundaries used in experiments
        settings: Settings dictionary
        pip_value: Pip value for instrument
        
    Returns:
        FinalModel ready for production
    """
    config = best_config.config
    
    # -----------------------------------------------------------------
    # STEP 1: Regenerate labels and signals
    # -----------------------------------------------------------------
    df_filtered, label_stats, signal_stats = generate_labels_and_signals(
        df=df,
        tp_pips=config.tp_pips,
        sl_pips=config.sl_pips,
        max_holding_bars=config.max_holding_bars,
        bb_threshold=config.bb_threshold,
        rsi_threshold=config.rsi_threshold,
        pip_value=pip_value,
        direction=TradeDirection.SHORT
    )
    
    # -----------------------------------------------------------------
    # STEP 2 & 3: Collect all train and calibration data
    # -----------------------------------------------------------------
    all_train_dfs = []
    all_cal_dfs = []
    
    for boundary in fold_boundaries:
        fold_data = apply_split_to_filtered(
            df_filtered=df_filtered,
            boundary=boundary,
            timestamp_column='timestamp'
        )
        
        if len(fold_data.train_df) > 0:
            all_train_dfs.append(fold_data.train_df)
        if len(fold_data.calibration_df) > 0:
            all_cal_dfs.append(fold_data.calibration_df)
    
    # Combine training data (remove duplicates by timestamp)
    combined_train = pd.concat(all_train_dfs, ignore_index=True)
    if 'timestamp' in combined_train.columns:
        combined_train = combined_train.drop_duplicates(
            subset=['timestamp']
        ).reset_index(drop=True)
    
    # Combine calibration data
    combined_cal = pd.concat(all_cal_dfs, ignore_index=True)
    if 'timestamp' in combined_cal.columns:
        combined_cal = combined_cal.drop_duplicates(
            subset=['timestamp']
        ).reset_index(drop=True)
    
    # -----------------------------------------------------------------
    # STEP 4: Train model on combined training data
    # -----------------------------------------------------------------
    features = best_config.features
    hyperparameters = best_config.hyperparameters.copy()
    
    # Use the same model type that was used during experiments
    model_type = get_best_model_type()
    
    # Filter hyperparameters based on model type
    # LightGBM params that don't work with sklearn
    lgb_only_params = {'num_leaves', 'min_child_samples', 'verbose', 'force_col_wise', 'n_jobs'}
    # sklearn params that don't work with LightGBM
    sklearn_only_params = {'min_samples_leaf', 'validation_fraction', 'n_iter_no_change'}
    
    if model_type == 'GradientBoostingClassifier':
        # Remove LightGBM-specific params
        hyperparameters = {k: v for k, v in hyperparameters.items() if k not in lgb_only_params}
        # Convert min_child_samples to min_samples_leaf if present
        if 'min_child_samples' in best_config.hyperparameters:
            hyperparameters['min_samples_leaf'] = best_config.hyperparameters['min_child_samples']
    elif model_type == 'LGBMClassifier':
        # Remove sklearn-specific params
        hyperparameters = {k: v for k, v in hyperparameters.items() if k not in sklearn_only_params}
    
    hp_settings = settings.get('hyperparameters', {})
    random_state = hp_settings.get('random_state', 42)
    
    trained_model = train_model(
        X_train=combined_train,
        y_train=combined_train['label'],
        feature_columns=features,
        hyperparameters=hyperparameters,
        model_type=model_type,
        random_state=random_state
    )
    
    # -----------------------------------------------------------------
    # STEP 5: Calibrate on combined calibration data
    # -----------------------------------------------------------------
    cal_settings = settings.get('calibration', {})
    cal_method = cal_settings.get('method', 'sigmoid')
    
    calibrated_model, cal_result = calibrate_model(
        trained_model=trained_model,
        X_cal=combined_cal,
        y_cal=combined_cal['label'],
        method=cal_method
    )
    
    # -----------------------------------------------------------------
    # Extract final feature importances from trained model
    # -----------------------------------------------------------------
    final_importances = get_feature_importance(calibrated_model)
    
    # -----------------------------------------------------------------
    # Generate regime recommendation
    # -----------------------------------------------------------------
    regime_recommendation = _generate_regime_recommendation(
        best_config.regime_breakdown
    )
    
    return FinalModel(
        trained_model=calibrated_model,
        config=config,
        features=features,
        feature_importances=final_importances,
        hyperparameters=hyperparameters,
        threshold=best_config.threshold,
        total_training_rows=len(combined_train),
        total_calibration_rows=len(combined_cal),
        expected_precision=best_config.aggregate_metrics.precision_mean,
        expected_ev=best_config.aggregate_metrics.ev_mean,
        regime_breakdown=best_config.regime_breakdown,
        regime_recommendation=regime_recommendation
    )


def _generate_regime_recommendation(
    regime_breakdown: Dict[str, Dict[str, float]]
) -> str:
    """
    Generate trading recommendation based on regime performance.
    
    Args:
        regime_breakdown: Performance metrics by regime
        
    Returns:
        Recommendation string
    """
    if not regime_breakdown:
        return "No regime data available."
    
    recommendations = []
    
    for regime, metrics in regime_breakdown.items():
        ev = metrics.get('expected_value', 0)
        pct = metrics.get('pct', 0)
        
        if ev > 1.0:
            status = "performs well"
        elif ev > 0:
            status = "marginally profitable"
        else:
            status = "underperforms"
        
        recommendations.append(f"{regime.capitalize()}: {status} (EV={ev:+.1f}, {pct:.0f}% of trades)")
    
    # Overall recommendation
    best_regime = max(regime_breakdown.items(), key=lambda x: x[1].get('expected_value', 0))
    worst_regime = min(regime_breakdown.items(), key=lambda x: x[1].get('expected_value', 0))
    
    summary = f"Model performs best in {best_regime[0]} markets. "
    
    if worst_regime[1].get('expected_value', 0) < 0:
        summary += f"Consider caution or reduced position size in {worst_regime[0]} conditions."
    
    return summary


# =============================================================================
# MODEL VALIDATION
# =============================================================================

def validate_final_model(
    final_model: FinalModel,
    min_features: int = 3,
    min_training_rows: int = 500
) -> Tuple[bool, List[str]]:
    """
    Validate final model is ready for production.
    
    Args:
        final_model: The final model to validate
        min_features: Minimum required features
        min_training_rows: Minimum training rows
        
    Returns:
        Tuple of (is_valid, issues list)
    """
    issues = []
    
    # Check features
    if len(final_model.features) < min_features:
        issues.append(f"Too few features: {len(final_model.features)} < {min_features}")
    
    # Check training size
    if final_model.total_training_rows < min_training_rows:
        issues.append(f"Insufficient training data: {final_model.total_training_rows} < {min_training_rows}")
    
    # Check calibration size
    if final_model.total_calibration_rows < 100:
        issues.append(f"Small calibration set: {final_model.total_calibration_rows}")
    
    # Check threshold range
    if not 0.3 < final_model.threshold < 0.95:
        issues.append(f"Unusual threshold: {final_model.threshold}")
    
    # Check model is calibrated
    if not final_model.trained_model.is_calibrated:
        issues.append("Model is not calibrated")
    
    # Check expected EV is positive
    if final_model.expected_ev <= 0:
        issues.append(f"Non-positive expected value: {final_model.expected_ev}")
    
    is_valid = len([i for i in issues if not i.startswith("Small")]) == 0
    
    return is_valid, issues


# =============================================================================
# COMPARISON UTILITIES
# =============================================================================

def compare_top_configs(
    top_configs: List[BestConfiguration]
) -> pd.DataFrame:
    """
    Create comparison table of top configurations.
    
    Args:
        top_configs: List of top configurations
        
    Returns:
        DataFrame with comparison
    """
    rows = []
    
    for config in top_configs:
        m = config.aggregate_metrics
        c = config.config
        
        rows.append({
            'rank': config.rank,
            'config_id': c.config_id,
            'bb_threshold': c.bb_threshold,
            'rsi_threshold': c.rsi_threshold,
            'tp_pips': c.tp_pips,
            'max_holding_bars': c.max_holding_bars,
            'precision': m.precision_mean if m else 0,
            'precision_std': m.precision_std if m else 0,
            'f1_score': m.f1_mean if m else 0,
            'expected_value': m.ev_mean if m else 0,
            'ev_std': m.ev_std if m else 0,
            'total_trades': m.total_trades if m else 0,
            'n_features': len(config.features),
            'threshold': config.threshold
        })
    
    return pd.DataFrame(rows)


def get_config_differences(
    config1: BestConfiguration,
    config2: BestConfiguration
) -> Dict[str, Any]:
    """
    Get differences between two configurations.
    
    Args:
        config1: First configuration
        config2: Second configuration
        
    Returns:
        Dictionary of differences
    """
    c1 = config1.config
    c2 = config2.config
    m1 = config1.aggregate_metrics
    m2 = config2.aggregate_metrics
    
    differences = {
        'parameters': {},
        'metrics': {},
        'features': {}
    }
    
    # Parameter differences
    if c1.bb_threshold != c2.bb_threshold:
        differences['parameters']['bb_threshold'] = (c1.bb_threshold, c2.bb_threshold)
    if c1.rsi_threshold != c2.rsi_threshold:
        differences['parameters']['rsi_threshold'] = (c1.rsi_threshold, c2.rsi_threshold)
    if c1.tp_pips != c2.tp_pips:
        differences['parameters']['tp_pips'] = (c1.tp_pips, c2.tp_pips)
    if c1.max_holding_bars != c2.max_holding_bars:
        differences['parameters']['max_holding_bars'] = (c1.max_holding_bars, c2.max_holding_bars)
    
    # Metric differences
    if m1 and m2:
        differences['metrics']['precision'] = (m1.precision_mean, m2.precision_mean)
        differences['metrics']['expected_value'] = (m1.ev_mean, m2.ev_mean)
        differences['metrics']['f1_score'] = (m1.f1_mean, m2.f1_mean)
    
    # Feature differences
    f1_set = set(config1.features)
    f2_set = set(config2.features)
    
    differences['features']['only_in_first'] = list(f1_set - f2_set)
    differences['features']['only_in_second'] = list(f2_set - f1_set)
    differences['features']['common'] = list(f1_set & f2_set)
    
    return differences


# =============================================================================
# SELECTION SUMMARY
# =============================================================================

def generate_selection_summary(
    best_config: BestConfiguration,
    final_model: FinalModel
) -> str:
    """
    Generate human-readable summary of selection.
    
    Args:
        best_config: Selected best configuration
        final_model: Trained final model
        
    Returns:
        Summary string
    """
    c = best_config.config
    m = best_config.aggregate_metrics
    
    lines = [
        "=" * 80,
        "BEST CONFIGURATION SELECTED",
        "=" * 80,
        "",
        f"Config ID: {c.config_id}",
        f"Parameters: BB={c.bb_threshold:.2f} | RSI={c.rsi_threshold} | TP={c.tp_pips} | SL={c.sl_pips} | HOLD={c.max_holding_bars}",
        "",
        f"Rank: #{best_config.rank} of {best_config.total_passed} passed ({best_config.total_tested} tested)",
        "",
        "Features ({0}):".format(len(best_config.features)),
    ]
    
    for i, (feat, imp) in enumerate(best_config.feature_importances.items(), 1):
        if i <= 10:  # Top 10
            lines.append(f"  {i}. {feat} (importance: {imp:.3f})")
    
    if len(best_config.features) > 10:
        lines.append(f"  ... and {len(best_config.features) - 10} more")
    
    lines.extend([
        "",
        "Hyperparameters:",
    ])
    
    for key, value in best_config.hyperparameters.items():
        lines.append(f"  {key}: {value}")
    
    lines.extend([
        "",
        f"Threshold: {best_config.threshold:.2f}",
        "",
        "Expected Performance:",
        f"  Precision:      {m.precision_mean:.2f} Â± {m.precision_std:.2f}",
        f"  Recall:         {m.recall_mean:.2f} Â± {m.recall_std:.2f}",
        f"  F1 Score:       {m.f1_mean:.2f} Â± {m.f1_std:.2f}",
        f"  AUC-PR:         {m.auc_pr_mean:.2f} Â± {m.auc_pr_std:.2f}",
        f"  Expected Value: {m.ev_mean:+.2f} Â± {m.ev_std:.2f} pips/trade",
        f"  Total Trades:   {m.total_trades:,}",
        "",
        "Regime Breakdown:",
    ])
    
    for regime, metrics in best_config.regime_breakdown.items():
        ev = metrics.get('expected_value', 0)
        pct = metrics.get('pct', 0)
        prec = metrics.get('precision', 0)
        status = "âœ“" if ev > 0 else "âš ï¸"
        lines.append(f"  {regime.capitalize():10} P={prec:.2f} | EV={ev:+.1f} | {pct:.0f}% {status}")
    
    lines.extend([
        "",
        "Final Model Training:",
        f"  Training rows:     {final_model.total_training_rows:,}",
        f"  Calibration rows:  {final_model.total_calibration_rows:,}",
        f"  Calibrated:        {final_model.trained_model.is_calibrated}",
        "",
        f"Recommendation: {final_model.regime_recommendation}",
        "",
        "=" * 80,
    ])
    
    return "\n".join(lines)


# =============================================================================
# PERSISTENCE
# =============================================================================

def save_best_config_info(
    best_config: BestConfiguration,
    output_dir: str
) -> Dict[str, str]:
    """
    Save best configuration information to files.
    
    Args:
        best_config: Best configuration to save
        output_dir: Output directory path
        
    Returns:
        Dictionary mapping file type to path
    """
    import json
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    saved_files = {}
    
    # Trading config
    config_path = output_path / 'trading_config.json'
    with open(config_path, 'w') as f:
        json.dump(best_config.config.to_dict(), f, indent=2)
    saved_files['trading_config'] = str(config_path)
    
    # Hyperparameters
    hp_path = output_path / 'hyperparameters.json'
    with open(hp_path, 'w') as f:
        json.dump(best_config.hyperparameters, f, indent=2)
    saved_files['hyperparameters'] = str(hp_path)
    
    # Threshold
    thresh_path = output_path / 'threshold.json'
    with open(thresh_path, 'w') as f:
        json.dump({
            'probability_threshold': best_config.threshold,
            'optimization_method': 'ev_maximization'
        }, f, indent=2)
    saved_files['threshold'] = str(thresh_path)
    
    return saved_files


def save_final_model_complete(
    final_model: FinalModel,
    output_dir: str
) -> Dict[str, str]:
    """
    Save final model and all associated files.
    
    Args:
        final_model: Final model to save
        output_dir: Output directory path
        
    Returns:
        Dictionary mapping file type to path
    """
    import json
    
    output_path = Path(output_dir)
    
    saved_files = {}
    
    # Model
    model_dir = output_path / 'model'
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / 'short_entry_model.pkl'
    save_model(final_model.trained_model, str(model_path))
    saved_files['model'] = str(model_path)
    
    # Features
    features_dir = output_path / 'features'
    features_dir.mkdir(parents=True, exist_ok=True)
    features_path = features_dir / 'selected_features.csv'
    
    features_df = pd.DataFrame([
        {
            'feature_name': name,
            'rank': i + 1,
            'importance': final_model.feature_importances.get(name, 0)
        }
        for i, name in enumerate(final_model.features)
    ])
    features_df.to_csv(features_path, index=False)
    saved_files['features'] = str(features_path)
    
    # Config files
    config_dir = output_path / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Trading config
    trading_config = {
        'config_id': final_model.config.config_id,
        'bb_threshold': final_model.config.bb_threshold,
        'rsi_threshold': final_model.config.rsi_threshold,
        'tp_pips': final_model.config.tp_pips,
        'sl_pips': final_model.config.sl_pips,
        'max_holding_bars': final_model.config.max_holding_bars,
        'direction': 'SHORT'
    }
    trading_path = config_dir / 'trading_config.json'
    with open(trading_path, 'w') as f:
        json.dump(trading_config, f, indent=2)
    saved_files['trading_config'] = str(trading_path)
    
    # Hyperparameters
    hp_path = config_dir / 'hyperparameters.json'
    with open(hp_path, 'w') as f:
        json.dump(final_model.hyperparameters, f, indent=2)
    saved_files['hyperparameters'] = str(hp_path)
    
    # Threshold
    thresh_path = config_dir / 'threshold.json'
    with open(thresh_path, 'w') as f:
        json.dump({
            'probability_threshold': final_model.threshold,
            'optimization_method': 'ev_maximization',
            'min_trades_constraint': 30
        }, f, indent=2)
    saved_files['threshold'] = str(thresh_path)
    
    # Metrics
    metrics_dir = output_path / 'metrics'
    metrics_dir.mkdir(parents=True, exist_ok=True)
    
    aggregate_metrics = {
        'precision': final_model.expected_precision,
        'expected_value': final_model.expected_ev,
        'total_training_rows': final_model.total_training_rows,
        'total_calibration_rows': final_model.total_calibration_rows
    }
    agg_path = metrics_dir / 'aggregate_metrics.json'
    with open(agg_path, 'w') as f:
        json.dump(aggregate_metrics, f, indent=2)
    saved_files['aggregate_metrics'] = str(agg_path)
    
    # Regime breakdown
    regime_path = metrics_dir / 'regime_breakdown.json'
    regime_data = {
        'breakdown': final_model.regime_breakdown,
        'recommendation': final_model.regime_recommendation
    }
    with open(regime_path, 'w') as f:
        json.dump(regime_data, f, indent=2)
    saved_files['regime_breakdown'] = str(regime_path)
    
    return saved_files