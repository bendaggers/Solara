#!/usr/bin/env python3
"""
ALL TEST SCENARIOS (UT-001 to UT-029)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survivor_engine import SurvivorEngineV3
from dummy_data import get_all_test_data

# ================== TEST SCENARIO DEFINITIONS ==================

class TestScenario:
    """Base test scenario"""
    
    def __init__(self, test_id, name, description, priority='P1'):
        self.test_id = test_id
        self.name = name
        self.description = description
        self.priority = priority
        self.passed = False
        self.result = {}
        
    def run(self, engine):
        """Run the test - to be implemented by subclasses"""
        raise NotImplementedError
        
    def log_result(self, result_dir="results"):
        """Log test result"""
        os.makedirs(result_dir, exist_ok=True)
        
        log_data = {
            'test_id': self.test_id,
            'name': self.name,
            'description': self.description,
            'priority': self.priority,
            'passed': self.passed,
            'result': self.result,
            'timestamp': datetime.now().isoformat()
        }
        
        filename = f"{result_dir}/{self.test_id}.json"
        import json
        with open(filename, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        return filename

# ================== CORE LOGIC TESTS ==================

class StageProgressionTest(TestScenario):
    """UT-001: Stage progression logic"""
    
    def __init__(self):
        super().__init__(
            test_id='UT-001',
            name='Stage Progression Logic',
            description='Test stage progression through various profit levels',
            priority='P0'
        )
        
    def run(self, engine):
        from dummy_data import get_stage_progression_data
        
        print(f"\n{self.test_id}: {self.name}")
        print("-" * 50)
        
        all_passed = True
        results = []
        
        for variation in get_stage_progression_data():
            print(f"  Variation: {variation['name']}")
            
            # Test each price in sequence
            position = {
                'ticket': 1001,
                'symbol': 'EURUSD',
                'type': 0,
                'entry_price': variation['entry'],
                'current_price': variation['entry'],
                'sl': 0.0,
                'tp': 0.0,
                'volume': 0.1
            }
            
            for i, price in enumerate(variation['prices']):
                position['current_price'] = price
                result = engine.process_all_positions([position])[0]
                
                expected = variation['expected_stages'][i]
                actual = result['stage']
                passed = (actual == expected)
                
                if not passed:
                    all_passed = False
                    print(f"    ❌ Price {price:.5f}: Expected {expected}, got {actual}")
                else:
                    print(f"    ✅ Price {price:.5f}: {actual}")
                
                results.append({
                    'variation': variation['name'],
                    'price': price,
                    'expected': expected,
                    'actual': actual,
                    'passed': passed
                })
        
        self.passed = all_passed
        self.result = {
            'total_variations': len(get_stage_progression_data()),
            'passed': all_passed,
            'details': results
        }
        
        if all_passed:
            print(f"  ✅ {self.test_id} PASSED")
        else:
            print(f"  ❌ {self.test_id} FAILED")
        
        return self.passed

class RegressionDetectionTest(TestScenario):
    """UT-002: Regression detection"""
    
    def __init__(self):
        super().__init__(
            test_id='UT-002',
            name='Regression Detection',
            description='Test regression detection logic',
            priority='P0'
        )
    
    def run(self, engine):
        from dummy_data import get_regression_data
        
        print(f"\n{self.test_id}: {self.name}")
        print("-" * 50)
        
        all_passed = True
        results = []
        
        for variation in get_regression_data():
            print(f"  Variation: {variation['name']}")
            
            position = {
                'ticket': 1002,
                'symbol': 'EURUSD',
                'type': 0,
                'entry_price': variation['entry'],
                'current_price': variation['entry'],
                'sl': 0.0,
                'tp': 0.0
            }
            
            regression_detected = False
            
            for price in variation['prices']:
                position['current_price'] = price
                result = engine.process_all_positions([position])[0]
                
                if result['regression_detected']:
                    regression_detected = True
            
            expected = variation['should_trigger']
            passed = (regression_detected == expected)
            
            if not passed:
                all_passed = False
                status = "detected" if regression_detected else "not detected"
                print(f"    ❌ Regression {status}, expected {'trigger' if expected else 'no trigger'}")
            else:
                print(f"    ✅ Regression {'triggered' if regression_detected else 'not triggered'} as expected")
            
            results.append({
                'variation': variation['name'],
                'regression_detected': regression_detected,
                'expected': expected,
                'passed': passed
            })
        
        self.passed = all_passed
        self.result = results
        
        if all_passed:
            print(f"  ✅ {self.test_id} PASSED")
        else:
            print(f"  ❌ {self.test_id} FAILED")
        
        return self.passed

# ================== MULTI-DAY TESTS ==================

class ThreeDaySteadyTest(TestScenario):
    """UT-015: 3-day holding (steady growth)"""
    
    def __init__(self):
        super().__init__(
            test_id='UT-015',
            name='3-Day Holding (Steady Growth)',
            description='Test position held for 3 days with steady growth',
            priority='P0'
        )
    
    def run(self, engine):
        from dummy_data import get_3day_steady_data
        
        print(f"\n{self.test_id}: {self.name}")
        print("-" * 50)
        
        data = get_3day_steady_data()
        print(f"  Testing {data['days']} days, {len(data['prices'])} cycles total")
        
        position = {
            'ticket': 1015,
            'symbol': 'EURUSD',
            'type': 0,
            'entry_price': data['entry'],
            'current_price': data['entry'],
            'sl': 0.0,
            'tp': 0.0
        }
        
        daily_stages = []
        
        # Process each cycle
        for i, price in enumerate(data['prices']):
            position['current_price'] = price
            result = engine.process_all_positions([position])[0]
            
            # Record end of day
            if (i + 1) % data['cycles_per_day'] == 0:
                day = (i + 1) // data['cycles_per_day']
                daily_stages.append({
                    'day': day,
                    'stage': result['stage'],
                    'price': price,
                    'sl': result['new_sl']
                })
                print(f"    Day {day}: Stage {result['stage']}, Price {price:.5f}")
        
        # Check final stage
        final_stage = result['stage']
        expected = data['expected_final_stage']
        passed = (final_stage == expected)
        
        self.passed = passed
        self.result = {
            'days': data['days'],
            'final_stage': final_stage,
            'expected_stage': expected,
            'daily_stages': daily_stages,
            'passed': passed
        }
        
        if passed:
            print(f"  ✅ {self.test_id} PASSED - Final stage: {final_stage}")
        else:
            print(f"  ❌ {self.test_id} FAILED - Expected {expected}, got {final_stage}")
        
        return passed

# ================== ALL SCENARIOS ==================

def get_all_scenarios():
    """Get all test scenarios"""
    return [
        # Core Logic Tests
        StageProgressionTest(),
        RegressionDetectionTest(),
        
        # Multi-Day Tests
        ThreeDaySteadyTest(),
        
        # Add more as needed...
    ]

def run_scenario_by_id(test_id):
    """Run a specific scenario by ID"""
    scenarios = get_all_scenarios()
    for scenario in scenarios:
        if scenario.test_id == test_id:
            return scenario
    return None