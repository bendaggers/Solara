#!/usr/bin/env python3
"""
Test if RFE cache is actually working.
"""

import pandas as pd
import numpy as np
import time
import sys
import os
import yaml
import warnings
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

warnings.filterwarnings('ignore')
os.environ['LIGHTGBM_VERBOSITY'] = '-1'

sys.path.insert(0, 'src')

from features import rfe_select, RFEResult

# Recreate the cache exactly as in experiment.py
@dataclass
class RFECache:
    results: Dict[str, RFEResult] = field(default_factory=dict)
    
    def get_key(self, bb: float, rsi: int, fold: int) -> str:
        return f"bb{bb:.2f}_rsi{rsi}_fold{fold}"
    
    def get(self, bb: float, rsi: int, fold: int) -> Optional[RFEResult]:
        key = self.get_key(bb, rsi, fold)
        return self.results.get(key)
    
    def set(self, bb: float, rsi: int, fold: int, result: RFEResult) -> None:
        key = self.get_key(bb, rsi, fold)
        self.results[key] = result

_rfe_cache = RFECache()
_rfe_cache_lock = threading.Lock()

def get_or_compute_rfe(bb, rsi, fold, train_df, feature_columns, rfe_settings):
    global _rfe_cache
    
    # Check cache
    with _rfe_cache_lock:
        cached = _rfe_cache.get(bb, rsi, fold)
        if cached is not None:
            print(f"    CACHE HIT: bb={bb}, rsi={rsi}, fold={fold}")
            return cached
    
    print(f"    CACHE MISS: bb={bb}, rsi={rsi}, fold={fold} - Computing RFE...")
    start = time.time()
    
    rfe_result = rfe_select(
        X_train=train_df,
        y_train=train_df['label'],
        feature_columns=feature_columns,
        min_features=rfe_settings.get('min_features', 5),
        max_features=rfe_settings.get('max_features', 15),
        cv_folds=rfe_settings.get('cv_folds', 3)
    )
    
    elapsed = time.time() - start
    print(f"    RFE computed in {elapsed:.1f}s, selected {len(rfe_result.selected_features)} features")
    
    with _rfe_cache_lock:
        _rfe_cache.set(bb, rsi, fold, rfe_result)
    
    return rfe_result


def main():
    print("=" * 70)
    print("TESTING RFE CACHE")
    print("=" * 70)
    
    # Load data
    df = pd.read_csv('data/EURUSD-RAW_Data.csv')
    
    with open('config/settings.yaml', 'r') as f:
        settings = yaml.safe_load(f)
    
    rfe_settings = settings.get('rfe', {})
    
    # Filter
    bb = 0.81
    rsi = 72
    df_filtered = df[(df['bb_position'] >= bb) & (df['rsi_value'] >= rsi)].copy()
    
    # Features
    exclude = ['timestamp', 'pair', 'open', 'high', 'low', 'close', 'volume',
               'lower_band', 'middle_band', 'upper_band', 'label', 'label_reason',
               'signal', 'regime']
    feature_columns = [c for c in df_filtered.columns if c not in exclude]
    
    # Create labels (simulating TP=40)
    np.random.seed(42)
    df_filtered['label'] = np.random.randint(0, 2, size=len(df_filtered))
    
    # Train split
    train_size = int(len(df_filtered) * 0.6)
    train_df = df_filtered.iloc[:train_size].copy()
    
    print(f"\nData: {len(train_df)} train rows, {len(feature_columns)} features")
    print(f"Testing BB={bb}, RSI={rsi}")
    
    # Test 1: First call (should compute)
    print("\n[TEST 1] First call - should COMPUTE")
    start = time.time()
    result1 = get_or_compute_rfe(bb, rsi, fold=1, train_df=train_df, 
                                  feature_columns=feature_columns, rfe_settings=rfe_settings)
    time1 = time.time() - start
    print(f"    Total time: {time1:.1f}s")
    
    # Test 2: Same params (should cache hit)
    print("\n[TEST 2] Same params - should CACHE HIT")
    start = time.time()
    result2 = get_or_compute_rfe(bb, rsi, fold=1, train_df=train_df,
                                  feature_columns=feature_columns, rfe_settings=rfe_settings)
    time2 = time.time() - start
    print(f"    Total time: {time2:.1f}s")
    
    # Test 3: Different fold (should compute)
    print("\n[TEST 3] Different fold - should COMPUTE")
    start = time.time()
    result3 = get_or_compute_rfe(bb, rsi, fold=2, train_df=train_df,
                                  feature_columns=feature_columns, rfe_settings=rfe_settings)
    time3 = time.time() - start
    print(f"    Total time: {time3:.1f}s")
    
    # Test 4: Different RSI (should compute)
    print("\n[TEST 4] Different RSI - should COMPUTE")
    start = time.time()
    result4 = get_or_compute_rfe(bb, rsi=73, fold=1, train_df=train_df,
                                  feature_columns=feature_columns, rfe_settings=rfe_settings)
    time4 = time.time() - start
    print(f"    Total time: {time4:.1f}s")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Cache entries: {len(_rfe_cache.results)}")
    for key in _rfe_cache.results:
        print(f"  - {key}")
    
    print(f"\nFirst call (compute): {time1:.1f}s")
    print(f"Cache hit:            {time2:.1f}s")
    
    if time2 < 1.0:
        print("\n✓ CACHE IS WORKING!")
    else:
        print("\n✗ CACHE IS NOT WORKING!")


if __name__ == '__main__':
    main()