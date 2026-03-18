#!/usr/bin/env python3
"""
Simple test script for Dummy Predictor
"""
import sys
import os
import pandas as pd
import numpy as np

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress structlog output for testing
import logging
logging.basicConfig(level=logging.WARNING)

from predictors.dummy_predictor import DummyRandomPredictor
from engine.model_registry import ModelRegistry

def create_test_dataframe():
    """Create a mock featured DataFrame with dummy data"""
    # Create test data for 3 symbols
    data = []
    symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    
    for symbol in symbols:
        # Create dummy feature values
        row = {
            "symbol": symbol,
            "open": 1.1000,
            "high": 1.1050,
            "low": 1.0950,
            "close": 1.1020,
            "price": 1.1020,
            "ret": np.random.uniform(-0.01, 0.01),
            "ret_lag1": np.random.uniform(-0.01, 0.01),
            "ret_lag2": np.random.uniform(-0.01, 0.01),
            "ret_lag3": np.random.uniform(-0.01, 0.01),
            "body_size": np.random.uniform(0, 0.01),
            "candle_body_pct": np.random.uniform(0, 100),
            "rsi_value": np.random.uniform(30, 70),
            "rsi_slope": np.random.uniform(-5, 5),
            "rsi_slope_lag1": np.random.uniform(-5, 5),
            "rsi_slope_lag2": np.random.uniform(-5, 5),
            "rsi_slope_lag3": np.random.uniform(-5, 5),
            "RSI_slope_3": np.random.uniform(-5, 5),
            "dist_bb_upper": np.random.uniform(-0.02, 0.02),
            "dist_bb_lower": np.random.uniform(-0.02, 0.02),
            "dist_bb_upper_lag1": np.random.uniform(-0.02, 0.02),
            "dist_bb_upper_lag2": np.random.uniform(-0.02, 0.02),
            "dist_bb_upper_lag3": np.random.uniform(-0.02, 0.02),
            "price_momentum": np.random.uniform(-0.01, 0.01),
        }
        data.append(row)
    
    return pd.DataFrame(data)

def test_dummy_predictor():
    """Test the dummy predictor with mock data"""
    print("Testing Dummy Random Predictor...")
    
    # Create a mock registry entry
    class MockEntry:
        def __init__(self):
            self.name = "Dummy Test Model"
            self.model_type = "LONG"
            self.timeframe = "M5"
            self.min_confidence = 0.60
            self.magic = 999999
            self.weight = 1.0
            self.comment = "SAQ_DummyTest"
            self.model_file = ""  # Empty for dummy
            self.symbols = []  # All symbols
    
    mock_entry = MockEntry()
    
    # Create predictor
    predictor = DummyRandomPredictor(mock_entry)
    
    # Test feature list
    features = predictor.get_feature_list()
    print(f"[OK] Predictor requires {len(features)} features")
    print(f"  Sample features: {features[:5]}...")
    
    # Create test dataframe
    df = create_test_dataframe()
    print(f"[OK] Created test dataframe with {len(df)} symbols")
    
    # Run prediction
    signals = predictor.predict(df)
    
    print(f"[OK] Generated {len(signals)} signals")
    
    for i, signal in enumerate(signals):
        print(f"  Signal {i+1}: {signal.symbol} {signal.direction} "
              f"@{signal.confidence:.2f} confidence")
    
    # Test multiple runs to see random behavior
    print("\nTesting multiple runs (should vary randomly):")
    all_signals_count = []
    for run in range(5):
        signals = predictor.predict(df)
        all_signals_count.append(len(signals))
        print(f"  Run {run+1}: {len(signals)} signals")
    
    print(f"\nSummary: Generated {sum(all_signals_count)} total signals "
          f"across 5 runs (avg: {sum(all_signals_count)/5:.1f})")
    
    return True

def test_registry_loading():
    """Test that the model registry loads with dummy entries"""
    print("\n" + "="*50)
    print("Testing Model Registry Loading...")
    
    try:
        # Load registry
        registry = ModelRegistry()
        registry.load()
        
        print(f"[OK] Registry loaded successfully")
        print(f"  Total models: {registry.count()}")
        print(f"  Enabled models: {registry.count_enabled()}")
        print(f"  Active timeframes: {registry.timeframes_active()}")
        
        # Check for dummy models
        dummy_models = []
        for timeframe in ["M5", "M15", "H1", "H4"]:
            enabled = registry.get_enabled(timeframe)
            for model in enabled:
                if "Dummy" in model.name:
                    dummy_models.append(model)
        
        print(f"  Found {len(dummy_models)} dummy models")
        for model in dummy_models:
            print(f"    - {model.name} ({model.timeframe}, {model.model_type})")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Registry loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*50)
    print("Solara AI Quant - Dummy Predictor Test")
    print("="*50)
    
    # Test 1: Dummy predictor
    test1_ok = test_dummy_predictor()
    
    # Test 2: Registry loading
    test2_ok = test_registry_loading()
    
    print("\n" + "="*50)
    print("Test Results:")
    print(f"  Dummy Predictor: {'[PASS]' if test1_ok else '[FAIL]'}")
    print(f"  Registry Loading: {'[PASS]' if test2_ok else '[FAIL]'}")
    
    if test1_ok and test2_ok:
        print("\n[OK] All tests passed! Dummy predictor is ready for testing.")
        print("\nNext steps:")
        print("  1. Run: python main.py (with proper .env configuration)")
        print("  2. The dummy models will generate random signals")
        print("  3. Check logs for 'dummy_predictor' entries")
    else:
        print("\n[ERROR] Some tests failed. Please check the errors above.")
        sys.exit(1)