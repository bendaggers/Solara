#!/usr/bin/env python3
"""
ML Training Pipeline - Main Entry Point

This script orchestrates the complete training pipeline:
1. Load configuration
2. Ingest and preprocess data
3. Tag regimes
4. Define walk-forward splits
5. Run parallel configuration experiments
6. Select best configuration
7. Train final model
8. Publish artifacts

Usage:
    python run_pipeline.py --config config/settings.yaml --input data/input.csv
    python run_pipeline.py --config config/settings.yaml --input data/input.csv --workers 10
    python run_pipeline.py --config config/settings.yaml --input data/input.csv --debug
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
import warnings

# Suppress sklearn warnings during training
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

import yaml
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.logging_utils import (
    setup_logger,
    log_header,
    log_subheader,
    log_separator,
    log_pipeline_start,
    log_preprocessing_complete,
    log_regime_tagging_complete,
    log_walk_forward_boundaries,
    log_config_start,
    log_config_labels,
    log_config_signals,
    log_config_aggregate,
    log_progress,
    log_experiments_complete,
    log_best_config,
    log_final_training,
    log_artifacts_published,
    log_pipeline_complete,
    FoldMetricsLog,
    ConfigResultLog
)
from src.data import (
    load_and_prepare_data,
    get_feature_columns,
    DataStats
)
from src.splits import (
    define_walk_forward_splits,
    boundaries_to_dict
)
from src.experiment import (
    generate_config_space_from_settings,
    run_parallel_experiments,
    run_sequential_experiments,
    ExperimentResult,
    ExperimentProgress,
    summarize_experiments,
    filter_passed_results,
    get_rejection_summary
)
from src.selection import (
    select_best_config,
    train_final_model,
    validate_final_model,
    generate_selection_summary,
    BestConfiguration,
    FinalModel
)
from src.artifacts import (
    publish_artifacts,
    validate_artifacts,
    get_artifact_summary,
    ArtifactManifest
)
# ===== NEW IMPORT =====
from src.checkpoint_db import FastCheckpointManager


# =============================================================================
# CONFIGURATION LOADING
# =============================================================================

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def validate_config(config: Dict[str, Any]) -> None:
    """
    Validate configuration has required sections.
    
    Args:
        config: Configuration dictionary
        
    Raises:
        ValueError: If required sections are missing
    """
    required_sections = ['schema', 'config_space', 'walk_forward', 'acceptance_criteria']
    
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: {section}")


# =============================================================================
# PROGRESS CALLBACK
# =============================================================================

def create_progress_callback(logger, total_configs: int, progress_interval: int):
    """
    Create a progress callback function for parallel experiments.
    
    Args:
        logger: Logger instance
        total_configs: Total number of configurations
        progress_interval: How often to log progress
        
    Returns:
        Callback function
    """
    def callback(progress: ExperimentProgress):
        log_progress(
            logger=logger,
            current=progress.completed,
            total=progress.total,
            passed=progress.passed,
            rejected=progress.rejected,
            elapsed_seconds=progress.elapsed_seconds()
        )
    
    return callback


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_pipeline(
    config_path: str,
    input_csv: str,
    output_dir: Optional[str] = None,
    max_workers: Optional[int] = None,
    debug: bool = False,
    dry_run: bool = False,
    # ===== NEW PARAMETERS =====
    checkpoint_db: Optional[str] = None,
    resume: bool = False,
    export_csv: Optional[str] = None
) -> Optional[ArtifactManifest]:
    """
    Run the complete training pipeline.
    
    Args:
        config_path: Path to configuration YAML file
        input_csv: Path to input CSV file
        output_dir: Override output directory (optional)
        max_workers: Override max parallel workers (optional)
        debug: Run in debug mode (sequential, verbose)
        dry_run: Only validate, don't train
        checkpoint_db: Path to SQLite database for checkpoints
        resume: Resume from checkpoint (skip completed)
        export_csv: Export results to CSV after completion
        
    Returns:
        ArtifactManifest if successful, None otherwise
    """
    pipeline_start_time = time.time()
    
    # =========================================================================
    # STEP 1: LOAD CONFIGURATION
    # =========================================================================
    config = load_config(config_path)
    validate_config(config)
    
    # Override settings from command line
    if output_dir:
        config['paths'] = config.get('paths', {})
        config['paths']['artifacts_dir'] = output_dir
    
    if max_workers:
        config['parallel'] = config.get('parallel', {})
        config['parallel']['max_workers'] = max_workers
    
    # Get paths
    paths_config = config.get('paths', {})
    artifacts_dir = paths_config.get('artifacts_dir', 'artifacts')
    logs_dir = paths_config.get('logs_dir', 'logs')
    
    # Get parallel config
    parallel_config = config.get('parallel', {})
    n_workers = parallel_config.get('max_workers', 15)
    
    # Get logging config
    logging_config = config.get('logging', {})
    progress_interval = logging_config.get('progress_interval', 100)
    
    # Setup logger
    logger = setup_logger(
        name='ml_training',
        level='DEBUG' if debug else logging_config.get('level', 'INFO'),
        log_to_file=logging_config.get('log_to_file', True),
        log_file=logging_config.get('log_file'),
        logs_dir=logs_dir
    )
    
    # ===== NEW: Log checkpoint info if resuming =====
    if resume and checkpoint_db:
        try:
            mgr = FastCheckpointManager(checkpoint_db)
            stats = mgr.get_progress_stats()
            # CHANGE THIS LINE:
            logger.info(f"\n📋 Checkpoint found: {stats['total']} configs already completed")
            logger.info(f"   Database size: {stats['database_size_mb']:.2f} MB")
            if stats['best_config']:
                logger.info(f"   Best EV so far: {stats['best_ev']:.2f} ({stats['best_config']})")
        except Exception as e:
            logger.warning(f"Could not read checkpoint: {e}")
    
    try:
        # =====================================================================
        # STEP 2: LOAD AND PREPROCESS DATA
        # =====================================================================
        logger.info("")
        log_subheader(logger, "LOADING DATA")
        
        df, data_stats = load_and_prepare_data(
            csv_path=input_csv,
            config=config
        )
        
        log_preprocessing_complete(
            logger=logger,
            rows_before=data_stats.total_rows + data_stats.rows_dropped,
            rows_after=data_stats.total_rows,
            dropped=data_stats.rows_dropped
        )
        
        log_regime_tagging_complete(
            logger=logger,
            trending_count=data_stats.regime_counts.get('trending', 0),
            ranging_count=data_stats.regime_counts.get('ranging', 0),
            volatile_count=data_stats.regime_counts.get('volatile', 0),
            total=data_stats.total_rows
        )
        
        # =====================================================================
        # STEP 3: GET FEATURE COLUMNS
        # =====================================================================
        exclude_columns = config.get('schema', {}).get('exclude_from_features', [])
        feature_columns = get_feature_columns(df, exclude_columns)
        
        logger.info(f"\nFeatures identified: {len(feature_columns)}")
        logger.debug(f"Feature columns: {feature_columns}")
        
        # =====================================================================
        # STEP 4: DEFINE WALK-FORWARD SPLITS
        # =====================================================================
        wf_config = config.get('walk_forward', {})
        
        fold_boundaries, split_stats = define_walk_forward_splits(
            df=df,
            n_folds=wf_config.get('n_folds', 5),
            train_ratio=wf_config.get('train_ratio', 0.60),
            calibration_ratio=wf_config.get('calibration_ratio', 0.20),
            threshold_ratio=wf_config.get('threshold_ratio', 0.20),
            timestamp_column=config.get('schema', {}).get('timestamp_column', 'timestamp'),
            expanding_window=True
        )
        
        log_walk_forward_boundaries(
            logger=logger,
            fold_boundaries=boundaries_to_dict(fold_boundaries)
        )
        
        # =====================================================================
        # STEP 5: GENERATE CONFIGURATION SPACE
        # =====================================================================
        configs = generate_config_space_from_settings(config)
        
        logger.info(f"\nConfiguration space: {len(configs):,} combinations")
        
        # Dry run - stop here
        if dry_run:
            logger.info("\n[DRY RUN] Pipeline validation complete. Exiting.")
            return None
        
        # =====================================================================
        # STEP 6: LOG PIPELINE START
        # =====================================================================
        log_pipeline_start(
            logger=logger,
            n_rows=data_stats.total_rows,
            n_features=len(feature_columns),
            date_range=data_stats.date_range,
            n_folds=split_stats.n_folds,
            n_configs=len(configs),
            max_workers=n_workers if not debug else 1
        )
        
        # =====================================================================
        # STEP 7: RUN EXPERIMENTS
        # =====================================================================
        logger.info("")
        log_subheader(logger, f"RUNNING CONFIGURATION EXPERIMENTS ({len(configs):,} configs)")
        
        pip_value = config.get('instrument', {}).get('pip_value', 0.0001)
        
        progress_callback = create_progress_callback(
            logger=logger,
            total_configs=len(configs),
            progress_interval=progress_interval
        )
        
        experiment_start_time = time.time()
        
        if debug:
            # Sequential execution for debugging
            logger.info("Running in DEBUG mode (sequential execution)")
            results = run_sequential_experiments(
                df=df,
                configs=configs,
                fold_boundaries=fold_boundaries,
                feature_columns=feature_columns,
                settings=config,
                pip_value=pip_value,
                progress_callback=progress_callback,
                progress_interval=progress_interval
            )
        else:
            # Parallel execution WITH CHECKPOINT SUPPORT
            results = run_parallel_experiments(
                df=df,
                configs=configs,
                fold_boundaries=fold_boundaries,
                feature_columns=feature_columns,
                settings=config,
                max_workers=n_workers,
                pip_value=pip_value,
                progress_callback=progress_callback,
                progress_interval=progress_interval,
                # ===== NEW: Pass checkpoint parameters =====
                checkpoint_db=checkpoint_db,
                resume=resume
            )
        
        experiment_duration = time.time() - experiment_start_time
        
        # =====================================================================
        # STEP 8: SUMMARIZE EXPERIMENTS
        # =====================================================================
        summary = summarize_experiments(results)
        rejection_summary = get_rejection_summary(results)
        
        log_experiments_complete(
            logger=logger,
            total=summary['total'],
            passed=summary['passed'],
            rejected=summary['rejected'],
            rejection_reasons=rejection_summary,
            duration_seconds=experiment_duration
        )
        
        # Check if any passed
        if summary['passed'] == 0:
            logger.error("\n❌ NO CONFIGURATIONS PASSED ACCEPTANCE CRITERIA")
            logger.error("Consider adjusting:")
            logger.error("  - min_precision threshold")
            logger.error("  - min_trades_per_fold")
            logger.error("  - Configuration space ranges")
            return None
        
        # =====================================================================
        # STEP 9: SELECT BEST CONFIGURATION
        # =====================================================================
        logger.info("")
        log_subheader(logger, "SELECTING BEST CONFIGURATION")
        
        best_config = select_best_config(results)
        
        if best_config is None:
            logger.error("Failed to select best configuration")
            return None
        
        # Log best config details
        log_best_config(
            logger=logger,
            config_id=best_config.config.config_id,
            bb_threshold=best_config.config.bb_threshold,
            rsi_threshold=best_config.config.rsi_threshold,
            tp_pips=best_config.config.tp_pips,
            sl_pips=best_config.config.sl_pips,
            max_holding_bars=best_config.config.max_holding_bars,
            features=best_config.features,
            feature_importances=list(best_config.feature_importances.values()),
            hyperparams=best_config.hyperparameters,
            threshold=best_config.threshold,
            precision=best_config.aggregate_metrics.precision_mean,
            precision_std=best_config.aggregate_metrics.precision_std,
            recall=best_config.aggregate_metrics.recall_mean,
            f1=best_config.aggregate_metrics.f1_mean,
            auc_pr=best_config.aggregate_metrics.auc_pr_mean,
            ev=best_config.aggregate_metrics.ev_mean,
            ev_std=best_config.aggregate_metrics.ev_std,
            total_trades=best_config.aggregate_metrics.total_trades,
            regime_breakdown=best_config.regime_breakdown
        )
        
        # =====================================================================
        # STEP 10: TRAIN FINAL MODEL
        # =====================================================================
        logger.info("")
        log_subheader(logger, "TRAINING FINAL MODEL")
        
        final_model = train_final_model(
            df=df,
            best_config=best_config,
            fold_boundaries=fold_boundaries,
            settings=config,
            pip_value=pip_value
        )
        
        log_final_training(
            logger=logger,
            combined_train_rows=final_model.total_training_rows,
            combined_cal_rows=final_model.total_calibration_rows
        )
        
        # Validate final model
        is_valid, issues = validate_final_model(final_model)
        
        if not is_valid:
            logger.warning("Final model validation issues:")
            for issue in issues:
                logger.warning(f"  - {issue}")
        
        # =====================================================================
        # STEP 11: PUBLISH ARTIFACTS
        # =====================================================================
        logger.info("")
        log_subheader(logger, "PUBLISHING ARTIFACTS")
        
        # Prepare fold results for saving
        fold_results_list = []
        for fold_result in best_config.experiment_result.fold_results:
            fold_results_list.append(fold_result.to_dict())
        
        manifest = publish_artifacts(
            final_model=final_model,
            best_config=best_config,
            fold_results=fold_results_list,
            output_dir=artifacts_dir,
            version="1.0.0"
        )
        
        # Log published artifacts
        artifact_paths = {
            'model': manifest.model_path,
            'features': manifest.features_path,
            'trading_config': manifest.trading_config_path,
            'hyperparameters': manifest.hyperparameters_path,
            'threshold': manifest.threshold_path,
            'fold_metrics': manifest.fold_metrics_path,
            'aggregate_metrics': manifest.aggregate_metrics_path,
            'regime_breakdown': manifest.regime_breakdown_path
        }
        
        log_artifacts_published(logger=logger, artifacts=artifact_paths)
        
        # Validate artifacts
        validation = validate_artifacts(artifacts_dir)
        if not validation['is_valid']:
            logger.warning("Artifact validation issues:")
            for issue in validation['issues']:
                logger.warning(f"  - {issue}")
        
        # ===== NEW: Export to CSV if requested =====
        if export_csv and checkpoint_db:
            logger.info(f"\n📊 Exporting results to {export_csv}...")
            try:
                mgr = FastCheckpointManager(checkpoint_db)
                mgr.export_to_csv(export_csv, include_folds=True)
                logger.info(f"   ✅ Export complete")
            except Exception as e:
                logger.warning(f"   ❌ Export failed: {e}")
        
        # =====================================================================
        # STEP 12: PIPELINE COMPLETE
        # =====================================================================
        pipeline_duration = time.time() - pipeline_start_time
        
        log_pipeline_complete(
            logger=logger,
            duration_seconds=pipeline_duration,
            best_config_id=best_config.config.config_id,
            best_params={
                'bb_threshold': best_config.config.bb_threshold,
                'rsi_threshold': best_config.config.rsi_threshold,
                'tp_pips': best_config.config.tp_pips,
                'max_holding_bars': best_config.config.max_holding_bars
            },
            best_ev=best_config.aggregate_metrics.ev_mean,
            recommendation=final_model.regime_recommendation
        )
        
        return manifest
    
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️ Pipeline interrupted by user")
        return None
    
    except Exception as e:
        logger.error(f"\n\n❌ Pipeline failed with error: {e}")
        if debug:
            import traceback
            logger.error(traceback.format_exc())
        return None


# =============================================================================
# CLI ARGUMENT PARSING
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='ML Training Pipeline for SHORT-only Trade Filtering',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py --config config/settings.yaml --input data/EURUSD_H4.csv
  python run_pipeline.py --config config/settings.yaml --input data/EURUSD_H4.csv --workers 10
  python run_pipeline.py --config config/settings.yaml --input data/EURUSD_H4.csv --debug
  python run_pipeline.py --config config/settings.yaml --input data/EURUSD_H4.csv --dry-run
  # ===== NEW EXAMPLES =====
  python run_pipeline.py --config config.yaml --input data.csv --checkpoint-db checkpoints/experiments.db
  python run_pipeline.py --config config.yaml --input data.csv --checkpoint-db checkpoints/experiments.db --resume
  python run_pipeline.py --config config.yaml --input data.csv --checkpoint-db checkpoints/experiments.db --export-csv results.csv
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        required=True,
        help='Path to configuration YAML file'
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Path to input CSV file'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Override output directory for artifacts'
    )
    
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=None,
        help='Override maximum parallel workers'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Run in debug mode (sequential, verbose)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate configuration and data without training'
    )
    
    # ===== NEW ARGUMENTS =====
    parser.add_argument(
        '--checkpoint-db', '-db',
        type=str,
        default=None,
        help='SQLite database path for checkpoints (e.g., checkpoints/experiments.db)'
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from checkpoint (skip completed configs)'
    )
    
    parser.add_argument(
        '--export-csv',
        type=str,
        help='Export results to CSV after completion'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='ML Training Pipeline v3.0.0'
    )

    return parser.parse_args()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point."""
    args = parse_args()
    
    # Validate paths
    if not Path(args.config).exists():
        print(f"Error: Configuration file not found: {args.config}")
        sys.exit(1)
    
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    # Run pipeline with all arguments
    manifest = run_pipeline(
        config_path=args.config,
        input_csv=args.input,
        output_dir=args.output,
        max_workers=args.workers,
        debug=args.debug,
        dry_run=args.dry_run,
        # ===== NEW: Pass checkpoint arguments =====
        checkpoint_db=args.checkpoint_db,
        resume=args.resume,
        export_csv=args.export_csv
    )
    
    # Exit code
    if manifest is not None:
        print("\n✅ Pipeline completed successfully!")
        print(f"   Artifacts saved to: {Path(args.output or 'artifacts').absolute()}")
        sys.exit(0)
    elif args.dry_run:
        print("\n✅ Dry run completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Pipeline failed. Check logs for details.")
        sys.exit(1)


if __name__ == '__main__':
    main()