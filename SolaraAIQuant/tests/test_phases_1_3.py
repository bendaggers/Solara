#!/usr/bin/env python
"""
Solara AI Quant - Phase 1-3 Test Script

Tests core infrastructure, data pipeline, and watchdog components.
Run this to verify installation and configuration.

Usage:
    python test_phases_1_3.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_imports():
    """Test that all modules can be imported."""
    print("\n" + "="*60)
    print("  TEST: Module Imports")
    print("="*60)
    
    modules = [
        ("config", "Configuration"),
        ("utils.logging_utils", "Logging"),
        ("state.models", "Database Models"),
        ("state.database", "Database Manager"),
        ("mt5.mt5_manager", "MT5 Manager"),
        ("mt5.symbol_helper", "Symbol Helper"),
        ("ingestion.csv_reader", "CSV Reader"),
        ("ingestion.data_validator", "Data Validator"),
        ("features.h4_d1_merger", "H4/D1 Merger"),
        ("features.feature_engineer", "Feature Engineer"),
        ("watchdog.cycle_lock", "Cycle Lock"),
        ("watchdog.file_observer", "File Observer"),
        ("watchdog.pipeline_runner", "Pipeline Runner"),
    ]
    
    passed = 0
    failed = 0
    
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"  ✓ {description:<25} ({module_name})")
            passed += 1
        except Exception as e:
            print(f"  ✗ {description:<25} FAILED: {e}")
            failed += 1
    
    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_config():
    """Test configuration loading."""
    print("\n" + "="*60)
    print("  TEST: Configuration")
    print("="*60)
    
    from config import (
        PROJECT_ROOT, MQL5_FILES_DIR, TIMEFRAMES,
        mt5_config, ingestion_config, feature_config,
        validate_config, print_config
    )
    
    print(f"  PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"  MQL5_FILES_DIR: {MQL5_FILES_DIR}")
    print(f"  Timeframes: {list(TIMEFRAMES.keys())}")
    
    # Validate config
    is_valid, errors = validate_config()
    
    if is_valid:
        print("  ✓ Configuration valid")
        return True
    else:
        print(f"  ✗ Configuration errors: {errors}")
        return False


def test_database():
    """Test database initialization."""
    print("\n" + "="*60)
    print("  TEST: Database")
    print("="*60)
    
    from state.database import db_manager
    
    # Check session works
    try:
        with db_manager.session_scope() as session:
            # Simple query
            result = session.execute("SELECT 1")
            print("  ✓ Database session works")
            return True
    except Exception as e:
        print(f"  ✗ Database error: {e}")
        return False


def test_cycle_lock():
    """Test cycle lock mechanism."""
    print("\n" + "="*60)
    print("  TEST: Cycle Lock")
    print("="*60)
    
    from watchdog.cycle_lock import cycle_lock, Timeframe
    
    # Test acquire and release
    tf = Timeframe.H4
    
    # Should acquire successfully
    acquired = cycle_lock.acquire(tf)
    if not acquired:
        print("  ✗ Failed to acquire lock")
        return False
    print("  ✓ Acquired H4 lock")
    
    # Should fail to acquire again
    acquired2 = cycle_lock.acquire(tf)
    if acquired2:
        print("  ✗ Should not acquire twice")
        cycle_lock.release(tf)
        return False
    print("  ✓ Second acquire correctly blocked")
    
    # Release
    cycle_lock.release(tf)
    print("  ✓ Released lock")
    
    # Should acquire again
    acquired3 = cycle_lock.acquire(tf)
    if not acquired3:
        print("  ✗ Failed to acquire after release")
        return False
    print("  ✓ Re-acquired after release")
    
    cycle_lock.release(tf)
    
    print("  ✓ Cycle lock working correctly")
    return True


def test_feature_engineer():
    """Test feature engineering on sample data."""
    print("\n" + "="*60)
    print("  TEST: Feature Engineering")
    print("="*60)
    
    import pandas as pd
    import numpy as np
    from features import feature_engineer
    
    # Create sample OHLCV data
    np.random.seed(42)
    n = 100
    
    dates = pd.date_range('2024-01-01', periods=n, freq='4h')
    close = 1.1000 + np.cumsum(np.random.randn(n) * 0.001)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': close - np.random.rand(n) * 0.0005,
        'high': close + np.random.rand(n) * 0.001,
        'low': close - np.random.rand(n) * 0.001,
        'close': close,
        'volume': np.random.randint(100, 1000, n),
    })
    
    # Ensure high >= close and low <= close
    df['high'] = df[['high', 'close', 'open']].max(axis=1)
    df['low'] = df[['low', 'close', 'open']].min(axis=1)
    
    print(f"  Input: {len(df)} rows, {len(df.columns)} columns")
    
    # Compute features
    df_features = feature_engineer.compute_all_features(df, include_d1=False)
    
    print(f"  Output: {len(df_features)} rows, {len(df_features.columns)} columns")
    
    # Check key features exist
    required = ['rsi_value', 'bb_position', 'atr_pct', 'trend_strength', 'adx']
    missing = [f for f in required if f not in df_features.columns]
    
    if missing:
        print(f"  ✗ Missing features: {missing}")
        return False
    
    print(f"  ✓ All required features computed")
    
    # Check no NaN in key columns (after warmup)
    df_stable = df_features.iloc[50:]  # Skip warmup
    nan_cols = [c for c in required if df_stable[c].isna().any()]
    
    if nan_cols:
        print(f"  ✗ NaN in columns: {nan_cols}")
        return False
    
    print(f"  ✓ No NaN in stable region")
    
    return True


def test_h4_d1_merger():
    """Test H4/D1 merger with no leakage."""
    print("\n" + "="*60)
    print("  TEST: H4/D1 Merger")
    print("="*60)
    
    import pandas as pd
    import numpy as np
    from features import H4D1Merger
    
    # Create sample H4 data
    h4_dates = pd.date_range('2024-01-15 04:00', periods=24, freq='4h')
    df_h4 = pd.DataFrame({
        'timestamp': h4_dates,
        'close': 1.1000 + np.arange(24) * 0.0001,
    })
    
    # Create sample D1 data
    d1_dates = pd.date_range('2024-01-13', periods=5, freq='D')
    df_d1 = pd.DataFrame({
        'timestamp': d1_dates,
        'close': [1.0980, 1.0990, 1.1000, 1.1010, 1.1020],
        'rsi_value': [50, 55, 60, 65, 70],
    })
    
    print(f"  H4 data: {len(df_h4)} rows ({h4_dates[0]} to {h4_dates[-1]})")
    print(f"  D1 data: {len(df_d1)} rows ({d1_dates[0]} to {d1_dates[-1]})")
    
    # Merge
    merger = H4D1Merger(d1_lookback_shift=1)
    
    try:
        df_merged = merger.merge(df_h4, df_d1, validate=True)
        print(f"  ✓ Merge successful: {len(df_merged)} rows")
        
        # Verify no leakage
        # H4 on Jan 15 should use D1 from Jan 14
        jan15_rows = df_merged[df_merged['timestamp'].dt.date == pd.Timestamp('2024-01-15').date()]
        
        for _, row in jan15_rows.iterrows():
            if pd.notna(row['d1_timestamp']):
                d1_date = pd.to_datetime(row['d1_timestamp']).date()
                expected = pd.Timestamp('2024-01-14').date()
                
                if d1_date != expected:
                    print(f"  ✗ Leakage: H4 Jan 15 uses D1 {d1_date}, expected {expected}")
                    return False
        
        print(f"  ✓ No data leakage detected")
        return True
        
    except ValueError as e:
        print(f"  ✗ Merge failed: {e}")
        return False


def test_file_observer_setup():
    """Test file observer can be created."""
    print("\n" + "="*60)
    print("  TEST: File Observer Setup")
    print("="*60)
    
    from watchdog.file_observer import FileObserver
    from pathlib import Path
    import tempfile
    
    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        observer = FileObserver(
            watch_directory=Path(tmpdir),
            on_file_changed=lambda f, t: None
        )
        
        watched = observer.get_watched_files()
        print(f"  Watched files: {list(watched.keys())}")
        
        # Start and stop (quick test)
        observer.start()
        print(f"  ✓ Observer started")
        
        if observer.is_running():
            print(f"  ✓ Observer running")
        
        observer.stop()
        print(f"  ✓ Observer stopped")
        
        return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("  SOLARA AI QUANT - PHASE 1-3 TESTS")
    print("="*60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_config),
        ("Database", test_database),
        ("Cycle Lock", test_cycle_lock),
        ("Feature Engineering", test_feature_engineer),
        ("H4/D1 Merger", test_h4_d1_merger),
        ("File Observer", test_file_observer_setup),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  ✗ {name} raised exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, p in results if p)
    failed = len(results) - passed
    
    for name, p in results:
        status = "✓ PASS" if p else "✗ FAIL"
        print(f"  {status}  {name}")
    
    print(f"\n  Total: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
