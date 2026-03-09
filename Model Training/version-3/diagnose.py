#!/usr/bin/env python3
"""
DEEP DIAGNOSTIC - Find exactly where the slowdown is.

Tests each component individually with timing.
"""

import pandas as pd
import numpy as np
import time
import sys
import os
import yaml
import warnings

warnings.filterwarnings('ignore')
os.environ['LIGHTGBM_VERBOSITY'] = '-1'

# Add src to path
sys.path.insert(0, 'src')

def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.1f}s"
    else:
        return f"{seconds/60:.1f}min"

def main():
    print("=" * 70)
    print("DEEP DIAGNOSTIC - IDENTIFYING BOTTLENECK")
    print("=" * 70)
    
    # Load data
    print("\n[1] Loading data...")
    df = pd.read_csv('data/EURUSD-RAW_Data.csv')
    print(f"    Rows: {len(df)}")
    
    # Load settings
    with open('config/settings.yaml', 'r') as f:
        settings = yaml.safe_load(f)
    
    bb_min = settings['config_space']['bb_threshold']['min']
    rsi_min = settings['config_space']['rsi_threshold']['min']
    
    # Filter data
    print(f"\n[2] Filtering data (BB>={bb_min}, RSI>={rsi_min})...")
    df_filtered = df[(df['bb_position'] >= bb_min) & (df['rsi_value'] >= rsi_min)].copy()
    print(f"    Filtered rows: {len(df_filtered)}")
    
    # Create dummy labels
    np.random.seed(42)
    df_filtered['label'] = np.random.randint(0, 2, size=len(df_filtered))
    
    # Get features
    exclude = settings.get('schema', {}).get('exclude_from_features', [])
    if not exclude:
        exclude = ['timestamp', 'pair', 'open', 'high', 'low', 'close', 'volume',
                   'lower_band', 'middle_band', 'upper_band', 'label', 'label_reason',
                   'signal', 'regime']
    feature_columns = [c for c in df_filtered.columns if c not in exclude]
    print(f"    Features: {len(feature_columns)}")
    
    # Simulate fold split (60% train)
    train_size = int(len(df_filtered) * 0.6)
    train_df = df_filtered.iloc[:train_size].copy()
    print(f"    Train size: {len(train_df)}")
    
    X_train = train_df[feature_columns].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_train = train_df['label']
    
    # =========================================================================
    # TEST 1: RFE with GradientBoosting (baseline)
    # =========================================================================
    print("\n" + "=" * 70)
    print("[TEST 1] RFE with GradientBoostingClassifier (CPU)")
    print("=" * 70)
    
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.feature_selection import RFECV
    from sklearn.model_selection import StratifiedKFold
    
    start = time.time()
    
    estimator_gb = GradientBoostingClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.1,
        min_samples_leaf=20,
        random_state=42
    )
    
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    
    rfecv_gb = RFECV(
        estimator=estimator_gb,
        step=1,
        cv=cv,
        scoring='average_precision',
        min_features_to_select=5,
        n_jobs=-1
    )
    
    rfecv_gb.fit(X_train, y_train)
    gb_time = time.time() - start
    print(f"    Time: {format_time(gb_time)}")
    print(f"    Features selected: {rfecv_gb.n_features_}")
    
    # =========================================================================
    # TEST 2: RFE with LightGBM CPU
    # =========================================================================
    print("\n" + "=" * 70)
    print("[TEST 2] RFE with LightGBM (CPU)")
    print("=" * 70)
    
    import lightgbm as lgb
    
    start = time.time()
    
    estimator_lgb_cpu = lgb.LGBMClassifier(
        n_estimators=50,
        max_depth=4,
        learning_rate=0.1,
        min_child_samples=20,
        random_state=42,
        verbose=-1,
        n_jobs=1,
        device='cpu'
    )
    
    rfecv_lgb_cpu = RFECV(
        estimator=estimator_lgb_cpu,
        step=1,
        cv=cv,
        scoring='average_precision',
        min_features_to_select=5,
        n_jobs=-1
    )
    
    rfecv_lgb_cpu.fit(X_train, y_train)
    lgb_cpu_time = time.time() - start
    print(f"    Time: {format_time(lgb_cpu_time)}")
    print(f"    Features selected: {rfecv_lgb_cpu.n_features_}")
    
    # =========================================================================
    # TEST 3: RFE with LightGBM GPU
    # =========================================================================
    print("\n" + "=" * 70)
    print("[TEST 3] RFE with LightGBM (GPU)")
    print("=" * 70)
    
    start = time.time()
    
    try:
        estimator_lgb_gpu = lgb.LGBMClassifier(
            n_estimators=50,
            max_depth=4,
            learning_rate=0.1,
            min_child_samples=20,
            random_state=42,
            verbose=-1,
            n_jobs=1,
            device='gpu',
            gpu_use_dp=False
        )
        
        rfecv_lgb_gpu = RFECV(
            estimator=estimator_lgb_gpu,
            step=1,
            cv=cv,
            scoring='average_precision',
            min_features_to_select=5,
            n_jobs=-1
        )
        
        rfecv_lgb_gpu.fit(X_train, y_train)
        lgb_gpu_time = time.time() - start
        print(f"    Time: {format_time(lgb_gpu_time)}")
        print(f"    Features selected: {rfecv_lgb_gpu.n_features_}")
    except Exception as e:
        lgb_gpu_time = float('inf')
        print(f"    GPU FAILED: {e}")
    
    # =========================================================================
    # TEST 4: Hyperparameter Tuning
    # =========================================================================
    print("\n" + "=" * 70)
    print("[TEST 4] Hyperparameter Tuning (20 iterations)")
    print("=" * 70)
    
    from sklearn.model_selection import RandomizedSearchCV
    
    # Use first 10 features
    selected_features = feature_columns[:10]
    X_train_small = X_train[selected_features]
    
    param_dist = {
        'n_estimators': [50, 100, 200, 300],
        'max_depth': [3, 4, 5, 6, 8],
        'learning_rate': [0.01, 0.05, 0.1],
        'num_leaves': [15, 31, 63],
        'min_child_samples': [10, 20, 50]
    }
    
    # CPU
    start = time.time()
    model_cpu = lgb.LGBMClassifier(random_state=42, verbose=-1, device='cpu')
    search_cpu = RandomizedSearchCV(
        model_cpu, param_dist, n_iter=20, cv=3, scoring='average_precision',
        n_jobs=-1, random_state=42
    )
    search_cpu.fit(X_train_small, y_train)
    hp_cpu_time = time.time() - start
    print(f"    CPU Time: {format_time(hp_cpu_time)}")
    
    # GPU
    start = time.time()
    try:
        model_gpu = lgb.LGBMClassifier(random_state=42, verbose=-1, device='gpu', gpu_use_dp=False)
        search_gpu = RandomizedSearchCV(
            model_gpu, param_dist, n_iter=20, cv=3, scoring='average_precision',
            n_jobs=-1, random_state=42
        )
        search_gpu.fit(X_train_small, y_train)
        hp_gpu_time = time.time() - start
        print(f"    GPU Time: {format_time(hp_gpu_time)}")
    except Exception as e:
        hp_gpu_time = float('inf')
        print(f"    GPU FAILED: {e}")
    
    # =========================================================================
    # TEST 5: Single Model Training
    # =========================================================================
    print("\n" + "=" * 70)
    print("[TEST 5] Single Model Training")
    print("=" * 70)
    
    # CPU
    start = time.time()
    model_train_cpu = lgb.LGBMClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        random_state=42, verbose=-1, device='cpu'
    )
    model_train_cpu.fit(X_train_small, y_train)
    train_cpu_time = time.time() - start
    print(f"    CPU Time: {format_time(train_cpu_time)}")
    
    # GPU
    start = time.time()
    try:
        model_train_gpu = lgb.LGBMClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            random_state=42, verbose=-1, device='gpu', gpu_use_dp=False
        )
        model_train_gpu.fit(X_train_small, y_train)
        train_gpu_time = time.time() - start
        print(f"    GPU Time: {format_time(train_gpu_time)}")
    except Exception as e:
        train_gpu_time = float('inf')
        print(f"    GPU FAILED: {e}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print(f"\nRFE (147 features, step=1, 3-fold CV):")
    print(f"  GradientBoosting: {format_time(gb_time)}")
    print(f"  LightGBM CPU:     {format_time(lgb_cpu_time)}")
    print(f"  LightGBM GPU:     {format_time(lgb_gpu_time)}")
    
    print(f"\nHyperparameter Tuning (20 iter, 3-fold CV):")
    print(f"  LightGBM CPU:     {format_time(hp_cpu_time)}")
    print(f"  LightGBM GPU:     {format_time(hp_gpu_time)}")
    
    print(f"\nSingle Model Training:")
    print(f"  LightGBM CPU:     {format_time(train_cpu_time)}")
    print(f"  LightGBM GPU:     {format_time(train_gpu_time)}")
    
    # Estimate per-config time
    print("\n" + "=" * 70)
    print("ESTIMATED TIME PER CONFIG (5 folds)")
    print("=" * 70)
    
    # Per fold = RFE + HP tuning + training + calibration + threshold
    # But RFE is cached after first config per (BB, RSI)
    
    rfe_time = min(lgb_cpu_time, lgb_gpu_time) if lgb_gpu_time != float('inf') else lgb_cpu_time
    hp_time = min(hp_cpu_time, hp_gpu_time) if hp_gpu_time != float('inf') else hp_cpu_time
    train_time = min(train_cpu_time, train_gpu_time) if train_gpu_time != float('inf') else train_cpu_time
    
    # First config (RFE computed)
    first_config = 5 * (rfe_time + hp_time + train_time + 2)
    print(f"  First config (RFE computed): {format_time(first_config)}")
    
    # Subsequent configs (RFE cached)
    subsequent_config = 5 * (hp_time + train_time + 2)
    print(f"  Subsequent configs (RFE cached): {format_time(subsequent_config)}")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    
    if lgb_gpu_time > lgb_cpu_time * 1.5:
        print("  ⚠️  GPU is SLOWER than CPU for this workload!")
        print("  → Use CPU-only (remove device='gpu')")
    elif lgb_gpu_time < lgb_cpu_time:
        print("  ✓ GPU is faster")
    
    if gb_time < lgb_cpu_time:
        print("  ⚠️  GradientBoosting is faster than LightGBM!")
        print("  → Consider switching back")


if __name__ == '__main__':
    main()