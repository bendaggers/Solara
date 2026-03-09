"""
Pure ML Pipeline - Source Module

This module provides a Pure ML approach to SHORT entry prediction:
- NO pre-filtering by BB/RSI thresholds
- Evaluates EVERY candle as a potential entry
- Model learns what conditions predict profitable shorts

Reuses components from the v3 Signal Filter pipeline where appropriate.
"""

from .pure_ml_labels import (
    generate_labels,
    filter_valid_labels,
    precompute_all_labels,
    apply_precomputed_labels,
    get_unique_label_configs,
    estimate_class_imbalance,
    LabelStats,
    LabelCache,
    TradeDirection
)

from .experiment import (
    ConfigurationSpec,
    FoldResult,
    AggregateMetrics,
    ExperimentResult,
    ExperimentProgress,
    generate_config_space,
    process_fold,
    run_experiment,
    run_all_experiments,
    filter_passed_results,
    sort_results_by_ranking,
    select_best_result
)

__all__ = [
    # Labels
    'generate_labels',
    'filter_valid_labels',
    'precompute_all_labels',
    'apply_precomputed_labels',
    'get_unique_label_configs',
    'estimate_class_imbalance',
    'LabelStats',
    'LabelCache',
    'TradeDirection',
    
    # Experiments
    'ConfigurationSpec',
    'FoldResult',
    'AggregateMetrics',
    'ExperimentResult',
    'ExperimentProgress',
    'generate_config_space',
    'process_fold',
    'run_experiment',
    'run_all_experiments',
    'filter_passed_results',
    'sort_results_by_ranking',
    'select_best_result'
]
