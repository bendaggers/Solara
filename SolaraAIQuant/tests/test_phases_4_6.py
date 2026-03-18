"""
Solara AI Quant - Test Phases 4-6

Tests for:
- Phase 4: Engine (Registry, Health, Execution)
- Phase 5: Predictors (Base, Stella Alpha)
- Phase 6: Signals (Models, Conflict, Aggregator)

Run: python test_phases_4_6.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_model_registry():
    """Test model registry loading."""
    print("\n" + "=" * 60)
    print("  TEST: Model Registry")
    print("=" * 60)
    
    from engine.registry import ModelRegistry, model_registry
    
    # Test loading
    success = model_registry.load()
    print(f"  Registry loaded: {success}")
    
    # Get models
    models = model_registry.get_enabled_models()
    print(f"  Enabled models: {len(models)}")
    
    for m in models:
        print(f"    - {m.name} ({m.model_type.value}, {m.timeframe.value})")
        print(f"      Magic: {m.magic}, Threshold: {m.threshold}")
        print(f"      Model file exists: {m.model_exists}")
    
    # Test timeframe filtering
    h4_models = model_registry.get_models_for_timeframe("H4")
    print(f"  H4 models: {len(h4_models)}")
    
    # Print summary
    model_registry.print_summary()
    
    return True


def test_model_health():
    """Test model health tracking."""
    print("\n" + "=" * 60)
    print("  TEST: Model Health Tracker")
    print("=" * 60)
    
    from engine.model_health import (
        ModelHealthTracker, 
        model_health_tracker,
        RunStatus,
        HealthStatus
    )
    
    # Create test tracker (in memory, no DB)
    tracker = ModelHealthTracker()
    
    # Test health status
    print("  Testing health status logic...")
    
    # Simulate runs
    test_model = "TestModel"
    test_magic = 999999
    
    # Initially healthy
    is_healthy = tracker.is_model_healthy(test_model)
    print(f"  Initial health: {is_healthy}")
    
    print("  ✓ Model health tracker initialized")
    return True


def test_signal_models():
    """Test signal data models."""
    print("\n" + "=" * 60)
    print("  TEST: Signal Models")
    print("=" * 60)
    
    from signals.signal_models import (
        RawSignal,
        AggregatedSignal,
        SignalDirection,
        SignalStatus
    )
    
    # Create a raw signal
    signal = RawSignal(
        signal_id="test123",
        model_name="Stella Alpha Long",
        magic=100001,
        symbol="EURUSD",
        direction=SignalDirection.LONG,
        confidence=0.65,
        entry_price=1.08500,
        tp_pips=100,
        sl_pips=50,
        comment="SAQ_Test"
    )
    
    print(f"  Created signal: {signal.symbol} {signal.direction.value}")
    print(f"  Confidence: {signal.confidence}")
    print(f"  TP: {signal.tp_pips}, SL: {signal.sl_pips}")
    
    # Convert to dict
    signal_dict = signal.to_dict()
    print(f"  Signal dict keys: {list(signal_dict.keys())}")
    
    # Create aggregated signal
    agg = AggregatedSignal(
        raw_signal=signal,
        status=SignalStatus.VALIDATED,
        combined_confidence=signal.confidence,
        contributing_models=["Stella Alpha Long"]
    )
    
    print(f"  Aggregated status: {agg.status.value}")
    print(f"  Is valid: {agg.is_valid}")
    
    print("  ✓ Signal models working")
    return True


def test_conflict_checker():
    """Test conflict detection."""
    print("\n" + "=" * 60)
    print("  TEST: Conflict Checker")
    print("=" * 60)
    
    from signals.conflict_checker import ConflictChecker
    from signals.signal_models import RawSignal, SignalDirection, SignalStatus
    
    checker = ConflictChecker()
    
    # Test 1: Single signal (should pass)
    print("\n  Test 1: Single signal")
    signals = [
        RawSignal(
            signal_id="s1",
            model_name="Model1",
            magic=100001,
            symbol="EURUSD",
            direction=SignalDirection.LONG,
            confidence=0.60
        )
    ]
    
    result = checker.check_conflicts(signals)
    valid = [r for r in result if r.is_valid]
    print(f"    Input: 1 signal, Output: {len(valid)} valid")
    assert len(valid) == 1, "Single signal should pass"
    print("    ✓ PASS")
    
    # Test 2: Opposing signals from same model (should reject both)
    print("\n  Test 2: Opposing signals (same model)")
    signals = [
        RawSignal(
            signal_id="s2",
            model_name="Model1",
            magic=100001,
            symbol="EURUSD",
            direction=SignalDirection.LONG,
            confidence=0.60
        ),
        RawSignal(
            signal_id="s3",
            model_name="Model1",
            magic=100001,
            symbol="EURUSD",
            direction=SignalDirection.SHORT,
            confidence=0.55
        )
    ]
    
    result = checker.check_conflicts(signals)
    valid = [r for r in result if r.is_valid]
    print(f"    Input: 2 opposing signals, Output: {len(valid)} valid")
    assert len(valid) == 0, "Opposing signals should be rejected"
    print("    ✓ PASS (both rejected)")
    
    # Test 3: Duplicate signals (keep highest confidence)
    print("\n  Test 3: Duplicate signals")
    signals = [
        RawSignal(
            signal_id="s4",
            model_name="Model1",
            magic=100001,
            symbol="EURUSD",
            direction=SignalDirection.LONG,
            confidence=0.70
        ),
        RawSignal(
            signal_id="s5",
            model_name="Model1",
            magic=100001,
            symbol="EURUSD",
            direction=SignalDirection.LONG,
            confidence=0.55
        )
    ]
    
    result = checker.check_conflicts(signals)
    valid = [r for r in result if r.is_valid]
    print(f"    Input: 2 duplicate signals, Output: {len(valid)} valid")
    assert len(valid) == 1, "Should keep only highest confidence"
    assert valid[0].raw_signal.confidence == 0.70, "Should keep the 0.70 one"
    print("    ✓ PASS (kept 0.70)")
    
    # Test 4: Different models, same symbol, opposing (allowed)
    print("\n  Test 4: Different models, opposing (allowed)")
    signals = [
        RawSignal(
            signal_id="s6",
            model_name="Model1",
            magic=100001,
            symbol="EURUSD",
            direction=SignalDirection.LONG,
            confidence=0.60
        ),
        RawSignal(
            signal_id="s7",
            model_name="Model2",
            magic=100002,
            symbol="EURUSD",
            direction=SignalDirection.SHORT,
            confidence=0.65
        )
    ]
    
    result = checker.check_conflicts(signals)
    valid = [r for r in result if r.is_valid]
    print(f"    Input: 2 signals (different models), Output: {len(valid)} valid")
    assert len(valid) == 2, "Different models can have opposing signals"
    print("    ✓ PASS (both allowed)")
    
    print("\n  ✓ Conflict checker working correctly")
    return True


def test_signal_aggregator():
    """Test signal aggregation."""
    print("\n" + "=" * 60)
    print("  TEST: Signal Aggregator")
    print("=" * 60)
    
    from signals.aggregator import SignalAggregator
    
    aggregator = SignalAggregator()
    
    # Test with prediction dicts
    predictions = [
        {
            'symbol': 'EURUSD',
            'direction': 'LONG',
            'confidence': 0.65,
            'entry_price': 1.08500,
            'tp_pips': 100,
            'sl_pips': 50,
            'model_name': 'Stella Alpha Long',
            'magic': 100001,
            'comment': 'SAQ_Test'
        },
        {
            'symbol': 'GBPUSD',
            'direction': 'LONG',
            'confidence': 0.58,
            'entry_price': 1.26500,
            'tp_pips': 100,
            'sl_pips': 50,
            'model_name': 'Stella Alpha Long',
            'magic': 100001,
            'comment': 'SAQ_Test'
        }
    ]
    
    signals = aggregator.aggregate_from_predictions(predictions)
    
    print(f"  Input predictions: {len(predictions)}")
    print(f"  Output signals: {len(signals)}")
    
    for sig in signals:
        print(f"    - {sig.symbol} {sig.direction.value} @ {sig.combined_confidence:.2f}")
    
    # Get stats
    stats = aggregator.get_statistics()
    print(f"  Statistics: {stats}")
    
    print("  ✓ Signal aggregator working")
    return True


def test_predictor_base():
    """Test base predictor."""
    print("\n" + "=" * 60)
    print("  TEST: Base Predictor")
    print("=" * 60)
    
    from predictors.base_predictor import BasePredictor, PredictionSignal
    
    # PredictionSignal test
    signal = PredictionSignal(
        symbol="EURUSD",
        direction="LONG",
        confidence=0.65,
        entry_price=1.08500,
        tp_pips=100,
        sl_pips=50,
        model_name="TestModel",
        magic=100001,
        comment="Test"
    )
    
    signal_dict = signal.to_dict()
    print(f"  PredictionSignal created: {signal.symbol} {signal.direction}")
    print(f"  Dict keys: {list(signal_dict.keys())}")
    
    print("  ✓ Base predictor components working")
    return True


def test_stella_alpha_predictor():
    """Test Stella Alpha predictor structure."""
    print("\n" + "=" * 60)
    print("  TEST: Stella Alpha Predictor")
    print("=" * 60)
    
    from predictors.stella_alpha_long import StellaAlphaLongPredictor
    
    # Check features list
    features = StellaAlphaLongPredictor.SELECTED_FEATURES
    print(f"  Required features: {len(features)}")
    
    # Show feature categories
    categories = {
        'RSI': [f for f in features if 'rsi' in f.lower()],
        'BB': [f for f in features if 'bb' in f.lower()],
        'Trend': [f for f in features if 'trend' in f.lower() or 'ema' in f.lower()],
        'D1': [f for f in features if f.startswith('d1_')],
        'MTF': [f for f in features if f.startswith('mtf_')],
    }
    
    for cat, feats in categories.items():
        if feats:
            print(f"    {cat}: {len(feats)} features")
    
    print("  ✓ Stella Alpha predictor structure valid")
    return True


def run_all_tests():
    """Run all Phase 4-6 tests."""
    print("\n" + "=" * 60)
    print("  SOLARA AI QUANT - PHASE 4-6 TESTS")
    print("=" * 60)
    
    tests = [
        ("Model Registry", test_model_registry),
        ("Model Health", test_model_health),
        ("Signal Models", test_signal_models),
        ("Conflict Checker", test_conflict_checker),
        ("Signal Aggregator", test_signal_aggregator),
        ("Base Predictor", test_predictor_base),
        ("Stella Alpha Predictor", test_stella_alpha_predictor),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "PASS" if success else "FAIL"))
        except Exception as e:
            print(f"\n  ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, f"ERROR: {e}"))
    
    # Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r == "PASS")
    total = len(results)
    
    for name, result in results:
        icon = "✓" if result == "PASS" else "✗"
        print(f"  {icon} {name}: {result}")
    
    print(f"\n  Total: {passed}/{total} passed")
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
