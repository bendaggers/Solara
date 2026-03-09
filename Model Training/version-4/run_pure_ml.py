#!/usr/bin/env python3
"""
Pure ML Training Pipeline - Main Entry Point

This script orchestrates the Pure ML training pipeline:
1. Load configuration
2. Ingest and preprocess data
3. **Run feature engineering (from v3)**
4. Tag regimes (for diagnostics)
5. Pre-compute all label configurations
6. Define walk-forward splits
7. Run experiments for all TP/SL/Hold combinations
8. Select best configuration
9. Train final model
10. Publish artifacts

Key differences from Signal Filter model:
- NO BB/RSI pre-filtering (evaluates ALL candles)
- Simpler config space (only TP/SL/Hold)
- Larger dataset (more rows per fold)
- Higher class imbalance (model learns entry conditions)

Usage:
    python run_pure_ml.py --config config/pure_ml_settings.yaml --input ../version-3/data/EURUSD-RAW_Data.csv
    python run_pure_ml.py --config config/pure_ml_settings.yaml --input ../version-3/data/EURUSD-RAW_Data.csv --debug
"""

import argparse
import sys
import time
import json
import warnings
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Suppress ALL warnings globally
warnings.filterwarnings('ignore')
os.environ['LIGHTGBM_VERBOSITY'] = '-1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Suppress LightGBM logger
try:
    import lightgbm as lgb
    lgb.register_logger(lgb.basic.NullLogger())
except:
    pass

import yaml
import pandas as pd
import numpy as np
import joblib

# Add src to path - Windows compatible
SCRIPT_DIR = Path(__file__).parent.resolve()
SRC_DIR = SCRIPT_DIR / 'src'
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SRC_DIR))

# Add version-3 to path for feature engineering
V3_PATH = SCRIPT_DIR.parent / 'version-3'
if V3_PATH.exists() and str(V3_PATH) not in sys.path:
    sys.path.insert(0, str(V3_PATH))

from pure_ml_labels import (
    precompute_all_labels,
    apply_precomputed_labels,
    get_unique_label_configs,
    estimate_class_imbalance,
    TradeDirection
)
from experiment import (
    generate_config_space,
    run_all_experiments,
    select_best_result
)
from training import (
    train_model,
    calibrate_model,
    save_model,
    get_feature_importance,
    get_best_model_type
)
from evaluation import (
    compute_metrics,
    optimize_threshold
)

# Try to import feature engineering from various locations
FEATURE_ENGINEERING_AVAILABLE = False
FeatureEngineering = None

# Try 1: From src folder (v4 local)
try:
    from feature_engineering import FeatureEngineering
    FEATURE_ENGINEERING_AVAILABLE = True
except ImportError:
    pass

# Try 2: From v3 folder
if not FEATURE_ENGINEERING_AVAILABLE:
    try:
        V3_PATH = Path(__file__).parent.parent / 'version-3'
        if V3_PATH.exists():
            sys.path.insert(0, str(V3_PATH))
            from features import FeatureEngineering
            FEATURE_ENGINEERING_AVAILABLE = True
    except ImportError:
        pass

# Try 3: Direct import (if features.py is in same folder)
if not FEATURE_ENGINEERING_AVAILABLE:
    try:
        from features import FeatureEngineering
        FEATURE_ENGINEERING_AVAILABLE = True
    except ImportError:
        pass


# =============================================================================
# LOGGING UTILITIES
# =============================================================================

class PipelineLogger:
    """Simple logger for pipeline output."""
    
    def __init__(self, log_file: Optional[str] = None, verbose: bool = True):
        self.verbose = verbose
        self.log_file = log_file
        self.start_time = datetime.now()
        
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        
        if self.verbose:
            print(formatted)
        
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(formatted + "\n")
    
    def header(self, title: str):
        border = "=" * 70
        self.log("")
        self.log(border)
        self.log(f"  {title}")
        self.log(border)
    
    def subheader(self, title: str):
        self.log("")
        self.log(f"--- {title} ---")
    
    def elapsed(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()


# =============================================================================
# DATA LOADING
# =============================================================================

def load_and_prepare_data(
    csv_path: str,
    config: Dict[str, Any],
    logger: PipelineLogger
) -> pd.DataFrame:
    """
    Load CSV and prepare data for training.
    Applies feature engineering if available.
    """
    schema = config.get('schema', {})
    
    # Load CSV
    logger.log(f"Loading data from: {csv_path}")
    df = pd.read_csv(csv_path, sep=None, engine='python')
    
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    # Parse timestamps
    timestamp_col = schema.get('timestamp_column', 'timestamp')
    timestamp_fmt = schema.get('timestamp_format', '%Y.%m.%d %H:%M:%S')
    
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], format=timestamp_fmt)
    df = df.sort_values(timestamp_col).reset_index(drop=True)
    
    logger.log(f"   Loaded {len(df):,} rows")
    logger.log(f"   Date range: {df[timestamp_col].min()} to {df[timestamp_col].max()}")
    
    # Apply feature engineering if available and enabled
    features_config = config.get('features', {})
    compute_additional = features_config.get('compute_additional', True)
    
    if compute_additional and FEATURE_ENGINEERING_AVAILABLE:
        logger.log(f"   Applying feature engineering...")
        fe = FeatureEngineering(verbose=False)
        df = fe.calculate_features(df, drop_na=True, min_periods=30)
        logger.log(f"   After feature engineering: {len(df):,} rows, {len(df.columns)} columns")
    elif compute_additional and not FEATURE_ENGINEERING_AVAILABLE:
        logger.log(f"   WARNING: Feature engineering not available (FeatureEngineering not found)")
    else:
        logger.log(f"   Feature engineering disabled in config")
    
    return df


def get_feature_columns(
    df: pd.DataFrame,
    config: Dict[str, Any]
) -> List[str]:
    """
    Get list of feature columns (exclude non-features).
    """
    features_config = config.get('features', {})
    exclude_cols = set(col.lower() for col in features_config.get('exclude_columns', []))
    
    feature_columns = [
        col for col in df.columns
        if col.lower() not in exclude_cols
        and pd.api.types.is_numeric_dtype(df[col])
    ]
    
    return feature_columns


def tag_regimes(
    df: pd.DataFrame,
    config: Dict[str, Any],
    logger: PipelineLogger
) -> pd.DataFrame:
    """
    Tag market regimes for diagnostics.
    """
    regime_config = config.get('regime', {})
    
    # Calculate ADX
    adx_period = regime_config.get('adx_period', 14)
    
    # Simplified ADX calculation
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr = np.maximum(
        high - low,
        np.maximum(
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        )
    )
    
    atr = tr.rolling(window=adx_period).mean()
    
    # Calculate directional movement
    up = high - high.shift(1)
    down = low.shift(1) - low
    
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    
    plus_di = 100 * pd.Series(plus_dm).rolling(adx_period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).rolling(adx_period).mean() / atr
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.rolling(adx_period).mean()
    
    # Assign regimes
    trending_threshold = regime_config.get('trending_adx_threshold', 25)
    volatile_threshold = regime_config.get('volatile_atr_percentile', 70)
    
    atr_pct = atr.rolling(100).apply(lambda x: (x.iloc[-1] > np.percentile(x, volatile_threshold)) * 100)
    
    conditions = [
        adx > trending_threshold,
        (adx <= trending_threshold) & (atr_pct >= 50)
    ]
    choices = ['trending', 'volatile']
    
    df['regime'] = np.select(conditions, choices, default='ranging')
    
    regime_counts = df['regime'].value_counts().to_dict()
    logger.log(f"   Regimes: {regime_counts}")
    
    return df


# =============================================================================
# WALK-FORWARD SPLITS
# =============================================================================

def define_walk_forward_splits(
    df: pd.DataFrame,
    config: Dict[str, Any],
    logger: PipelineLogger
) -> List[Dict[str, Any]]:
    """
    Define walk-forward fold boundaries.
    """
    wf_config = config.get('walk_forward', {})
    
    n_folds = wf_config.get('n_folds', 5)
    train_ratio = wf_config.get('train_ratio', 0.60)
    cal_ratio = wf_config.get('calibration_ratio', 0.20)
    thresh_ratio = wf_config.get('threshold_ratio', 0.20)
    expanding = wf_config.get('expanding_window', True)
    
    n_rows = len(df)
    validation_ratio = cal_ratio + thresh_ratio
    
    boundaries = []
    
    if expanding:
        segment_size = n_rows // (n_folds + 1)
        
        for fold_idx in range(n_folds):
            train_start_idx = 0
            train_end_idx = (fold_idx + 1) * segment_size
            
            cal_start_idx = train_end_idx
            cal_end_idx = cal_start_idx + int(segment_size * cal_ratio / validation_ratio)
            
            thresh_start_idx = cal_end_idx
            thresh_end_idx = min(cal_start_idx + segment_size, n_rows - 1)
            
            if thresh_end_idx <= thresh_start_idx:
                continue
            
            boundaries.append({
                'fold_number': fold_idx + 1,
                'train_start_idx': train_start_idx,
                'train_end_idx': min(train_end_idx, n_rows - 1),
                'cal_start_idx': min(cal_start_idx, n_rows - 1),
                'cal_end_idx': min(cal_end_idx, n_rows - 1),
                'thresh_start_idx': min(thresh_start_idx, n_rows - 1),
                'thresh_end_idx': min(thresh_end_idx, n_rows - 1)
            })
    
    logger.log(f"   Defined {len(boundaries)} folds")
    for b in boundaries:
        train_size = b['train_end_idx'] - b['train_start_idx']
        thresh_size = b['thresh_end_idx'] - b['thresh_start_idx']
        logger.log(f"      Fold {b['fold_number']}: Train={train_size:,}, Thresh={thresh_size:,}")
    
    return boundaries


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_pipeline(
    config_path: str,
    input_csv: str,
    output_dir: Optional[str] = None,
    n_workers: Optional[int] = None,
    debug: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Run the complete Pure ML training pipeline.
    """
    pipeline_start = time.time()
    
    # Load configuration
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Get paths
    paths = config.get('paths', {})
    artifacts_dir = output_dir or paths.get('artifacts_dir', 'artifacts')
    logs_dir = paths.get('logs_dir', 'logs')
    
    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    
    # Setup logger
    log_file = Path(logs_dir) / f"pure_ml_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logger = PipelineLogger(log_file=str(log_file), verbose=True)
    
    logger.header("PURE ML TRAINING PIPELINE")
    logger.log(f"Configuration: {config_path}")
    logger.log(f"Input data: {input_csv}")
    logger.log(f"Output directory: {artifacts_dir}")
    
    try:
        # =====================================================================
        # STEP 1: Load and prepare data
        # =====================================================================
        logger.subheader("STEP 1: Loading Data")
        
        df = load_and_prepare_data(input_csv, config, logger)
        feature_columns = get_feature_columns(df, config)
        logger.log(f"   Found {len(feature_columns)} feature columns")
        
        # Tag regimes
        df = tag_regimes(df, config, logger)
        
        pip_value = config.get('schema', {}).get('pip_value', 0.0001)
        
        # =====================================================================
        # STEP 2: Pre-compute labels
        # =====================================================================
        logger.subheader("STEP 2: Pre-computing Labels")
        
        config_space = config.get('config_space', {})
        label_configs = get_unique_label_configs(config_space)
        logger.log(f"   Label configurations to compute: {len(label_configs)}")
        
        label_cache = precompute_all_labels(
            df=df,
            label_configs=label_configs,
            pip_value=pip_value,
            direction=TradeDirection.SHORT,
            verbose=True
        )
        
        # Show class imbalance for first config
        first_config = label_configs[0]
        precomputed = label_cache.get(*first_config)
        imbalance = estimate_class_imbalance(precomputed.stats)
        logger.log(f"   Class imbalance (first config): {imbalance['imbalance_ratio']:.1f}:1")
        logger.log(f"   Win rate: {imbalance['minority_pct']:.1f}%")
        
        # =====================================================================
        # STEP 3: Define walk-forward splits
        # =====================================================================
        logger.subheader("STEP 3: Defining Walk-Forward Splits")
        
        fold_boundaries = define_walk_forward_splits(df, config, logger)
        
        # =====================================================================
        # STEP 4: Generate configuration space
        # =====================================================================
        logger.subheader("STEP 4: Generating Configuration Space")
        
        configs = generate_config_space(config)
        logger.log(f"   Total configurations to test: {len(configs)}")
        
        # =====================================================================
        # STEP 5: Run experiments
        # =====================================================================
        logger.subheader("STEP 5: Running Experiments")
        
        # Get number of workers - CLI overrides config
        if n_workers is not None:
            workers = n_workers
        else:
            parallel_config = config.get('parallel', {})
            workers = parallel_config.get('max_workers', 8)
        
        # Database path for checkpoints
        db_path = Path(artifacts_dir) / "pure_ml.db"
        
        results = run_all_experiments(
            df=df,
            label_cache=label_cache,
            configs=configs,
            fold_boundaries=fold_boundaries,
            feature_columns=feature_columns,
            settings=config,
            pip_value=pip_value,
            max_workers=workers,
            db_path=str(db_path)
        )
        
        # Summarize results
        passed = [r for r in results if r.passed]
        logger.log(f"   Experiments complete: {len(passed)}/{len(results)} passed")
        
        # =====================================================================
        # STEP 6: Select best configuration
        # =====================================================================
        logger.subheader("STEP 6: Selecting Best Configuration")
        
        best_result = select_best_result(results)
        
        if best_result is None:
            logger.log("   ❌ No configurations passed acceptance criteria!")
            logger.log("   Consider relaxing criteria or checking data quality.")
            return None
        
        logger.log(f"   ✅ Best config: {best_result.config.config_id}")
        logger.log(f"      TP={best_result.config.tp_pips}, SL={best_result.config.sl_pips}, "
                   f"Hold={best_result.config.max_holding_bars}")
        logger.log(f"      Precision: {best_result.aggregate_metrics.precision_mean:.3f}")
        logger.log(f"      EV: {best_result.aggregate_metrics.ev_mean:+.2f} pips")
        logger.log(f"      Features: {len(best_result.consensus_features)}")
        logger.log(f"      Threshold: {best_result.consensus_threshold:.2f}")
        
        # =====================================================================
        # STEP 7: Train final model
        # =====================================================================
        logger.subheader("STEP 7: Training Final Model")
        
        # Use all data up to last fold for final training
        last_fold = fold_boundaries[-1]
        
        # Apply labels for best config
        df_labeled, _ = apply_precomputed_labels(
            df=df,
            label_cache=label_cache,
            tp_pips=best_result.config.tp_pips,
            sl_pips=best_result.config.sl_pips,
            max_holding_bars=best_result.config.max_holding_bars
        )
        
        # Get training data
        train_df = df_labeled[df_labeled.index <= last_fold['cal_end_idx']]
        
        X_train = train_df[best_result.consensus_features]
        y_train = train_df['label']
        
        logger.log(f"   Training on {len(train_df):,} rows")
        logger.log(f"   Features: {best_result.consensus_features}")
        
        # Train model
        final_model = train_model(
            X_train=X_train,
            y_train=y_train,
            feature_columns=best_result.consensus_features,
            hyperparameters=best_result.consensus_hyperparameters,
            model_type=get_best_model_type()
        )
        
        # Calibrate
        cal_df = df_labeled[
            (df_labeled.index > last_fold['cal_start_idx']) &
            (df_labeled.index <= last_fold['cal_end_idx'])
        ]
        
        if len(cal_df) > 20:
            X_cal = cal_df[best_result.consensus_features]
            y_cal = cal_df['label']
            
            calibrated_model, cal_result = calibrate_model(
                trained_model=final_model,
                X_cal=X_cal,
                y_cal=y_cal,
                method=config.get('calibration', {}).get('method', 'sigmoid')
            )
            logger.log(f"   Calibration improvement: {cal_result.improvement_pct:.1f}%")
            final_model = calibrated_model
        
        # =====================================================================
        # STEP 8: Publish artifacts
        # =====================================================================
        logger.subheader("STEP 8: Publishing Artifacts")
        
        # Save model
        model_path = Path(artifacts_dir) / "pure_ml_model.pkl"
        
        model_bundle = {
            'model': final_model,
            'features': best_result.consensus_features,
            'threshold': best_result.consensus_threshold,
            'tp_pips': best_result.config.tp_pips,
            'sl_pips': best_result.config.sl_pips,
            'max_holding_bars': best_result.config.max_holding_bars,
            'training_date': datetime.now().isoformat(),
            'model_type': 'pure_ml',
            'metrics': {
                'precision': best_result.aggregate_metrics.precision_mean,
                'ev': best_result.aggregate_metrics.ev_mean,
                'f1': best_result.aggregate_metrics.f1_mean
            }
        }
        
        joblib.dump(model_bundle, model_path)
        logger.log(f"   Model saved: {model_path}")
        
        # Save features
        features_path = Path(artifacts_dir) / "features.json"
        with open(features_path, 'w') as f:
            json.dump({'features': best_result.consensus_features}, f, indent=2)
        logger.log(f"   Features saved: {features_path}")
        
        # Save config
        trading_config_path = Path(artifacts_dir) / "trading_config.json"
        trading_config = {
            'tp_pips': best_result.config.tp_pips,
            'sl_pips': best_result.config.sl_pips,
            'max_holding_bars': best_result.config.max_holding_bars,
            'threshold': best_result.consensus_threshold,
            'model_type': 'pure_ml'
        }
        with open(trading_config_path, 'w') as f:
            json.dump(trading_config, f, indent=2)
        logger.log(f"   Trading config saved: {trading_config_path}")
        
        # Save metrics
        metrics_path = Path(artifacts_dir) / "metrics.json"
        metrics = {
            'aggregate': best_result.aggregate_metrics.to_dict(),
            'fold_results': [fr.to_dict() for fr in best_result.fold_results],
            'config': best_result.config.to_dict()
        }
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        logger.log(f"   Metrics saved: {metrics_path}")
        
        # =====================================================================
        # COMPLETE
        # =====================================================================
        pipeline_duration = time.time() - pipeline_start
        
        logger.header("PIPELINE COMPLETE")
        logger.log(f"Duration: {pipeline_duration:.1f} seconds")
        logger.log(f"Best Config: TP={best_result.config.tp_pips}, "
                   f"SL={best_result.config.sl_pips}, "
                   f"Hold={best_result.config.max_holding_bars}")
        logger.log(f"Precision: {best_result.aggregate_metrics.precision_mean:.3f}")
        logger.log(f"Expected Value: {best_result.aggregate_metrics.ev_mean:+.2f} pips/trade")
        logger.log(f"Artifacts saved to: {artifacts_dir}")
        
        return {
            'status': 'success',
            'best_config': best_result.config.to_dict(),
            'metrics': best_result.aggregate_metrics.to_dict(),
            'artifacts_dir': str(artifacts_dir),
            'duration_seconds': pipeline_duration
        }
    
    except Exception as e:
        logger.log(f"❌ Pipeline failed: {e}", level="ERROR")
        if debug:
            import traceback
            logger.log(traceback.format_exc(), level="ERROR")
        return None


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Pure ML Training Pipeline for SHORT-only Trade Prediction',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pure_ml.py --config config/pure_ml_settings.yaml --input data/EURUSD_H4.csv
  python run_pure_ml.py --config config/pure_ml_settings.yaml --input data/EURUSD_H4.csv --workers 20
  python run_pure_ml.py --config config/pure_ml_settings.yaml --input data/EURUSD_H4.csv --debug
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
        help='Number of parallel workers (default: from config or 8)'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Run in debug mode (verbose error output)'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='Pure ML Pipeline v1.0.0'
    )
    
    return parser.parse_args()


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
    
    # Run pipeline
    result = run_pipeline(
        config_path=args.config,
        input_csv=args.input,
        output_dir=args.output,
        n_workers=args.workers,
        debug=args.debug
    )
    
    if result is not None:
        print("\n✅ Pipeline completed successfully!")
        print(f"   Artifacts saved to: {result['artifacts_dir']}")
        sys.exit(0)
    else:
        print("\n❌ Pipeline failed. Check logs for details.")
        sys.exit(1)


if __name__ == '__main__':
    main()