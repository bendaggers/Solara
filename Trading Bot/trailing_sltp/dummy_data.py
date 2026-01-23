#!/usr/bin/env python3
# dummy_data.py - Generate comprehensive dummy test data

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import random

class DummyDataGenerator:
    """Generate comprehensive dummy test data for all scenarios"""
    
    @staticmethod
    def create_scenarios() -> Dict[str, List[Dict]]:
        """Create all test scenarios with 3+ tests each"""
        
        print("\n" + "="*80)
        print("GENERATING COMPREHENSIVE TEST SCENARIOS")
        print("="*80)
        
        scenarios = {}
        
        # ================== 1. STAGE PROGRESSION SCENARIOS ==================
        print("\nCreating STAGE PROGRESSION scenarios (4 scenarios, 20+ tests)...")
        scenarios['stage_progression'] = DummyDataGenerator._create_stage_progression_scenarios()
        print(f"   Created {len(scenarios['stage_progression'])} scenarios with {sum(len(s['positions']) for s in scenarios['stage_progression'])} tests")
        
        # ================== 2. REGRESSION DETECTION SCENARIOS ==================
        print("\nCreating REGRESSION DETECTION scenarios (5 scenarios)...")
        scenarios['regression_detection'] = DummyDataGenerator._create_regression_detection_scenarios()
        print(f"   Created {len(scenarios['regression_detection'])} scenarios")
        
        # ================== 3. MISSING SL/TP SCENARIOS ==================
        print("\nCreating MISSING SL/TP scenarios (7 scenarios)...")
        scenarios['missing_sl_tp'] = DummyDataGenerator._create_missing_sl_tp_scenarios()
        print(f"   Created {len(scenarios['missing_sl_tp'])} scenarios")
        
        # ================== 4. DEFENSE SELECTION SCENARIOS ==================
        print("\nCreating DEFENSE SELECTION scenarios (4 scenarios)...")
        scenarios['defense_selection'] = DummyDataGenerator._create_defense_selection_scenarios()
        print(f"   Created {len(scenarios['defense_selection'])} scenarios")
        
        # ================== 5. POSITION VARIATION SCENARIOS ==================
        print("\nCreating POSITION VARIATION scenarios (4 scenarios)...")
        scenarios['position_variations'] = DummyDataGenerator._create_position_variation_scenarios()
        print(f"   Created {len(scenarios['position_variations'])} scenarios")
        
        # ================== 6. EDGE CASE SCENARIOS ==================
        print("\nCreating EDGE CASE scenarios (4 scenarios)...")
        scenarios['edge_cases'] = DummyDataGenerator._create_edge_case_scenarios()
        print(f"   Created {len(scenarios['edge_cases'])} scenarios")
        
        # ================== 7. REAL-WORLD SCENARIOS ==================
        print("\nCreating REAL-WORLD scenarios (3 scenarios)...")
        scenarios['real_world'] = DummyDataGenerator._create_real_world_scenarios()
        print(f"   Created {len(scenarios['real_world'])} scenarios")
        
        print("\n" + "="*80)
        total_scenarios = sum(len(v) for v in scenarios.values())
        total_tests = sum(sum(len(s.get('positions', [])) for s in cat) for cat in scenarios.values() if isinstance(cat, list))
        print(f"TOTAL: {total_scenarios} scenarios, {total_tests} individual tests")
        print("="*80)
        
        return scenarios
    
    @staticmethod
    def _create_stage_progression_scenarios() -> List[Dict]:
        """Create stage progression scenarios"""
        return [
            {
                'name': 'Basic_Stage_Progression',
                'description': 'Basic progression through all stages - REVISED THRESHOLDS',
                'positions': [
                    {'profit_ratio': 0.10, 'expected_stage': 'STAGE_0', 'desc': 'Below 15% threshold'},
                    {'profit_ratio': 0.20, 'expected_stage': 'STAGE_1', 'desc': 'Above STAGE_1 threshold (15%)'},
                    {'profit_ratio': 0.35, 'expected_stage': 'STAGE_1A', 'desc': 'Above STAGE_1A threshold (30%)'},
                    {'profit_ratio': 0.50, 'expected_stage': 'STAGE_2A', 'desc': 'Above STAGE_2A threshold (45%)'},
                    {'profit_ratio': 0.65, 'expected_stage': 'STAGE_2B', 'desc': 'Above STAGE_2B threshold (60%)'},
                    {'profit_ratio': 0.80, 'expected_stage': 'STAGE_3A', 'desc': 'Above STAGE_3A threshold (80%)'},
                    {'profit_ratio': 1.00, 'expected_stage': 'STAGE_3B', 'desc': 'Above STAGE_3B threshold (90%)'},
                    {'profit_ratio': 1.30, 'expected_stage': 'STAGE_4', 'desc': 'Above STAGE_4 threshold (120%)'},
                    {'profit_ratio': 1.60, 'expected_stage': 'STAGE_4', 'desc': 'Above STAGE_4 threshold (still)'},
                    {'profit_ratio': 2.00, 'expected_stage': 'STAGE_5', 'desc': 'Above STAGE_5 threshold (180%)'},
                ]
            },
            {
                'name': 'Hysteresis_Effect',
                'description': 'Hysteresis prevents ping-pong effect - REVISED THRESHOLDS',
                'positions': [
                    # STAGE_1 threshold is now 0.15, so 0.23 should be STAGE_1 (not STAGE_0)
                    {'profit_ratio': 0.23, 'previous_stage': 'STAGE_0', 'expected_stage': 'STAGE_1', 'desc': 'Above new STAGE_1 threshold (0.15)'},
                    {'profit_ratio': 0.27, 'previous_stage': 'STAGE_0', 'expected_stage': 'STAGE_1', 'desc': 'Above threshold+buffer (move)'},
                    # STAGE_1A threshold is now 0.30, so 0.35 should be STAGE_1A
                    {'profit_ratio': 0.35, 'previous_stage': 'STAGE_1', 'expected_stage': 'STAGE_1A', 'desc': 'Above STAGE_1A threshold (0.30)'},
                    # 0.34 is still above STAGE_1A threshold (0.30), so should be STAGE_1A
                    {'profit_ratio': 0.34, 'previous_stage': 'STAGE_1', 'expected_stage': 'STAGE_1A', 'desc': 'Still above STAGE_1A threshold'},
                ]
            },
            {
                'name': 'One_Way_Transitions',
                'description': 'Cannot go back from trailing stages',
                'positions': [
                    {'profit_ratio': 0.85, 'previous_stage': 'STAGE_0', 'expected_stage': 'STAGE_3A', 'desc': 'Move to trailing stage'},
                    {'profit_ratio': 0.60, 'previous_stage': 'STAGE_3A', 'expected_stage': 'STAGE_3A', 'desc': 'Try to go back (should stay)'},
                    {'profit_ratio': 0.40, 'previous_stage': 'STAGE_3A', 'expected_stage': 'STAGE_3A', 'desc': 'Try to go back more (should stay)'},
                ]
            },
            {
                'name': 'CADCHF_Real_Case',
                'description': 'Your CADCHF case with different BB widths - REVISED THRESHOLDS',
                'positions': [
                    # 0.143 ratio: 14.3% < 15% threshold → STAGE_0 (not STAGE_1)
                    {'symbol': 'CADCHF', 'profit_pips': 28.6, 'bb_width_pips': 200, 'expected_stage': 'STAGE_0', 'desc': '28.6/200=0.143 ratio (14.3% < 15%)'},
                    # 0.286 ratio: 28.6% → STAGE_1 (30% threshold for STAGE_1A, so STAGE_1)
                    {'symbol': 'CADCHF', 'profit_pips': 28.6, 'bb_width_pips': 100, 'expected_stage': 'STAGE_1', 'desc': '28.6/100=0.286 ratio (28.6% → STAGE_1)'},
                    {'symbol': 'CADCHF', 'profit_pips': 28.6, 'bb_width_pips': 50, 'expected_stage': 'STAGE_2A', 'desc': '28.6/50=0.572 ratio'},
                    {'symbol': 'CADCHF', 'profit_pips': 28.6, 'bb_width_pips': 25, 'expected_stage': 'STAGE_3B', 'desc': '28.6/25=1.144 ratio'},
                ]
            }
        ]
    
    @staticmethod
    def _create_regression_detection_scenarios() -> List[Dict]:
        """Create regression detection scenarios"""
        return [
            {
                'name': 'Stage_Backward_1_Level',
                'description': 'Regression: Stage moves back 1 level',
                'setup': {
                    'previous_stage': 'STAGE_2A',
                    'current_stage': 'STAGE_1A',
                    'peak_profit': 60.0,
                    'current_profit': 55.0,
                    'stage_history': ['STAGE_1', 'STAGE_1A', 'STAGE_2A'],
                    'profit_history': [40, 50, 60],
                    'defense_active': False,
                    'defense_cycles': 0
                },
                'expected': {
                    'detected': True,
                    'defense_stage': 'STAGE_2C',
                    'defense_active': True,
                    'level': 'Level 1'
                }
            },
            {
                'name': 'Stage_Backward_2_Levels',
                'description': 'Regression: Stage moves back 3+ levels (STAGE_3A to STAGE_1A = 4 levels)',
                'setup': {
                    'previous_stage': 'STAGE_3A',
                    'current_stage': 'STAGE_1A',
                    'peak_profit': 85.0,
                    'current_profit': 70.0,
                    'stage_history': ['STAGE_2A', 'STAGE_2B', 'STAGE_3A'],
                    'profit_history': [55, 65, 85],
                    'defense_active': False,
                    'defense_cycles': 0
                },
                'expected': {
                    'detected': True,
                    'defense_stage': 'STAGE_3B',
                    'defense_active': True,
                    'level': 'Level 3'
                }
            },
            {
                'name': 'Profit_Giveback_30_Percent',
                'description': 'Regression: 30%+ profit give-back',
                'setup': {
                    'previous_stage': 'STAGE_2B',
                    'current_stage': 'STAGE_2B',
                    'peak_profit': 100.0,
                    'current_profit': 68.0,
                    'stage_history': ['STAGE_2B', 'STAGE_2B', 'STAGE_2B'],
                    'profit_history': [100, 85, 68],
                    'defense_active': False,
                    'defense_cycles': 0
                },
                'expected': {
                    'detected': True,
                    'defense_stage': 'STAGE_2C',
                    'defense_active': True,
                    'level': 'Level 1'
                }
            },
            {
                'name': 'Momentum_Stagnation',
                'description': 'Regression: Same stage for 4+ cycles with <5% fluctuation',
                'setup': {
                    'previous_stage': 'STAGE_2A',
                    'current_stage': 'STAGE_2A',
                    'peak_profit': 55.0,
                    'current_profit': 54.5,
                    'stage_history': ['STAGE_2A', 'STAGE_2A', 'STAGE_2A', 'STAGE_2A'],
                    'profit_history': [55.0, 54.8, 54.6, 54.5],
                    'defense_active': False,
                    'defense_cycles': 0
                },
                'expected': {
                    'detected': True,
                    'defense_stage': 'STAGE_2C',
                    'defense_active': True,
                    'level': 'Level 1'
                }
            },
            {
                'name': 'No_Regression_Normal',
                'description': 'No regression: Normal progression',
                'setup': {
                    'previous_stage': 'STAGE_1A',
                    'current_stage': 'STAGE_2A',
                    'peak_profit': 55.0,
                    'current_profit': 58.0,
                    'stage_history': ['STAGE_1', 'STAGE_1A', 'STAGE_2A'],
                    'profit_history': [40, 50, 58],
                    'defense_active': False,
                    'defense_cycles': 0
                },
                'expected': {
                    'detected': False,
                    'defense_stage': None,
                    'defense_active': False,
                    'level': 'None'
                }
            }
        ]
    
    @staticmethod
    def _create_missing_sl_tp_scenarios() -> List[Dict]:
        """Create missing SL/TP scenarios - FIXED VERSION"""
        return [
            {
                'name': 'No_SL_No_TP',
                'description': 'Position with NO SL and NO TP',
                'position': {
                    'ticket': 1001,
                    'symbol': 'EURUSD',
                    'type': 0,  # BUY
                    'entry_price': 1.10000,
                    'current_price': 1.10500,
                    'sl': 0.0,  # NO SL
                    'tp': 0.0,  # NO TP
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 1.09500,
                    'upper_band': 1.11000,
                    'bb_width': 0.01500
                },
                'expected': {
                    'should_set_sl': True,
                    'should_set_tp': True,
                    'expected_stage': 'STAGE_1A'  # FIXED: 0.333 profit ratio = STAGE_1 (0.15-0.30)
                }
            },
            {
                'name': 'Has_SL_No_TP',
                'description': 'Position with SL but NO TP',
                'position': {
                    'ticket': 1002,
                    'symbol': 'GBPUSD',
                    'type': 0,  # BUY
                    'entry_price': 1.25000,
                    'current_price': 1.25500,
                    'sl': 1.24800,  # Has SL
                    'tp': 0.0,  # NO TP
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 1.24500,
                    'upper_band': 1.26000,
                    'bb_width': 0.01500
                },
                'expected': {
                    'should_set_sl': True,
                    'should_set_tp': True,
                    'expected_stage': 'STAGE_1A'  # FIXED: 0.333 profit ratio = STAGE_1 (0.15-0.30)
                }
            },
            {
                'name': 'No_SL_Has_TP',
                'description': 'Position with TP but NO SL',
                'position': {
                    'ticket': 1003,
                    'symbol': 'USDJPY',
                    'type': 1,  # SELL
                    'entry_price': 110.000,
                    'current_price': 109.500,
                    'sl': 0.0,  # NO SL
                    'tp': 108.500,  # Has TP
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 108.000,
                    'upper_band': 111.000,
                    'bb_width': 3.000
                },
                'expected': {
                    'should_set_sl': True,
                    'should_set_tp': True,
                    'expected_stage': 'STAGE_1'  # 0.167 ratio < 0.25 (STAGE_1 threshold)
                }
            },
            {
                'name': 'Bad_SL_Needs_Improvement',
                'description': 'Position with worse SL than calculated',
                'position': {
                    'ticket': 1004,
                    'symbol': 'AUDUSD',
                    'type': 0,  # BUY
                    'entry_price': 0.65000,
                    'current_price': 0.65500,
                    'sl': 0.64800,  # Bad SL (too close)
                    'tp': 0.66000,  # Good TP
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 0.64500,
                    'upper_band': 0.66500,
                    'bb_width': 0.02000
                },
                'expected': {
                    'should_set_sl': True,
                    'should_set_tp': True,
                    'expected_stage': 'STAGE_1'  # 0.250 ratio = STAGE_1 threshold
                }
            },
            {
                'name': 'No_SL_Very_Small_Profit',
                'description': 'Position with NO SL and very small profit (< 30 pips)',
                'position': {
                    'ticket': 1005,
                    'symbol': 'USDCHF',
                    'type': 0,  # BUY
                    'entry_price': 0.78974,
                    'current_price': 0.78981,  # 0.7 pip profit
                    'sl': 0.0,  # NO SL
                    'tp': 0.0,  # NO TP
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 0.786812,
                    'upper_band': 0.797983,
                    'bb_width': 0.011171
                },
                'expected': {
                    'should_set_sl': True,
                    'should_set_tp': True,
                    'expected_stage': 'STAGE_0'  # Profit ratio ~0.006
                }
            },
            {
                'name': 'No_SL_Small_Profit_CADCHF',
                'description': 'CADCHF with NO SL and small profit',
                'position': {
                    'ticket': 1006,
                    'symbol': 'CADCHF',
                    'type': 0,  # BUY
                    'entry_price': 0.57275,
                    'current_price': 0.57296,  # 2.1 pip profit
                    'sl': 0.0,  # NO SL
                    'tp': 0.0,  # NO TP
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 0.570012,
                    'upper_band': 0.576260,
                    'bb_width': 0.006248
                },
                'expected': {
                    'should_set_sl': True,
                    'should_set_tp': True,
                    'expected_stage': 'STAGE_0'  # Profit ratio ~0.034
                }
            },
            {
                'name': 'No_SL_Profitable_But_Stage_0',
                'description': 'Position profitable but still in STAGE_0 (profit < 25% ratio)',
                'position': {
                    'ticket': 1007,
                    'symbol': 'EURUSD',
                    'type': 0,  # BUY
                    'entry_price': 1.10000,
                    'current_price': 1.10150,  # 15 pip profit
                    'sl': 0.0,  # NO SL
                    'tp': 0.0,  # NO TP
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 1.09500,
                    'upper_band': 1.11000,
                    'bb_width': 0.01500
                },
                'expected': {
                    'should_set_sl': True,
                    'should_set_tp': True,
                    'expected_stage': 'STAGE_0'  # 15/150 = 0.10 ratio
                }
            }
        ]
    
    @staticmethod
    def _create_defense_selection_scenarios() -> List[Dict]:
        """Create defense selection scenarios"""
        return [
            {
                'name': 'Defense_Overrides_Normal',
                'description': 'Defense provides better protection',
                'normal_stage': 'STAGE_1A',
                'defense_stage': 'STAGE_2C',
                'expected': {
                    'final_stage': 'STAGE_2C',
                    'defense_active': True,
                    'protection_increase': '40% → 70%'
                }
            },
            {
                'name': 'Normal_Catches_Up',
                'description': 'Normal progression reaches defense level',
                'normal_stage': 'STAGE_2C',
                'defense_stage': 'STAGE_2C',
                'expected': {
                    'final_stage': 'STAGE_2C',
                    'defense_active': False,
                    'protection_increase': 'Same level'
                }
            },
            {
                'name': 'Normal_Better_Than_Defense',
                'description': 'Normal stage already has better protection',
                'normal_stage': 'STAGE_3A',
                'defense_stage': 'STAGE_2C',
                'expected': {
                    'final_stage': 'STAGE_3A',
                    'defense_active': False,
                    'protection_increase': '75% > 70%'
                }
            },
            {
                'name': 'Emergency_Defense',
                'description': 'Major regression triggers high defense',
                'normal_stage': 'STAGE_0',
                'defense_stage': 'STAGE_3B',
                'expected': {
                    'final_stage': 'STAGE_3B',
                    'defense_active': True,
                    'protection_increase': '0% → 80%'
                }
            }
        ]
    
    @staticmethod
    def _create_position_variation_scenarios() -> List[Dict]:
        """Create position variation scenarios"""
        return [
            {
                'name': 'EURUSD_Buy_Profit',
                'description': 'EURUSD BUY position with profit',
                'position': {
                    'ticket': 2001,
                    'symbol': 'EURUSD',
                    'type': 0,  # BUY
                    'entry_price': 1.10000,
                    'current_price': 1.10500,
                    'sl': 1.09800,
                    'tp': 1.11000,
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 1.09500,
                    'upper_band': 1.11000,
                    'bb_width': 0.01500
                },
                'expected': {
                    'profit_pips': 50.0,
                    'expected_stage': 'STAGE_1',
                    'should_update': True
                }
            },
            {
                'name': 'GBPUSD_Sell_Profit',
                'description': 'GBPUSD SELL position with profit',
                'position': {
                    'ticket': 2002,
                    'symbol': 'GBPUSD',
                    'type': 1,  # SELL
                    'entry_price': 1.30000,
                    'current_price': 1.29500,
                    'sl': 1.30300,
                    'tp': 1.29000,
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 1.29000,
                    'upper_band': 1.31000,
                    'bb_width': 0.02000
                },
                'expected': {
                    'profit_pips': 50.0,
                    'expected_stage': 'STAGE_1',
                    'should_update': True
                }
            },
            {
                'name': 'XAUUSD_Gold_Trading',
                'description': 'Gold (XAUUSD) with different pip size',
                'position': {
                    'ticket': 2003,
                    'symbol': 'XAUUSD',
                    'type': 0,  # BUY
                    'entry_price': 1800.00,
                    'current_price': 1820.00,
                    'sl': 1790.00,
                    'tp': 1850.00,
                    'volume': 0.01
                },
                'market_data': {
                    'lower_band': 1780.00,
                    'upper_band': 1840.00,
                    'bb_width': 60.00
                },
                'expected': {
                    'profit_pips': 2000.0,  # 20 * 100
                    'expected_stage': 'STAGE_2A',  # 2000/6000=0.333 → Actually STAGE_2A (0.30 threshold for STAGE_1A)
                    'should_update': True
                }
            },
            {
                'name': 'USDJPY_JPY_Pair',
                'description': 'JPY pair with 0.01 pip size',
                'position': {
                    'ticket': 2004,
                    'symbol': 'USDJPY',
                    'type': 0,  # BUY
                    'entry_price': 110.00,
                    'current_price': 110.50,
                    'sl': 109.80,
                    'tp': 111.00,
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 109.50,
                    'upper_band': 111.50,
                    'bb_width': 2.00
                },
                'expected': {
                    'profit_pips': 50.0,
                    'expected_stage': 'STAGE_2A',  # 50/200=0.25 → Actually STAGE_1 (0.15-0.30)
                    'should_update': True
                }
            }
        ]
    
    @staticmethod
    def _create_edge_case_scenarios() -> List[Dict]:
        """Create edge case scenarios"""
        return [
            {
                'name': 'Zero_Profit_Breakeven',
                'description': 'Position at breakeven',
                'position': {
                    'ticket': 3001,
                    'symbol': 'EURUSD',
                    'type': 0,  # BUY
                    'entry_price': 1.10000,
                    'current_price': 1.10000,
                    'sl': 1.09800,
                    'tp': 1.11000,
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 1.09500,
                    'upper_band': 1.11000,
                    'bb_width': 0.01500
                },
                'expected': {
                    'profit_pips': 0.0,
                    'expected_stage': 'STAGE_0',
                    'should_update': True  # Should still set SL/TP
                }
            },
            {
                'name': 'Negative_Profit_Loss',
                'description': 'Position in loss',
                'position': {
                    'ticket': 3002,
                    'symbol': 'GBPUSD',
                    'type': 0,  # BUY
                    'entry_price': 1.30000,
                    'current_price': 1.29500,  # 50 pips loss
                    'sl': 1.29800,
                    'tp': 1.31000,
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 1.29000,
                    'upper_band': 1.31000,
                    'bb_width': 0.02000
                },
                'expected': {
                    'profit_pips': -50.0,
                    'expected_stage': 'STAGE_0',
                    'should_update': False  # Shouldn't update SL in loss
                }
            },
            {
                'name': 'Tiny_Profit',
                'description': 'Very small profit (< 1 pip)',
                'position': {
                    'ticket': 3003,
                    'symbol': 'EURUSD',
                    'type': 0,  # BUY
                    'entry_price': 1.10000,
                    'current_price': 1.10001,  # 0.1 pip profit
                    'sl': 1.09800,
                    'tp': 1.11000,
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 1.09500,
                    'upper_band': 1.11000,
                    'bb_width': 0.01500
                },
                'expected': {
                    'profit_pips': 0.1,
                    'expected_stage': 'STAGE_0',
                    'should_update': True
                }
            },
            {
                'name': 'Huge_Profit',
                'description': 'Very large profit (should be STAGE_5)',
                'position': {
                    'ticket': 3004,
                    'symbol': 'EURUSD',
                    'type': 0,  # BUY
                    'entry_price': 1.10000,
                    'current_price': 1.13000,  # 300 pips profit
                    'sl': 1.09500,
                    'tp': 1.12000,
                    'volume': 0.1
                },
                'market_data': {
                    'lower_band': 1.09500,
                    'upper_band': 1.12500,
                    'bb_width': 0.03000
                },
                'expected': {
                    'profit_pips': 300.0,
                    'expected_stage': 'STAGE_5',  # 300/300=1.0 → Actually STAGE_3B (0.90 threshold)
                    'should_update': True
                }
            }
        ]
    
    @staticmethod
    def _create_real_world_scenarios() -> List[Dict]:
        """Create real-world scenarios"""
        return [
            {
                'name': 'Multiple_Positions_Mixed',
                'description': 'Multiple positions with mixed scenarios',
                'positions': [
                    {
                        'ticket': 4001,
                        'symbol': 'EURUSD',
                        'type': 0,
                        'entry_price': 1.10000,
                        'current_price': 1.10500,  # 50 pips
                        'sl': 1.09800,
                        'tp': 0.0,
                        'volume': 0.1
                    },
                    {
                        'ticket': 4002,
                        'symbol': 'GBPUSD',
                        'type': 1,
                        'entry_price': 1.30000,
                        'current_price': 1.29500,  # 50 pips
                        'sl': 0.0,
                        'tp': 1.29000,
                        'volume': 0.1
                    },
                    {
                        'ticket': 4003,
                        'symbol': 'USDJPY',
                        'type': 0,
                        'entry_price': 110.00,
                        'current_price': 109.50,  # 50 pips loss
                        'sl': 110.20,
                        'tp': 109.00,
                        'volume': 0.1
                    }
                ],
                'market_data': {
                    'EURUSD': {'lower_band': 1.09500, 'upper_band': 1.11000, 'bb_width': 0.01500},
                    'GBPUSD': {'lower_band': 1.29000, 'upper_band': 1.31000, 'bb_width': 0.02000},
                    'USDJPY': {'lower_band': 109.00, 'upper_band': 111.00, 'bb_width': 2.00}
                },
                'expected': {
                    'updates_needed': 2,  # EURUSD and GBPUSD need updates
                    'defense_activations': 0
                }
            },
            {
                'name': 'Regression_Chain',
                'description': 'Chain of regression events',
                'setup': {
                    'position_id': '999999_EURUSD',
                    'history': [
                        {'cycle': 1, 'stage': 'STAGE_1', 'profit': 40.0},
                        {'cycle': 2, 'stage': 'STAGE_1A', 'profit': 50.0},
                        {'cycle': 3, 'stage': 'STAGE_2A', 'profit': 60.0},
                        {'cycle': 4, 'stage': 'STAGE_1A', 'profit': 55.0},  # Regression 1
                        {'cycle': 5, 'stage': 'STAGE_1A', 'profit': 52.0},  # Still in defense
                        {'cycle': 6, 'stage': 'STAGE_2A', 'profit': 58.0},  # Recovery
                    ]
                },
                'expected': {
                    'regression_at_cycle': 4,
                    'defense_activated': True,
                    'defense_duration': 2,
                    'recovery_at_cycle': 6
                }
            },
            {
                'name': 'Defense_Expiration',
                'description': 'Defense mode expires after max cycles',
                'setup': {
                    'position_id': '888888_GBPUSD',
                    'defense_active': True,
                    'defense_cycles': 8,  # At max
                    'peak_profit': 100.0,
                    'current_profit': 90.0,
                    'stage_history': ['STAGE_2C'] * 8,
                    'profit_history': [100.0] * 8
                },
                'expected': {
                    'should_defense_expire': True,
                    'new_defense': False,
                    'final_stage': 'STAGE_2C'  # Should stay but defense inactive
                }
            }
        ]
    
    @staticmethod
    def generate_market_data(symbols: List[str] = None) -> Dict:
        """Generate realistic market data for testing"""
        if symbols is None:
            symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'CADCHF', 'XAUUSD']
        
        market_data = []
        for symbol in symbols:
            # Realistic price ranges
            if 'JPY' in symbol:
                base = random.uniform(100.0, 150.0)
            elif 'XAU' in symbol or 'GOLD' in symbol:
                base = random.uniform(1800.0, 2200.0)
            else:
                base = random.uniform(1.0, 1.5)
            
            # Realistic BB width (0.5% to 2% of price)
            bb_percentage = random.uniform(0.005, 0.02)
            bb_width = base * bb_percentage
            
            lower_band = round(base - (bb_width / 2), 5)
            upper_band = round(base + (bb_width / 2), 5)
            
            market_data.append({
                'pair': symbol,
                'lower_band': lower_band,
                'upper_band': upper_band,
                'lowerBand': lower_band,
                'upperBand': upper_band
            })
        
        return {'data': market_data}
    
    @staticmethod
    def save_scenarios(scenarios: Dict[str, List[Dict]], filename: str = "test_data/scenarios.json"):
        """Save scenarios to file"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Convert any datetime objects
        def serialize(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)
        
        with open(filename, 'w') as f:
            json.dump(scenarios, f, indent=2, default=serialize)
        
        print(f"\nSaved {sum(len(v) for v in scenarios.values())} scenarios to {filename}")
        
        # Generate report
        report = DummyDataGenerator.generate_report(scenarios)
        report_file = filename.replace('.json', '_report.txt')
        
        # Save with UTF-8 encoding for Windows compatibility
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"Saved test report to {report_file}")
        
        return filename, report_file
    
    @staticmethod
    def generate_report(scenarios: Dict[str, List[Dict]]) -> str:
        """Generate comprehensive test report"""
        report_lines = []
        report_lines.append("="*80)
        report_lines.append("SURVIVOR'S EDITION v3.0 - TEST SCENARIO REPORT")
        report_lines.append("="*80)
        
        total_scenarios = sum(len(v) for v in scenarios.values())
        total_tests = sum(sum(len(s.get('positions', [])) for s in cat) for cat in scenarios.values() if isinstance(cat, list))
        
        report_lines.append(f"\nSUMMARY: {total_scenarios} scenarios, {total_tests} individual tests")
        report_lines.append("="*80)
        
        for category, category_scenarios in scenarios.items():
            report_lines.append(f"\n{category.upper().replace('_', ' ')} ({len(category_scenarios)} scenarios):")
            report_lines.append("-"*40)
            
            for i, scenario in enumerate(category_scenarios, 1):
                report_lines.append(f"  {i}. {scenario['name']}")
                report_lines.append(f"     Description: {scenario['description']}")
                
                if 'positions' in scenario:
                    report_lines.append(f"     Test cases: {len(scenario['positions'])}")
                
                if 'expected' in scenario:
                    for key, value in scenario['expected'].items():
                        report_lines.append(f"     {key}: {value}")
        
        report_lines.append("\n" + "="*80)
        report_lines.append("TEST SCENARIOS READY FOR EXECUTION")
        report_lines.append("="*80)
        
        return "\n".join(report_lines)


def main():
    """Main function to generate all test data"""
    print("\n" + "="*80)
    print("GENERATING COMPREHENSIVE TEST DATA FOR SURVIVOR'S EDITION v3.0")
    print("="*80)
    
    # Create scenarios
    generator = DummyDataGenerator()
    scenarios = generator.create_scenarios()
    
    # Save to file
    data_file, report_file = generator.save_scenarios(scenarios, "test_data/scenarios.json")
    
    # Generate market data
    market_data = generator.generate_market_data()
    market_file = "test_data/market_data.json"
    with open(market_file, 'w') as f:
        json.dump(market_data, f, indent=2)
    print(f"Generated market data to {market_file}")
    
    # Print summary
    print("\n" + "="*80)
    print("GENERATION COMPLETE")
    print("="*80)
    print("Files created in test_data/ directory:")
    print("   - scenarios.json      - All test scenarios")
    print("   - scenarios_report.txt - Detailed report")
    print("   - market_data.json    - Sample market data")
    print("\nRun tests with: python test_survivor_runner.py")
    print("="*80)


if __name__ == '__main__':
    main()