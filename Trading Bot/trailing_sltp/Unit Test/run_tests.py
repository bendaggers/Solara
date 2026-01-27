#!/usr/bin/env python3
"""
SIMPLE DYNAMIC TEST RUNNER - Runs ALL tests
"""
import sys
import os
import json
import time
from datetime import datetime

# Setup
sys.path.append('..')
from survivor_engine import SurvivorEngineV3
from dummy_data import get_test_scenarios

def create_test_engine():
    """Create a test engine with market data"""
    # Create market data
    market_data = {
        "data": [
            {
                "pair": "EURUSD",
                "lower_band": 1.09500,
                "upper_band": 1.10500,
                "lowerBand": 1.09500,
                "upperBand": 1.10500
            }
        ]
    }
    
    os.makedirs("Unit Test", exist_ok=True)
    with open("Unit Test/test_market.json", "w") as f:
        json.dump(market_data, f)
    
    # Create engine
    engine = SurvivorEngineV3(
        market_data_file="Unit Test/test_market.json",
        hysteresis_config={'up_buffer': 0.02, 'down_buffer': 0.05},
        safe_distance_config={'min_pips': 10},
        regression_config={
            'min_stage_for_detection': 'STAGE_1',
            'giveback_threshold': 0.30,
            'stagnation_cycles': 4,
            'defense_level_1': 'STAGE_2C',
            'defense_level_2': 'STAGE_3A',
            'defense_level_3': 'STAGE_3B'
        }
    )
    
    engine.load_market_data()
    return engine

def run_ut001(engine, test_data):
    """UT-001: Stage Progression Logic"""
    print(f"\n{'='*60}")
    print("UT-001: Stage Progression Logic")
    print(f"{'='*60}")
    
    all_passed = True
    results = []
    
    for scenario in test_data['data']:
        print(f"\n  Scenario: {scenario['name']}")
        
        position = {
            'ticket': 1001,
            'symbol': 'EURUSD',
            'type': 0,
            'entry_price': scenario['entry'],
            'current_price': scenario['entry'],
            'sl': 0.0,
            'tp': 0.0,
            'volume': 0.1
        }
        
        final_stage = None
        
        # Process each price over 5 days
        for price_info in scenario['prices']:
            position['current_price'] = price_info['price']
            result = engine.process_all_positions([position])[0]
            
            # Show progress every day
            if price_info['cycle'] == 4:  # End of day
                print(f"    Day {price_info['day']}: Stage {result['stage']}, "
                      f"Price {price_info['price']:.5f}")
            
            final_stage = result['stage']
        
        # Check result
        expected = scenario.get('expected_final_stage')
        if expected:
            passed = (final_stage == expected)
            if not passed:
                all_passed = False
                print(f"    ❌ Expected {expected}, got {final_stage}")
            else:
                print(f"    ✅ Final stage: {final_stage}")
        
        results.append({
            'scenario': scenario['name'],
            'final_stage': final_stage,
            'expected': expected,
            'passed': passed if expected else True
        })
    
    return all_passed, results

def run_ut002(engine, test_data):
    """UT-002: Regression Detection"""
    print(f"\n{'='*60}")
    print("UT-002: Regression Detection")
    print(f"{'='*60}")
    
    all_passed = True
    results = []
    
    for scenario in test_data['data']:
        print(f"\n  Scenario: {scenario['name']}")
        
        position = {
            'ticket': 1002,
            'symbol': 'EURUSD',
            'type': 0,
            'entry_price': scenario['entry'],
            'current_price': scenario['entry'],
            'sl': 0.0,
            'tp': 0.0,
            'volume': 0.1
        }
        
        regression_detected = False
        
        # Process each price
        for price_info in scenario['prices']:
            position['current_price'] = price_info['price']
            result = engine.process_all_positions([position])[0]
            
            if result['regression_detected']:
                regression_detected = True
                print(f"    ⚡ Regression detected at Day {price_info['day']}, "
                      f"Cycle {price_info['cycle']}")
        
        # Check result
        expected = scenario.get('should_trigger_regression')
        if expected is not None:
            passed = (regression_detected == expected)
            if not passed:
                all_passed = False
                status = "detected" if regression_detected else "not detected"
                print(f"    ❌ Regression {status}, expected {'trigger' if expected else 'no trigger'}")
            else:
                print(f"    ✅ Regression {'triggered' if regression_detected else 'not triggered'} as expected")
        
        results.append({
            'scenario': scenario['name'],
            'regression_detected': regression_detected,
            'expected': expected,
            'passed': passed if expected is not None else True
        })
    
    return all_passed, results

def run_ut003(engine, test_data):
    """UT-003: SL/TP Assignment"""
    print(f"\n{'='*60}")
    print("UT-003: SL/TP Assignment")
    print(f"{'='*60}")
    
    all_passed = True
    results = []
    
    for scenario in test_data['data']:
        print(f"\n  Scenario: {scenario['name']}")
        
        for pos_data in scenario['positions']:
            position = {
                'ticket': pos_data['ticket'],
                'symbol': pos_data['symbol'],
                'type': pos_data['type'],
                'entry_price': pos_data['entry'],
                'current_price': pos_data['price'],
                'sl': 0.0,
                'tp': 0.0,
                'volume': 0.1
            }
            
            result = engine.process_all_positions([position])[0]
            
            # Check stage
            expected_stage = pos_data.get('expected_stage')
            if expected_stage:
                stage_passed = (result['stage'] == expected_stage)
                if not stage_passed:
                    all_passed = False
                    print(f"    ❌ Stage: Expected {expected_stage}, got {result['stage']}")
                else:
                    print(f"    ✅ Stage: {result['stage']}")
            
            # Check SL
            expected_sl = pos_data.get('expected_sl')
            if expected_sl:
                sl_passed = abs(result['new_sl'] - expected_sl) < 0.00001
                if not sl_passed:
                    all_passed = False
                    print(f"    ❌ SL: Expected {expected_sl:.5f}, got {result['new_sl']:.5f}")
                else:
                    print(f"    ✅ SL: {result['new_sl']:.5f}")
            
            # Check TP
            expected_has_tp = pos_data.get('expected_has_tp')
            if expected_has_tp is not None:
                has_tp = (result['new_tp'] is not None and result['new_tp'] > 0)
                tp_passed = (has_tp == expected_has_tp)
                if not tp_passed:
                    all_passed = False
                    status = "has TP" if has_tp else "no TP"
                    expected_status = "should have TP" if expected_has_tp else "should not have TP"
                    print(f"    ❌ TP: {status}, {expected_status}")
                else:
                    print(f"    ✅ TP: {'Has TP' if has_tp else 'No TP'} as expected")
            
            results.append({
                'position': pos_data['ticket'],
                'stage': result['stage'],
                'sl': result['new_sl'],
                'tp': result['new_tp'],
                'passed': True  # Will be updated by checks
            })
    
    return all_passed, results

def main():
    """Run ALL tests"""
    print("\n" + "="*60)
    print("🚀 SURVIVOR ENGINE v3.0 - DYNAMIC TEST RUNNER")
    print("="*60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create results directory
    os.makedirs("results", exist_ok=True)
    
    # Create engine
    engine = create_test_engine()
    
    # Get all test scenarios
    all_tests = get_test_scenarios()
    
    print(f"\n📋 Running {len(all_tests)} test categories...")
    print("="*60)
    
    results = {}
    passed_count = 0
    total_tests = len(all_tests)
    
    # Map test IDs to functions
    test_runners = {
        'UT-001': run_ut001,
        'UT-002': run_ut002,
        'UT-003': run_ut003,
        # Add more as we create them...
    }
    
    # Run each test
    for test_id, test_data in all_tests.items():
        if test_id in test_runners:
            print(f"\n▶️ Running {test_id}: {test_data['name']}")
            print(f"   {test_data['description']}")
            print(f"   Priority: {test_data['priority']}")
            
            start_time = time.time()
            
            try:
                runner = test_runners[test_id]
                passed, test_results = runner(engine, test_data)
                
                elapsed = time.time() - start_time
                
                # Save results
                results[test_id] = {
                    'name': test_data['name'],
                    'passed': passed,
                    'time': elapsed,
                    'results': test_results
                }
                
                if passed:
                    passed_count += 1
                    print(f"   ✅ {test_id} PASSED in {elapsed:.2f}s")
                else:
                    print(f"   ❌ {test_id} FAILED in {elapsed:.2f}s")
                    
            except Exception as e:
                print(f"   💥 {test_id} ERROR: {e}")
                import traceback
                traceback.print_exc()
                results[test_id] = {
                    'name': test_data['name'],
                    'passed': False,
                    'error': str(e)
                }
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    print(f"Total Categories: {total_tests}")
    print(f"✅ Passed: {passed_count}")
    print(f"❌ Failed: {total_tests - passed_count}")
    
    # Save results
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_tests': total_tests,
        'passed_tests': passed_count,
        'failed_tests': total_tests - passed_count,
        'results': results
    }
    
    with open("results/test_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n📁 Results saved to: results/test_summary.json")
    
    if passed_count == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️ {total_tests - passed_count} test(s) failed.")

if __name__ == "__main__":
    main()