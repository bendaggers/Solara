{
  "metadata": {
    "generated_date": "2024-01-15T00:00:00Z",
    "version": "3.0",
    "description": "Comprehensive dummy data for Survivor's Edition v3.0 testing - 48+ test scenarios"
  },
  
  "market_data": {
    "data": [
      {
        "pair": "EURUSD",
        "lower_band": 1.08245,
        "upper_band": 1.09245,
        "lowerBand": 1.08245,
        "upperBand": 1.09245,
        "bb_width": 0.01000,
        "current_price": 1.08745,
        "description": "Standard Forex pair - BB width 100 pips"
      },
      {
        "pair": "USDJPY",
        "lower_band": 145.230,
        "upper_band": 146.230,
        "lowerBand": 145.230,
        "upperBand": 146.230,
        "bb_width": 1.000,
        "current_price": 145.730,
        "description": "JPY pair - BB width 100 pips (JPY pip = 0.01)"
      },
      {
        "pair": "GBPJPY",
        "lower_band": 183.450,
        "upper_band": 184.450,
        "bb_width": 1.000,
        "current_price": 183.950,
        "description": "JPY cross pair"
      },
      {
        "pair": "XAUUSD",
        "lower_band": 2020.50,
        "upper_band": 2030.50,
        "bb_width": 10.00,
        "current_price": 2025.50,
        "description": "Gold - pip = 0.01"
      },
      {
        "pair": "US30",
        "lower_band": 37500.0,
        "upper_band": 37700.0,
        "bb_width": 200.0,
        "current_price": 37600.0,
        "description": "Dow Jones - pip = 1.0"
      },
      {
        "pair": "BTCUSD",
        "lower_band": 42000.0,
        "upper_band": 44000.0,
        "bb_width": 2000.0,
        "current_price": 43000.0,
        "description": "Bitcoin - pip = 1.0"
      },
      {
        "pair": "AUDCAD",
        "lower_band": 0.88850,
        "upper_band": 0.89850,
        "bb_width": 0.01000,
        "current_price": 0.89350,
        "description": "Minor Forex pair"
      },
      {
        "pair": "EURUSD_NARROW",
        "lower_band": 1.08700,
        "upper_band": 1.08800,
        "bb_width": 0.00100,
        "current_price": 1.08750,
        "description": "Narrow BB for edge cases - width 10 pips"
      },
      {
        "pair": "EURUSD_WIDE",
        "lower_band": 1.07000,
        "upper_band": 1.11000,
        "bb_width": 0.04000,
        "current_price": 1.09000,
        "description": "Wide BB for extreme profits - width 400 pips"
      },
      {
        "pair": "MISSING_DATA",
        "lower_band": 0.00000,
        "upper_band": 0.00000,
        "bb_width": 0.00000,
        "current_price": 1.00000,
        "description": "Zero BB width for error testing"
      }
    ]
  },
  
  "test_positions": {
    "category_a_core_logic": [
      {
        "test_id": "UT-001_STAGE_0",
        "ticket": 1001,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08570,
        "volume": 0.1,
        "profit": 7.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "STAGE_0: 7 pips profit (7% of 100p BB) - should stay STAGE_0"
      },
      {
        "test_id": "UT-001_STAGE_1",
        "ticket": 1002,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08650,
        "volume": 0.1,
        "profit": 15.0,
        "sl": 1.08200,
        "tp": 1.09245,
        "description": "STAGE_1: 15 pips profit (15% threshold) - should advance to STAGE_1"
      },
      {
        "test_id": "UT-001_STAGE_1A",
        "ticket": 1003,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08800,
        "volume": 0.1,
        "profit": 30.0,
        "sl": 1.08425,
        "tp": 1.09245,
        "description": "STAGE_1A: 30 pips profit (30% threshold)"
      },
      {
        "test_id": "UT-001_STAGE_2A",
        "ticket": 1004,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08950,
        "volume": 0.1,
        "profit": 45.0,
        "sl": 1.08625,
        "tp": 1.09245,
        "description": "STAGE_2A: 45 pips profit (45% threshold)"
      },
      {
        "test_id": "UT-001_STAGE_2B",
        "ticket": 1005,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.09100,
        "volume": 0.1,
        "profit": 60.0,
        "sl": 1.08800,
        "tp": 1.09245,
        "description": "STAGE_2B: 60 pips profit (60% threshold)"
      },
      {
        "test_id": "UT-001_STAGE_2C",
        "ticket": 1006,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.09200,
        "volume": 0.1,
        "profit": 70.0,
        "sl": 1.09000,
        "tp": 0.0,
        "description": "STAGE_2C: 70 pips profit (70% threshold) - no TP"
      },
      {
        "test_id": "UT-001_STAGE_3A",
        "ticket": 1007,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.09300,
        "volume": 0.1,
        "profit": 80.0,
        "sl": 1.09140,
        "tp": 0.0,
        "description": "STAGE_3A: 80 pips profit (80% threshold)"
      },
      {
        "test_id": "UT-001_STAGE_3B",
        "ticket": 1008,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.09500,
        "volume": 0.1,
        "profit": 100.0,
        "sl": 1.09300,
        "tp": 0.0,
        "description": "STAGE_3B: 100 pips profit (100% threshold)"
      },
      {
        "test_id": "UT-001_STAGE_4",
        "ticket": 1009,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.09700,
        "volume": 0.1,
        "profit": 120.0,
        "sl": 1.09580,
        "tp": 0.0,
        "description": "STAGE_4: 120 pips profit (120% threshold)"
      },
      {
        "test_id": "UT-001_STAGE_5",
        "ticket": 1010,
        "symbol": "EURUSD_WIDE",
        "type": 0,
        "entry_price": 1.07000,
        "current_price": 1.10600,
        "volume": 0.1,
        "profit": 360.0,
        "sl": 1.10240,
        "tp": 0.0,
        "description": "STAGE_5: 360 pips profit (180% of 200p BB)"
      }
    ],
    
    "category_b_order_types": [
      {
        "test_id": "UT-008_BUY_PROGRESSION",
        "ticket": 2001,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08000,
        "current_price": 1.09400,
        "volume": 0.1,
        "profit": 140.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "BUY order at 140 pips profit - should be STAGE_4"
      },
      {
        "test_id": "UT-009_SELL_PROGRESSION",
        "ticket": 2002,
        "symbol": "EURUSD",
        "type": 1,
        "entry_price": 1.09500,
        "current_price": 1.08100,
        "volume": 0.1,
        "profit": 140.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "SELL order at 140 pips profit - inverted logic test"
      },
      {
        "test_id": "UT-010_MIXED_1",
        "ticket": 2003,
        "symbol": "USDJPY",
        "type": 0,
        "entry_price": 145.000,
        "current_price": 146.200,
        "volume": 0.1,
        "profit": 120.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "JPY BUY - verify pip size 0.01"
      },
      {
        "test_id": "UT-010_MIXED_2",
        "ticket": 2004,
        "symbol": "US30",
        "type": 1,
        "entry_price": 37800.0,
        "current_price": 37400.0,
        "volume": 0.1,
        "profit": 400.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Index SELL - verify pip size 1.0"
      },
      {
        "test_id": "UT-011_LOSS_MAKING",
        "ticket": 2005,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.09000,
        "current_price": 1.08800,
        "volume": 0.1,
        "profit": -20.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Loss position: -20 pips - should stay STAGE_0"
      },
      {
        "test_id": "UT-012_BREAKEVEN",
        "ticket": 2006,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08745,
        "current_price": 1.08755,
        "volume": 0.1,
        "profit": 1.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Breakeven: +1 pip - should stay STAGE_0"
      },
      {
        "test_id": "UT-013_EXTREME_PROFIT",
        "ticket": 2007,
        "symbol": "EURUSD_WIDE",
        "type": 0,
        "entry_price": 1.07000,
        "current_price": 1.15000,
        "volume": 0.1,
        "profit": 800.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Extreme: 800 pips profit (200% of 400p BB) - max STAGE_5"
      },
      {
        "test_id": "UT-014_CRYPTO",
        "ticket": 2008,
        "symbol": "BTCUSD",
        "type": 0,
        "entry_price": 42500.0,
        "current_price": 43500.0,
        "volume": 0.01,
        "profit": 1000.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Crypto: 1000 pips profit (50% of 2000p BB)"
      }
    ],
    
    "category_c_multi_day": [
      {
        "test_id": "UT-015_3DAY_STEADY",
        "ticket": 3001,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08950,
        "volume": 0.1,
        "profit": 45.0,
        "sl": 1.08200,
        "tp": 1.09245,
        "history": [
          {"cycle": 1, "price": 1.08570, "profit_pips": 7, "stage": "STAGE_0"},
          {"cycle": 2, "price": 1.08720, "profit_pips": 22, "stage": "STAGE_1"},
          {"cycle": 3, "price": 1.08950, "profit_pips": 45, "stage": "STAGE_2A"}
        ],
        "description": "3-day steady growth test position"
      },
      {
        "test_id": "UT-016_5DAY_VOLATILE",
        "ticket": 3002,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.09000,
        "volume": 0.1,
        "profit": 50.0,
        "sl": 1.08600,
        "tp": 1.09245,
        "history": [
          {"cycle": 1, "price": 1.08700, "profit_pips": 20, "stage": "STAGE_1"},
          {"cycle": 2, "price": 1.08900, "profit_pips": 40, "stage": "STAGE_1A"},
          {"cycle": 3, "price": 1.08800, "profit_pips": 30, "stage": "STAGE_1A"},
          {"cycle": 4, "price": 1.09100, "profit_pips": 60, "stage": "STAGE_2B"},
          {"cycle": 5, "price": 1.09000, "profit_pips": 50, "stage": "STAGE_2A"}
        ],
        "description": "5-day volatile position with regression"
      }
    ],
    
    "category_d_edge_cases": [
      {
        "test_id": "UT-023_NO_MARKET_DATA",
        "ticket": 4001,
        "symbol": "UNKNOWN",
        "type": 0,
        "entry_price": 1.00000,
        "current_price": 1.01000,
        "volume": 0.1,
        "profit": 100.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Symbol not in market data - should handle gracefully"
      },
      {
        "test_id": "UT-025_INVALID_SL",
        "ticket": 4002,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.09000,
        "volume": 0.1,
        "profit": 50.0,
        "sl": 1.08999,
        "tp": 0.0,
        "description": "SL too close (0.1 pip from price) - should be adjusted"
      },
      {
        "test_id": "UT-026_ZERO_BB",
        "ticket": 4003,
        "symbol": "MISSING_DATA",
        "type": 0,
        "entry_price": 1.00000,
        "current_price": 1.00100,
        "volume": 0.1,
        "profit": 100.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Zero BB width - division by zero protection"
      },
      {
        "test_id": "UT-027_OUTSIDE_BB",
        "ticket": 4004,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.07000,
        "current_price": 1.09500,
        "volume": 0.1,
        "profit": 250.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Price above upper BB (1.09245) - extreme move"
      },
      {
        "test_id": "UT-028_MULTIPLE_REGRESSION",
        "ticket": 4005,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08600,
        "volume": 0.1,
        "profit": 10.0,
        "sl": 0.0,
        "tp": 0.0,
        "history": [
          {"cycle": -3, "stage": "STAGE_2B", "profit": 65},
          {"cycle": -2, "stage": "STAGE_1A", "profit": 35},
          {"cycle": -1, "stage": "STAGE_2C", "profit": 72},
          {"cycle": 0, "stage": "STAGE_1", "profit": 15}
        ],
        "description": "Multiple regression events in history"
      }
    ],
    
    "category_e_critical_tests": [
      {
        "test_id": "UT-030_CONCURRENT_LIMIT",
        "ticket": 5001,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08700,
        "volume": 0.1,
        "profit": 20.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Part of 100+ position batch test"
      },
      {
        "test_id": "UT-035_PERFORMANCE_1",
        "ticket": 5002,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08600,
        "volume": 0.1,
        "profit": 10.0,
        "sl": 0.0,
        "tp": 0.0,
        "description": "Standard position for performance benchmark"
      }
    ],
    
    "regression_test_positions": [
      {
        "test_id": "UT-002_REGRESSION_1",
        "ticket": 6001,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08600,
        "volume": 0.1,
        "profit": 10.0,
        "sl": 0.0,
        "tp": 0.0,
        "previous_stage": "STAGE_2B",
        "peak_profit": 65.0,
        "stage_history": ["STAGE_0", "STAGE_1", "STAGE_2A", "STAGE_2B"],
        "description": "Regression: Moved back from STAGE_2B to STAGE_0 - should trigger defense"
      },
      {
        "test_id": "UT-002_REGRESSION_2",
        "ticket": 6002,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.09100,
        "volume": 0.1,
        "profit": 60.0,
        "sl": 0.0,
        "tp": 0.0,
        "previous_stage": "STAGE_3A",
        "peak_profit": 85.0,
        "stage_history": ["STAGE_1", "STAGE_2A", "STAGE_3A", "STAGE_2B"],
        "description": "Profit giveback: 85→60 pips (29.4%) - borderline, may not trigger"
      },
      {
        "test_id": "UT-002_REGRESSION_3",
        "ticket": 6003,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.09000,
        "volume": 0.1,
        "profit": 50.0,
        "sl": 0.0,
        "tp": 0.0,
        "previous_stage": "STAGE_2B",
        "peak_profit": 75.0,
        "stage_history": ["STAGE_2B", "STAGE_2B", "STAGE_2B", "STAGE_2B"],
        "description": "Stagnation: 4 cycles at STAGE_2B with <5% fluctuation"
      }
    ],
    
    "hysteresis_test_positions": [
      {
        "test_id": "UT-005_HYSTERESIS_UP",
        "ticket": 7001,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08648,
        "volume": 0.1,
        "profit": 14.8,
        "sl": 0.0,
        "tp": 0.0,
        "previous_stage": "STAGE_0",
        "description": "Hysteresis up test: 14.8% profit (15% threshold - 0.2% buffer) - should NOT advance"
      },
      {
        "test_id": "UT-005_HYSTERESIS_DOWN",
        "ticket": 7002,
        "symbol": "EURUSD",
        "type": 0,
        "entry_price": 1.08500,
        "current_price": 1.08652,
        "volume": 0.1,
        "profit": 15.2,
        "sl": 0.0,
        "tp": 0.0,
        "previous_stage": "STAGE_1",
        "description": "Hysteresis down test: Fell to 15.2% (just above 15% + buffer) from higher stage"
      }
    ]
  },
  
  "test_scenarios": {
    "multi_day_sequences": {
      "ut_015_3day_steady": {
        "description": "3 days of steady 5% daily growth",
        "days": [
          {
            "day": 1,
            "positions": [
              {"ticket": 3001, "price": 1.08570, "expected_stage": "STAGE_0"}
            ]
          },
          {
            "day": 2,
            "positions": [
              {"ticket": 3001, "price": 1.08720, "expected_stage": "STAGE_1"}
            ]
          },
          {
            "day": 3,
            "positions": [
              {"ticket": 3001, "price": 1.08950, "expected_stage": "STAGE_2A"}
            ]
          }
        ]
      },
      "ut_016_5day_volatile": {
        "description": "5 days with ±10% daily swings",
        "days": [
          {
            "day": 1,
            "positions": [
              {"ticket": 3002, "price": 1.08700, "expected_stage": "STAGE_1", "defense_expected": false}
            ]
          },
          {
            "day": 2,
            "positions": [
              {"ticket": 3002, "price": 1.08900, "expected_stage": "STAGE_1A", "defense_expected": false}
            ]
          },
          {
            "day": 3,
            "positions": [
              {"ticket": 3002, "price": 1.08800, "expected_stage": "STAGE_1A", "defense_expected": false}
            ]
          },
          {
            "day": 4,
            "positions": [
              {"ticket": 3002, "price": 1.09100, "expected_stage": "STAGE_2B", "defense_expected": false}
            ]
          },
          {
            "day": 5,
            "positions": [
              {"ticket": 3002, "price": 1.09000, "expected_stage": "STAGE_2C", "defense_expected": true}
            ]
          }
        ]
      }
    },
    
    "position_history_templates": {
      "fresh_position": {
        "stage_history": [],
        "profit_history": [],
        "peak_profit": 0.0,
        "peak_profit_time": null,
        "defense_active": false,
        "defense_cycles": 0,
        "regression_count": 0
      },
      "mature_position": {
        "stage_history": ["STAGE_0", "STAGE_1", "STAGE_1A", "STAGE_2A", "STAGE_2B"],
        "profit_history": [5.0, 20.0, 35.0, 48.0, 62.0],
        "peak_profit": 62.0,
        "peak_profit_time": "2024-01-14T15:30:00Z",
        "defense_active": false,
        "defense_cycles": 0,
        "regression_count": 0
      },
      "defense_active_position": {
        "stage_history": ["STAGE_0", "STAGE_1", "STAGE_2A", "STAGE_2B", "STAGE_2C"],
        "profit_history": [10.0, 25.0, 50.0, 65.0, 60.0],
        "peak_profit": 65.0,
        "peak_profit_time": "2024-01-14T14:00:00Z",
        "defense_active": true,
        "defense_since": "2024-01-14T15:00:00Z",
        "defense_cycles": 2,
        "regression_count": 1
      }
    }
  },
  
  "expected_results": {
    "stage_mappings": {
      "profit_ratios": [
        {"ratio": 0.00, "expected_stage": "STAGE_0"},
        {"ratio": 0.14, "expected_stage": "STAGE_0"},
        {"ratio": 0.15, "expected_stage": "STAGE_1"},
        {"ratio": 0.29, "expected_stage": "STAGE_1"},
        {"ratio": 0.30, "expected_stage": "STAGE_1A"},
        {"ratio": 0.44, "expected_stage": "STAGE_1A"},
        {"ratio": 0.45, "expected_stage": "STAGE_2A"},
        {"ratio": 0.59, "expected_stage": "STAGE_2A"},
        {"ratio": 0.60, "expected_stage": "STAGE_2B"},
        {"ratio": 0.69, "expected_stage": "STAGE_2B"},
        {"ratio": 0.70, "expected_stage": "STAGE_2C"},
        {"ratio": 0.79, "expected_stage": "STAGE_2C"},
        {"ratio": 0.80, "expected_stage": "STAGE_3A"},
        {"ratio": 0.99, "expected_stage": "STAGE_3A"},
        {"ratio": 1.00, "expected_stage": "STAGE_3B"},
        {"ratio": 1.19, "expected_stage": "STAGE_3B"},
        {"ratio": 1.20, "expected_stage": "STAGE_4"},
        {"ratio": 1.79, "expected_stage": "STAGE_4"},
        {"ratio": 1.80, "expected_stage": "STAGE_5"},
        {"ratio": 2.50, "expected_stage": "STAGE_5"}
      ]
    },
    
    "sl_calculations": {
      "STAGE_0": {"pip_offset": 30, "description": "Fixed 30 pip stop from entry"},
      "STAGE_1": {"protection": 0.25, "description": "Lock 25% of profit"},
      "STAGE_1A": {"protection": 0.40, "description": "Lock 40% of profit"},
      "STAGE_2A": {"protection": 0.50, "description": "Lock 50% of profit"},
      "STAGE_2B": {"protection": 0.60, "description": "Lock 60% of profit"},
      "STAGE_2C": {"protection": 0.70, "description": "Lock 70% of profit"},
      "STAGE_3A": {"protection": 0.75, "description": "Lock 75% of profit"},
      "STAGE_3B": {"description": "Hybrid: max(80% profit lock, 20% BB trailing)"},
      "STAGE_4": {"protection": 0.85, "description": "Trail with 15% giveback"},
      "STAGE_5": {"protection": 0.90, "description": "Trail with 10% giveback"}
    },
    
    "regression_triggers": {
      "stage_backward": {
        "from": "STAGE_2B",
        "to": "STAGE_1",
        "expected_defense": "STAGE_2C",
        "description": "1 stage drop → level 1 defense"
      },
      "profit_giveback": {
        "peak": 100.0,
        "current": 65.0,
        "giveback_ratio": 0.35,
        "expected_defense": "STAGE_2C",
        "description": "35% giveback → level 1 defense"
      },
      "stagnation": {
        "cycles_same_stage": 4,
        "profit_fluctuation": "<5%",
        "expected_defense": "STAGE_2C",
        "description": "4 cycles stagnation → level 1 defense"
      }
    }
  }
}