#!/usr/bin/env python3
"""
Diagnostic script to identify training bottleneck.
Run this to see where the hang is happening.
"""

import pandas as pd
import numpy as np
import time
import sys

# Add src to path
sys.path.insert(0, 'src')

from features import rfe_select
from training import tune_hyperparameters, get_best_model_type

def main():
    print("=" * 60)
    print("DIAGNOSTIC: Identifying Training Bottleneck")
    print("=" * 60)
    
    # Load data
    print("\n[1] Loading data...")
    start = time.time()
    df = pd.read_csv('data/EURUSD-RAW_Data.csv')
    print(f"    Loaded {len(df)} rows in {time.time()-start:.1f}s")
    
    # Filter like BB=0.80, RSI=60
    print("\n[2] Filtering data (BB>=0.80, RSI>=60)...")
    start = time.time()
    df_filtered = df[(df['bb_position'] >= 0.80) & (df['rsi_value'] >= 60)].copy()
    print(f"    Filtered to {len(df_filtered)} rows in {time.time()-start:.1f}s")
    
    # Get feature columns
    exclude = ['timestamp', 'pair', 'open', 'high', 'low', 'close', 'volume',
               'lower_band', 'middle_band', 'upper_band', 'label', 'label_reason',
               'signal', 'regime']
    feature_columns = [c for c in df_filtered.columns if c not in exclude]
    print(f"    Features: {len(feature_columns)}")
    
    # Create dummy labels
    df_filtered['label'] = np.random.randint(0, 2, size=len(df_filtered))
    
    # Split train (just use first 60%)
    train_size = int(len(df_filtered) * 0.6)
    train_df = df_filtered.iloc[:train_size].copy()
    print(f"    Train size: {len(train_df)}")
    
    # Test RFE
    print("\n[3] Testing RFE (this is likely the bottleneck)...")
    print("    Running RFE with 147 features, 3-fold CV...")
    start = time.time()
    
    try:
        rfe_result = rfe_select(
            X_train=train_df,
            y_train=train_df['label'],
            feature_columns=feature_columns,
            min_features=5,
            max_features=15,
            cv_folds=3
        )
        elapsed = time.time() - start
        print(f"    RFE completed in {elapsed:.1f}s ({elapsed/60:.1f} min)")
        print(f"    Selected {len(rfe_result.selected_features)} features")
    except Exception as e:
        print(f"    RFE FAILED: {e}")
        return
    
    # Test HP tuning
    print("\n[4] Testing Hyperparameter Tuning...")
    start = time.time()
    
    try:
        hp_result = tune_hyperparameters(
            X_train=train_df,
            y_train=train_df['label'],
            feature_columns=rfe_result.selected_features,
            model_type=get_best_model_type(),
            cv_folds=3,
            random_state=42,
            use_randomized=True,
            n_iter=20
        )
        elapsed = time.time() - start
        print(f"    HP Tuning completed in {elapsed:.1f}s ({elapsed/60:.1f} min)")
    except Exception as e:
        print(f"    HP Tuning FAILED: {e}")
        return
    
    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)
    print("\nIf RFE took > 10 minutes, that's your bottleneck.")
    print("Consider reducing feature count or increasing RFE step size.")


if __name__ == '__main__':
    main()
