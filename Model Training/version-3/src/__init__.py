"""
ML Training System for SHORT-only Trade Filtering.

This package provides a complete training pipeline for building
machine learning models that filter discretionary trading signals.

Modules:
    data: Data ingestion, preprocessing, regime tagging
    labels: Label generation, signal generation
    splits: Walk-forward validation splitting
    features: Feature selection (RFE)
    training: Model training, hyperparameter tuning, calibration
    evaluation: Metrics computation, threshold optimization
    experiment: Configuration experiments, parallel execution
    selection: Best model selection, final training
    artifacts: Artifact publishing, serialization
    logging_utils: Structured logging

Usage:
    python run_pipeline.py --config config/settings.yaml --input data/input.csv
"""

__version__ = '3.0.0'
__author__ = 'ML Training System'

from .data import load_and_prepare_data, get_feature_columns
from .labels import generate_labels_and_signals, TradeDirection
from .splits import define_walk_forward_splits, FoldBoundary, FoldData
from .features import rfe_select, RFEResult
from .training import train_model, calibrate_model, TrainedModel
from .evaluation import compute_metrics, optimize_threshold, MetricsBundle
from .experiment import run_parallel_experiments, ExperimentResult, ConfigurationSpec
from .selection import select_best_config, train_final_model, FinalModel
from .artifacts import publish_artifacts, load_all_artifacts, ArtifactManifest
from .checkpoint_db import FastCheckpointManager 


__all__ = [
    # Data
    'load_and_prepare_data',
    'get_feature_columns',
    
    # Labels
    'generate_labels_and_signals',
    'TradeDirection',
    
    # Splits
    'define_walk_forward_splits',
    'FoldBoundary',
    'FoldData',
    
    # Features
    'rfe_select',
    'RFEResult',
    
    # Training
    'train_model',
    'calibrate_model',
    'TrainedModel',
    
    # Evaluation
    'compute_metrics',
    'optimize_threshold',
    'MetricsBundle',
    
    # Experiment
    'run_parallel_experiments',
    'ExperimentResult',
    'ConfigurationSpec',
    
    # Selection
    'select_best_config',
    'train_final_model',
    'FinalModel',
    
    # Artifacts
    'publish_artifacts',
    'load_all_artifacts',
    'ArtifactManifest'

    'FastCheckpointManager'
]