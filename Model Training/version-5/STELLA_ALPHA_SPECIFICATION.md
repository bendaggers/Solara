# STELLA ALPHA: MULTI-TIMEFRAME PURE ML PIPELINE
## Complete Development Specification with Loss Analysis

---

# DOCUMENT OVERVIEW

**Purpose:** This document provides COMPLETE specifications for implementing Stella Alpha of the Pure ML trading pipeline. It includes ALL functionality from V3/V4 plus new multi-timeframe capabilities AND a comprehensive Loss Analysis system.

**Critical:** When implementing Stella Alpha, you MUST carry forward ALL existing features from V4. This document details EVERYTHING needed - nothing should be assumed or skipped.

**Version:** 3.0 (Added Loss Analysis Module)
**Status:** Ready for Implementation

---

# TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Complete Feature Inventory](#2-complete-feature-inventory)
3. [Background & Project History](#3-background--project-history)
4. [Problem Statement & Hypothesis](#4-problem-statement--hypothesis)
5. [Data Architecture](#5-data-architecture)
6. [Data Leakage Prevention (CRITICAL)](#6-data-leakage-prevention-critical)
7. [Feature Engineering Specifications](#7-feature-engineering-specifications)
8. [Statistical Validation Framework](#8-statistical-validation-framework)
9. [Multi-Model Export & Tier Classification](#9-multi-model-export--tier-classification)
10. [Pipeline Architecture](#10-pipeline-architecture)
11. [Checkpoint & Resume System](#11-checkpoint--resume-system)
12. [Parallel Processing System](#12-parallel-processing-system)
13. [Walk-Forward Cross-Validation](#13-walk-forward-cross-validation)
14. [Model Training Configuration](#14-model-training-configuration)
15. [Threshold Optimization](#15-threshold-optimization)
16. [Evaluation Metrics](#16-evaluation-metrics)
17. [Diagnostic Analysis System](#17-diagnostic-analysis-system)
18. [Loss Analysis System](#18-loss-analysis-system)
19. [Loss Filter Recommendations](#19-loss-filter-recommendations)
20. [Configuration System (YAML)](#20-configuration-system)
21. [Command Line Interface](#21-command-line-interface)
22. [Artifacts & Output Files](#22-artifacts--output-files)
23. [Logging System](#23-logging-system)
24. [Windows Compatibility](#24-windows-compatibility)
25. [Version Comparison Tool](#25-version-comparison-tool)
26. [Data Handling & NaN Management](#26-data-handling--nan-management)
27. [Implementation Risks & Mitigations](#27-implementation-risks--mitigations)
28. [Implementation Checklist](#28-implementation-checklist)
29. [File Structure](#29-file-structure)
30. [Success Metrics](#30-success-metrics)
31. [Appendices](#31-appendices)

---

# 1. EXECUTIVE SUMMARY

## 1.1 What is Stella Alpha?

Stella Alpha extends the Pure ML pipeline (V4) with:
1. **Multi-Timeframe Analysis (MTF)** - D1 data integration
2. **Loss Analysis System** - Understanding WHY trades lose
3. **Loss Filter Recommendations** - Actionable filters to avoid bad trades

## 1.2 Key Additions in Stella Alpha

```
NEW IN Stella Alpha:
├── D1 Data Integration (with leakage prevention)
├── D1 Feature Engineering (~40 new features)
├── Cross-Timeframe Features (~20 new features)
├── MTF Confluence Scoring
├── V4 vs Stella Alpha Comparison Tool
├── Enhanced Diagnostics for MTF analysis
│
├── ★ LOSS ANALYSIS SYSTEM (NEW) ★
│   ├── Trade-level recording (every win/loss)
│   ├── Feature distribution comparison (wins vs losses)
│   ├── Statistical significance testing
│   ├── Pattern detection in losing trades
│   ├── Session/time analysis of losses
│   └── Confidence level analysis
│
└── ★ LOSS FILTER RECOMMENDATIONS (NEW) ★
    ├── Auto-generated filter suggestions
    ├── Impact simulation (trades saved vs lost)
    ├── Net P&L improvement calculation
    └── Filter combination testing

CARRIED FORWARD FROM V4:
├── Checkpoint/Resume Database System
├── Parallel Processing with Live Display
├── Walk-Forward Cross-Validation (5 folds)
├── RFE Feature Selection
├── LightGBM Training with Class Weights
├── Threshold Optimization (0.40-0.70)
├── Comprehensive Diagnostic Analysis (diagnose.py)
├── GOLD/SILVER/BRONZE Classification
├── CLI with -w, -c, -i arguments
├── Windows Compatibility (UTF-8, paths)
└── All V4 Features (~214)
```

## 1.3 The Loss Problem We're Solving

```
V4 GOLD CONFIG (TP=30 SL=50 H=36):
──────────────────────────────────
Total Trades:  10,268
Wins:          6,869 (66.9%)  →  +206,070 pips
Losses:        3,399 (33.1%)  →  -169,950 pips
Net:                          →  +36,120 pips

THE QUESTION:
Can we AVOID some of those 3,399 losing trades?

If we could avoid just 500 losses (15%):
- Saved: 500 × 50 pips = 25,000 pips
- New Net: 61,120 pips (+69% improvement!)

Stella Alpha GOAL: Identify patterns in losing trades and 
         create filters to avoid them.
```

## 1.4 Expected Outcome

```
V4 LIMITATION:
- Can only predict 30-pip moves reliably
- High R:R configs (TP > SL) fail
- No understanding of WHY trades lose
- No mechanism to filter bad trades

Stella Alpha GOALS:
- Predict 50-80 pip moves with D1 context
- Find profitable high R:R configs (TP >= SL)
- Understand patterns in losing trades
- Generate actionable filters to improve win rate
- Improve net P&L by avoiding predictable losses
```

---

# 2. COMPLETE FEATURE INVENTORY

## 2.1 Features Stella Alpha MUST Have (Carried from V4)

### Core Pipeline Features
```
□ Load H4 CSV data with configurable schema
□ Feature engineering (214 H4 features)
□ Pure ML labeling (TP/SL/MaxHold based)
□ Label pre-computation and caching
□ Walk-forward cross-validation (5 folds)
□ RFE feature selection per fold
□ LightGBM training with class weights
□ Threshold optimization per fold
□ Consensus threshold selection
□ Multi-metric evaluation
```

### Checkpoint/Resume System
```
□ SQLite database (pure_ml.db → pure_ml_stella_alpha.db)
□ Store completed config results
□ Resume from interruption
□ Skip already-completed configs
□ Progress tracking
□ Thread-safe for parallel execution
```

### Parallel Processing System
```
□ ProcessPoolExecutor for parallel configs
□ Configurable worker count (-w argument)
□ Live terminal display with progress bar
□ Worker status display (current task, last result)
□ ETA calculation
□ Average time per config tracking
□ Pass/Fail counters
```

### Diagnostic Analysis (diagnose.py)
```
□ Load results from checkpoint database
□ Overview statistics
□ GOLD/SILVER/BRONZE classification
□ All passed configs listing (sorted by EV)
□ Rejection analysis with reasons
□ Near-miss detection
□ Parameter pattern analysis (TP, SL, Hold, R:R)
□ Feature importance analysis
□ Recommendations generation
□ Final verdict (Ready/Caution/Not Ready)
□ Colored terminal output
□ --db and --top CLI arguments
```

### CLI & Configuration
```
□ --config / -c : YAML config file path
□ --input / -i  : Input CSV path (H4 data)
□ --workers / -w: Number of parallel workers
□ --d1-input    : D1 CSV path (NEW in Stella Alpha)
□ YAML configuration with all settings
□ Config space definition (TP, SL, Hold ranges)
□ Feature settings
□ Model hyperparameters
□ Acceptance criteria
```

### Logging & Compatibility
```
□ UTF-8 encoding for all file operations
□ Windows path compatibility
□ Colored console output (colorama)
□ Progress logging with timestamps
□ Error handling and reporting
```

### Artifacts Output
```
□ Checkpoint database (pure_ml_stella_alpha.db)
□ Best model (pure_ml_model.pkl)
□ Selected features (features.json)
□ Trading config (trading_config.json)
□ Metrics summary (metrics.json)
□ Detailed results CSV
□ Training log
```

## 2.2 New Features in Stella Alpha - Multi-Timeframe

### D1 Data Integration
```
□ D1 CSV loading
□ D1 data validation
□ Safe merge with H4 (no leakage)
□ Leakage validation check
□ D1 timestamp handling
```

### D1 Feature Engineering
```
□ D1 base features (from EA export)
□ D1 derived features (momentum, regime, etc.)
□ D1 pattern features
□ D1 statistical features
```

### Cross-Timeframe Features
```
□ H4-D1 alignment features
□ MTF confluence score
□ MTF divergence detection
□ Relative position features
```

### Enhanced Diagnostics
```
□ D1 feature importance analysis
□ Cross-TF feature importance
□ MTF confluence effectiveness
□ V4 vs Stella Alpha comparison report
```

### New CLI Arguments
```
□ --d1-input    : Path to D1 CSV file
□ --compare-v4  : Path to V4 database for comparison
□ --analyze-losses : Run loss analysis (NEW)
```

## 2.3 New Features in Stella Alpha - Loss Analysis System

### Trade-Level Recording
```
□ Record every trade decision (win/loss)
□ Store all features at entry time
□ Store model confidence (probability)
□ Store session/hour of entry
□ Store outcome details (pips gained/lost)
□ Store time to outcome (bars held)
```

### Loss Pattern Analysis
```
□ Compare feature distributions (wins vs losses)
□ Statistical significance testing (t-test, KS-test)
□ Identify features with significant differences
□ Session/time analysis of losses
□ Confidence level analysis
□ D1 alignment analysis
```

### Filter Recommendation Engine
```
□ Generate candidate filters automatically
□ Simulate filter impact on historical trades
□ Calculate trades eliminated (wins and losses)
□ Calculate net P&L improvement
□ Rank filters by effectiveness
□ Test filter combinations
```

### Loss Analysis Artifacts
```
□ Trade log database (trades_stella_alpha.db)
□ Loss analysis report (loss_analysis.json)
□ Filter recommendations (filter_recommendations.json)
□ Win vs Loss feature comparison charts
□ analyze_losses.py script
```

---

# 3. BACKGROUND & PROJECT HISTORY

## 3.1 Version History

| Version | Approach | Key Features | Outcome |
|---------|----------|--------------|---------|
| V1-V2 | Initial exploration | Basic ML | Learning |
| V3 | Signal Filter | BB touch → ML filter | Moderate success |
| V4 | Pure ML | ML predicts everything | TP=30 works, high R:R fails |
| Stella Alpha | MTF + Loss Analysis | H4+D1 context, loss filtering | TBD |

## 3.2 V4 Results Summary

```
BEST V4 CONFIGS:
────────────────
TP=30 SL=30 H=36: EV=+4.17, Precision=57.0%, Edge=+7.0%
TP=30 SL=50 H=36: EV=+3.55, Precision=66.9%, Edge=+4.4% (GOLD)
TP=30 SL=40 H=18: EV=+2.72, Precision=61.0%, Edge=+3.9%

PASS RATE: 39.6% (19/48 configs)
GOLD CONFIGS: 1
SILVER CONFIGS: 10

KEY FINDING:
- TP=30 configs: 90.5% pass rate
- TP=40+ configs: 0% pass rate
- Model CANNOT predict large moves with H4 alone

LOSS BREAKDOWN (GOLD config):
- Total trades: 10,268
- Wins: 6,869 (66.9%)
- Losses: 3,399 (33.1%)
- Potential improvement: If we avoid 500 losses = +69% more profit
```

## 3.3 Feature Evolution

```
V4 FEATURES (214 total):
├── H4 Base (from EA): 22
├── Binary flags: 11
├── Price change: 7
├── Lags: 18
├── Slopes: 12
├── Z-scores: 6
├── Rolling stats: 10
├── Percentiles: 7
├── Momentum: 15
├── Divergence: 4
├── Patterns: 10
├── BB patterns: 8
├── Volume patterns: 6
├── Session: 16
├── Regime: 11
├── Mean reversion: 13
├── Volatility: 7
├── MACD: 14
├── Quality: 15
└── Composite: 2

Stella Alpha ADDITIONS (~80 new):
├── D1 Base (from EA): 22
├── D1 Derived: ~40
└── Cross-Timeframe: ~20

Stella Alpha TOTAL: ~294 features
```

---

# 4. PROBLEM STATEMENT & HYPOTHESIS

## 4.1 The Multi-Timeframe Problem

```
OBSERVATION:
H4 BB/RSI signals predict 30-pip reversions accurately (57-67%)
H4 BB/RSI signals CANNOT predict 50+ pip moves (<10% precision)

WHY?
After 30 pips, market behavior depends on:
- Daily trend direction
- D1 support/resistance
- Macro context
- Institutional order flow

These factors are NOT visible in H4 data alone.
```

## 4.2 The Loss Problem

```
OBSERVATION:
Even with 66.9% win rate, 33.1% of trades LOSE.
These losses eat into profits significantly.

WHY DO TRADES LOSE?

HYPOTHESIS 1: Wrong Market Regime
- H4 signal correct, but D1 trend opposed
- Fighting the bigger trend

HYPOTHESIS 2: Bad Session/Timing
- Entry during low liquidity
- Price didn't move enough

HYPOTHESIS 3: Weak Signal Strength
- Model confidence was marginal (0.55-0.60)
- These trades lose more often

HYPOTHESIS 4: Specific Feature Patterns
- Certain feature combinations predict losses
- These patterns are detectable
```

## 4.3 Combined Hypothesis for Stella Alpha

```
HYPOTHESIS:
By combining:
1. D1 context (avoid fighting daily trend)
2. Loss pattern analysis (understand why trades fail)
3. Smart filters (avoid predictable losses)

We can:
- Reduce losses by 20-30%
- Improve win rate from 67% to 75%+
- Enable higher R:R configs (TP > SL)
- Significantly increase net profitability
```

## 4.4 Target Outcomes

```
NOTE: All Stella Alpha configs use:
      • Fixed SL = 30 pips
      • Minimum TP = 50 pips
      • This guarantees R:R >= 1.67:1 for ALL configs
      • Only TIER 0 and TIER 1 are possible (no unfavorable R:R)

TIER 0 - RUNNERS 🚀 (TP >= 75, R:R >= 2.5:1):
─────────────────────────────────────────────
TP=150 SL=30: Risk 30 to make 150 (5.0:1 R:R) - Need 17% win rate
TP=140 SL=30: Risk 30 to make 140 (4.67:1 R:R) - Need 18% win rate
TP=130 SL=30: Risk 30 to make 130 (4.33:1 R:R) - Need 19% win rate
TP=120 SL=30: Risk 30 to make 120 (4.0:1 R:R) - Need 20% win rate
TP=110 SL=30: Risk 30 to make 110 (3.67:1 R:R) - Need 21% win rate
TP=100 SL=30: Risk 30 to make 100 (3.33:1 R:R) - Need 23% win rate
TP=90 SL=30:  Risk 30 to make 90 (3.0:1 R:R) - Need 25% win rate
TP=80 SL=30:  Risk 30 to make 80 (2.67:1 R:R) - Need 27% win rate

→ 8 configs in Tier 0
→ One winner covers 2.67-5 losers


TIER 1 - IDEAL ⭐ (TP 50-70, R:R 1.67:1 to 2.49:1):
───────────────────────────────────────────────────
TP=70 SL=30:  Risk 30 to make 70 (2.33:1 R:R) - Need 30% win rate
TP=60 SL=30:  Risk 30 to make 60 (2.0:1 R:R) - Need 33% win rate
TP=50 SL=30:  Risk 30 to make 50 (1.67:1 R:R) - Need 37% win rate

→ 3 configs in Tier 1
→ One winner covers 1.67-2.33 losers


TOTAL CONFIG SPACE:
───────────────────
TP values: 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150 (11 values)
SL values: 30 (fixed)
Hold values: 12, 24, 36, 48, 60, 72 (6 values)
Total: 11 × 1 × 6 = 66 configs

Tier 0 configs: 8 TP values × 6 Hold values = 48 configs
Tier 1 configs: 3 TP values × 6 Hold values = 18 configs


KEY GUARANTEE:
──────────────
WORST case: TP=50 SL=30 (1.67:1 R:R) - Need only 37% win rate
BEST case: TP=150 SL=30 (5.0:1 R:R) - Need only 17% win rate

ALL configs have favorable R:R. No bad configs possible!
```

## 4.5 The Runner Strategy (Why High R:R Matters)

```
MATH: WHY RUNNERS ARE BETTER
─────────────────────────────

SCENARIO A: High Win Rate, Low R:R (Current V4)
──────────────────────────────────────────────
TP=30, SL=50, Win Rate=67%
100 trades:
  67 wins × 30 pips = +2,010 pips
  33 losses × 50 pips = -1,650 pips
  NET = +360 pips
  
SCENARIO B: Lower Win Rate, High R:R (Runner Strategy)
──────────────────────────────────────────────────────
TP=100, SL=30, Win Rate=45%
100 trades:
  45 wins × 100 pips = +4,500 pips
  55 losses × 30 pips = -1,650 pips
  NET = +2,850 pips  ← 8x MORE PROFITABLE!

SCENARIO C: Dream Runner
────────────────────────
TP=150, SL=30, Win Rate=35%
100 trades:
  35 wins × 150 pips = +5,250 pips
  65 losses × 30 pips = -1,950 pips
  NET = +3,300 pips  ← EVEN BETTER!

BREAKEVEN WIN RATES BY R:R:
───────────────────────────
TP=30  SL=50  (0.6:1) → Need 62.5% to break even
TP=50  SL=30  (1.67:1) → Need 37.5% to break even
TP=80  SL=30  (2.67:1) → Need 27.3% to break even
TP=100 SL=30  (3.33:1) → Need 23.1% to break even
TP=150 SL=30  (5:1)    → Need 16.7% to break even

CONCLUSION:
With D1 confluence, if we can predict 100+ pip moves with even 
35-45% accuracy, we have a MUCH more profitable system than 
predicting 30-pip moves with 65% accuracy.
```

---

# 5. DATA ARCHITECTURE

## 5.1 H4 Data Schema (Existing)

```
FILE: EURUSD_H4_features.csv
ROWS: ~41,000 (25 years of H4 data)
TIMEFRAME: H4 (4-hour candles)

COLUMNS (22 base features):
──────────────────────────
timestamp               datetime    "2024.01.15 08:00:00"
open                    float       1.0850
high                    float       1.0890
low                     float       1.0840
close                   float       1.0875
volume                  int         1250
lower_band              float       1.0820
middle_band             float       1.0855
upper_band              float       1.0890
bb_touch_strength       float       1.02 (high/upper_band)
bb_position             float       0.85 (0-1 scale)
bb_width_pct            float       0.0065
rsi_value               float       72.5
volume_ratio            float       1.3
candle_rejection        float       0.4 (upper wick ratio)
candle_body_pct         float       0.6
atr_pct                 float       0.0035
trend_strength          float       1.2
prev_candle_body_pct    float       0.5
prev_volume_ratio       float       1.1
gap_from_prev_close     float       0.0002
price_momentum          float       0.003
previous_touches        int         2
time_since_last_touch   int         5
resistance_distance_pct float       0.0015
```

## 5.2 D1 Data Schema (NEW)

```
FILE: EURUSD_D1_features.csv
ROWS: ~6,500 (25 years of daily data)
TIMEFRAME: D1 (Daily candles)

COLUMNS (same structure as H4):
─────────────────────────────
timestamp               datetime    "2024.01.15 00:00:00" (daily close)
open                    float       1.0820
high                    float       1.0900
low                     float       1.0810
close                   float       1.0878
volume                  int         45000
lower_band              float       1.0750 (D1 BB)
middle_band             float       1.0825 (D1 BB)
upper_band              float       1.0900 (D1 BB)
bb_touch_strength       float       1.01
bb_position             float       0.78
bb_width_pct            float       0.0055
rsi_value               float       68.5 (D1 RSI)
volume_ratio            float       1.1
candle_rejection        float       0.35
candle_body_pct         float       0.55
atr_pct                 float       0.0042
trend_strength          float       0.8
prev_candle_body_pct    float       0.45
prev_volume_ratio       float       0.9
gap_from_prev_close     float       0.00015
price_momentum          float       0.002
previous_touches        int         1
time_since_last_touch   int         3
resistance_distance_pct float       0.0012

CRITICAL: D1 data uses same Bollinger Band settings (20,2)
          and RSI period (14) as H4 but calculated on D1 bars.
```

## 5.3 Merged Data Schema

```
MERGED DATAFRAME:
─────────────────
Each H4 row contains:
├── All H4 columns (original names)
├── All D1 columns (prefixed with 'd1_')
└── Cross-timeframe features (prefixed with 'mtf_')

TOTAL COLUMNS: ~65 base + ~230 derived = ~295

MERGE RULE (CRITICAL):
For H4 candle at timestamp T:
  → Use D1 candle from floor(T.date) - 1 day
  → This ensures we only use COMPLETED D1 data
  → NEVER use same-day D1 data (not yet closed)

EXAMPLE:
┌─────────────────────┬────────────────────┐
│ H4 Timestamp        │ D1 Data From       │
├─────────────────────┼────────────────────┤
│ 2024-01-15 04:00    │ 2024-01-14         │
│ 2024-01-15 08:00    │ 2024-01-14         │
│ 2024-01-15 12:00    │ 2024-01-14         │
│ 2024-01-15 16:00    │ 2024-01-14         │
│ 2024-01-15 20:00    │ 2024-01-14         │
│ 2024-01-16 00:00    │ 2024-01-15         │ ← D1 Jan 15 now available
│ 2024-01-16 04:00    │ 2024-01-15         │
└─────────────────────┴────────────────────┘
```

## 5.4 Trade Log Schema (NEW for Loss Analysis)

```
TABLE: trades
─────────────
Each trade taken by the model is recorded with full context.

COLUMNS:
├── trade_id            INTEGER PRIMARY KEY
├── config_id           TEXT        "TP30_SL50_H36"
├── fold                INTEGER     1-5
├── timestamp           TEXT        Entry timestamp
├── outcome             TEXT        "WIN" or "LOSS"
├── pips_result         REAL        +30 or -50
├── bars_held           INTEGER     How long position was open
├── model_probability   REAL        Model's confidence (0-1)
├── threshold_used      REAL        Threshold that was applied
│
├── # H4 Features at Entry
├── h4_rsi_value        REAL
├── h4_bb_position      REAL
├── h4_trend_strength   REAL
├── h4_atr_pct          REAL
├── h4_volume_ratio     REAL
├── h4_session          TEXT        "asian", "london", "ny", "overlap"
├── h4_hour             INTEGER     0-23
├── h4_day_of_week      INTEGER     0-4 (Mon-Fri)
├── ... (all relevant H4 features)
│
├── # D1 Features at Entry
├── d1_rsi_value        REAL
├── d1_bb_position      REAL
├── d1_trend_strength   REAL
├── d1_trend_direction  REAL        +1 bullish, -1 bearish
├── d1_atr_pct          REAL
├── ... (all relevant D1 features)
│
├── # Cross-TF Features at Entry
├── mtf_confluence_score REAL
├── mtf_rsi_aligned     INTEGER     0 or 1
├── mtf_trend_aligned   INTEGER     0 or 1
├── d1_supports_short   INTEGER     0 or 1
└── d1_opposes_short    INTEGER     0 or 1
```

---

# 6. DATA LEAKAGE PREVENTION (CRITICAL)

## 6.1 What is Data Leakage?

```
DATA LEAKAGE:
Using information that would NOT be available at prediction time.

WRONG APPROACH:
At H4 2024-01-15 08:00, using D1 2024-01-15 close price
→ D1 Jan 15 closes at 2024-01-16 00:00
→ At 08:00, we're 16 hours BEFORE D1 close
→ Using it = using FUTURE data
→ Backtest looks great, LIVE trading fails

CORRECT APPROACH:
At H4 2024-01-15 08:00, using D1 2024-01-14 close price
→ D1 Jan 14 closed at 2024-01-15 00:00
→ At 08:00, this data is 8 hours OLD
→ Safe to use, no leakage
```

## 6.2 Merge Implementation

```python
"""
D1 Safe Merge Module

CRITICAL: This is the most important code in Stella Alpha.
Any bug here invalidates all results.
"""

import pandas as pd
import numpy as np
from typing import Tuple

def merge_h4_d1_safe(
    df_h4: pd.DataFrame, 
    df_d1: pd.DataFrame,
    validate: bool = True
) -> pd.DataFrame:
    """
    Merge D1 data into H4 data WITHOUT data leakage.
    
    RULE: For each H4 candle, use ONLY the most recent
          COMPLETED D1 candle (previous day).
    
    Args:
        df_h4: H4 dataframe with 'timestamp' column
        df_d1: D1 dataframe with 'timestamp' column
        validate: If True, run leakage validation
        
    Returns:
        Merged dataframe with D1 columns prefixed 'd1_'
        
    Raises:
        ValueError: If data leakage is detected
    """
    df_h4 = df_h4.copy()
    df_d1 = df_d1.copy()
    
    # 1. Parse timestamps
    df_h4['timestamp'] = pd.to_datetime(df_h4['timestamp'])
    df_d1['timestamp'] = pd.to_datetime(df_d1['timestamp'])
    
    # 2. Get DATE of each H4 candle (normalized to midnight)
    df_h4['_h4_date'] = df_h4['timestamp'].dt.normalize()
    
    # 3. D1 data becomes available AFTER the day closes
    #    So a D1 candle dated Jan 15 is available starting Jan 16 00:00
    #    We shift the "available from" date by +1 day
    df_d1['_d1_close_date'] = df_d1['timestamp'].dt.normalize()
    df_d1['_d1_available_from'] = df_d1['_d1_close_date'] + pd.Timedelta(days=1)
    
    # 4. Rename D1 columns with 'd1_' prefix
    d1_cols_to_rename = [c for c in df_d1.columns 
                         if c not in ['timestamp', '_d1_close_date', '_d1_available_from']]
    rename_map = {c: f'd1_{c}' for c in d1_cols_to_rename}
    rename_map['timestamp'] = 'd1_timestamp'
    df_d1 = df_d1.rename(columns=rename_map)
    
    # 5. Sort both dataframes by time
    df_h4 = df_h4.sort_values('timestamp').reset_index(drop=True)
    df_d1 = df_d1.sort_values('_d1_available_from').reset_index(drop=True)
    
    # 6. Merge using merge_asof
    #    For each H4 row, find the most recent D1 where available_from <= h4_date
    df_merged = pd.merge_asof(
        df_h4,
        df_d1.drop(columns=['_d1_close_date']),
        left_on='_h4_date',
        right_on='_d1_available_from',
        direction='backward'  # Use most recent PAST D1
    )
    
    # 7. Clean up helper columns
    df_merged = df_merged.drop(columns=['_h4_date', '_d1_available_from'], errors='ignore')
    
    # 8. Validate no leakage
    if validate:
        is_valid, violations = validate_no_leakage(df_merged)
        if not is_valid:
            raise ValueError(
                f"DATA LEAKAGE DETECTED: {len(violations)} rows have future D1 data!\n"
                f"First violations:\n{violations.head(5)}"
            )
    
    return df_merged


def validate_no_leakage(df_merged: pd.DataFrame) -> Tuple[bool, pd.DataFrame]:
    """
    Validate that no D1 data comes from same day or future.
    
    RULE: d1_timestamp.date() must be < timestamp.date()
          (D1 date must be strictly BEFORE H4 date)
    
    Exception: H4 candles at exactly 00:00 can use previous day's D1
    
    Returns:
        (is_valid, violations_df)
    """
    df = df_merged.copy()
    
    h4_date = pd.to_datetime(df['timestamp']).dt.date
    d1_date = pd.to_datetime(df['d1_timestamp']).dt.date
    
    # D1 date must be strictly before H4 date
    violations = df[d1_date >= h4_date]
    
    is_valid = len(violations) == 0
    
    if is_valid:
        print("✓ Data leakage validation PASSED")
    else:
        print(f"✗ Data leakage validation FAILED: {len(violations)} violations")
    
    return is_valid, violations[['timestamp', 'd1_timestamp']]


def get_merge_stats(df_merged: pd.DataFrame) -> dict:
    """Get statistics about the merge."""
    return {
        'total_h4_rows': len(df_merged),
        'h4_date_range': f"{df_merged['timestamp'].min()} to {df_merged['timestamp'].max()}",
        'd1_date_range': f"{df_merged['d1_timestamp'].min()} to {df_merged['d1_timestamp'].max()}",
        'd1_columns_added': len([c for c in df_merged.columns if c.startswith('d1_')]),
        'rows_with_d1_data': df_merged['d1_timestamp'].notna().sum(),
        'rows_without_d1_data': df_merged['d1_timestamp'].isna().sum(),
    }
```

## 6.3 Validation Tests

```python
def test_merge_leakage_prevention():
    """Unit test for data leakage prevention."""
    
    # Create test H4 data
    h4_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-15 04:00', periods=12, freq='4H'),
        'close': [1.08] * 12
    })
    
    # Create test D1 data
    d1_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-13', periods=5, freq='D'),
        'd1_close': [1.07, 1.075, 1.08, 1.085, 1.09]
    })
    
    # Merge
    merged = merge_h4_d1_safe(h4_data, d1_data, validate=True)
    
    # Check: H4 on Jan 15 should use D1 from Jan 14
    jan15_rows = merged[merged['timestamp'].dt.date == pd.Timestamp('2024-01-15').date()]
    
    for _, row in jan15_rows.iterrows():
        d1_date = pd.to_datetime(row['d1_timestamp']).date()
        assert d1_date == pd.Timestamp('2024-01-14').date(), \
            f"H4 on Jan 15 should use D1 Jan 14, got {d1_date}"
    
    print("✓ Leakage prevention test PASSED")
```

---

# 7. FEATURE ENGINEERING SPECIFICATIONS

## 7.1 H4 Features (From V4 - Keep All)

```
H4 FEATURES (214 total) - KEEP ALL FROM V4:
────────────────────────────────────────────

BINARY (11):
touched_upper_bb, rsi_overbought, rsi_extreme_overbought,
rsi_very_extreme, bearish_candle, strong_bearish, bb_very_high,
bb_above_upper, high_volume, extreme_volume, strong_uptrend

PRICE_CHANGE (7):
price_change_1, price_change_3, price_change_5, price_change_10,
high_change_1, high_change_3, range_pct

LAGS (18):
rsi_lag1-5, bb_position_lag1-3, price_change_lag1-3,
volume_ratio_lag1-3, bb_width_lag1-2, trend_strength_lag1-2

SLOPES (12):
rsi_slope_3/5/10, price_slope_3/5/10, bb_position_slope_3/5,
volume_slope_3, bb_width_slope_3/5, trend_slope_3

ZSCORES (6):
price_zscore, rsi_zscore, volume_zscore, bb_position_zscore,
atr_zscore, high_zscore

ROLLING_STATS (10):
price_rolling_std, rsi_rolling_std/max/min, rsi_range,
bb_position_rolling_std/max, volume_rolling_std,
price_skew_20, price_kurtosis_20

PERCENTILES (7):
price_percentile, rsi_percentile, volume_percentile,
bb_position_percentile, high_percentile, atr_percentile, range_percentile

MOMENTUM (15):
price_roc_3/5/10, rsi_roc_3/5, volume_roc_3, bb_width_roc_5,
price_velocity, price_acceleration, price_accel_norm,
rsi_velocity, rsi_acceleration, momentum_deceleration,
rsi_deceleration, price_accel_smooth

DIVERGENCE (4):
bearish_div_10, bearish_div_3, volume_divergence, divergence_strength

PATTERNS (10):
consecutive_bullish, consecutive_bearish, consecutive_higher_highs,
consecutive_higher_closes, bullish_exhaustion, upper_wick_ratio,
shooting_star, bearish_engulfing, evening_star, near_double_top

BB_PATTERNS (8):
bb_squeeze, bb_expansion, walking_upper_band, bb_upper_rejection,
distance_from_upper, distance_from_lower, bb_overextended, bb_squeeze_pct

VOLUME_PATTERNS (6):
volume_climax_top, volume_decline_3, volume_spike_rejection,
volume_trend, obv_direction, obv_divergence

SESSION (16):
hour, day_of_week, is_asian_session, is_london_session, is_ny_session,
is_overlap_session, session_volatility_weight, is_session_start,
is_session_end, is_monday, is_friday, is_midweek,
hour_sin, hour_cos, dow_sin, dow_cos

REGIME (11):
adx, plus_di, minus_di, trend_direction, is_trending, is_ranging,
is_volatile, regime_trend_score, regime_volatility_score,
is_trending_up, is_trending_down

MEAN_REVERSION (13):
dist_from_ma10, dist_from_ma20, dist_from_ma50,
overextension_10, overextension_20, ma20_slope, ma50_slope,
price_above_ma10, price_above_ma20, price_above_ma50,
all_ma_bullish, extreme_overextension, mean_reversion_score

VOLATILITY (7):
volatility_contraction, volatility_expansion, historical_vol,
volatility_ratio, intrabar_vol, intrabar_vol_percentile, vol_cluster

MACD (14):
macd_line, macd_signal, macd_histogram, macd_normalized,
macd_hist_normalized, macd_cross_down, macd_cross_up,
macd_above_zero, macd_below_zero, macd_hist_rising,
macd_hist_falling, macd_bearish_div, macd_slope, macd_hist_slope

QUALITY (15):
rsi_peaked, rsi_drop_size, rsi_drop_large, rsi_was_extreme,
rsi_slope_strong_neg, rsi_momentum_shift, bb_extreme_prev,
touched_prev_1, touched_prev_2, touched_recently, rejection_candle,
volume_spike, high_volume_reversal, not_choppy, first_touch

COMPOSITE (2):
exhaustion_score, exhaustion_level
```

## 7.2 D1 Base Features (From EA Export)

```
D1 BASE FEATURES (22) - prefixed with 'd1_':
────────────────────────────────────────────

PRICE:
d1_open, d1_high, d1_low, d1_close, d1_volume

BOLLINGER BANDS:
d1_lower_band, d1_middle_band, d1_upper_band
d1_bb_touch_strength, d1_bb_position, d1_bb_width_pct

INDICATORS:
d1_rsi_value, d1_volume_ratio, d1_atr_pct, d1_trend_strength

CANDLE:
d1_candle_rejection, d1_candle_body_pct
d1_prev_candle_body_pct, d1_prev_volume_ratio

OTHER:
d1_gap_from_prev_close, d1_price_momentum
d1_previous_touches, d1_time_since_last_touch
d1_resistance_distance_pct
```

## 7.3 D1 Derived Features (NEW - Calculate in Python)

```python
D1 DERIVED FEATURES (~40 new):
──────────────────────────────

# D1 BINARY FLAGS (10)
'd1_touched_upper_bb'        # d1_high >= d1_upper_band
'd1_rsi_overbought'          # d1_rsi > 70
'd1_rsi_extreme'             # d1_rsi > 80
'd1_bearish_candle'          # d1_close < d1_open
'd1_strong_bearish'          # Large bearish body
'd1_bb_very_high'            # d1_bb_position > 0.95
'd1_bb_above_upper'          # d1_close > d1_upper_band
'd1_high_volume'             # d1_volume_ratio > 1.5
'd1_strong_uptrend'          # d1_trend_strength > 1.0
'd1_near_resistance'         # d1_resistance_distance_pct < 0.005

# D1 MOMENTUM (8)
'd1_rsi_slope_3'             # RSI change over 3 D1 bars
'd1_rsi_slope_5'             # RSI change over 5 D1 bars
'd1_price_roc_3'             # Price ROC 3 days
'd1_price_roc_5'             # Price ROC 5 days
'd1_price_roc_10'            # Price ROC 10 days
'd1_bb_position_slope_3'     # BB position change 3 days
'd1_trend_slope_3'           # Trend strength change
'd1_momentum_deceleration'   # Price slowing down

# D1 MEAN REVERSION (6)
'd1_dist_from_ma10'          # Distance from D1 MA10
'd1_dist_from_ma20'          # Distance from D1 MA20
'd1_dist_from_ma50'          # Distance from D1 MA50
'd1_overextension'           # Max(0, dist_from_ma20)
'd1_mean_reversion_score'    # Composite score
'd1_extreme_overextension'   # Above 95th percentile

# D1 REGIME (6)
'd1_adx'                     # D1 ADX value
'd1_is_trending'             # D1 ADX > 25
'd1_is_ranging'              # D1 ADX < 20
'd1_trend_direction'         # +1 bullish, -1 bearish
'd1_is_trending_up'          # Trending AND bullish
'd1_is_trending_down'        # Trending AND bearish

# D1 VOLATILITY (5)
'd1_atr_percentile'          # ATR percentile rank
'd1_bb_squeeze'              # BB width < 20th percentile
'd1_volatility_regime'       # Low/Medium/High
'd1_range_percentile'        # Daily range percentile
'd1_volatility_expansion'    # ATR increasing

# D1 PATTERNS (5)
'd1_consecutive_bullish'     # Consecutive bullish D1 candles
'd1_consecutive_bearish'     # Consecutive bearish D1 candles
'd1_bearish_divergence'      # Price up but RSI down
'd1_near_d1_high'            # Near 20-day high
'd1_shooting_star'           # D1 shooting star pattern
```

## 7.4 Cross-Timeframe Features (NEW)

```python
CROSS-TIMEFRAME FEATURES (~20 new):
───────────────────────────────────

# ALIGNMENT FEATURES (5)
'mtf_rsi_aligned'            # Both H4 and D1 RSI > 65
'mtf_bb_aligned'             # Both H4 and D1 bb_position > 0.8
'mtf_trend_aligned'          # Both showing same trend direction
'mtf_bearish_aligned'        # Both candles bearish
'mtf_overbought_aligned'     # Both RSI > 70

# CONFLUENCE SCORE (1)
'mtf_confluence_score'       # Weighted combination:
                             # 0.25 * mtf_rsi_aligned +
                             # 0.25 * mtf_bb_aligned +
                             # 0.25 * mtf_trend_aligned +
                             # 0.25 * mtf_bearish_aligned

# DIVERGENCE FEATURES (4)
'mtf_rsi_divergence'         # H4 RSI > 70 but D1 RSI < 50
'mtf_bb_divergence'          # H4 at upper BB but D1 not
'mtf_trend_divergence'       # H4 bullish but D1 bearish
'mtf_momentum_divergence'    # H4 rising but D1 falling

# RELATIVE POSITION (4)
'h4_position_in_d1_range'    # (h4_close - d1_low) / (d1_high - d1_low)
'h4_vs_d1_bb_position'       # h4_bb_position - d1_bb_position
'h4_vs_d1_rsi'               # h4_rsi - d1_rsi
'h4_vs_d1_trend'             # h4_trend - d1_trend

# VOLATILITY COMPARISON (2)
'h4_vs_d1_atr_ratio'         # h4_atr / d1_atr
'h4_vs_d1_range_ratio'       # h4_range / d1_range

# CONTEXT FLAGS (4)
'd1_supports_short'          # D1 conditions favor SHORT
'd1_opposes_short'           # D1 conditions oppose SHORT
'd1_neutral'                 # D1 gives no clear signal
'mtf_strong_short_setup'     # Both TFs strongly support SHORT
```

## 7.5 Feature Summary

```
TOTAL Stella Alpha FEATURES:
──────────────────
H4 Base (from EA):           22
H4 Derived (from V4):       192
D1 Base (from EA):           22
D1 Derived (new):           ~40
Cross-Timeframe (new):      ~20
────────────────────────────────
TOTAL:                     ~296

After Statistical Pre-Filter: ~80-120 (significant only)
After RFE Selection:          15-25
```

---

# 8. STATISTICAL VALIDATION FRAMEWORK

## 8.1 Overview

```
PURPOSE:
Use statistical tests throughout the pipeline to ensure:
1. Features have REAL predictive power (not noise)
2. Model performance differences are SIGNIFICANT (not luck)
3. Results are RELIABLE and will generalize to live trading

STATISTICAL TESTS USED:
├── T-Test: Compare means between two groups (wins vs losses)
├── Mann-Whitney U: Non-parametric alternative to t-test
├── Cohen's d: Effect size (practical significance)
├── ANOVA: Compare across multiple groups (folds)
├── Chi-Square: Compare categorical distributions
└── Kolmogorov-Smirnov: Compare distributions

KEY THRESHOLDS:
├── P-value < 0.05: Statistically significant
├── P-value < 0.01: Highly significant
├── Effect size > 0.2: Small practical significance
├── Effect size > 0.5: Medium practical significance
└── Effect size > 0.8: Large practical significance
```

## 8.2 Stage 1: Feature Pre-Filtering (Before RFE)

```python
"""
FEATURE PRE-FILTERING WITH STATISTICAL SIGNIFICANCE

Before running expensive RFE, filter out features that show
no significant difference between wins and losses.

This reduces ~296 features to ~80-120 significant features.
Makes RFE faster and removes noise early.
"""

from scipy import stats
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class FeatureSignificance:
    """Statistical significance results for a feature."""
    feature_name: str
    wins_mean: float
    losses_mean: float
    wins_std: float
    losses_std: float
    t_statistic: float
    p_value: float
    effect_size: float          # Cohen's d
    is_significant: bool        # p < 0.05
    is_practically_significant: bool  # effect_size > 0.2
    recommendation: str         # "KEEP", "MAYBE", "DROP"


class StatisticalFeatureFilter:
    """
    Filter features based on statistical significance.
    """
    
    def __init__(
        self, 
        p_threshold: float = 0.05,
        min_effect_size: float = 0.2,
        min_samples: int = 100
    ):
        self.p_threshold = p_threshold
        self.min_effect_size = min_effect_size
        self.min_samples = min_samples
        self.results: List[FeatureSignificance] = []
    
    def analyze_feature(
        self, 
        wins: np.ndarray, 
        losses: np.ndarray,
        feature_name: str
    ) -> FeatureSignificance:
        """Analyze single feature for significance."""
        
        # Remove NaN
        wins = wins[~np.isnan(wins)]
        losses = losses[~np.isnan(losses)]
        
        if len(wins) < self.min_samples or len(losses) < self.min_samples:
            return FeatureSignificance(
                feature_name=feature_name,
                wins_mean=0, losses_mean=0, wins_std=0, losses_std=0,
                t_statistic=0, p_value=1.0, effect_size=0,
                is_significant=False, is_practically_significant=False,
                recommendation="DROP"
            )
        
        # Calculate statistics
        wins_mean, wins_std = np.mean(wins), np.std(wins)
        losses_mean, losses_std = np.mean(losses), np.std(losses)
        
        # T-test (Welch's t-test for unequal variances)
        t_stat, p_value = stats.ttest_ind(wins, losses, equal_var=False)
        
        # Effect size (Cohen's d)
        pooled_std = np.sqrt((wins_std**2 + losses_std**2) / 2)
        effect_size = abs(wins_mean - losses_mean) / pooled_std if pooled_std > 0 else 0
        
        # Determine significance
        is_significant = p_value < self.p_threshold
        is_practical = effect_size >= self.min_effect_size
        
        # Recommendation
        if is_significant and is_practical:
            recommendation = "KEEP"
        elif is_significant or effect_size >= 0.15:
            recommendation = "MAYBE"
        else:
            recommendation = "DROP"
        
        return FeatureSignificance(
            feature_name=feature_name,
            wins_mean=wins_mean,
            losses_mean=losses_mean,
            wins_std=wins_std,
            losses_std=losses_std,
            t_statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            is_significant=is_significant,
            is_practically_significant=is_practical,
            recommendation=recommendation
        )
    
    def filter_features(
        self, 
        df, 
        feature_columns: List[str],
        label_column: str = 'label'
    ) -> Tuple[List[str], List[str], List[FeatureSignificance]]:
        """
        Filter features based on statistical significance.
        
        Returns:
            (kept_features, dropped_features, all_results)
        """
        wins_mask = df[label_column] == 1
        losses_mask = df[label_column] == 0
        
        kept = []
        dropped = []
        self.results = []
        
        for feature in feature_columns:
            if feature not in df.columns:
                continue
            
            wins = df.loc[wins_mask, feature].values
            losses = df.loc[losses_mask, feature].values
            
            result = self.analyze_feature(wins, losses, feature)
            self.results.append(result)
            
            if result.recommendation == "KEEP":
                kept.append(feature)
            elif result.recommendation == "MAYBE":
                kept.append(feature)  # Keep maybes for RFE to decide
            else:
                dropped.append(feature)
        
        return kept, dropped, self.results
    
    def print_report(self):
        """Print feature filtering report."""
        print("\n" + "=" * 70)
        print("  STATISTICAL FEATURE PRE-FILTER REPORT")
        print("=" * 70)
        
        # Sort by effect size
        sorted_results = sorted(self.results, key=lambda x: x.effect_size, reverse=True)
        
        kept = [r for r in sorted_results if r.recommendation in ("KEEP", "MAYBE")]
        dropped = [r for r in sorted_results if r.recommendation == "DROP"]
        
        print(f"\n  SUMMARY:")
        print(f"  ─────────────────────────────")
        print(f"  Total features analyzed: {len(self.results)}")
        print(f"  KEEP (significant):      {len([r for r in kept if r.recommendation == 'KEEP'])}")
        print(f"  MAYBE (borderline):      {len([r for r in kept if r.recommendation == 'MAYBE'])}")
        print(f"  DROP (not significant):  {len(dropped)}")
        
        print(f"\n  TOP SIGNIFICANT FEATURES:")
        print(f"  {'Feature':<35} {'P-Value':>10} {'Effect':>10} {'Action':>8}")
        print(f"  " + "─" * 65)
        
        for r in sorted_results[:20]:
            if r.is_significant:
                sig_marker = "***" if r.p_value < 0.001 else "**" if r.p_value < 0.01 else "*"
                print(f"  {r.feature_name:<35} {r.p_value:>10.4f}{sig_marker} {r.effect_size:>7.3f} {r.recommendation:>8}")
        
        print("\n" + "=" * 70)
```

## 8.3 Stage 2: Feature Importance Validation

```python
"""
FEATURE IMPORTANCE VALIDATION

After LightGBM training, validate that top features have
statistically significant differences between wins/losses.

A feature might have high importance but no real predictive power
(model might be overfitting to noise).
"""

@dataclass
class ValidatedFeatureImportance:
    """Feature importance with statistical validation."""
    feature_name: str
    lgbm_importance: float      # From LightGBM
    lgbm_rank: int              # Rank by importance
    p_value: float              # Statistical significance
    effect_size: float          # Practical significance
    is_validated: bool          # Both important AND significant
    confidence: str             # "HIGH", "MEDIUM", "LOW", "UNVALIDATED"


def validate_feature_importance(
    model,
    df_test,
    y_test,
    feature_columns: List[str]
) -> List[ValidatedFeatureImportance]:
    """
    Validate LightGBM feature importance with statistical tests.
    """
    # Get LightGBM importance
    lgbm_importance = dict(zip(feature_columns, model.feature_importances_))
    
    # Sort by importance
    sorted_features = sorted(lgbm_importance.items(), key=lambda x: x[1], reverse=True)
    
    results = []
    stat_filter = StatisticalFeatureFilter()
    
    for rank, (feature, importance) in enumerate(sorted_features, 1):
        # Get statistical significance
        wins = df_test[y_test == 1][feature].values
        losses = df_test[y_test == 0][feature].values
        
        stat_result = stat_filter.analyze_feature(wins, losses, feature)
        
        # Determine validation status
        is_validated = stat_result.is_significant and importance > 0
        
        # Confidence level
        if is_validated and stat_result.effect_size > 0.5:
            confidence = "HIGH"
        elif is_validated and stat_result.effect_size > 0.2:
            confidence = "MEDIUM"
        elif stat_result.is_significant:
            confidence = "LOW"
        else:
            confidence = "UNVALIDATED"
        
        results.append(ValidatedFeatureImportance(
            feature_name=feature,
            lgbm_importance=importance,
            lgbm_rank=rank,
            p_value=stat_result.p_value,
            effect_size=stat_result.effect_size,
            is_validated=is_validated,
            confidence=confidence
        ))
    
    return results


def print_validated_importance(results: List[ValidatedFeatureImportance]):
    """Print validated feature importance report."""
    print("\n" + "=" * 80)
    print("  VALIDATED FEATURE IMPORTANCE")
    print("=" * 80)
    
    print(f"\n  {'Rank':<6} {'Feature':<30} {'Importance':>12} {'P-Value':>10} {'Effect':>8} {'Status':>12}")
    print(f"  " + "─" * 80)
    
    for r in results[:25]:
        status_emoji = "✅" if r.confidence == "HIGH" else "⚠️" if r.confidence == "MEDIUM" else "❓" if r.confidence == "LOW" else "❌"
        print(f"  {r.lgbm_rank:<6} {r.feature_name:<30} {r.lgbm_importance:>12.1f} {r.p_value:>10.4f} {r.effect_size:>8.3f} {status_emoji} {r.confidence:>10}")
    
    # Summary
    validated = [r for r in results if r.is_validated]
    high_conf = [r for r in results if r.confidence == "HIGH"]
    
    print(f"\n  VALIDATION SUMMARY:")
    print(f"  ─────────────────────────────")
    print(f"  Total features:     {len(results)}")
    print(f"  Validated:          {len(validated)} ({100*len(validated)/len(results):.1f}%)")
    print(f"  High confidence:    {len(high_conf)}")
    
    if len(validated) < len(results) * 0.5:
        print(f"\n  ⚠️ WARNING: Less than 50% of features validated!")
        print(f"     Model may be overfitting to noise.")
```

## 8.4 Stage 3: Fold Stability Testing (ANOVA)

```python
"""
FOLD STABILITY TESTING

Use statistical tests to check if model performance is 
consistent across folds. Significant differences indicate
regime changes or instability.
"""

from scipy import stats

@dataclass
class FoldStabilityResult:
    """Results of fold stability analysis."""
    metric_name: str
    fold_values: List[float]
    mean: float
    std: float
    cv: float                   # Coefficient of variation
    is_stable: bool             # CV < 15%
    stability_grade: str        # "A", "B", "C", "F"
    interpretation: str


def test_fold_stability(
    fold_results: List[dict],
    metrics: List[str] = ['precision', 'ev', 'recall']
) -> List[FoldStabilityResult]:
    """
    Test if metrics are stable across folds.
    
    Uses Coefficient of Variation (CV) as primary measure.
    CV < 10%: Very stable (Grade A)
    CV < 15%: Stable (Grade B)
    CV < 20%: Moderate (Grade C)
    CV >= 20%: Unstable (Grade F)
    """
    results = []
    
    for metric in metrics:
        # Extract metric values per fold
        fold_values = [r[metric] for r in fold_results if metric in r]
        
        if len(fold_values) < 3:
            continue
        
        mean = np.mean(fold_values)
        std = np.std(fold_values)
        cv = (std / abs(mean)) if mean != 0 else 0
        
        # Stability grading
        if cv < 0.10:
            grade = "A"
            interpretation = "VERY STABLE - Consistent across all market regimes"
            is_stable = True
        elif cv < 0.15:
            grade = "B"
            interpretation = "STABLE - Minor variations, acceptable for trading"
            is_stable = True
        elif cv < 0.20:
            grade = "C"
            interpretation = "MODERATE - Some regime sensitivity, use caution"
            is_stable = False
        else:
            grade = "F"
            interpretation = "UNSTABLE - Significant regime dependency, investigate before using"
            is_stable = False
        
        results.append(FoldStabilityResult(
            metric_name=metric,
            fold_values=fold_values,
            mean=mean,
            std=std,
            cv=cv,
            is_stable=is_stable,
            stability_grade=grade,
            interpretation=interpretation
        ))
    
    return results


def print_fold_stability_report(results: List[FoldStabilityResult]):
    """Print fold stability report."""
    print("\n" + "=" * 70)
    print("  FOLD STABILITY ANALYSIS")
    print("  (Cross-Validation Consistency Check)")
    print("=" * 70)
    
    for r in results:
        grade_emoji = {"A": "🟢", "B": "🟡", "C": "🟠", "F": "🔴"}
        
        print(f"\n  {r.metric_name.upper()}:")
        print(f"  ─────────────────────────────")
        print(f"  Fold values: {['%.3f' % v for v in r.fold_values]}")
        print(f"  Mean ± Std:  {r.mean:.4f} ± {r.std:.4f}")
        print(f"  CV:          {r.cv*100:.1f}%")
        print(f"  Grade:       {grade_emoji.get(r.stability_grade, '❓')} {r.stability_grade}")
        print(f"  Status:      {r.interpretation}")
    
    # Overall assessment
    all_stable = all(r.is_stable for r in results)
    print(f"\n  OVERALL: {'✅ Model is stable across folds' if all_stable else '⚠️ Model shows instability'}")
```

## 8.5 Stage 4: Config Comparison Significance

```python
"""
CONFIG COMPARISON SIGNIFICANCE

When comparing two configs, test if the difference in 
performance is statistically significant or just random variation.
"""

@dataclass
class ConfigComparisonResult:
    """Results of comparing two configs."""
    config_a: str
    config_b: str
    metric: str
    value_a: float
    value_b: float
    difference: float
    pct_difference: float
    t_statistic: float
    p_value: float
    is_significant: bool
    better_config: str
    confidence: str


def compare_configs_significance(
    results_a: List[dict],  # Results per fold for config A
    results_b: List[dict],  # Results per fold for config B
    config_a_name: str,
    config_b_name: str,
    metric: str = 'ev'
) -> ConfigComparisonResult:
    """
    Compare two configs using paired t-test across folds.
    
    This tests if the difference is statistically significant,
    not just random variation between runs.
    """
    values_a = [r[metric] for r in results_a]
    values_b = [r[metric] for r in results_b]
    
    # Paired t-test (same folds, different configs)
    t_stat, p_value = stats.ttest_rel(values_a, values_b)
    
    mean_a = np.mean(values_a)
    mean_b = np.mean(values_b)
    difference = mean_b - mean_a
    pct_diff = (difference / abs(mean_a) * 100) if mean_a != 0 else 0
    
    is_significant = p_value < 0.05
    better = config_b_name if difference > 0 else config_a_name
    
    # Confidence level
    if p_value < 0.01:
        confidence = "HIGH (p < 0.01) - Very confident"
    elif p_value < 0.05:
        confidence = "MEDIUM (p < 0.05) - Confident"
    elif p_value < 0.10:
        confidence = "LOW (p < 0.10) - Marginal"
    else:
        confidence = "NONE (p >= 0.10) - Not significant"
    
    return ConfigComparisonResult(
        config_a=config_a_name,
        config_b=config_b_name,
        metric=metric,
        value_a=mean_a,
        value_b=mean_b,
        difference=difference,
        pct_difference=pct_diff,
        t_statistic=t_stat,
        p_value=p_value,
        is_significant=is_significant,
        better_config=better if is_significant else "NO CLEAR WINNER",
        confidence=confidence
    )


def compare_top_configs(all_results: List[dict], top_n: int = 5):
    """Compare top N configs against each other."""
    print("\n" + "=" * 70)
    print("  CONFIG COMPARISON MATRIX")
    print("  (Statistical Significance of Differences)")
    print("=" * 70)
    
    # Get top configs by EV
    sorted_configs = sorted(all_results, key=lambda x: x['ev_mean'], reverse=True)[:top_n]
    
    print(f"\n  Comparing top {top_n} configs:")
    for i, config in enumerate(sorted_configs, 1):
        print(f"  {i}. {config['config_id']}: EV={config['ev_mean']:+.2f}")
    
    # Compare #1 vs others
    best = sorted_configs[0]
    print(f"\n  Is #{1} ({best['config_id']}) significantly better?")
    print(f"  " + "─" * 50)
    
    for i, other in enumerate(sorted_configs[1:], 2):
        # This would need fold-level data for proper comparison
        ev_diff = best['ev_mean'] - other['ev_mean']
        print(f"  vs #{i} ({other['config_id']}): Δ={ev_diff:+.2f} pips")
```

## 8.6 Summary: Statistical Validation Framework

```
STELLA ALPHA STATISTICAL VALIDATION FRAMEWORK
═══════════════════════════════════════════════════════════════════

STAGE 1: FEATURE PRE-FILTER (Before RFE)
────────────────────────────────────────
• When: After feature engineering, before RFE
• Test: T-test + Cohen's d effect size
• Purpose: Remove noise features early
• Input: ~296 features
• Output: ~80-120 statistically significant features
• Benefit: Faster RFE, cleaner signal, less overfitting

STAGE 2: FEATURE IMPORTANCE VALIDATION (After Training)
───────────────────────────────────────────────────────
• When: After LightGBM training per fold
• Test: T-test on each top feature
• Purpose: Confirm important features have real predictive power
• Output: Confidence rating (HIGH/MEDIUM/LOW/UNVALIDATED)
• Benefit: Identify potential overfitting to noise

STAGE 3: FOLD STABILITY TESTING (After CV)
──────────────────────────────────────────
• When: After all folds complete
• Test: Coefficient of Variation analysis
• Purpose: Check consistency across time periods
• Output: Stability grade (A/B/C/F)
• Benefit: Identify regime-dependent models

STAGE 4: CONFIG COMPARISON (Final Selection)
────────────────────────────────────────────
• When: Comparing final config candidates
• Test: Paired t-test across folds
• Purpose: Ensure config differences are real, not luck
• Output: Significance level + confidence
• Benefit: Confident config selection

SIGNIFICANCE THRESHOLDS:
────────────────────────
• P-value < 0.001: Highly significant (***)
• P-value < 0.01:  Very significant (**)
• P-value < 0.05:  Significant (*)
• P-value >= 0.05: Not significant

EFFECT SIZE THRESHOLDS (Cohen's d):
───────────────────────────────────
• d > 0.8: Large effect
• d > 0.5: Medium effect
• d > 0.2: Small effect
• d < 0.2: Negligible effect
```

---

# 9. MULTI-MODEL EXPORT & TIER CLASSIFICATION

## 9.1 Overview

```
STELLA ALPHA OUTPUT:
────────────────────

Instead of saving ONE "best" model, Stella Alpha saves:
• ALL passing config models (each as separate .pkl file)
• Tier classification for each model
• Config details (TP, SL, Hold, Threshold)

WHY MULTIPLE MODELS?
• Each config answers a different question
• TP=100 SL=30 model: "Will price move 100 pips?"
• TP=50 SL=30 model: "Will price move 50 pips?"
• Different models for different trade setups
• Allows hierarchical execution (check Tier 0 first, then Tier 1, etc.)
```

## 9.2 Tier Classification Rules

```
TIER CLASSIFICATION (Based on Risk:Reward Ratio):
═════════════════════════════════════════════════

NOTE: With fixed SL=30 and minimum TP=50, ALL configs have R:R >= 1.67:1
      No Tier 2 or Rejected configs possible in Stella Alpha.

TIER 0 - RUNNERS 🚀
───────────────────
Criteria: R:R >= 2.5:1 (TP >= 75 with SL=30)
Examples:
  • TP=150 SL=30 → 5.0:1 R:R   ✅ Tier 0
  • TP=120 SL=30 → 4.0:1 R:R   ✅ Tier 0
  • TP=100 SL=30 → 3.33:1 R:R  ✅ Tier 0
  • TP=90 SL=30  → 3.0:1 R:R   ✅ Tier 0
  • TP=80 SL=30  → 2.67:1 R:R  ✅ Tier 0
  • TP=75 SL=30  → 2.5:1 R:R   ✅ Tier 0 (minimum for this tier)

Min win rate needed: 17-29%
Characteristic: One winner covers 3-5 losers


TIER 1 - IDEAL ⭐
─────────────────
Criteria: R:R 1.67:1 to 2.49:1 (TP 50-74 with SL=30)
Examples:
  • TP=70 SL=30  → 2.33:1 R:R  ✅ Tier 1
  • TP=60 SL=30  → 2.0:1 R:R   ✅ Tier 1
  • TP=50 SL=30  → 1.67:1 R:R  ✅ Tier 1 (minimum config)

Min win rate needed: 30-37%
Characteristic: Balanced risk/reward, good profitability


NOT APPLICABLE IN STELLA ALPHA:
───────────────────────────────
TIER 2 - ACCEPTABLE (R:R 1.0:1 to 1.49:1)
  → Not possible with TP>=50 and SL=30

REJECTED (R:R < 1.0:1)
  → Not possible with TP>=50 and SL=30


CONFIG SPACE SUMMARY:
─────────────────────
TP Range: 50 to 150 (step 10) = 11 values
SL Fixed: 30
Hold Range: 12 to 72 (step 12) = 6 values
Total Configs: 66

All configs guaranteed R:R >= 1.67:1 ✅
```

## 9.3 Tier Classification Code

```python
# src/tier_classification.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional

class Tier(Enum):
    """Trade tier classification."""
    TIER_0_RUNNER = 0
    TIER_1_IDEAL = 1
    # Note: No Tier 2 in Stella Alpha (min R:R is 1.67:1)


@dataclass
class TierClassification:
    """Tier classification result for a config."""
    config_id: str
    tp_pips: int
    sl_pips: int
    max_hold: int
    risk_reward_ratio: float
    tier: Tier
    tier_name: str
    tier_emoji: str
    min_winrate_needed: float


def calculate_risk_reward(tp_pips: int, sl_pips: int) -> float:
    """Calculate R:R ratio (TP/SL)."""
    return tp_pips / sl_pips if sl_pips > 0 else 0


def calculate_min_winrate(tp_pips: int, sl_pips: int) -> float:
    """Calculate minimum win rate needed to break even."""
    return sl_pips / (tp_pips + sl_pips)


def classify_tier(tp_pips: int, sl_pips: int, max_hold: int) -> TierClassification:
    """
    Classify a config into a tier based on R:R ratio.
    
    Stella Alpha Config Space:
    - SL is fixed at 30 pips
    - TP ranges from 50 to 150 pips
    - Minimum R:R is 1.67:1 (TP=50/SL=30)
    
    Tier 0 (Runner):  R:R >= 2.5:1 (TP >= 75)
    Tier 1 (Ideal):   R:R 1.67:1 to 2.49:1 (TP 50-70)
    """
    rr = calculate_risk_reward(tp_pips, sl_pips)
    min_wr = calculate_min_winrate(tp_pips, sl_pips)
    config_id = f"TP{tp_pips}_SL{sl_pips}_H{max_hold}"
    
    if rr >= 2.5:
        return TierClassification(
            config_id=config_id,
            tp_pips=tp_pips,
            sl_pips=sl_pips,
            max_hold=max_hold,
            risk_reward_ratio=rr,
            tier=Tier.TIER_0_RUNNER,
            tier_name="TIER 0 - RUNNER",
            tier_emoji="🚀",
            min_winrate_needed=min_wr
        )
    else:  # R:R >= 1.67 (minimum in Stella Alpha)
        return TierClassification(
            config_id=config_id,
            tp_pips=tp_pips,
            sl_pips=sl_pips,
            max_hold=max_hold,
            risk_reward_ratio=rr,
            tier=Tier.TIER_1_IDEAL,
            tier_name="TIER 1 - IDEAL",
            tier_emoji="⭐",
            min_winrate_needed=min_wr
        )


def print_tier_summary(classifications: list):
    """Print summary of tier classifications."""
    print("\n" + "=" * 70)
    print("  TIER CLASSIFICATION SUMMARY")
    print("=" * 70)
    
    tier_0 = [c for c in classifications if c.tier == Tier.TIER_0_RUNNER]
    tier_1 = [c for c in classifications if c.tier == Tier.TIER_1_IDEAL]
    
    print(f"""
    TIER 0 - RUNNERS 🚀 (R:R >= 2.5:1):  {len(tier_0)} configs
    TIER 1 - IDEAL ⭐ (R:R 1.67-2.49:1): {len(tier_1)} configs
    ─────────────────────────────────────────────────
    TOTAL CONFIGS:                       {len(tier_0) + len(tier_1)} configs
    
    All configs have favorable R:R (minimum 1.67:1) ✅
    """)
    
    if tier_0:
        print("    TIER 0 - RUNNERS 🚀:")
        for c in sorted(tier_0, key=lambda x: x.risk_reward_ratio, reverse=True)[:5]:
            print(f"      {c.config_id}: R:R={c.risk_reward_ratio:.2f}:1, Need {c.min_winrate_needed*100:.1f}% WR")
        if len(tier_0) > 5:
            print(f"      ... and {len(tier_0) - 5} more")
    
    if tier_1:
        print("\n    TIER 1 - IDEAL ⭐:")
        for c in sorted(tier_1, key=lambda x: x.risk_reward_ratio, reverse=True):
            print(f"      {c.config_id}: R:R={c.risk_reward_ratio:.2f}:1, Need {c.min_winrate_needed*100:.1f}% WR")
```

## 9.4 Multi-Model Export

```python
# src/model_exporter.py

import pickle
import json
from pathlib import Path
from typing import List, Dict
from tier_classification import classify_tier, Tier

class MultiModelExporter:
    """
    Export multiple models - one for each passing config.
    All configs in Stella Alpha are exportable (R:R >= 1.67:1).
    """
    
    def __init__(self, output_dir: str = "artifacts/models"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.exported_models = []
    
    def export_model(
        self,
        model,
        config: dict,
        metrics: dict,
        selected_features: list,
        threshold: float
    ) -> dict:
        """
        Export a single model with its config and tier classification.
        """
        tp = config['tp_pips']
        sl = config['sl_pips']
        hold = config['max_holding_bars']
        
        # Classify tier
        tier_info = classify_tier(tp, sl, hold)
        
        # Create filenames
        config_id = tier_info.config_id
        model_filename = f"stella_{config_id}.pkl"
        config_filename = f"stella_{config_id}_config.json"
        
        # Save model
        model_path = self.output_dir / model_filename
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        # Create config JSON
        config_data = {
            "config_id": config_id,
            "tier": tier_info.tier.value,
            "tier_name": tier_info.tier_name,
            "tier_emoji": tier_info.tier_emoji,
            "tp_pips": tp,
            "sl_pips": sl,
            "max_holding_bars": hold,
            "risk_reward_ratio": tier_info.risk_reward_ratio,
            "min_winrate_needed": tier_info.min_winrate_needed,
            "threshold": threshold,
            "selected_features": selected_features,
            "metrics": {
                "precision": metrics.get('precision_mean', 0),
                "ev": metrics.get('ev_mean', 0),
                "recall": metrics.get('recall_mean', 0),
                "total_trades": metrics.get('total_trades', 0),
                "precision_cv": metrics.get('precision_cv', 0)
            },
            "model_file": model_filename
        }
        
        # Save config
        config_path = self.output_dir / config_filename
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"  {tier_info.tier_emoji} Exported: {config_id} (Tier {tier_info.tier.value})")
        
        self.exported_models.append(config_data)
        return config_data
    
    def export_tier_summary(self) -> dict:
        """
        Export summary of all models organized by tier.
        """
        summary = {
            "total_models": len(self.exported_models),
            "tier_0_runners": [],
            "tier_1_ideal": [],
            "best_per_tier": {}
        }
        
        # Organize by tier
        for model in self.exported_models:
            tier = model['tier']
            if tier == 0:
                summary['tier_0_runners'].append(model)
            elif tier == 1:
                summary['tier_1_ideal'].append(model)
        
        # Sort each tier by EV (best first)
        summary['tier_0_runners'].sort(key=lambda x: x['metrics']['ev'], reverse=True)
        summary['tier_1_ideal'].sort(key=lambda x: x['metrics']['ev'], reverse=True)
        
        # Best per tier
        if summary['tier_0_runners']:
            summary['best_per_tier']['tier_0'] = summary['tier_0_runners'][0]
        if summary['tier_1_ideal']:
            summary['best_per_tier']['tier_1'] = summary['tier_1_ideal'][0]
        
        # Save summary
        summary_path = self.output_dir / "tier_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary
    
    def print_export_summary(self):
        """Print summary of exported models."""
        print("\n" + "=" * 70)
        print("  MULTI-MODEL EXPORT SUMMARY")
        print("=" * 70)
        
        tier_0 = [m for m in self.exported_models if m['tier'] == 0]
        tier_1 = [m for m in self.exported_models if m['tier'] == 1]
        
        print(f"""
    Total Models Exported: {len(self.exported_models)}
    
    🚀 TIER 0 - RUNNERS (R:R >= 2.5:1): {len(tier_0)} models
    ⭐ TIER 1 - IDEAL (R:R 1.67-2.49:1): {len(tier_1)} models
    
    Output Directory: {self.output_dir}
        """)
        
        if tier_0:
            print("    🚀 TIER 0 - RUNNERS (Best R:R):")
            for m in tier_0[:5]:  # Top 5
                print(f"       {m['config_id']}: EV={m['metrics']['ev']:+.2f}, Precision={m['metrics']['precision']*100:.1f}%, R:R={m['risk_reward_ratio']:.2f}:1")
            if len(tier_0) > 5:
                print(f"       ... and {len(tier_0) - 5} more")
        
        if tier_1:
            print("\n    ⭐ TIER 1 - IDEAL:")
            for m in tier_1[:5]:
                print(f"       {m['config_id']}: EV={m['metrics']['ev']:+.2f}, Precision={m['metrics']['precision']*100:.1f}%, R:R={m['risk_reward_ratio']:.2f}:1")
            if len(tier_1) > 5:
                print(f"       ... and {len(tier_1) - 5} more")
        
        print("\n" + "=" * 70)
```

## 9.5 Output Artifacts Structure

```
artifacts/
├── models/                              # All exported models
│   ├── stella_TP100_SL30_H48.pkl       # Tier 0 model
│   ├── stella_TP100_SL30_H48_config.json
│   ├── stella_TP90_SL30_H48.pkl        # Tier 0 model
│   ├── stella_TP90_SL30_H48_config.json
│   ├── stella_TP80_SL30_H36.pkl        # Tier 1 model
│   ├── stella_TP80_SL30_H36_config.json
│   ├── stella_TP60_SL30_H36.pkl        # Tier 1 model
│   ├── stella_TP60_SL30_H36_config.json
│   ├── stella_TP50_SL30_H24.pkl        # Tier 2 model
│   ├── stella_TP50_SL30_H24_config.json
│   └── tier_summary.json               # Summary of all tiers
│
├── pure_ml_stella_alpha.db             # Checkpoint database
├── trades_stella_alpha.db              # Trade log
└── ...
```

## 9.6 Config JSON Format

```json
// artifacts/models/stella_TP100_SL30_H48_config.json

{
  "config_id": "TP100_SL30_H48",
  "tier": 0,
  "tier_name": "TIER 0 - RUNNER",
  "tier_emoji": "🚀",
  "tp_pips": 100,
  "sl_pips": 30,
  "max_holding_bars": 48,
  "risk_reward_ratio": 3.33,
  "min_winrate_needed": 0.231,
  "threshold": 0.55,
  "selected_features": [
    "rsi_value",
    "bb_position",
    "d1_trend_direction",
    "mtf_confluence_score",
    "..."
  ],
  "metrics": {
    "precision": 0.38,
    "ev": 15.2,
    "recall": 0.42,
    "total_trades": 2450,
    "precision_cv": 0.12
  },
  "model_file": "stella_TP100_SL30_H48.pkl"
}
```

## 9.7 Tier Summary JSON Format

```json
// artifacts/models/tier_summary.json

{
  "total_models": 12,
  
  "tier_0_runners": [
    {
      "config_id": "TP150_SL30_H48",
      "tier": 0,
      "tier_name": "TIER 0 - RUNNER",
      "tp_pips": 150,
      "sl_pips": 30,
      "risk_reward_ratio": 5.0,
      "metrics": {"precision": 0.28, "ev": 18.5}
    },
    {
      "config_id": "TP100_SL30_H48",
      "tier": 0,
      "tier_name": "TIER 0 - RUNNER",
      "tp_pips": 100,
      "sl_pips": 30,
      "risk_reward_ratio": 3.33,
      "metrics": {"precision": 0.38, "ev": 15.2}
    },
    {
      "config_id": "TP80_SL30_H36",
      "tier": 0,
      "tier_name": "TIER 0 - RUNNER",
      "tp_pips": 80,
      "sl_pips": 30,
      "risk_reward_ratio": 2.67,
      "metrics": {"precision": 0.45, "ev": 12.8}
    }
  ],
  
  "tier_1_ideal": [
    {
      "config_id": "TP70_SL30_H36",
      "tier": 1,
      "tier_name": "TIER 1 - IDEAL",
      "tp_pips": 70,
      "sl_pips": 30,
      "risk_reward_ratio": 2.33,
      "metrics": {"precision": 0.48, "ev": 9.5}
    },
    {
      "config_id": "TP60_SL30_H36",
      "tier": 1,
      "tier_name": "TIER 1 - IDEAL",
      "tp_pips": 60,
      "sl_pips": 30,
      "risk_reward_ratio": 2.0,
      "metrics": {"precision": 0.52, "ev": 8.2}
    },
    {
      "config_id": "TP50_SL30_H24",
      "tier": 1,
      "tier_name": "TIER 1 - IDEAL",
      "tp_pips": 50,
      "sl_pips": 30,
      "risk_reward_ratio": 1.67,
      "metrics": {"precision": 0.55, "ev": 6.2}
    }
  ],
  
  "best_per_tier": {
    "tier_0": {"config_id": "TP150_SL30_H48", "ev": 18.5, "rr": 5.0},
    "tier_1": {"config_id": "TP70_SL30_H36", "ev": 9.5, "rr": 2.33}
  },
  
  "config_space": {
    "tp_range": "50-150 (step 10)",
    "sl_fixed": 30,
    "hold_range": "12-72 (step 12)",
    "total_configs": 66,
    "min_rr": 1.67,
    "max_rr": 5.0
  }
}
```

## 9.8 Integration into Pipeline

```python
# In run_pure_ml_stella_alpha.py

def export_all_passing_models(results, checkpoint_db, config):
    """
    Export all passing configs as separate models with tier classification.
    """
    exporter = MultiModelExporter(output_dir="artifacts/models")
    
    # Get all passing results
    passing_results = [r for r in results if r['status'] == 'passed']
    
    print(f"\nExporting {len(passing_results)} passing models...")
    
    for result in passing_results:
        # Load the trained model for this config
        model = load_model_from_checkpoint(checkpoint_db, result['config_id'])
        
        exporter.export_model(
            model=model,
            config={
                'tp_pips': result['tp_pips'],
                'sl_pips': result['sl_pips'],
                'max_holding_bars': result['max_holding_bars']
            },
            metrics={
                'precision_mean': result['precision_mean'],
                'ev_mean': result['ev_mean'],
                'recall_mean': result['recall_mean'],
                'total_trades': result['total_trades'],
                'precision_cv': result['precision_cv']
            },
            selected_features=result['selected_features'],
            threshold=result['consensus_threshold']
        )
    
    # Export tier summary
    summary = exporter.export_tier_summary()
    exporter.print_export_summary()
    
    return summary
```

---

# 10. PIPELINE ARCHITECTURE

## 8.1 High-Level Flow (Updated with Loss Analysis)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Stella Alpha PIPELINE FLOW (WITH LOSS ANALYSIS)            │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐     ┌──────────────┐
    │   H4 CSV     │     │   D1 CSV     │
    │   (input)    │     │   (input)    │
    └──────┬───────┘     └──────┬───────┘
           │                    │
           └────────┬───────────┘
                    ↓
    ┌───────────────────────────────────────┐
    │  STEP 1: LOAD & MERGE                 │
    │  • Load H4 data                       │
    │  • Load D1 data                       │
    │  • Safe merge (no leakage)            │
    │  • Validate merge                     │
    └───────────────────┬───────────────────┘
                        ↓
    ┌───────────────────────────────────────┐
    │  STEP 2: FEATURE ENGINEERING          │
    │  • H4 derived features (V4)           │
    │  • D1 derived features (NEW)          │
    │  • Cross-TF features (NEW)            │
    │  • ~296 total features                │
    └───────────────────┬───────────────────┘
                        ↓
    ┌───────────────────────────────────────┐
    │  STEP 3: PRE-COMPUTE LABELS           │
    │  • For each (TP, SL, MaxHold) config  │
    │  • Label based on H4 price movement   │
    │  • Cache labels for efficiency        │
    └───────────────────┬───────────────────┘
                        ↓
    ┌───────────────────────────────────────┐
    │  STEP 4: CHECK CHECKPOINT             │
    │  • Load pure_ml_stella_alpha.db                 │
    │  • Find completed configs             │
    │  • Filter to pending configs only     │
    │  • Display resume status              │
    └───────────────────┬───────────────────┘
                        ↓
    ┌───────────────────────────────────────┐
    │  STEP 5: PARALLEL EXPERIMENTS         │
    │  • ProcessPoolExecutor                │
    │  • N workers (configurable)           │
    │  • Live progress display              │
    │  • For each config:                   │
    │    ├── Walk-forward CV (5 folds)      │
    │    ├── RFE feature selection          │
    │    ├── LightGBM training              │
    │    ├── Threshold optimization         │
    │    ├── Evaluation                     │
    │    ├── ★ RECORD ALL TRADES ★ (NEW)   │
    │    └── Save to checkpoint DB          │
    └───────────────────┬───────────────────┘
                        ↓
    ┌───────────────────────────────────────┐
    │  STEP 6: LOSS ANALYSIS (NEW)          │
    │  • Load all recorded trades           │
    │  • Separate WINS vs LOSSES            │
    │  • Compare feature distributions      │
    │  • Statistical significance tests     │
    │  • Generate loss patterns report      │
    └───────────────────┬───────────────────┘
                        ↓
    ┌───────────────────────────────────────┐
    │  STEP 7: FILTER RECOMMENDATIONS (NEW) │
    │  • Generate candidate filters         │
    │  • Simulate each filter's impact      │
    │  • Calculate net P&L improvement      │
    │  • Rank and recommend filters         │
    │  • Test filter combinations           │
    └───────────────────┬───────────────────┘
                        ↓
    ┌───────────────────────────────────────┐
    │  STEP 8: RESULTS & ARTIFACTS          │
    │  • Find best config                   │
    │  • Save model, features, metrics      │
    │  • Save trade log (trades_stella_alpha.db)      │
    │  • Save loss analysis report          │
    │  • Save filter recommendations        │
    │  • Generate summary report            │
    └───────────────────────────────────────┘
```

## 8.2 Trade Recording Integration

```python
# During Step 5 (Experiments), for each fold's test predictions:

def record_trades(
    df_test: pd.DataFrame,
    y_true: pd.Series,
    y_pred: pd.Series,
    y_proba: np.ndarray,
    config: dict,
    fold: int,
    trade_db: TradeDatabase
):
    """
    Record every trade decision for loss analysis.
    
    Args:
        df_test: Test dataframe with all features
        y_true: Actual outcomes (1=win, 0=loss)
        y_pred: Model predictions (1=trade, 0=no trade)
        y_proba: Model probabilities
        config: Config being tested (TP, SL, Hold)
        fold: Current fold number
        trade_db: Database connection for recording
    """
    # Get indices where model decided to trade
    trade_indices = y_pred == 1
    
    for idx in df_test[trade_indices].index:
        row = df_test.loc[idx]
        
        trade_record = {
            'config_id': f"TP{config['tp']}_SL{config['sl']}_H{config['hold']}",
            'fold': fold,
            'timestamp': str(row['timestamp']),
            'outcome': 'WIN' if y_true.loc[idx] == 1 else 'LOSS',
            'pips_result': config['tp'] if y_true.loc[idx] == 1 else -config['sl'],
            'model_probability': float(y_proba[idx]),
            
            # H4 features at entry
            'h4_rsi_value': row.get('rsi_value', None),
            'h4_bb_position': row.get('bb_position', None),
            'h4_trend_strength': row.get('trend_strength', None),
            'h4_atr_pct': row.get('atr_pct', None),
            'h4_volume_ratio': row.get('volume_ratio', None),
            'h4_hour': row.get('hour', None),
            'h4_is_london_session': row.get('is_london_session', None),
            'h4_is_ny_session': row.get('is_ny_session', None),
            'h4_is_asian_session': row.get('is_asian_session', None),
            
            # D1 features at entry
            'd1_rsi_value': row.get('d1_rsi_value', None),
            'd1_bb_position': row.get('d1_bb_position', None),
            'd1_trend_strength': row.get('d1_trend_strength', None),
            'd1_trend_direction': row.get('d1_trend_direction', None),
            'd1_is_trending_up': row.get('d1_is_trending_up', None),
            
            # Cross-TF features
            'mtf_confluence_score': row.get('mtf_confluence_score', None),
            'mtf_rsi_aligned': row.get('mtf_rsi_aligned', None),
            'mtf_trend_aligned': row.get('mtf_trend_aligned', None),
            'd1_supports_short': row.get('d1_supports_short', None),
            'd1_opposes_short': row.get('d1_opposes_short', None),
        }
        
        trade_db.insert_trade(trade_record)
```

---

# 11. CHECKPOINT & RESUME SYSTEM

## 11.1 Overview

```
PURPOSE:
Enable interrupt/resume capability for long-running experiments.
Store all results, models, and progress in SQLite database.

KEY FEATURES:
├── Resume from any interruption point
├── Skip already-completed configs
├── Store trained models for later export
├── Thread-safe for parallel execution
├── Progress tracking and ETA calculation
```

## 11.2 Database Schema

```sql
-- File: artifacts/pure_ml_stella_alpha.db

-- Main results table
CREATE TABLE IF NOT EXISTS completed (
    -- Primary key (config identifier)
    config_id TEXT PRIMARY KEY,
    tp_pips INTEGER NOT NULL,
    sl_pips INTEGER NOT NULL,
    max_holding_bars INTEGER NOT NULL,
    
    -- Status
    status TEXT NOT NULL,  -- 'passed' or 'failed'
    tier INTEGER,          -- 0, 1 (Stella Alpha only has 2 tiers)
    tier_name TEXT,        -- 'TIER 0 - RUNNER' or 'TIER 1 - IDEAL'
    
    -- Metrics (aggregated across folds)
    ev_mean REAL,
    ev_std REAL,
    precision_mean REAL,
    precision_std REAL,
    precision_cv REAL,
    recall_mean REAL,
    f1_mean REAL,
    auc_pr_mean REAL,
    total_trades INTEGER,
    
    -- Feature selection
    selected_features TEXT,  -- JSON array
    n_features INTEGER,
    consensus_threshold REAL,
    
    -- Classification
    classification TEXT,  -- 'GOLD', 'SILVER', 'BRONZE', or NULL
    
    -- Rejection info (if failed)
    rejection_reasons TEXT,  -- JSON array or NULL
    
    -- Risk/Reward
    risk_reward_ratio REAL,
    min_winrate_required REAL,
    edge_above_breakeven REAL,
    
    -- Execution metadata
    execution_time_seconds REAL,
    completed_at TEXT,
    
    UNIQUE(tp_pips, sl_pips, max_holding_bars)
);

-- Models table (for multi-model export)
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id TEXT NOT NULL,
    fold INTEGER NOT NULL,
    model_blob BLOB NOT NULL,  -- Pickled model
    threshold REAL,
    precision REAL,
    ev REAL,
    saved_at TEXT,
    
    UNIQUE(config_id, fold),
    FOREIGN KEY (config_id) REFERENCES completed(config_id)
);

-- Per-fold results (for detailed analysis)
CREATE TABLE IF NOT EXISTS fold_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id TEXT NOT NULL,
    fold INTEGER NOT NULL,
    
    -- Fold-specific metrics
    precision REAL,
    recall REAL,
    f1 REAL,
    ev REAL,
    auc_pr REAL,
    threshold REAL,
    n_trades INTEGER,
    
    -- Fold date range
    train_start TEXT,
    train_end TEXT,
    test_start TEXT,
    test_end TEXT,
    
    UNIQUE(config_id, fold),
    FOREIGN KEY (config_id) REFERENCES completed(config_id)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_status ON completed(status);
CREATE INDEX IF NOT EXISTS idx_tier ON completed(tier);
CREATE INDEX IF NOT EXISTS idx_ev ON completed(ev_mean DESC);
CREATE INDEX IF NOT EXISTS idx_classification ON completed(classification);
```

## 11.3 Checkpoint Manager Implementation

```python
# src/checkpoint_db.py

import sqlite3
import pickle
import json
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ConfigResult:
    """Result for a single config."""
    config_id: str
    tp_pips: int
    sl_pips: int
    max_holding_bars: int
    status: str
    tier: int
    tier_name: str
    ev_mean: float
    ev_std: float
    precision_mean: float
    precision_std: float
    precision_cv: float
    recall_mean: float
    f1_mean: float
    auc_pr_mean: float
    total_trades: int
    selected_features: List[str]
    n_features: int
    consensus_threshold: float
    classification: Optional[str]
    rejection_reasons: Optional[List[str]]
    risk_reward_ratio: float
    min_winrate_required: float
    edge_above_breakeven: float
    execution_time_seconds: float


class CheckpointDB:
    """
    Thread-safe checkpoint database manager.
    
    Provides:
    - Resume capability from interruption
    - Model storage for multi-model export
    - Progress tracking
    - Thread-safe parallel access
    """
    
    def __init__(self, db_path: str = "artifacts/pure_ml_stella_alpha.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(str(self.db_path), timeout=30)
            self._local.conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL for concurrency
            self._local.conn.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS completed (
                config_id TEXT PRIMARY KEY,
                tp_pips INTEGER NOT NULL,
                sl_pips INTEGER NOT NULL,
                max_holding_bars INTEGER NOT NULL,
                status TEXT NOT NULL,
                tier INTEGER,
                tier_name TEXT,
                ev_mean REAL,
                ev_std REAL,
                precision_mean REAL,
                precision_std REAL,
                precision_cv REAL,
                recall_mean REAL,
                f1_mean REAL,
                auc_pr_mean REAL,
                total_trades INTEGER,
                selected_features TEXT,
                n_features INTEGER,
                consensus_threshold REAL,
                classification TEXT,
                rejection_reasons TEXT,
                risk_reward_ratio REAL,
                min_winrate_required REAL,
                edge_above_breakeven REAL,
                execution_time_seconds REAL,
                completed_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_id TEXT NOT NULL,
                fold INTEGER NOT NULL,
                model_blob BLOB NOT NULL,
                threshold REAL,
                precision REAL,
                ev REAL,
                saved_at TEXT,
                UNIQUE(config_id, fold)
            );
            
            CREATE TABLE IF NOT EXISTS fold_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_id TEXT NOT NULL,
                fold INTEGER NOT NULL,
                precision REAL,
                recall REAL,
                f1 REAL,
                ev REAL,
                auc_pr REAL,
                threshold REAL,
                n_trades INTEGER,
                train_start TEXT,
                train_end TEXT,
                test_start TEXT,
                test_end TEXT,
                UNIQUE(config_id, fold)
            );
            
            CREATE INDEX IF NOT EXISTS idx_status ON completed(status);
            CREATE INDEX IF NOT EXISTS idx_tier ON completed(tier);
            CREATE INDEX IF NOT EXISTS idx_ev ON completed(ev_mean DESC);
        """)
        conn.commit()
    
    def is_completed(self, config_id: str) -> bool:
        """Check if config already completed."""
        conn = self._get_connection()
        result = conn.execute(
            "SELECT 1 FROM completed WHERE config_id = ?",
            (config_id,)
        ).fetchone()
        return result is not None
    
    def get_completed_configs(self) -> List[str]:
        """Get list of completed config IDs."""
        conn = self._get_connection()
        results = conn.execute("SELECT config_id FROM completed").fetchall()
        return [r['config_id'] for r in results]
    
    def get_pending_configs(self, all_configs: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int]]:
        """Filter to configs not yet completed."""
        completed = set(self.get_completed_configs())
        pending = []
        for tp, sl, hold in all_configs:
            config_id = f"TP{tp}_SL{sl}_H{hold}"
            if config_id not in completed:
                pending.append((tp, sl, hold))
        return pending
    
    def save_result(self, result: ConfigResult):
        """Save completed config result."""
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO completed (
                config_id, tp_pips, sl_pips, max_holding_bars,
                status, tier, tier_name,
                ev_mean, ev_std, precision_mean, precision_std, precision_cv,
                recall_mean, f1_mean, auc_pr_mean, total_trades,
                selected_features, n_features, consensus_threshold,
                classification, rejection_reasons,
                risk_reward_ratio, min_winrate_required, edge_above_breakeven,
                execution_time_seconds, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.config_id, result.tp_pips, result.sl_pips, result.max_holding_bars,
            result.status, result.tier, result.tier_name,
            result.ev_mean, result.ev_std, result.precision_mean, result.precision_std, result.precision_cv,
            result.recall_mean, result.f1_mean, result.auc_pr_mean, result.total_trades,
            json.dumps(result.selected_features), result.n_features, result.consensus_threshold,
            result.classification, json.dumps(result.rejection_reasons) if result.rejection_reasons else None,
            result.risk_reward_ratio, result.min_winrate_required, result.edge_above_breakeven,
            result.execution_time_seconds, datetime.now().isoformat()
        ))
        conn.commit()
    
    def save_model(self, config_id: str, fold: int, model, threshold: float, precision: float, ev: float):
        """Save trained model to database."""
        conn = self._get_connection()
        model_bytes = pickle.dumps(model)
        conn.execute("""
            INSERT OR REPLACE INTO models (config_id, fold, model_blob, threshold, precision, ev, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (config_id, fold, model_bytes, threshold, precision, ev, datetime.now().isoformat()))
        conn.commit()
    
    def load_model(self, config_id: str, fold: Optional[int] = None):
        """
        Load model from database.
        
        Args:
            config_id: Config identifier
            fold: Specific fold, or None for best fold
        """
        conn = self._get_connection()
        if fold is not None:
            result = conn.execute(
                "SELECT model_blob FROM models WHERE config_id = ? AND fold = ?",
                (config_id, fold)
            ).fetchone()
        else:
            # Get model with best precision
            result = conn.execute(
                "SELECT model_blob FROM models WHERE config_id = ? ORDER BY precision DESC LIMIT 1",
                (config_id,)
            ).fetchone()
        
        if result:
            return pickle.loads(result['model_blob'])
        return None
    
    def save_fold_result(self, config_id: str, fold: int, metrics: dict, date_range: dict):
        """Save per-fold results."""
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO fold_results (
                config_id, fold, precision, recall, f1, ev, auc_pr, threshold, n_trades,
                train_start, train_end, test_start, test_end
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            config_id, fold,
            metrics.get('precision'), metrics.get('recall'), metrics.get('f1'),
            metrics.get('ev'), metrics.get('auc_pr'), metrics.get('threshold'), metrics.get('n_trades'),
            date_range.get('train_start'), date_range.get('train_end'),
            date_range.get('test_start'), date_range.get('test_end')
        ))
        conn.commit()
    
    def get_all_results(self) -> List[Dict]:
        """Get all completed results."""
        conn = self._get_connection()
        results = conn.execute("SELECT * FROM completed ORDER BY ev_mean DESC").fetchall()
        return [dict(r) for r in results]
    
    def get_passed_results(self) -> List[Dict]:
        """Get only passing results."""
        conn = self._get_connection()
        results = conn.execute(
            "SELECT * FROM completed WHERE status = 'passed' ORDER BY ev_mean DESC"
        ).fetchall()
        return [dict(r) for r in results]
    
    def get_progress_stats(self, total_configs: int) -> Dict:
        """Get progress statistics."""
        conn = self._get_connection()
        
        completed = conn.execute("SELECT COUNT(*) as c FROM completed").fetchone()['c']
        passed = conn.execute("SELECT COUNT(*) as c FROM completed WHERE status = 'passed'").fetchone()['c']
        failed = conn.execute("SELECT COUNT(*) as c FROM completed WHERE status = 'failed'").fetchone()['c']
        
        gold = conn.execute("SELECT COUNT(*) as c FROM completed WHERE classification = 'GOLD'").fetchone()['c']
        silver = conn.execute("SELECT COUNT(*) as c FROM completed WHERE classification = 'SILVER'").fetchone()['c']
        bronze = conn.execute("SELECT COUNT(*) as c FROM completed WHERE classification = 'BRONZE'").fetchone()['c']
        
        tier_0 = conn.execute("SELECT COUNT(*) as c FROM completed WHERE tier = 0 AND status = 'passed'").fetchone()['c']
        tier_1 = conn.execute("SELECT COUNT(*) as c FROM completed WHERE tier = 1 AND status = 'passed'").fetchone()['c']
        
        return {
            'total_configs': total_configs,
            'completed': completed,
            'pending': total_configs - completed,
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / completed if completed > 0 else 0,
            'gold': gold,
            'silver': silver,
            'bronze': bronze,
            'tier_0_runners': tier_0,
            'tier_1_ideal': tier_1
        }
    
    def close(self):
        """Close thread-local connection."""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn
```

## 11.4 Resume Logic

```python
def run_pipeline_with_resume(config: dict, logger) -> List[Dict]:
    """
    Run pipeline with checkpoint/resume support.
    """
    # 1. Initialize checkpoint DB
    db = CheckpointDB(config['checkpoint_db'])
    
    # 2. Generate all configs
    all_configs = generate_config_space(config)
    total = len(all_configs)
    logger.log(f"Total configs in space: {total}")
    
    # 3. Filter to pending only
    pending_configs = db.get_pending_configs(all_configs)
    completed_count = total - len(pending_configs)
    
    if completed_count > 0:
        stats = db.get_progress_stats(total)
        logger.log(f"")
        logger.log(f"═══════════════════════════════════════════")
        logger.log(f"  RESUMING FROM CHECKPOINT")
        logger.log(f"═══════════════════════════════════════════")
        logger.log(f"  Completed: {completed_count}/{total} ({100*completed_count/total:.1f}%)")
        logger.log(f"  Passed: {stats['passed']} | Failed: {stats['failed']}")
        logger.log(f"  GOLD: {stats['gold']} | SILVER: {stats['silver']} | BRONZE: {stats['bronze']}")
        logger.log(f"  Tier 0 🚀: {stats['tier_0_runners']} | Tier 1 ⭐: {stats['tier_1_ideal']}")
        logger.log(f"  Remaining: {len(pending_configs)} configs")
        logger.log(f"═══════════════════════════════════════════")
        logger.log(f"")
    
    if len(pending_configs) == 0:
        logger.log("All configs completed! Loading results from checkpoint...")
        return db.get_all_results()
    
    # 4. Run pending configs
    results = run_experiments_parallel(pending_configs, db, config, logger)
    
    # 5. Return all results (completed + new)
    return db.get_all_results()
```

---

# 12. PARALLEL PROCESSING SYSTEM

## 12.1 Overview

```
PURPOSE:
Execute multiple config experiments in parallel to reduce total runtime.

KEY FEATURES:
├── ProcessPoolExecutor for true parallelism
├── Configurable worker count via CLI (-w argument)
├── Live terminal display with progress bar
├── Worker status display
├── ETA calculation
├── Thread-safe checkpoint saving
```

## 12.2 Parallel Runner Implementation

```python
# src/parallel_runner.py

from concurrent.futures import ProcessPoolExecutor, as_completed
import threading
import time
import sys
from typing import List, Tuple, Callable, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class WorkerStatus:
    """Status of a single worker."""
    worker_id: int
    current_config: str
    start_time: float
    last_result: str


class ParallelExperimentRunner:
    """
    Parallel experiment execution with live progress display.
    """
    
    def __init__(self, n_workers: int, db, logger):
        self.n_workers = n_workers
        self.db = db
        self.logger = logger
        self.lock = threading.Lock()
        
        # Progress tracking
        self.completed = 0
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.start_time = None
        self.times = []  # Execution times for ETA
        self.worker_status = {}
        self._stop_display = False
    
    def run_all(
        self, 
        configs: List[Tuple[int, int, int]], 
        run_single_fn: Callable,
        shared_args: tuple
    ) -> List[Dict]:
        """
        Run all configs in parallel.
        
        Args:
            configs: List of (tp, sl, hold) tuples
            run_single_fn: Function to run single experiment
            shared_args: Arguments to pass to run_single_fn
        
        Returns:
            List of results
        """
        self.total = len(configs)
        self.start_time = time.time()
        results = []
        
        # Start progress display thread
        display_thread = threading.Thread(target=self._display_loop, daemon=True)
        display_thread.start()
        
        try:
            with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
                # Submit all jobs
                future_to_config = {
                    executor.submit(run_single_fn, cfg, *shared_args): cfg
                    for cfg in configs
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_config):
                    cfg = future_to_config[future]
                    config_id = f"TP{cfg[0]}_SL{cfg[1]}_H{cfg[2]}"
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        with self.lock:
                            self.completed += 1
                            exec_time = result.get('execution_time_seconds', 0)
                            self.times.append(exec_time)
                            
                            if result.get('status') == 'passed':
                                self.passed += 1
                            else:
                                self.failed += 1
                        
                    except Exception as e:
                        self.logger.log(f"ERROR: {config_id} failed: {str(e)}", level="ERROR")
                        with self.lock:
                            self.completed += 1
                            self.failed += 1
        
        finally:
            self._stop_display = True
            time.sleep(0.5)  # Let display thread finish
        
        return results
    
    def _display_loop(self):
        """Live progress display loop."""
        while not self._stop_display and self.completed < self.total:
            self._print_progress()
            time.sleep(2)  # Update every 2 seconds
        
        # Final display
        self._print_progress(final=True)
    
    def _print_progress(self, final=False):
        """Print progress bar and stats."""
        with self.lock:
            elapsed = time.time() - self.start_time
            
            # Progress bar
            pct = self.completed / self.total if self.total > 0 else 0
            bar_width = 40
            filled = int(bar_width * pct)
            bar = '█' * filled + '░' * (bar_width - filled)
            
            # ETA calculation
            if self.completed > 0 and self.times:
                avg_time = sum(self.times) / len(self.times)
                remaining = self.total - self.completed
                eta_seconds = avg_time * remaining
                eta_str = str(timedelta(seconds=int(eta_seconds)))
            else:
                avg_time = 0
                eta_str = "calculating..."
            
            # Pass rate
            pass_rate = self.passed / self.completed * 100 if self.completed > 0 else 0
            
            # Build display
            line = (
                f"\r[{bar}] {pct*100:5.1f}% │ "
                f"{self.completed}/{self.total} │ "
                f"✓:{self.passed} ✗:{self.failed} ({pass_rate:.0f}%) │ "
                f"ETA: {eta_str} │ "
                f"Avg: {avg_time:.1f}s"
            )
            
            if final:
                print(line)
                print()
            else:
                print(line, end='', flush=True)
```

## 12.3 Process-Safe Experiment Function

```python
def run_single_experiment(
    config_tuple: Tuple[int, int, int],
    df: pd.DataFrame,
    feature_columns: List[str],
    settings: dict
) -> Dict:
    """
    Run single experiment (called in worker process).
    
    IMPORTANT: This function must be picklable for multiprocessing.
    Do not use lambda functions or nested functions.
    """
    tp, sl, hold = config_tuple
    config_id = f"TP{tp}_SL{sl}_H{hold}"
    start_time = time.time()
    
    try:
        # 1. Generate labels for this config
        labels = generate_labels(df, tp, sl, hold)
        
        # 2. Run walk-forward CV
        fold_results = run_walk_forward_cv(
            df, labels, feature_columns, settings
        )
        
        # 3. Aggregate results
        result = aggregate_fold_results(fold_results, config_id, tp, sl, hold)
        result['execution_time_seconds'] = time.time() - start_time
        
        return result
        
    except Exception as e:
        return {
            'config_id': config_id,
            'tp_pips': tp,
            'sl_pips': sl,
            'max_holding_bars': hold,
            'status': 'failed',
            'rejection_reasons': [f"Exception: {str(e)}"],
            'execution_time_seconds': time.time() - start_time
        }
```

---

# 13. WALK-FORWARD CROSS-VALIDATION

## 13.1 Overview

```
PURPOSE:
Simulate real trading conditions by always training on past, testing on future.

KEY PRINCIPLES:
├── Training data always BEFORE test data (no lookahead)
├── Test periods move forward in time
├── Each fold represents a different market regime
├── 5 folds with 2-year test periods
├── Ensures model generalizes across time

DATA SPLIT (25 years: 2000-2025):
──────────────────────────────────
Fold 1: Train [2000-2015], Test [2015-2017]
Fold 2: Train [2000-2017], Test [2017-2019]
Fold 3: Train [2000-2019], Test [2019-2021]
Fold 4: Train [2000-2021], Test [2021-2023]
Fold 5: Train [2000-2023], Test [2023-2025]
```

## 13.2 Implementation

```python
# src/walk_forward_cv.py

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FoldDefinition:
    """Definition of a single CV fold."""
    fold_num: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


def define_walk_forward_folds(
    df: pd.DataFrame,
    n_folds: int = 5,
    test_years: int = 2
) -> List[FoldDefinition]:
    """
    Define walk-forward CV folds.
    
    Args:
        df: DataFrame with 'timestamp' column
        n_folds: Number of folds
        test_years: Years per test period
    
    Returns:
        List of FoldDefinition objects
    """
    timestamps = pd.to_datetime(df['timestamp'])
    min_date = timestamps.min()
    max_date = timestamps.max()
    
    total_days = (max_date - min_date).days
    test_days = test_years * 365
    
    folds = []
    
    for fold_idx in range(n_folds):
        # Calculate test period (moving backwards from end)
        test_end = max_date - pd.Timedelta(days=(n_folds - fold_idx - 1) * test_days)
        test_start = test_end - pd.Timedelta(days=test_days)
        
        # Training is everything before test
        train_start = min_date
        train_end = test_start
        
        folds.append(FoldDefinition(
            fold_num=fold_idx + 1,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end
        ))
    
    return folds


def get_fold_data(
    df: pd.DataFrame,
    fold: FoldDefinition
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data for a single fold.
    
    Returns:
        (train_df, test_df)
    """
    timestamps = pd.to_datetime(df['timestamp'])
    
    train_mask = (timestamps >= fold.train_start) & (timestamps < fold.train_end)
    test_mask = (timestamps >= fold.test_start) & (timestamps < fold.test_end)
    
    train_df = df[train_mask].copy()
    test_df = df[test_mask].copy()
    
    return train_df, test_df


def run_walk_forward_cv(
    df: pd.DataFrame,
    labels: pd.Series,
    feature_columns: List[str],
    settings: dict
) -> List[Dict]:
    """
    Run walk-forward cross-validation.
    
    CRITICAL: Statistical pre-filter must run INSIDE each fold
              using only training data to avoid leakage.
    """
    n_folds = settings.get('n_folds', 5)
    test_years = settings.get('test_years', 2)
    
    folds = define_walk_forward_folds(df, n_folds, test_years)
    fold_results = []
    
    for fold in folds:
        # 1. Split data
        train_df, test_df = get_fold_data(df, fold)
        y_train = labels.loc[train_df.index]
        y_test = labels.loc[test_df.index]
        
        # 2. Statistical pre-filter ON TRAINING DATA ONLY (no leakage!)
        stat_filter = StatisticalFeatureFilter(p_threshold=0.05)
        kept_features, _, _ = stat_filter.filter_features(
            train_df, feature_columns, label_column='label'
        )
        
        # 3. RFE feature selection on pre-filtered features
        selected_features = run_rfe(
            train_df[kept_features], y_train, settings
        )
        
        # 4. Train model
        X_train = train_df[selected_features]
        X_test = test_df[selected_features]
        
        model = train_lightgbm(X_train, y_train, settings)
        
        # 5. Optimize threshold
        y_train_proba = model.predict_proba(X_train)[:, 1]
        best_threshold = optimize_threshold(y_train, y_train_proba, settings)
        
        # 6. Evaluate on test
        y_test_proba = model.predict_proba(X_test)[:, 1]
        y_test_pred = (y_test_proba >= best_threshold).astype(int)
        
        metrics = calculate_metrics(y_test, y_test_pred, y_test_proba, settings)
        metrics['threshold'] = best_threshold
        metrics['selected_features'] = selected_features
        
        fold_results.append({
            'fold': fold.fold_num,
            'metrics': metrics,
            'model': model,
            'date_range': {
                'train_start': str(fold.train_start),
                'train_end': str(fold.train_end),
                'test_start': str(fold.test_start),
                'test_end': str(fold.test_end)
            }
        })
    
    return fold_results
```

## 13.3 Data Leakage Prevention Checklist

```
CRITICAL: Avoid these common leakage sources:

✅ DO:
├── Run statistical pre-filter on TRAINING data only
├── Run RFE on TRAINING data only
├── Optimize threshold on TRAINING data only
├── Use only PAST D1 data (previous day)
├── Calculate features on training period only

❌ DON'T:
├── Pre-filter on full dataset
├── Normalize using full dataset statistics
├── Use future D1 data
├── Optimize anything on test data
├── Look at test metrics during training
```

---

# 14. MODEL TRAINING CONFIGURATION

## 14.1 LightGBM Settings

```yaml
# In config/pure_ml_stella_alpha_settings.yaml

model:
  type: "lightgbm"
  
  params:
    # Core parameters
    n_estimators: 200
    max_depth: 6
    learning_rate: 0.05
    num_leaves: 31
    
    # Regularization
    min_child_samples: 50
    subsample: 0.8
    colsample_bytree: 0.8
    reg_alpha: 0.1
    reg_lambda: 0.1
    
    # Class imbalance handling
    class_weight: "balanced"
    
    # Performance
    n_jobs: -1
    verbose: -1
    force_col_wise: true
    
    # Reproducibility
    random_state: 42
```

## 14.2 Training Implementation

```python
# src/training.py

import lightgbm as lgb
import numpy as np
from sklearn.utils.class_weight import compute_class_weight
from typing import Dict, List

def train_lightgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    settings: dict
) -> lgb.LGBMClassifier:
    """
    Train LightGBM classifier with class balancing.
    """
    model_params = settings.get('model', {}).get('params', {})
    
    # Calculate class weights
    classes = np.unique(y_train)
    weights = compute_class_weight('balanced', classes=classes, y=y_train)
    class_weight_dict = dict(zip(classes, weights))
    
    # Create model
    model = lgb.LGBMClassifier(
        n_estimators=model_params.get('n_estimators', 200),
        max_depth=model_params.get('max_depth', 6),
        learning_rate=model_params.get('learning_rate', 0.05),
        num_leaves=model_params.get('num_leaves', 31),
        min_child_samples=model_params.get('min_child_samples', 50),
        subsample=model_params.get('subsample', 0.8),
        colsample_bytree=model_params.get('colsample_bytree', 0.8),
        reg_alpha=model_params.get('reg_alpha', 0.1),
        reg_lambda=model_params.get('reg_lambda', 0.1),
        class_weight=class_weight_dict,
        n_jobs=-1,
        verbose=-1,
        random_state=42,
        force_col_wise=True
    )
    
    # Train
    model.fit(X_train, y_train)
    
    return model
```

## 14.3 RFE Feature Selection

```python
# src/features.py

from sklearn.feature_selection import RFECV
from sklearn.model_selection import StratifiedKFold
import lightgbm as lgb

def run_rfe(
    X: pd.DataFrame,
    y: pd.Series,
    settings: dict
) -> List[str]:
    """
    Run Recursive Feature Elimination with Cross-Validation.
    """
    rfe_settings = settings.get('rfe', {})
    
    min_features = rfe_settings.get('min_features', 10)
    max_features = rfe_settings.get('max_features', 25)
    cv_folds = rfe_settings.get('cv_folds', 3)
    
    # Base estimator
    estimator = lgb.LGBMClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        n_jobs=-1,
        verbose=-1,
        random_state=42
    )
    
    # RFECV
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
    
    selector = RFECV(
        estimator=estimator,
        step=1,
        cv=cv,
        scoring='average_precision',
        min_features_to_select=min_features,
        n_jobs=-1
    )
    
    selector.fit(X, y)
    
    # Get selected features
    selected_mask = selector.support_
    selected_features = X.columns[selected_mask].tolist()
    
    # Limit to max_features if needed
    if len(selected_features) > max_features:
        # Sort by importance and take top
        importances = selector.estimator_.feature_importances_
        feature_importance = list(zip(selected_features, importances))
        feature_importance.sort(key=lambda x: x[1], reverse=True)
        selected_features = [f[0] for f in feature_importance[:max_features]]
    
    return selected_features
```

---

# 15. THRESHOLD OPTIMIZATION

## 15.1 Overview

```
PURPOSE:
Find the optimal prediction threshold that maximizes expected value.

DEFAULT THRESHOLD: 0.50 (predict positive if probability > 50%)
OPTIMAL THRESHOLD: May be higher (0.55-0.70) for better precision

THRESHOLDS TESTED: [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]

SELECTION CRITERIA:
1. Precision >= minimum required for positive EV
2. Sufficient trade volume (>= 30 trades)
3. Maximize expected value
```

## 15.2 Implementation

```python
# src/threshold_optimization.py

import numpy as np
from sklearn.metrics import precision_score
from typing import Tuple, List, Dict

def calculate_ev(precision: float, tp_pips: int, sl_pips: int) -> float:
    """Calculate expected value per trade."""
    return precision * tp_pips - (1 - precision) * sl_pips


def optimize_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    settings: dict
) -> float:
    """
    Find optimal prediction threshold.
    
    Returns:
        Best threshold that maximizes EV while meeting constraints
    """
    tp_pips = settings['tp_pips']
    sl_pips = settings['sl_pips']
    
    thresholds = settings.get('thresholds', [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70])
    min_trades = settings.get('min_trades_per_threshold', 30)
    
    # Calculate breakeven precision
    breakeven_precision = sl_pips / (tp_pips + sl_pips)
    
    best_threshold = 0.50
    best_ev = -np.inf
    
    for thresh in thresholds:
        y_pred = (y_proba >= thresh).astype(int)
        n_trades = y_pred.sum()
        
        # Skip if not enough trades
        if n_trades < min_trades:
            continue
        
        # Calculate precision
        precision = precision_score(y_true, y_pred, zero_division=0)
        
        # Skip if precision below breakeven
        if precision < breakeven_precision:
            continue
        
        # Calculate EV
        ev = calculate_ev(precision, tp_pips, sl_pips)
        
        if ev > best_ev:
            best_ev = ev
            best_threshold = thresh
    
    return best_threshold


def get_consensus_threshold(fold_thresholds: List[float]) -> float:
    """
    Get consensus threshold from multiple folds.
    
    Uses mode (most common) with fallback to median.
    """
    from collections import Counter
    
    if not fold_thresholds:
        return 0.50
    
    # Try mode first
    counter = Counter(fold_thresholds)
    mode, count = counter.most_common(1)[0]
    
    # If mode appears in majority of folds, use it
    if count > len(fold_thresholds) / 2:
        return mode
    
    # Otherwise use median
    return np.median(fold_thresholds)


def analyze_threshold_stability(fold_results: List[Dict]) -> Dict:
    """Analyze threshold consistency across folds."""
    thresholds = [f['metrics']['threshold'] for f in fold_results]
    
    return {
        'thresholds': thresholds,
        'mean': np.mean(thresholds),
        'std': np.std(thresholds),
        'cv': np.std(thresholds) / np.mean(thresholds) if np.mean(thresholds) > 0 else 0,
        'consensus': get_consensus_threshold(thresholds),
        'is_stable': np.std(thresholds) < 0.10
    }
```

---

# 16. EVALUATION METRICS

## 16.1 Metrics Calculated

```
PER-FOLD METRICS:
─────────────────
precision       # TP / (TP + FP) - Win rate
recall          # TP / (TP + FN) - Signal capture rate
f1_score        # Harmonic mean of precision and recall
auc_pr          # Area under Precision-Recall curve
ev              # Expected Value per trade
n_trades        # Number of trades taken
threshold       # Optimal threshold for this fold

AGGREGATED METRICS:
───────────────────
precision_mean  # Mean precision across folds
precision_std   # Std of precision across folds
precision_cv    # Coefficient of variation (std/mean)
ev_mean         # Mean EV across folds
ev_std          # Std of EV
recall_mean     # Mean recall
f1_mean         # Mean F1
auc_pr_mean     # Mean AUC-PR
total_trades    # Sum of trades across all folds

STELLA ALPHA SPECIFIC:
──────────────────────
risk_reward_ratio       # TP / SL
min_winrate_required    # SL / (TP + SL)
edge_above_breakeven    # precision - min_winrate_required
```

## 16.2 Implementation

```python
# src/evaluation.py

import numpy as np
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    average_precision_score, confusion_matrix
)
from typing import Dict, List

def calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    settings: dict
) -> Dict:
    """Calculate all evaluation metrics."""
    tp_pips = settings['tp_pips']
    sl_pips = settings['sl_pips']
    
    # Basic metrics
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    # AUC-PR
    try:
        auc_pr = average_precision_score(y_true, y_proba)
    except:
        auc_pr = 0.0
    
    # Trade stats
    n_trades = int(y_pred.sum())
    n_wins = int(((y_pred == 1) & (y_true == 1)).sum())
    n_losses = int(((y_pred == 1) & (y_true == 0)).sum())
    
    # Expected value
    ev = precision * tp_pips - (1 - precision) * sl_pips
    
    # Risk/Reward analysis
    rr = tp_pips / sl_pips
    min_wr = sl_pips / (tp_pips + sl_pips)
    edge = precision - min_wr
    
    return {
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'auc_pr': auc_pr,
        'ev': ev,
        'n_trades': n_trades,
        'n_wins': n_wins,
        'n_losses': n_losses,
        'risk_reward_ratio': rr,
        'min_winrate_required': min_wr,
        'edge_above_breakeven': edge
    }


def aggregate_fold_results(
    fold_results: List[Dict],
    config_id: str,
    tp_pips: int,
    sl_pips: int,
    max_hold: int
) -> Dict:
    """Aggregate metrics across all folds."""
    
    metrics_list = [f['metrics'] for f in fold_results]
    
    # Calculate means and stds
    precision_values = [m['precision'] for m in metrics_list]
    ev_values = [m['ev'] for m in metrics_list]
    
    precision_mean = np.mean(precision_values)
    precision_std = np.std(precision_values)
    precision_cv = precision_std / precision_mean if precision_mean > 0 else 0
    
    ev_mean = np.mean(ev_values)
    ev_std = np.std(ev_values)
    
    # Consensus threshold
    thresholds = [m['threshold'] for m in metrics_list]
    consensus_threshold = get_consensus_threshold(thresholds)
    
    # Feature consensus (features selected in >60% of folds)
    all_features = [set(m['selected_features']) for m in metrics_list]
    feature_counts = {}
    for features in all_features:
        for f in features:
            feature_counts[f] = feature_counts.get(f, 0) + 1
    
    n_folds = len(fold_results)
    consensus_features = [f for f, count in feature_counts.items() 
                          if count >= n_folds * 0.6]
    
    # Risk/Reward
    rr = tp_pips / sl_pips
    min_wr = sl_pips / (tp_pips + sl_pips)
    
    # Determine tier
    if rr >= 2.5:
        tier = 0
        tier_name = "TIER 0 - RUNNER"
    else:
        tier = 1
        tier_name = "TIER 1 - IDEAL"
    
    # Check if passed
    passed = check_acceptance_criteria(
        precision_mean, precision_cv, ev_mean,
        sum(m['n_trades'] for m in metrics_list),
        min_wr
    )
    
    # Classification
    classification = classify_config(
        precision_mean, precision_cv, ev_mean,
        sum(m['n_trades'] for m in metrics_list),
        min_wr
    ) if passed else None
    
    return {
        'config_id': config_id,
        'tp_pips': tp_pips,
        'sl_pips': sl_pips,
        'max_holding_bars': max_hold,
        'status': 'passed' if passed else 'failed',
        'tier': tier,
        'tier_name': tier_name,
        'ev_mean': ev_mean,
        'ev_std': ev_std,
        'precision_mean': precision_mean,
        'precision_std': precision_std,
        'precision_cv': precision_cv,
        'recall_mean': np.mean([m['recall'] for m in metrics_list]),
        'f1_mean': np.mean([m['f1'] for m in metrics_list]),
        'auc_pr_mean': np.mean([m['auc_pr'] for m in metrics_list]),
        'total_trades': sum(m['n_trades'] for m in metrics_list),
        'selected_features': consensus_features,
        'n_features': len(consensus_features),
        'consensus_threshold': consensus_threshold,
        'classification': classification,
        'risk_reward_ratio': rr,
        'min_winrate_required': min_wr,
        'edge_above_breakeven': precision_mean - min_wr,
        'rejection_reasons': get_rejection_reasons(
            precision_mean, precision_cv, ev_mean,
            sum(m['n_trades'] for m in metrics_list),
            min_wr
        ) if not passed else None
    }
```

## 16.3 Acceptance Criteria

```python
def check_acceptance_criteria(
    precision: float,
    precision_cv: float,
    ev: float,
    total_trades: int,
    min_winrate: float
) -> bool:
    """Check if config passes acceptance criteria."""
    
    # Must have positive edge above breakeven
    if precision <= min_winrate:
        return False
    
    # Must have positive EV
    if ev <= 0:
        return False
    
    # Must be stable (CV < 20%)
    if precision_cv > 0.20:
        return False
    
    # Must have minimum volume
    if total_trades < 100:
        return False
    
    return True


def get_rejection_reasons(
    precision: float,
    precision_cv: float,
    ev: float,
    total_trades: int,
    min_winrate: float
) -> List[str]:
    """Get list of rejection reasons."""
    reasons = []
    
    if precision <= min_winrate:
        reasons.append(f"Precision {precision:.1%} below breakeven {min_winrate:.1%}")
    
    if ev <= 0:
        reasons.append(f"Negative EV: {ev:.2f}")
    
    if precision_cv > 0.20:
        reasons.append(f"Unstable: CV={precision_cv:.1%} > 20%")
    
    if total_trades < 100:
        reasons.append(f"Low volume: {total_trades} trades < 100")
    
    return reasons
```

## 16.4 GOLD/SILVER/BRONZE Classification (Stella Alpha)

```python
def classify_config(
    precision: float,
    precision_cv: float,
    ev: float,
    total_trades: int,
    min_winrate: float
) -> str:
    """
    Classify config as GOLD, SILVER, or BRONZE.
    
    STELLA ALPHA SPECIFIC:
    - Lower precision thresholds (high R:R means lower win rates)
    - Edge above breakeven is key metric
    - EV thresholds adjusted for pip values
    """
    edge = precision - min_winrate
    
    # GOLD: Strong edge + very stable + high volume + strong EV
    if (edge > 0.10 and              # 10%+ above breakeven
        precision_cv < 0.12 and      # Very stable
        total_trades > 500 and       # Good volume
        ev > 8.0):                   # Strong EV (adjusted for high R:R)
        return 'GOLD'
    
    # SILVER: Good edge + stable + decent volume
    if (edge > 0.05 and              # 5%+ above breakeven
        precision_cv < 0.18 and      # Stable
        total_trades > 200 and
        ev > 3.0):
        return 'SILVER'
    
    # BRONZE: Passes minimum criteria
    if edge > 0 and ev > 0:
        return 'BRONZE'
    
    return None
```

---

# 17. DIAGNOSTIC ANALYSIS SYSTEM (diagnose.py)

## 17.1 Overview

```
PURPOSE:
Comprehensive analysis of experiment results after pipeline completion.

FEATURES:
├── Overview statistics
├── Tier breakdown (Tier 0 vs Tier 1)
├── GOLD/SILVER/BRONZE classification
├── All passed configs listing
├── Rejection analysis
├── Near-miss detection
├── Parameter pattern analysis
├── Feature importance analysis
├── D1/MTF feature analysis
├── Recommendations generation
├── V4 comparison (optional)
```

## 17.2 CLI Arguments

```python
# diagnose.py

import argparse

parser = argparse.ArgumentParser(description='Stella Alpha Diagnostic Analyzer')

parser.add_argument(
    '--db', '-d',
    type=str,
    default='artifacts/pure_ml_stella_alpha.db',
    help='Path to checkpoint database'
)

parser.add_argument(
    '--top', '-t',
    type=int,
    default=10,
    help='Number of top configs to show'
)

parser.add_argument(
    '--compare-v4',
    type=str,
    default=None,
    help='Path to V4 database for comparison'
)

parser.add_argument(
    '--output', '-o',
    type=str,
    default=None,
    help='Output file for report (optional)'
)

parser.add_argument(
    '--format',
    choices=['text', 'json', 'csv'],
    default='text',
    help='Output format'
)
```

## 17.3 Diagnostic Sections

```python
# src/diagnostics.py

def run_full_diagnostics(db_path: str, top_n: int = 10):
    """Run complete diagnostic analysis."""
    
    db = CheckpointDB(db_path)
    all_results = db.get_all_results()
    passed = [r for r in all_results if r['status'] == 'passed']
    failed = [r for r in all_results if r['status'] == 'failed']
    
    # 1. Overview
    print_overview(all_results, passed, failed)
    
    # 2. Tier Analysis
    print_tier_analysis(passed)
    
    # 3. GOLD Configs
    print_gold_configs(passed)
    
    # 4. SILVER Configs
    print_silver_configs(passed, top_n)
    
    # 5. All Passed Configs
    print_all_passed(passed)
    
    # 6. Rejection Analysis
    print_rejection_analysis(failed)
    
    # 7. Near Misses
    print_near_misses(failed)
    
    # 8. Parameter Patterns
    print_parameter_patterns(passed, failed)
    
    # 9. Feature Analysis
    print_feature_analysis(passed)
    
    # 10. D1/MTF Feature Analysis
    print_d1_mtf_analysis(passed)
    
    # 11. Recommendations
    print_recommendations(passed, failed)


def print_overview(all_results, passed, failed):
    """Print overview statistics."""
    print("\n" + "=" * 70)
    print("  STELLA ALPHA DIAGNOSTIC REPORT")
    print("=" * 70)
    
    total = len(all_results)
    n_passed = len(passed)
    n_failed = len(failed)
    
    gold = len([r for r in passed if r.get('classification') == 'GOLD'])
    silver = len([r for r in passed if r.get('classification') == 'SILVER'])
    bronze = len([r for r in passed if r.get('classification') == 'BRONZE'])
    
    tier_0 = len([r for r in passed if r.get('tier') == 0])
    tier_1 = len([r for r in passed if r.get('tier') == 1])
    
    print(f"""
    OVERVIEW
    ────────────────────────────────────────
    Total Configs Tested:  {total}
    Passed:                {n_passed} ({100*n_passed/total:.1f}%)
    Failed:                {n_failed} ({100*n_failed/total:.1f}%)
    
    CLASSIFICATIONS
    ────────────────────────────────────────
    🥇 GOLD:               {gold}
    🥈 SILVER:             {silver}
    🥉 BRONZE:             {bronze}
    
    TIER BREAKDOWN
    ────────────────────────────────────────
    🚀 Tier 0 (Runners):   {tier_0}
    ⭐ Tier 1 (Ideal):     {tier_1}
    """)
    
    if passed:
        evs = [r['ev_mean'] for r in passed]
        precs = [r['precision_mean'] for r in passed]
        print(f"""
    PERFORMANCE SUMMARY (Passed Only)
    ────────────────────────────────────────
    Best EV:      {max(evs):+.2f} pips
    Worst EV:     {min(evs):+.2f} pips
    Mean EV:      {np.mean(evs):+.2f} pips
    
    Best Precision:   {max(precs)*100:.1f}%
    Worst Precision:  {min(precs)*100:.1f}%
    Mean Precision:   {np.mean(precs)*100:.1f}%
        """)


def print_tier_analysis(passed):
    """Analyze Tier 0 vs Tier 1 performance."""
    print("\n" + "=" * 70)
    print("  TIER ANALYSIS")
    print("=" * 70)
    
    tier_0 = [r for r in passed if r.get('tier') == 0]
    tier_1 = [r for r in passed if r.get('tier') == 1]
    
    print(f"""
    🚀 TIER 0 - RUNNERS (R:R >= 2.5:1)
    ─────────────────────────────────────────
    Configs Passed:  {len(tier_0)}
    TP Range:        75-150 pips
    Avg EV:          {np.mean([r['ev_mean'] for r in tier_0]):+.2f} pips if tier_0 else 'N/A'
    Avg Precision:   {np.mean([r['precision_mean'] for r in tier_0])*100:.1f}% if tier_0 else 'N/A'
    
    ⭐ TIER 1 - IDEAL (R:R 1.67-2.49:1)
    ─────────────────────────────────────────
    Configs Passed:  {len(tier_1)}
    TP Range:        50-70 pips
    Avg EV:          {np.mean([r['ev_mean'] for r in tier_1]):+.2f} pips if tier_1 else 'N/A'
    Avg Precision:   {np.mean([r['precision_mean'] for r in tier_1])*100:.1f}% if tier_1 else 'N/A'
    """)


def print_gold_configs(passed):
    """Print detailed GOLD config analysis."""
    gold = [r for r in passed if r.get('classification') == 'GOLD']
    
    if not gold:
        print("\n  No GOLD configs found.")
        return
    
    print("\n" + "=" * 70)
    print("  🥇 GOLD CONFIGURATIONS")
    print("=" * 70)
    
    for r in sorted(gold, key=lambda x: x['ev_mean'], reverse=True):
        print(f"""
    {r['config_id']} {r.get('tier_name', '')}
    ──────────────────────────────────────────────────
    TP: {r['tp_pips']} | SL: {r['sl_pips']} | Hold: {r['max_holding_bars']} bars
    R:R: {r['risk_reward_ratio']:.2f}:1 | Need: {r['min_winrate_required']*100:.1f}% WR
    
    Performance:
      EV:        {r['ev_mean']:+.2f} ± {r['ev_std']:.2f} pips
      Precision: {r['precision_mean']*100:.1f}% ± {r['precision_std']*100:.1f}%
      CV:        {r['precision_cv']*100:.1f}%
      Edge:      {r['edge_above_breakeven']*100:+.1f}% above breakeven
      Trades:    {r['total_trades']:,}
      Threshold: {r['consensus_threshold']:.2f}
    
    Features ({r['n_features']}): {', '.join(r['selected_features'][:5])}...
        """)


def print_feature_analysis(passed):
    """Analyze which features are most important."""
    print("\n" + "=" * 70)
    print("  FEATURE ANALYSIS")
    print("=" * 70)
    
    # Count feature occurrences
    feature_counts = {}
    for r in passed:
        if r.get('selected_features'):
            features = json.loads(r['selected_features']) if isinstance(r['selected_features'], str) else r['selected_features']
            for f in features:
                feature_counts[f] = feature_counts.get(f, 0) + 1
    
    # Sort by frequency
    sorted_features = sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n  Features used across {len(passed)} passed configs:\n")
    print(f"  {'Feature':<40} {'Count':>6} {'%':>8}")
    print(f"  " + "─" * 56)
    
    for feature, count in sorted_features[:20]:
        pct = 100 * count / len(passed)
        bar = '█' * int(pct / 5)
        print(f"  {feature:<40} {count:>6} {pct:>7.1f}% {bar}")


def print_d1_mtf_analysis(passed):
    """Analyze D1 and MTF feature importance."""
    print("\n" + "=" * 70)
    print("  D1 & MTF FEATURE ANALYSIS")
    print("=" * 70)
    
    d1_counts = {}
    mtf_counts = {}
    
    for r in passed:
        if r.get('selected_features'):
            features = json.loads(r['selected_features']) if isinstance(r['selected_features'], str) else r['selected_features']
            for f in features:
                if f.startswith('d1_'):
                    d1_counts[f] = d1_counts.get(f, 0) + 1
                elif f.startswith('mtf_'):
                    mtf_counts[f] = mtf_counts.get(f, 0) + 1
    
    print(f"\n  D1 FEATURES (from Daily timeframe):")
    if d1_counts:
        for f, c in sorted(d1_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {f:<35} {c:>4} ({100*c/len(passed):>5.1f}%)")
    else:
        print("    None selected - D1 may not be adding value")
    
    print(f"\n  MTF FEATURES (Cross-timeframe):")
    if mtf_counts:
        for f, c in sorted(mtf_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {f:<35} {c:>4} ({100*c/len(passed):>5.1f}%)")
    else:
        print("    None selected - MTF confluence may not be helping")
    
    # Assessment
    total_d1 = sum(d1_counts.values())
    total_mtf = sum(mtf_counts.values())
    
    print(f"""
  ASSESSMENT:
  ───────────────────────────────────────
  D1 features selected:  {len(d1_counts)} unique, {total_d1} total uses
  MTF features selected: {len(mtf_counts)} unique, {total_mtf} total uses
    """)
    
    if total_d1 > len(passed) * 2:
        print("  ✅ D1 data is contributing to model performance")
    else:
        print("  ⚠️  D1 data may not be adding significant value")


def print_recommendations(passed, failed):
    """Generate recommendations."""
    print("\n" + "=" * 70)
    print("  RECOMMENDATIONS")
    print("=" * 70)
    
    recommendations = []
    
    # Check tier distribution
    tier_0 = [r for r in passed if r.get('tier') == 0]
    tier_1 = [r for r in passed if r.get('tier') == 1]
    
    if len(tier_0) > 0:
        recommendations.append({
            'priority': 'HIGH',
            'finding': f'{len(tier_0)} RUNNER configs found (Tier 0)',
            'action': 'Deploy best Tier 0 model for high R:R trading'
        })
    
    if len(tier_0) == 0 and len(tier_1) > 0:
        recommendations.append({
            'priority': 'MEDIUM',
            'finding': 'No Tier 0 Runners found, but Tier 1 available',
            'action': 'Use Tier 1 models, consider parameter tuning for higher TP'
        })
    
    # Check GOLD configs
    gold = [r for r in passed if r.get('classification') == 'GOLD']
    if gold:
        best_gold = max(gold, key=lambda x: x['ev_mean'])
        recommendations.append({
            'priority': 'HIGH',
            'finding': f'GOLD config found: {best_gold["config_id"]}',
            'action': f'Recommended for deployment with EV={best_gold["ev_mean"]:+.2f} pips'
        })
    
    # Print recommendations
    for rec in recommendations:
        emoji = '🔴' if rec['priority'] == 'HIGH' else '🟡' if rec['priority'] == 'MEDIUM' else '🟢'
        print(f"""
    {emoji} [{rec['priority']}]
    Finding: {rec['finding']}
    Action:  {rec['action']}
        """)
    
    # Final verdict
    print("\n  FINAL VERDICT:")
    print("  " + "─" * 50)
    
    if gold:
        print("  ✅ READY FOR DEPLOYMENT")
        print(f"     Recommended: {gold[0]['config_id']}")
    elif passed:
        print("  ⚠️  PROCEED WITH CAUTION")
        print("     No GOLD configs, use SILVER with careful monitoring")
    else:
        print("  ❌ NOT READY")
        print("     No passing configs found")
```

---

# 18. LOSS ANALYSIS SYSTEM

## 16.1 Overview

```
PURPOSE:
Understand WHY trades lose and identify patterns that predict losses.

GOAL:
Turn 33% loss rate into actionable insights for filtering bad trades.

APPROACH:
1. Record every trade with full context
2. Compare winning vs losing trades
3. Find statistically significant differences
4. Generate filter recommendations
```

## 16.2 Trade Database Schema

```sql
-- File: artifacts/trades_stella_alpha.db

CREATE TABLE IF NOT EXISTS trades (
    -- Primary key
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Trade identification
    config_id TEXT NOT NULL,           -- "TP30_SL50_H36"
    fold INTEGER NOT NULL,             -- 1-5
    timestamp TEXT NOT NULL,           -- Entry time
    
    -- Outcome
    outcome TEXT NOT NULL,             -- "WIN" or "LOSS"
    pips_result REAL NOT NULL,         -- +30 or -50
    bars_held INTEGER,                 -- How long held
    
    -- Model info
    model_probability REAL NOT NULL,   -- Confidence 0-1
    threshold_used REAL,               -- Threshold applied
    
    -- H4 Features at Entry (key features for analysis)
    h4_rsi_value REAL,
    h4_bb_position REAL,
    h4_trend_strength REAL,
    h4_atr_pct REAL,
    h4_volume_ratio REAL,
    h4_hour INTEGER,
    h4_day_of_week INTEGER,
    h4_is_asian_session INTEGER,
    h4_is_london_session INTEGER,
    h4_is_ny_session INTEGER,
    h4_is_overlap_session INTEGER,
    h4_consecutive_bullish INTEGER,
    h4_exhaustion_score REAL,
    h4_macd_histogram REAL,
    h4_adx REAL,
    
    -- D1 Features at Entry
    d1_rsi_value REAL,
    d1_bb_position REAL,
    d1_trend_strength REAL,
    d1_trend_direction REAL,
    d1_is_trending_up INTEGER,
    d1_is_trending_down INTEGER,
    d1_atr_percentile REAL,
    d1_consecutive_bullish INTEGER,
    
    -- Cross-TF Features
    mtf_confluence_score REAL,
    mtf_rsi_aligned INTEGER,
    mtf_bb_aligned INTEGER,
    mtf_trend_aligned INTEGER,
    d1_supports_short INTEGER,
    d1_opposes_short INTEGER,
    
    -- Indexes for fast queries
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_outcome ON trades(outcome);
CREATE INDEX idx_config ON trades(config_id);
CREATE INDEX idx_fold ON trades(fold);
CREATE INDEX idx_probability ON trades(model_probability);
```

## 16.3 Loss Analysis Module

```python
# src/loss_analysis.py

"""
Loss Analysis Module

Analyzes patterns in losing trades to identify potential filters.
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import sqlite3
import json


@dataclass
class FeatureComparison:
    """Comparison of a feature between wins and losses."""
    feature_name: str
    wins_mean: float
    wins_std: float
    losses_mean: float
    losses_std: float
    difference: float          # losses_mean - wins_mean
    pct_difference: float      # percentage difference
    t_statistic: float
    p_value: float
    is_significant: bool       # p < 0.05
    effect_size: float         # Cohen's d
    direction: str             # "higher_in_losses" or "higher_in_wins"
    

@dataclass
class SessionAnalysis:
    """Analysis of wins/losses by session."""
    session: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    loss_rate: float
    is_problematic: bool       # Win rate significantly below average


@dataclass 
class ConfidenceAnalysis:
    """Analysis of wins/losses by model confidence."""
    confidence_bucket: str     # "0.50-0.55", "0.55-0.60", etc.
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_confidence: float


@dataclass
class LossAnalysisReport:
    """Complete loss analysis report."""
    config_id: str
    total_trades: int
    total_wins: int
    total_losses: int
    win_rate: float
    
    # Detailed analyses
    feature_comparisons: List[FeatureComparison]
    significant_features: List[FeatureComparison]
    session_analysis: List[SessionAnalysis]
    confidence_analysis: List[ConfidenceAnalysis]
    
    # Key findings
    top_loss_predictors: List[str]
    problematic_sessions: List[str]
    optimal_confidence_threshold: float
    
    # D1-specific findings
    d1_alignment_impact: Dict
    mtf_confluence_impact: Dict


class LossAnalyzer:
    """
    Analyzes trading losses to find patterns and recommend filters.
    """
    
    def __init__(self, db_path: str = "artifacts/trades_stella_alpha.db"):
        self.db_path = db_path
        self.trades_df = None
        
    def load_trades(self, config_id: Optional[str] = None) -> pd.DataFrame:
        """Load trades from database."""
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM trades"
        if config_id:
            query += f" WHERE config_id = '{config_id}'"
        
        self.trades_df = pd.read_sql_query(query, conn)
        conn.close()
        
        print(f"Loaded {len(self.trades_df)} trades")
        return self.trades_df
    
    def analyze(self, config_id: Optional[str] = None) -> LossAnalysisReport:
        """
        Run complete loss analysis.
        """
        if self.trades_df is None:
            self.load_trades(config_id)
        
        df = self.trades_df
        if config_id:
            df = df[df['config_id'] == config_id]
        
        wins = df[df['outcome'] == 'WIN']
        losses = df[df['outcome'] == 'LOSS']
        
        # 1. Feature comparisons
        feature_comparisons = self._compare_features(wins, losses)
        significant = [f for f in feature_comparisons if f.is_significant]
        
        # 2. Session analysis
        session_analysis = self._analyze_sessions(df)
        
        # 3. Confidence analysis
        confidence_analysis = self._analyze_confidence(df)
        
        # 4. D1 alignment impact
        d1_alignment_impact = self._analyze_d1_alignment(df)
        
        # 5. MTF confluence impact
        mtf_confluence_impact = self._analyze_mtf_confluence(df)
        
        # Generate report
        report = LossAnalysisReport(
            config_id=config_id or "ALL",
            total_trades=len(df),
            total_wins=len(wins),
            total_losses=len(losses),
            win_rate=len(wins) / len(df) if len(df) > 0 else 0,
            feature_comparisons=feature_comparisons,
            significant_features=significant,
            session_analysis=session_analysis,
            confidence_analysis=confidence_analysis,
            top_loss_predictors=[f.feature_name for f in significant[:10]],
            problematic_sessions=[s.session for s in session_analysis if s.is_problematic],
            optimal_confidence_threshold=self._find_optimal_confidence(df),
            d1_alignment_impact=d1_alignment_impact,
            mtf_confluence_impact=mtf_confluence_impact
        )
        
        return report
    
    def _compare_features(
        self, 
        wins: pd.DataFrame, 
        losses: pd.DataFrame
    ) -> List[FeatureComparison]:
        """
        Compare feature distributions between wins and losses.
        Uses t-test for statistical significance.
        """
        comparisons = []
        
        # Features to analyze
        features_to_compare = [
            # H4 features
            'h4_rsi_value', 'h4_bb_position', 'h4_trend_strength',
            'h4_atr_pct', 'h4_volume_ratio', 'h4_hour',
            'h4_consecutive_bullish', 'h4_exhaustion_score',
            'h4_macd_histogram', 'h4_adx',
            # D1 features
            'd1_rsi_value', 'd1_bb_position', 'd1_trend_strength',
            'd1_trend_direction', 'd1_atr_percentile', 'd1_consecutive_bullish',
            # Cross-TF features
            'mtf_confluence_score', 'model_probability'
        ]
        
        for feature in features_to_compare:
            if feature not in wins.columns or feature not in losses.columns:
                continue
                
            wins_vals = wins[feature].dropna()
            losses_vals = losses[feature].dropna()
            
            if len(wins_vals) < 30 or len(losses_vals) < 30:
                continue
            
            # Calculate statistics
            wins_mean = wins_vals.mean()
            wins_std = wins_vals.std()
            losses_mean = losses_vals.mean()
            losses_std = losses_vals.std()
            
            # T-test
            t_stat, p_value = stats.ttest_ind(wins_vals, losses_vals)
            
            # Effect size (Cohen's d)
            pooled_std = np.sqrt((wins_std**2 + losses_std**2) / 2)
            effect_size = (losses_mean - wins_mean) / pooled_std if pooled_std > 0 else 0
            
            # Percentage difference
            if wins_mean != 0:
                pct_diff = (losses_mean - wins_mean) / abs(wins_mean) * 100
            else:
                pct_diff = 0
            
            comparison = FeatureComparison(
                feature_name=feature,
                wins_mean=wins_mean,
                wins_std=wins_std,
                losses_mean=losses_mean,
                losses_std=losses_std,
                difference=losses_mean - wins_mean,
                pct_difference=pct_diff,
                t_statistic=t_stat,
                p_value=p_value,
                is_significant=p_value < 0.05,
                effect_size=effect_size,
                direction="higher_in_losses" if losses_mean > wins_mean else "higher_in_wins"
            )
            
            comparisons.append(comparison)
        
        # Sort by significance and effect size
        comparisons.sort(key=lambda x: (not x.is_significant, -abs(x.effect_size)))
        
        return comparisons
    
    def _analyze_sessions(self, df: pd.DataFrame) -> List[SessionAnalysis]:
        """Analyze win rates by trading session."""
        results = []
        
        session_cols = [
            ('h4_is_asian_session', 'Asian'),
            ('h4_is_london_session', 'London'),
            ('h4_is_ny_session', 'NY'),
            ('h4_is_overlap_session', 'Overlap')
        ]
        
        overall_win_rate = (df['outcome'] == 'WIN').mean()
        
        for col, name in session_cols:
            if col not in df.columns:
                continue
            
            session_trades = df[df[col] == 1]
            if len(session_trades) == 0:
                continue
            
            wins = (session_trades['outcome'] == 'WIN').sum()
            losses = (session_trades['outcome'] == 'LOSS').sum()
            total = wins + losses
            win_rate = wins / total if total > 0 else 0
            
            results.append(SessionAnalysis(
                session=name,
                total_trades=total,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                loss_rate=losses / total if total > 0 else 0,
                is_problematic=win_rate < overall_win_rate - 0.05  # 5% below average
            ))
        
        return results
    
    def _analyze_confidence(self, df: pd.DataFrame) -> List[ConfidenceAnalysis]:
        """Analyze win rates by model confidence buckets."""
        results = []
        
        buckets = [(0.40, 0.45), (0.45, 0.50), (0.50, 0.55), 
                   (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 1.0)]
        
        for low, high in buckets:
            bucket_df = df[(df['model_probability'] >= low) & (df['model_probability'] < high)]
            
            if len(bucket_df) == 0:
                continue
            
            wins = (bucket_df['outcome'] == 'WIN').sum()
            losses = (bucket_df['outcome'] == 'LOSS').sum()
            total = wins + losses
            
            results.append(ConfidenceAnalysis(
                confidence_bucket=f"{low:.2f}-{high:.2f}",
                total_trades=total,
                wins=wins,
                losses=losses,
                win_rate=wins / total if total > 0 else 0,
                avg_confidence=bucket_df['model_probability'].mean()
            ))
        
        return results
    
    def _analyze_d1_alignment(self, df: pd.DataFrame) -> Dict:
        """Analyze impact of D1 trend alignment on win rate."""
        result = {
            'd1_supports_short': {'total': 0, 'wins': 0, 'win_rate': 0},
            'd1_opposes_short': {'total': 0, 'wins': 0, 'win_rate': 0},
            'd1_neutral': {'total': 0, 'wins': 0, 'win_rate': 0}
        }
        
        if 'd1_supports_short' in df.columns:
            supports = df[df['d1_supports_short'] == 1]
            result['d1_supports_short'] = {
                'total': len(supports),
                'wins': (supports['outcome'] == 'WIN').sum(),
                'win_rate': (supports['outcome'] == 'WIN').mean() if len(supports) > 0 else 0
            }
        
        if 'd1_opposes_short' in df.columns:
            opposes = df[df['d1_opposes_short'] == 1]
            result['d1_opposes_short'] = {
                'total': len(opposes),
                'wins': (opposes['outcome'] == 'WIN').sum(),
                'win_rate': (opposes['outcome'] == 'WIN').mean() if len(opposes) > 0 else 0
            }
        
        return result
    
    def _analyze_mtf_confluence(self, df: pd.DataFrame) -> Dict:
        """Analyze impact of MTF confluence score on win rate."""
        result = {
            'high_confluence': {'total': 0, 'wins': 0, 'win_rate': 0},   # >= 0.75
            'medium_confluence': {'total': 0, 'wins': 0, 'win_rate': 0}, # 0.5-0.75
            'low_confluence': {'total': 0, 'wins': 0, 'win_rate': 0}     # < 0.5
        }
        
        if 'mtf_confluence_score' not in df.columns:
            return result
        
        high = df[df['mtf_confluence_score'] >= 0.75]
        medium = df[(df['mtf_confluence_score'] >= 0.5) & (df['mtf_confluence_score'] < 0.75)]
        low = df[df['mtf_confluence_score'] < 0.5]
        
        result['high_confluence'] = {
            'total': len(high),
            'wins': (high['outcome'] == 'WIN').sum(),
            'win_rate': (high['outcome'] == 'WIN').mean() if len(high) > 0 else 0
        }
        
        result['medium_confluence'] = {
            'total': len(medium),
            'wins': (medium['outcome'] == 'WIN').sum(),
            'win_rate': (medium['outcome'] == 'WIN').mean() if len(medium) > 0 else 0
        }
        
        result['low_confluence'] = {
            'total': len(low),
            'wins': (low['outcome'] == 'WIN').sum(),
            'win_rate': (low['outcome'] == 'WIN').mean() if len(low) > 0 else 0
        }
        
        return result
    
    def _find_optimal_confidence(self, df: pd.DataFrame) -> float:
        """Find confidence threshold that maximizes profit."""
        best_threshold = 0.50
        best_ev = -np.inf
        
        for threshold in [0.50, 0.55, 0.60, 0.65, 0.70]:
            trades = df[df['model_probability'] >= threshold]
            if len(trades) < 100:
                continue
            
            ev = trades['pips_result'].mean()
            if ev > best_ev:
                best_ev = ev
                best_threshold = threshold
        
        return best_threshold
    
    def print_report(self, report: LossAnalysisReport):
        """Print formatted loss analysis report."""
        print("\n" + "=" * 70)
        print("  LOSS ANALYSIS REPORT")
        print("=" * 70)
        
        print(f"""
    Config: {report.config_id}
    ─────────────────────────────────────────
    Total Trades:    {report.total_trades:,}
    Wins:            {report.total_wins:,} ({report.win_rate*100:.1f}%)
    Losses:          {report.total_losses:,} ({(1-report.win_rate)*100:.1f}%)
        """)
        
        # Significant features
        print("\n    SIGNIFICANT FEATURES (p < 0.05):")
        print("    " + "─" * 60)
        print(f"    {'Feature':<30} {'Wins Mean':>10} {'Loss Mean':>10} {'Effect':>10}")
        print("    " + "─" * 60)
        
        for f in report.significant_features[:15]:
            print(f"    {f.feature_name:<30} {f.wins_mean:>10.3f} {f.losses_mean:>10.3f} {f.effect_size:>+10.2f}")
        
        # Session analysis
        print("\n    SESSION ANALYSIS:")
        print("    " + "─" * 50)
        for s in report.session_analysis:
            status = "⚠️ PROBLEMATIC" if s.is_problematic else "✓ OK"
            print(f"    {s.session:<15} Win Rate: {s.win_rate*100:5.1f}%  ({s.total_trades:,} trades) {status}")
        
        # Confidence analysis
        print("\n    CONFIDENCE ANALYSIS:")
        print("    " + "─" * 50)
        for c in report.confidence_analysis:
            print(f"    {c.confidence_bucket}  Win Rate: {c.win_rate*100:5.1f}%  ({c.total_trades:,} trades)")
        
        # D1 alignment
        print("\n    D1 ALIGNMENT IMPACT:")
        print("    " + "─" * 50)
        d1 = report.d1_alignment_impact
        if d1['d1_supports_short']['total'] > 0:
            print(f"    D1 SUPPORTS SHORT:  Win Rate: {d1['d1_supports_short']['win_rate']*100:5.1f}%  ({d1['d1_supports_short']['total']:,} trades)")
        if d1['d1_opposes_short']['total'] > 0:
            print(f"    D1 OPPOSES SHORT:   Win Rate: {d1['d1_opposes_short']['win_rate']*100:5.1f}%  ({d1['d1_opposes_short']['total']:,} trades)")
        
        # MTF confluence
        print("\n    MTF CONFLUENCE IMPACT:")
        print("    " + "─" * 50)
        mtf = report.mtf_confluence_impact
        print(f"    HIGH (>=0.75):    Win Rate: {mtf['high_confluence']['win_rate']*100:5.1f}%  ({mtf['high_confluence']['total']:,} trades)")
        print(f"    MEDIUM (0.5-0.75): Win Rate: {mtf['medium_confluence']['win_rate']*100:5.1f}%  ({mtf['medium_confluence']['total']:,} trades)")
        print(f"    LOW (<0.5):       Win Rate: {mtf['low_confluence']['win_rate']*100:5.1f}%  ({mtf['low_confluence']['total']:,} trades)")
        
        # Key findings
        print("\n    KEY FINDINGS:")
        print("    " + "─" * 50)
        print(f"    • Top loss predictors: {', '.join(report.top_loss_predictors[:5])}")
        if report.problematic_sessions:
            print(f"    • Problematic sessions: {', '.join(report.problematic_sessions)}")
        print(f"    • Optimal confidence threshold: {report.optimal_confidence_threshold:.2f}")
        
        print("\n" + "=" * 70)
```

## 16.4 Analyze Losses Script

```python
# analyze_losses.py

"""
Standalone script to run loss analysis on completed experiments.

Usage:
    python analyze_losses.py --trades artifacts/trades_stella_alpha.db --config TP30_SL50_H36
    python analyze_losses.py --trades artifacts/trades_stella_alpha.db --all
"""

import argparse
from src.loss_analysis import LossAnalyzer

def main():
    parser = argparse.ArgumentParser(description='Analyze trading losses')
    parser.add_argument('--trades', '-t', default='artifacts/trades_stella_alpha.db',
                        help='Path to trades database')
    parser.add_argument('--config', '-c', default=None,
                        help='Specific config to analyze (e.g., TP30_SL50_H36)')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Analyze all configs combined')
    parser.add_argument('--output', '-o', default=None,
                        help='Output JSON file for report')
    
    args = parser.parse_args()
    
    analyzer = LossAnalyzer(args.trades)
    analyzer.load_trades()
    
    if args.config:
        report = analyzer.analyze(args.config)
    else:
        report = analyzer.analyze(None)  # All configs
    
    analyzer.print_report(report)
    
    if args.output:
        # Save to JSON
        import json
        with open(args.output, 'w') as f:
            json.dump(report.__dict__, f, indent=2, default=str)
        print(f"\nReport saved to: {args.output}")

if __name__ == '__main__':
    main()
```

---

# 19. LOSS FILTER RECOMMENDATIONS

## 17.1 Overview

```
PURPOSE:
Automatically generate filter recommendations based on loss analysis.

APPROACH:
1. Identify features with significant differences between wins/losses
2. Generate candidate filter rules
3. Simulate each filter's historical impact
4. Calculate net P&L improvement
5. Rank and recommend best filters
6. Test filter combinations
```

## 17.2 Filter Recommendation Engine

```python
# src/filter_recommendations.py

"""
Filter Recommendation Engine

Generates and evaluates potential filters to avoid losing trades.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import itertools


@dataclass
class FilterRule:
    """A single filter rule."""
    feature: str
    operator: str           # '>', '<', '>=', '<=', '==', '!='
    threshold: float
    description: str
    
    def apply(self, df: pd.DataFrame) -> pd.Series:
        """Apply filter to dataframe, returns boolean mask."""
        if self.feature not in df.columns:
            return pd.Series([True] * len(df))
        
        col = df[self.feature]
        
        if self.operator == '>':
            return col > self.threshold
        elif self.operator == '<':
            return col < self.threshold
        elif self.operator == '>=':
            return col >= self.threshold
        elif self.operator == '<=':
            return col <= self.threshold
        elif self.operator == '==':
            return col == self.threshold
        elif self.operator == '!=':
            return col != self.threshold
        else:
            return pd.Series([True] * len(df))


@dataclass
class FilterImpact:
    """Impact analysis of a filter."""
    filter_rule: FilterRule
    
    # Before filter
    total_trades_before: int
    wins_before: int
    losses_before: int
    win_rate_before: float
    total_pips_before: float
    
    # After filter
    total_trades_after: int
    wins_after: int
    losses_after: int
    win_rate_after: float
    total_pips_after: float
    
    # Impact
    trades_removed: int
    wins_removed: int
    losses_removed: int
    pips_saved: float          # From avoided losses
    pips_lost: float           # From missed wins
    net_pips_improvement: float
    pct_improvement: float
    
    # Quality metrics
    loss_removal_rate: float   # % of losses removed
    win_preservation_rate: float  # % of wins kept
    efficiency_ratio: float    # losses_removed / wins_removed


@dataclass
class FilterRecommendation:
    """A recommended filter with full analysis."""
    rank: int
    filter_rule: FilterRule
    impact: FilterImpact
    recommendation: str        # "STRONG", "MODERATE", "WEAK", "NOT RECOMMENDED"
    reasoning: str


class FilterRecommendationEngine:
    """
    Generates and evaluates filter recommendations.
    """
    
    def __init__(self, trades_df: pd.DataFrame, config: dict):
        self.trades_df = trades_df
        self.config = config
        self.tp = config.get('tp_pips', 30)
        self.sl = config.get('sl_pips', 50)
    
    def generate_recommendations(self) -> List[FilterRecommendation]:
        """
        Generate and rank filter recommendations.
        """
        # 1. Generate candidate filters
        candidate_filters = self._generate_candidate_filters()
        
        # 2. Evaluate each filter
        impacts = []
        for filter_rule in candidate_filters:
            impact = self._evaluate_filter(filter_rule)
            if impact.net_pips_improvement > 0:  # Only keep positive impact
                impacts.append(impact)
        
        # 3. Rank by net improvement
        impacts.sort(key=lambda x: x.net_pips_improvement, reverse=True)
        
        # 4. Generate recommendations
        recommendations = []
        for rank, impact in enumerate(impacts[:20], 1):  # Top 20
            rec = self._create_recommendation(rank, impact)
            recommendations.append(rec)
        
        return recommendations
    
    def _generate_candidate_filters(self) -> List[FilterRule]:
        """Generate candidate filter rules based on data analysis."""
        filters = []
        
        # Session filters
        filters.extend([
            FilterRule('h4_is_asian_session', '==', 0, "Avoid Asian session"),
            FilterRule('h4_is_overlap_session', '==', 1, "Only trade during overlap"),
        ])
        
        # Confidence filters
        for thresh in [0.55, 0.60, 0.65, 0.70]:
            filters.append(FilterRule(
                'model_probability', '>=', thresh,
                f"Require confidence >= {thresh}"
            ))
        
        # D1 alignment filters
        filters.extend([
            FilterRule('d1_opposes_short', '==', 0, "Skip when D1 opposes short"),
            FilterRule('d1_supports_short', '==', 1, "Only when D1 supports short"),
            FilterRule('d1_trend_direction', '<', 0.5, "D1 not strongly bullish"),
        ])
        
        # RSI filters
        for thresh in [65, 70, 75]:
            filters.append(FilterRule(
                'h4_rsi_value', '>=', thresh,
                f"Require H4 RSI >= {thresh}"
            ))
        
        for thresh in [50, 55, 60]:
            filters.append(FilterRule(
                'd1_rsi_value', '>=', thresh,
                f"Require D1 RSI >= {thresh}"
            ))
        
        # MTF confluence filters
        for thresh in [0.5, 0.6, 0.75]:
            filters.append(FilterRule(
                'mtf_confluence_score', '>=', thresh,
                f"Require MTF confluence >= {thresh}"
            ))
        
        # Trend filters
        filters.extend([
            FilterRule('d1_is_trending_up', '==', 0, "Skip D1 uptrend"),
            FilterRule('h4_adx', '>=', 20, "Require H4 trending"),
        ])
        
        # BB position filters
        for thresh in [0.85, 0.90, 0.95]:
            filters.append(FilterRule(
                'h4_bb_position', '>=', thresh,
                f"Require H4 BB position >= {thresh}"
            ))
        
        return filters
    
    def _evaluate_filter(self, filter_rule: FilterRule) -> FilterImpact:
        """Evaluate impact of a single filter."""
        df = self.trades_df
        
        # Before filter
        total_before = len(df)
        wins_before = (df['outcome'] == 'WIN').sum()
        losses_before = (df['outcome'] == 'LOSS').sum()
        pips_before = df['pips_result'].sum()
        
        # Apply filter (trades that PASS the filter)
        mask = filter_rule.apply(df)
        df_filtered = df[mask]
        
        # After filter
        total_after = len(df_filtered)
        wins_after = (df_filtered['outcome'] == 'WIN').sum()
        losses_after = (df_filtered['outcome'] == 'LOSS').sum()
        pips_after = df_filtered['pips_result'].sum()
        
        # Calculate impact
        trades_removed = total_before - total_after
        wins_removed = wins_before - wins_after
        losses_removed = losses_before - losses_after
        
        pips_saved = losses_removed * self.sl  # Each avoided loss saves SL pips
        pips_lost = wins_removed * self.tp     # Each missed win costs TP pips
        net_improvement = pips_saved - pips_lost
        
        pct_improvement = (net_improvement / abs(pips_before) * 100) if pips_before != 0 else 0
        
        return FilterImpact(
            filter_rule=filter_rule,
            total_trades_before=total_before,
            wins_before=wins_before,
            losses_before=losses_before,
            win_rate_before=wins_before/total_before if total_before > 0 else 0,
            total_pips_before=pips_before,
            total_trades_after=total_after,
            wins_after=wins_after,
            losses_after=losses_after,
            win_rate_after=wins_after/total_after if total_after > 0 else 0,
            total_pips_after=pips_after,
            trades_removed=trades_removed,
            wins_removed=wins_removed,
            losses_removed=losses_removed,
            pips_saved=pips_saved,
            pips_lost=pips_lost,
            net_pips_improvement=net_improvement,
            pct_improvement=pct_improvement,
            loss_removal_rate=losses_removed/losses_before if losses_before > 0 else 0,
            win_preservation_rate=wins_after/wins_before if wins_before > 0 else 0,
            efficiency_ratio=losses_removed/wins_removed if wins_removed > 0 else float('inf')
        )
    
    def _create_recommendation(self, rank: int, impact: FilterImpact) -> FilterRecommendation:
        """Create recommendation from impact analysis."""
        
        # Determine recommendation strength
        if impact.efficiency_ratio >= 3.0 and impact.net_pips_improvement > 1000:
            rec = "STRONG"
            reasoning = f"Removes {impact.losses_removed} losses for only {impact.wins_removed} missed wins (3:1+ ratio)"
        elif impact.efficiency_ratio >= 2.0 and impact.net_pips_improvement > 500:
            rec = "MODERATE"
            reasoning = f"Good efficiency ({impact.efficiency_ratio:.1f}:1) with solid net improvement"
        elif impact.net_pips_improvement > 0:
            rec = "WEAK"
            reasoning = f"Positive but marginal improvement ({impact.pct_improvement:.1f}%)"
        else:
            rec = "NOT RECOMMENDED"
            reasoning = "Filter removes more value than it saves"
        
        return FilterRecommendation(
            rank=rank,
            filter_rule=impact.filter_rule,
            impact=impact,
            recommendation=rec,
            reasoning=reasoning
        )
    
    def test_filter_combination(
        self, 
        filters: List[FilterRule]
    ) -> FilterImpact:
        """Test multiple filters combined."""
        df = self.trades_df
        
        # Apply all filters
        mask = pd.Series([True] * len(df))
        for f in filters:
            mask = mask & f.apply(df)
        
        # Create combined filter rule for reporting
        combined = FilterRule(
            feature="COMBINED",
            operator="AND",
            threshold=len(filters),
            description=" AND ".join([f.description for f in filters])
        )
        combined_impact = FilterImpact(
            filter_rule=combined,
            total_trades_before=len(self.trades_df),
            wins_before=(self.trades_df['outcome'] == 'WIN').sum(),
            losses_before=(self.trades_df['outcome'] == 'LOSS').sum(),
            win_rate_before=(self.trades_df['outcome'] == 'WIN').mean(),
            total_pips_before=self.trades_df['pips_result'].sum(),
            total_trades_after=mask.sum(),
            wins_after=(self.trades_df[mask]['outcome'] == 'WIN').sum(),
            losses_after=(self.trades_df[mask]['outcome'] == 'LOSS').sum(),
            win_rate_after=(self.trades_df[mask]['outcome'] == 'WIN').mean() if mask.sum() > 0 else 0,
            total_pips_after=self.trades_df[mask]['pips_result'].sum(),
            trades_removed=len(self.trades_df) - mask.sum(),
            wins_removed=(self.trades_df['outcome'] == 'WIN').sum() - (self.trades_df[mask]['outcome'] == 'WIN').sum(),
            losses_removed=(self.trades_df['outcome'] == 'LOSS').sum() - (self.trades_df[mask]['outcome'] == 'LOSS').sum(),
            pips_saved=0,  # Calculate below
            pips_lost=0,
            net_pips_improvement=0,
            pct_improvement=0,
            loss_removal_rate=0,
            win_preservation_rate=0,
            efficiency_ratio=0
        )
        
        # Calculate derived fields
        combined_impact.pips_saved = combined_impact.losses_removed * self.sl
        combined_impact.pips_lost = combined_impact.wins_removed * self.tp
        combined_impact.net_pips_improvement = combined_impact.pips_saved - combined_impact.pips_lost
        
        return combined_impact
    
    def print_recommendations(self, recommendations: List[FilterRecommendation]):
        """Print formatted recommendations."""
        print("\n" + "=" * 70)
        print("  FILTER RECOMMENDATIONS")
        print("=" * 70)
        
        for rec in recommendations[:10]:  # Top 10
            impact = rec.impact
            
            strength_emoji = {
                "STRONG": "🟢",
                "MODERATE": "🟡", 
                "WEAK": "🟠",
                "NOT RECOMMENDED": "🔴"
            }
            
            print(f"""
    #{rec.rank} {strength_emoji.get(rec.recommendation, '')} {rec.recommendation}
    ─────────────────────────────────────────────────────
    Filter: {rec.filter_rule.description}
    Rule:   {rec.filter_rule.feature} {rec.filter_rule.operator} {rec.filter_rule.threshold}
    
    Impact:
    • Trades: {impact.total_trades_before:,} → {impact.total_trades_after:,} (-{impact.trades_removed:,})
    • Losses avoided: {impact.losses_removed:,} (saves {impact.pips_saved:,.0f} pips)
    • Wins missed: {impact.wins_removed:,} (costs {impact.pips_lost:,.0f} pips)
    • Net improvement: {impact.net_pips_improvement:+,.0f} pips ({impact.pct_improvement:+.1f}%)
    • Win rate: {impact.win_rate_before*100:.1f}% → {impact.win_rate_after*100:.1f}%
    • Efficiency: {impact.efficiency_ratio:.1f}:1 (losses removed per win missed)
    
    Reasoning: {rec.reasoning}
            """)
        
        print("=" * 70)


def generate_filter_report(
    trades_db_path: str,
    config: dict,
    output_path: Optional[str] = None
) -> List[FilterRecommendation]:
    """
    Generate filter recommendations report.
    
    Args:
        trades_db_path: Path to trades database
        config: Config dict with tp_pips, sl_pips
        output_path: Optional path to save JSON report
        
    Returns:
        List of filter recommendations
    """
    import sqlite3
    
    # Load trades
    conn = sqlite3.connect(trades_db_path)
    trades_df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()
    
    # Generate recommendations
    engine = FilterRecommendationEngine(trades_df, config)
    recommendations = engine.generate_recommendations()
    
    # Print report
    engine.print_recommendations(recommendations)
    
    # Save if requested
    if output_path:
        import json
        report = {
            'config': config,
            'total_trades': len(trades_df),
            'recommendations': [
                {
                    'rank': r.rank,
                    'filter': {
                        'feature': r.filter_rule.feature,
                        'operator': r.filter_rule.operator,
                        'threshold': r.filter_rule.threshold,
                        'description': r.filter_rule.description
                    },
                    'impact': {
                        'trades_removed': r.impact.trades_removed,
                        'losses_avoided': r.impact.losses_removed,
                        'wins_missed': r.impact.wins_removed,
                        'net_pips': r.impact.net_pips_improvement,
                        'pct_improvement': r.impact.pct_improvement,
                        'new_win_rate': r.impact.win_rate_after
                    },
                    'recommendation': r.recommendation,
                    'reasoning': r.reasoning
                }
                for r in recommendations
            ]
        }
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {output_path}")
    
    return recommendations
```

## 17.3 Filter Recommendations CLI

```python
# recommend_filters.py

"""
Standalone script to generate filter recommendations.

Usage:
    python recommend_filters.py --trades artifacts/trades_stella_alpha.db --tp 30 --sl 50
"""

import argparse
from src.filter_recommendations import generate_filter_report

def main():
    parser = argparse.ArgumentParser(description='Generate filter recommendations')
    parser.add_argument('--trades', '-t', default='artifacts/trades_stella_alpha.db')
    parser.add_argument('--tp', type=int, default=30)
    parser.add_argument('--sl', type=int, default=50)
    parser.add_argument('--output', '-o', default='artifacts/filter_recommendations.json')
    
    args = parser.parse_args()
    
    config = {'tp_pips': args.tp, 'sl_pips': args.sl}
    generate_filter_report(args.trades, config, args.output)

if __name__ == '__main__':
    main()
```

---

# 20. CONFIGURATION SYSTEM

## 18.1 Complete YAML Configuration

```yaml
# config/pure_ml_stella_alpha_settings.yaml
# Stella Alpha: Multi-Timeframe Pure ML Pipeline with Loss Analysis

# =============================================================================
# DATA SOURCES
# =============================================================================
data:
  h4_file: "../version-3/data/EURUSD_H4_features.csv"
  d1_file: "../version-3/data/EURUSD_D1_features.csv"
  timezone: "UTC"

# =============================================================================
# SCHEMA CONFIGURATION
# =============================================================================
schema:
  timestamp_column: "timestamp"
  timestamp_format: "%Y.%m.%d %H:%M:%S"
  ohlcv_columns:
    - "open"
    - "high"
    - "low"
    - "close"
    - "volume"
  pip_value: 0.0001

# =============================================================================
# MULTI-TIMEFRAME SETTINGS
# =============================================================================
multi_timeframe:
  enabled: true
  d1_lookback_shift: 1
  compute_d1_derived: true
  compute_cross_tf: true
  validate_no_leakage: true

# =============================================================================
# FEATURE CONFIGURATION
# =============================================================================
features:
  exclude_columns:
    - "timestamp"
    - "open"
    - "high"
    - "low"
    - "close"
    - "volume"
    - "d1_timestamp"
    - "d1_open"
    - "d1_high"
    - "d1_low"
    - "d1_close"
    - "d1_volume"
    - "pair"
    - "symbol"
    - "label"
    - "label_reason"
    - "regime"
  
  compute_h4_derived: true
  compute_d1_derived: true
  compute_cross_tf: true

# =============================================================================
# CONFIGURATION SPACE (expanded for runners/high flyers)
# =============================================================================
config_space:
  tp_pips:
    min: 50
    max: 150
    step: 10
    # Values: 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150 (11 values)
  
  sl_pips:
    fixed: 30
    # Fixed at 30 pips - no variation
    # This ensures minimum R:R of 1.67:1 (TP50/SL30)
  
  max_holding_bars:
    min: 12
    max: 72
    step: 12
    # Values: 12, 24, 36, 48, 60, 72 (6 values)

# Total configs: 11 × 1 × 6 = 66 configs

# MINIMUM R:R GUARANTEE:
# TP=50 / SL=30 = 1.67:1 (all configs are Tier 1 or better)

# =============================================================================
# CROSS-VALIDATION SETTINGS
# =============================================================================
cv:
  n_folds: 5
  test_years: 2
  gap_bars: 0

# =============================================================================
# RFE FEATURE SELECTION
# =============================================================================
rfe:
  min_features: 10
  max_features: 25
  step: 1
  cv_folds: 3
  scoring: "average_precision"
  use_rfecv: true
  consensus_threshold: 0.6

# =============================================================================
# MODEL CONFIGURATION
# =============================================================================
model:
  type: "lightgbm"
  params:
    n_estimators: 200
    max_depth: 6
    learning_rate: 0.05
    min_child_samples: 50
    subsample: 0.8
    colsample_bytree: 0.8
    reg_alpha: 0.1
    reg_lambda: 0.1
    class_weight: "balanced"
    random_state: 42
    n_jobs: -1
    verbose: -1
    force_col_wise: true

# =============================================================================
# THRESHOLD OPTIMIZATION
# =============================================================================
thresholds:
  values: [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
  min_trades_per_threshold: 30
  optimize_for: "ev"

# =============================================================================
# ACCEPTANCE CRITERIA
# =============================================================================
acceptance:
  min_precision: 0.55
  max_precision_cv: 0.20
  min_ev: 0.0
  min_total_trades: 100
  min_trades_per_fold: 20

# =============================================================================
# LOSS ANALYSIS SETTINGS (NEW)
# =============================================================================
loss_analysis:
  enabled: true
  record_all_trades: true
  trades_db: "artifacts/trades_stella_alpha.db"
  
  # Features to record for each trade
  features_to_record:
    h4:
      - "rsi_value"
      - "bb_position"
      - "trend_strength"
      - "atr_pct"
      - "volume_ratio"
      - "hour"
      - "day_of_week"
      - "is_asian_session"
      - "is_london_session"
      - "is_ny_session"
      - "is_overlap_session"
      - "consecutive_bullish"
      - "exhaustion_score"
      - "macd_histogram"
      - "adx"
    d1:
      - "rsi_value"
      - "bb_position"
      - "trend_strength"
      - "trend_direction"
      - "is_trending_up"
      - "is_trending_down"
      - "atr_percentile"
      - "consecutive_bullish"
    mtf:
      - "confluence_score"
      - "rsi_aligned"
      - "bb_aligned"
      - "trend_aligned"
      - "d1_supports_short"
      - "d1_opposes_short"
  
  # Analysis settings
  min_trades_for_analysis: 500
  significance_level: 0.05

# =============================================================================
# FILTER RECOMMENDATIONS (NEW)
# =============================================================================
filter_recommendations:
  enabled: true
  output_file: "artifacts/filter_recommendations.json"
  top_n_filters: 20
  test_combinations: true
  max_combination_size: 3

# =============================================================================
# EXECUTION SETTINGS
# =============================================================================
execution:
  n_workers: 4
  checkpoint_db: "artifacts/pure_ml_stella_alpha.db"
  log_file: "artifacts/training_stella_alpha.log"
  random_state: 42

# =============================================================================
# OUTPUT SETTINGS
# =============================================================================
output:
  artifacts_dir: "artifacts"
  model_file: "pure_ml_stella_alpha_model.pkl"
  features_file: "features_stella_alpha.json"
  config_file: "trading_config_stella_alpha.json"
  metrics_file: "metrics_stella_alpha.json"
  loss_analysis_file: "loss_analysis_stella_alpha.json"
```

---

# 21. COMMAND LINE INTERFACE

## 20.1 Main Pipeline CLI

```python
# run_pure_ml_stella_alpha.py

import argparse

def parse_args():
    parser = argparse.ArgumentParser(
        description='Stella Alpha: Multi-Timeframe Pure ML Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  python run_pure_ml_stella_alpha.py
  
  # Run with custom config and 8 workers
  python run_pure_ml_stella_alpha.py -c config/custom.yaml -w 8
  
  # Run with specific input files
  python run_pure_ml_stella_alpha.py -i data/H4.csv --d1-input data/D1.csv
  
  # Resume from checkpoint
  python run_pure_ml_stella_alpha.py -c config/settings.yaml
  (Automatically resumes from pure_ml_stella_alpha.db)
        """
    )
    
    # Required/Main arguments
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config/pure_ml_stella_alpha_settings.yaml',
        help='Path to YAML configuration file'
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        default=None,
        help='Path to H4 input CSV (overrides config)'
    )
    
    parser.add_argument(
        '--d1-input',
        type=str,
        default=None,
        help='Path to D1 input CSV (overrides config)'
    )
    
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='artifacts',
        help='Output directory for artifacts'
    )
    
    parser.add_argument(
        '--checkpoint-db',
        type=str,
        default=None,
        help='Path to checkpoint database (default: artifacts/pure_ml_stella_alpha.db)'
    )
    
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Start fresh, ignore existing checkpoint'
    )
    
    parser.add_argument(
        '--analyze-losses',
        action='store_true',
        help='Run loss analysis after experiments complete'
    )
    
    parser.add_argument(
        '--recommend-filters',
        action='store_true',
        help='Generate filter recommendations after loss analysis'
    )
    
    parser.add_argument(
        '--compare-v4',
        type=str,
        default=None,
        help='Path to V4 database for comparison report'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without executing'
    )
    
    return parser.parse_args()
```

## 20.2 Usage Examples

```powershell
# Basic run (uses default config, 4 workers)
python run_pure_ml_stella_alpha.py

# Run with 8 parallel workers
python run_pure_ml_stella_alpha.py -w 8

# Run with custom config file
python run_pure_ml_stella_alpha.py -c config/my_settings.yaml

# Specify input files directly
python run_pure_ml_stella_alpha.py -i data/EURUSD_H4.csv --d1-input data/EURUSD_D1.csv

# Run with all analysis steps
python run_pure_ml_stella_alpha.py -w 6 --analyze-losses --recommend-filters

# Compare results with V4
python run_pure_ml_stella_alpha.py --compare-v4 ../version-4/artifacts/pure_ml.db

# Fresh start (ignore checkpoint)
python run_pure_ml_stella_alpha.py --no-resume

# Dry run to see config
python run_pure_ml_stella_alpha.py --dry-run
```

## 20.3 Diagnostic CLI

```python
# diagnose.py

parser = argparse.ArgumentParser(description='Stella Alpha Diagnostics')

parser.add_argument('--db', '-d', default='artifacts/pure_ml_stella_alpha.db')
parser.add_argument('--top', '-t', type=int, default=10)
parser.add_argument('--compare-v4', type=str, default=None)
parser.add_argument('--output', '-o', type=str, default=None)
parser.add_argument('--format', choices=['text', 'json', 'csv'], default='text')
parser.add_argument('--section', choices=['all', 'overview', 'gold', 'features', 'rejections'], default='all')
```

## 20.4 Loss Analysis CLI

```python
# analyze_losses.py

parser = argparse.ArgumentParser(description='Analyze Trading Losses')

parser.add_argument('--trades', '-t', default='artifacts/trades_stella_alpha.db')
parser.add_argument('--config', '-c', default=None, help='Specific config to analyze')
parser.add_argument('--all', '-a', action='store_true', help='Analyze all configs')
parser.add_argument('--output', '-o', default='artifacts/loss_analysis.json')
parser.add_argument('--top-features', type=int, default=20)
```

## 20.5 Filter Recommendations CLI

```python
# recommend_filters.py

parser = argparse.ArgumentParser(description='Generate Filter Recommendations')

parser.add_argument('--trades', '-t', default='artifacts/trades_stella_alpha.db')
parser.add_argument('--tp', type=int, required=True, help='TP pips for P&L calculation')
parser.add_argument('--sl', type=int, default=30, help='SL pips (default: 30)')
parser.add_argument('--output', '-o', default='artifacts/filter_recommendations.json')
parser.add_argument('--top-n', type=int, default=20)
parser.add_argument('--test-combinations', action='store_true')
parser.add_argument('--oos-validation', action='store_true', help='Use out-of-sample validation')
```

---

# 22. ARTIFACTS & OUTPUT FILES

## 21.1 Complete Artifacts List

```
artifacts/
│
├── DATABASES
│   ├── pure_ml_stella_alpha.db     # Main checkpoint database
│   │   ├── completed table         # All config results
│   │   ├── models table            # Stored trained models
│   │   └── fold_results table      # Per-fold metrics
│   │
│   └── trades_stella_alpha.db      # Trade recording database
│       └── trades table            # Every trade with features
│
├── MODELS (one per passing config)
│   └── models/
│       ├── stella_TP150_SL30_H48.pkl
│       ├── stella_TP150_SL30_H48_config.json
│       ├── stella_TP100_SL30_H36.pkl
│       ├── stella_TP100_SL30_H36_config.json
│       ├── ... (all passing configs)
│       └── tier_summary.json       # Tier 0/1 organization
│
├── CONFIGURATION
│   ├── features_stella_alpha.json  # Consensus selected features
│   ├── trading_config_stella_alpha.json  # Best config for deployment
│   └── full_config_dump.json       # Complete settings used
│
├── METRICS & REPORTS
│   ├── metrics_stella_alpha.json   # Aggregated metrics
│   ├── fold_details.json           # Per-fold breakdown
│   ├── parameter_analysis.json     # TP/SL/Hold patterns
│   └── feature_importance.json     # Feature ranking
│
├── STATISTICAL VALIDATION
│   ├── feature_prefilter_report.json   # Pre-filter results
│   ├── fold_stability_report.json      # Stability analysis
│   └── statistical_validation.json     # All stat tests
│
├── LOSS ANALYSIS
│   ├── loss_analysis_stella_alpha.json # Win vs Loss patterns
│   ├── session_analysis.json           # By trading session
│   ├── confidence_analysis.json        # By model confidence
│   └── d1_alignment_analysis.json      # D1 impact
│
├── FILTER RECOMMENDATIONS
│   ├── filter_recommendations.json     # All filter suggestions
│   ├── filter_oos_validation.json      # Out-of-sample tests
│   └── filter_combinations.json        # Combined filters
│
├── COMPARISON
│   └── v4_comparison_report.json       # V4 vs Stella Alpha
│
└── LOGS
    └── training_stella_alpha.log       # Execution log
```

## 21.2 Key JSON File Formats

### trading_config_stella_alpha.json (Best Config for Deployment)
```json
{
  "version": "Stella Alpha",
  "generated_at": "2025-01-15T10:30:00",
  "best_config": {
    "config_id": "TP100_SL30_H48",
    "tier": 0,
    "tier_name": "TIER 0 - RUNNER",
    "tp_pips": 100,
    "sl_pips": 30,
    "max_holding_bars": 48,
    "threshold": 0.55,
    "classification": "GOLD"
  },
  "performance": {
    "ev_mean": 15.2,
    "precision_mean": 0.38,
    "precision_cv": 0.10,
    "total_trades": 2450,
    "edge_above_breakeven": 0.15
  },
  "features": [
    "rsi_value",
    "bb_position",
    "d1_trend_direction",
    "mtf_confluence_score",
    "..."
  ],
  "model_file": "models/stella_TP100_SL30_H48.pkl"
}
```

### metrics_stella_alpha.json (Summary Metrics)
```json
{
  "run_summary": {
    "total_configs": 66,
    "passed": 24,
    "failed": 42,
    "pass_rate": 0.364
  },
  "classifications": {
    "gold": 2,
    "silver": 8,
    "bronze": 14
  },
  "tiers": {
    "tier_0_runners": 15,
    "tier_1_ideal": 9
  },
  "best_configs": {
    "by_ev": {"config_id": "TP100_SL30_H48", "ev": 15.2},
    "by_precision": {"config_id": "TP50_SL30_H36", "precision": 0.55},
    "by_rr": {"config_id": "TP150_SL30_H48", "rr": 5.0}
  },
  "execution": {
    "total_time_seconds": 3600,
    "avg_time_per_config": 54.5,
    "workers_used": 6
  }
}
```

---

# 23. LOGGING SYSTEM

## 22.1 Logger Implementation

```python
# src/logging_utils.py

import sys
import logging
from datetime import datetime
from pathlib import Path
import threading

class StellaAlphaLogger:
    """
    UTF-8 compatible logger for Windows and Linux.
    
    Features:
    - Console output with colors
    - File logging with timestamps
    - Thread-safe
    - Progress tracking
    """
    
    def __init__(
        self,
        log_file: str = "artifacts/training_stella_alpha.log",
        console_level: str = "INFO",
        file_level: str = "DEBUG"
    ):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.start_time = datetime.now()
        
        # Setup file handler with UTF-8
        self.file_handler = open(
            self.log_file, 'a', encoding='utf-8', errors='replace'
        )
        
        # Color codes for console
        self.colors = {
            'INFO': '\033[97m',      # White
            'SUCCESS': '\033[92m',   # Green
            'WARNING': '\033[93m',   # Yellow
            'ERROR': '\033[91m',     # Red
            'RESET': '\033[0m'
        }
        
        # Check if console supports colors
        self.use_colors = sys.stdout.isatty()
    
    def _format_message(self, message: str, level: str) -> str:
        """Format log message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elapsed = datetime.now() - self.start_time
        elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds
        
        return f"[{timestamp}] [{elapsed_str}] [{level}] {message}"
    
    def log(self, message: str, level: str = "INFO"):
        """Log message to console and file."""
        formatted = self._format_message(message, level)
        
        with self.lock:
            # Console output
            if self.use_colors and level in self.colors:
                color = self.colors.get(level, '')
                reset = self.colors['RESET']
                print(f"{color}{formatted}{reset}")
            else:
                print(formatted)
            
            # File output
            self.file_handler.write(formatted + "\n")
            self.file_handler.flush()
    
    def info(self, message: str):
        self.log(message, "INFO")
    
    def success(self, message: str):
        self.log(message, "SUCCESS")
    
    def warning(self, message: str):
        self.log(message, "WARNING")
    
    def error(self, message: str):
        self.log(message, "ERROR")
    
    def section(self, title: str):
        """Print section header."""
        self.log("")
        self.log("=" * 60)
        self.log(f"  {title}")
        self.log("=" * 60)
    
    def subsection(self, title: str):
        """Print subsection header."""
        self.log("")
        self.log(f"  {title}")
        self.log("  " + "-" * 40)
    
    def close(self):
        """Close file handler."""
        self.file_handler.close()
```

## 22.2 Usage Example

```python
logger = StellaAlphaLogger("artifacts/training.log")

logger.section("STELLA ALPHA PIPELINE START")
logger.info("Loading configuration...")
logger.info("H4 file: data/EURUSD_H4.csv")
logger.info("D1 file: data/EURUSD_D1.csv")

logger.subsection("Data Loading")
logger.info("Loading H4 data... 41,523 rows")
logger.info("Loading D1 data... 6,521 rows")
logger.success("Data loaded successfully")

logger.subsection("Merge & Validation")
logger.info("Merging H4 with D1...")
logger.info("Dropped 312 rows without D1 data")
logger.success("Leakage validation PASSED")

logger.warning("Some feature has high correlation with target")
logger.error("Config TP30_SL50_H12 failed: Not enough trades")

logger.close()
```

---

# 24. WINDOWS COMPATIBILITY

## 23.1 Key Compatibility Issues

```
WINDOWS-SPECIFIC ISSUES:
────────────────────────

1. MULTIPROCESSING
   Problem: Windows lacks fork(), requires spawn
   Solution: Use if __name__ == '__main__' guard

2. PATH HANDLING
   Problem: Backslashes vs forward slashes
   Solution: Use pathlib.Path everywhere

3. UTF-8 ENCODING
   Problem: Default encoding is cp1252
   Solution: Explicit encoding='utf-8' on all file ops

4. CONSOLE COLORS
   Problem: ANSI codes not supported by default
   Solution: Use colorama.init() or detect and disable

5. FILE LOCKING
   Problem: Different semantics than Unix
   Solution: Use portalocker or threading.Lock

6. LONG PATHS
   Problem: 260 character limit
   Solution: Use \\?\ prefix or enable long paths in registry
```

## 23.2 Compatibility Code

```python
# src/compat.py

import sys
import os
from pathlib import Path

# Platform detection
IS_WINDOWS = sys.platform.startswith('win')

def ensure_windows_compat():
    """Initialize Windows compatibility settings."""
    if IS_WINDOWS:
        # Enable ANSI colors in Windows console
        try:
            import colorama
            colorama.init()
        except ImportError:
            pass
        
        # Set UTF-8 mode
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        
        # Enable long path support (Python 3.6+)
        if sys.version_info >= (3, 6):
            os.environ['PYTHONLEGACYWINDOWSSTDIO'] = '0'


def safe_path(path_str: str) -> Path:
    """Convert path string to Path object safely."""
    return Path(path_str).resolve()


def safe_open(path: Path, mode: str = 'r', **kwargs):
    """Open file with UTF-8 encoding."""
    if 'encoding' not in kwargs and 'b' not in mode:
        kwargs['encoding'] = 'utf-8'
    if 'errors' not in kwargs and 'b' not in mode:
        kwargs['errors'] = 'replace'
    return open(path, mode, **kwargs)


# Multiprocessing guard
def run_parallel_safe(main_func):
    """
    Decorator for Windows-safe multiprocessing.
    
    Usage:
        @run_parallel_safe
        def main():
            ...
    """
    def wrapper():
        if IS_WINDOWS:
            import multiprocessing
            multiprocessing.freeze_support()
        return main_func()
    return wrapper
```

## 23.3 Main Script Guard

```python
# run_pure_ml_stella_alpha.py

from src.compat import ensure_windows_compat, run_parallel_safe

@run_parallel_safe
def main():
    ensure_windows_compat()
    
    # Parse args
    args = parse_args()
    
    # Run pipeline
    run_pipeline(args)


if __name__ == '__main__':
    main()
```

---

# 25. VERSION COMPARISON TOOL

## 24.1 Overview

```
PURPOSE:
Compare Stella Alpha results with V4 baseline to measure improvement.

COMPARISON METRICS:
├── Pass rate improvement
├── EV improvement
├── New configs passing (high R:R)
├── Tier distribution
├── Feature differences (D1/MTF contribution)
└── Statistical significance of improvement
```

## 24.2 Implementation

```python
# compare_versions.py

import argparse
import json
import sqlite3
from pathlib import Path
from scipy import stats
import numpy as np

def load_results(db_path: str) -> dict:
    """Load results from checkpoint database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    results = conn.execute("""
        SELECT * FROM completed ORDER BY ev_mean DESC
    """).fetchall()
    
    return {
        'path': db_path,
        'total': len(results),
        'passed': [dict(r) for r in results if r['status'] == 'passed'],
        'failed': [dict(r) for r in results if r['status'] == 'failed'],
        'all': [dict(r) for r in results]
    }


def compare_versions(v4_path: str, stella_path: str):
    """Compare V4 with Stella Alpha."""
    v4 = load_results(v4_path)
    stella = load_results(stella_path)
    
    print("\n" + "=" * 70)
    print("  V4 vs STELLA ALPHA COMPARISON")
    print("=" * 70)
    
    # Basic stats
    print(f"""
    OVERVIEW
    ────────────────────────────────────────────────
                        V4              Stella Alpha
    ────────────────────────────────────────────────
    Total Configs:      {v4['total']:<15} {stella['total']}
    Passed:             {len(v4['passed']):<15} {len(stella['passed'])}
    Pass Rate:          {100*len(v4['passed'])/v4['total']:.1f}%{' '*11} {100*len(stella['passed'])/stella['total']:.1f}%
    """)
    
    # EV comparison
    v4_evs = [r['ev_mean'] for r in v4['passed']] if v4['passed'] else [0]
    stella_evs = [r['ev_mean'] for r in stella['passed']] if stella['passed'] else [0]
    
    print(f"""
    EXPECTED VALUE (Passed Configs)
    ────────────────────────────────────────────────
    Best EV:            {max(v4_evs):+.2f}{' '*12} {max(stella_evs):+.2f}
    Mean EV:            {np.mean(v4_evs):+.2f}{' '*12} {np.mean(stella_evs):+.2f}
    """)
    
    # Tier analysis (Stella Alpha only)
    tier_0 = [r for r in stella['passed'] if r.get('tier') == 0]
    tier_1 = [r for r in stella['passed'] if r.get('tier') == 1]
    
    print(f"""
    TIER DISTRIBUTION (Stella Alpha)
    ────────────────────────────────────────────────
    🚀 Tier 0 (Runners):  {len(tier_0)} configs
    ⭐ Tier 1 (Ideal):    {len(tier_1)} configs
    
    V4 had no tier system (all configs R:R <= 1:1)
    """)
    
    # High R:R configs
    high_rr_v4 = [r for r in v4['passed'] if r.get('tp_pips', 0) > r.get('sl_pips', 100)]
    high_rr_stella = [r for r in stella['passed'] if r.get('tp_pips', 0) > r.get('sl_pips', 100)]
    
    print(f"""
    HIGH R:R CONFIGS (TP > SL)
    ────────────────────────────────────────────────
    V4:                 {len(high_rr_v4)} configs
    Stella Alpha:       {len(high_rr_stella)} configs
    Improvement:        +{len(high_rr_stella) - len(high_rr_v4)} configs
    """)
    
    # Feature comparison
    print(f"""
    D1/MTF FEATURE CONTRIBUTION
    ────────────────────────────────────────────────
    """)
    
    d1_count = 0
    mtf_count = 0
    total_features = 0
    
    for r in stella['passed']:
        features = r.get('selected_features', '[]')
        if isinstance(features, str):
            features = json.loads(features)
        total_features += len(features)
        d1_count += len([f for f in features if f.startswith('d1_')])
        mtf_count += len([f for f in features if f.startswith('mtf_')])
    
    if stella['passed']:
        print(f"    D1 features selected:  {d1_count} ({100*d1_count/total_features:.1f}% of all)")
        print(f"    MTF features selected: {mtf_count} ({100*mtf_count/total_features:.1f}% of all)")
        
        if d1_count > 0 or mtf_count > 0:
            print(f"\n    ✅ Multi-timeframe data IS contributing to model performance")
        else:
            print(f"\n    ⚠️  Multi-timeframe data is NOT being selected")
    
    # Statistical significance
    if len(v4_evs) > 2 and len(stella_evs) > 2:
        t_stat, p_value = stats.ttest_ind(stella_evs, v4_evs)
        
        print(f"""
    STATISTICAL SIGNIFICANCE
    ────────────────────────────────────────────────
    T-test (Stella Alpha vs V4 EVs):
    t-statistic: {t_stat:.3f}
    p-value:     {p_value:.4f}
    Significant: {'✅ YES (p < 0.05)' if p_value < 0.05 else '❌ NO'}
        """)
    
    # Final verdict
    print(f"""
    VERDICT
    ────────────────────────────────────────────────
    """)
    
    if len(tier_0) > 0:
        print(f"    🎉 SUCCESS: {len(tier_0)} RUNNER configs found!")
        print(f"       Stella Alpha unlocked high R:R trading.")
        best_runner = max(tier_0, key=lambda x: x['ev_mean'])
        print(f"       Best: {best_runner['config_id']} with EV={best_runner['ev_mean']:+.2f}")
    elif len(stella['passed']) > len(v4['passed']):
        print(f"    ⚠️  PARTIAL SUCCESS: More configs passing, but no Runners")
        print(f"       D1 data helps but not enough for high R:R")
    else:
        print(f"    ❌ NO IMPROVEMENT: Stella Alpha did not outperform V4")
        print(f"       Consider: different features, longer hold times, or other data")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Compare V4 with Stella Alpha')
    parser.add_argument('--v4', required=True, help='Path to V4 database')
    parser.add_argument('--stella', required=True, help='Path to Stella Alpha database')
    parser.add_argument('--output', '-o', default=None, help='Output JSON file')
    
    args = parser.parse_args()
    compare_versions(args.v4, args.stella)
```

---

# 26. DATA HANDLING & NaN MANAGEMENT

## 25.1 NaN Handling for D1 Data

```
PROBLEM:
────────
First ~300 H4 rows will have missing D1 data because:
1. D1 features need warmup (MA50 needs 50 D1 bars = 300 H4 rows)
2. First H4 row has no previous D1 bar to merge

SOLUTION:
─────────
1. Drop rows with missing D1 timestamp (no D1 data yet)
2. Drop rows with NaN in critical D1 features
3. Document minimum data requirement
4. Validate before training
```

## 25.2 NaN Handler Implementation

```python
# src/nan_handler.py

import pandas as pd
import numpy as np
from typing import Tuple, List

def handle_missing_d1_data(
    df_merged: pd.DataFrame,
    logger
) -> pd.DataFrame:
    """
    Handle rows where D1 data is missing.
    
    Returns:
        DataFrame with NaN rows removed
    """
    initial_rows = len(df_merged)
    
    # Step 1: Drop rows without D1 timestamp
    if 'd1_timestamp' in df_merged.columns:
        df_merged = df_merged.dropna(subset=['d1_timestamp'])
        after_d1_drop = len(df_merged)
        dropped_1 = initial_rows - after_d1_drop
        logger.info(f"Dropped {dropped_1} rows without D1 data")
    
    # Step 2: Identify D1 derived features that need warmup
    d1_warmup_features = [
        'd1_rsi_value',      # 14 bars
        'd1_ma20',           # 20 bars
        'd1_ma50',           # 50 bars
        'd1_roc_10',         # 10 bars
        'd1_adx',            # ~14 bars
    ]
    
    # Step 3: Drop rows with NaN in D1 features
    existing_d1_features = [f for f in d1_warmup_features if f in df_merged.columns]
    if existing_d1_features:
        before = len(df_merged)
        df_merged = df_merged.dropna(subset=existing_d1_features)
        dropped_2 = before - len(df_merged)
        logger.info(f"Dropped {dropped_2} rows with NaN in D1 features")
    
    # Step 4: Final cleanup - drop any remaining NaN in feature columns
    feature_cols = [c for c in df_merged.columns if c not in [
        'timestamp', 'd1_timestamp', 'open', 'high', 'low', 'close', 'volume',
        'd1_open', 'd1_high', 'd1_low', 'd1_close', 'd1_volume', 'label'
    ]]
    
    before = len(df_merged)
    df_merged = df_merged.dropna(subset=feature_cols)
    dropped_3 = before - len(df_merged)
    if dropped_3 > 0:
        logger.info(f"Dropped {dropped_3} rows with remaining NaN")
    
    total_dropped = initial_rows - len(df_merged)
    logger.info(f"Total rows dropped: {total_dropped} ({100*total_dropped/initial_rows:.1f}%)")
    logger.info(f"Remaining rows: {len(df_merged)}")
    
    return df_merged


def validate_no_nan(df: pd.DataFrame, feature_columns: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate that no NaN values exist in feature columns.
    
    Returns:
        (is_valid, list of columns with NaN)
    """
    nan_cols = []
    for col in feature_columns:
        if col in df.columns and df[col].isna().any():
            nan_count = df[col].isna().sum()
            nan_cols.append(f"{col} ({nan_count} NaN)")
    
    return len(nan_cols) == 0, nan_cols


def get_warmup_requirements() -> dict:
    """Document warmup requirements for all features."""
    return {
        'h4_features': {
            'rsi_value': 14,        # 14 H4 bars = 56 hours
            'ma20': 20,             # 20 H4 bars = 80 hours
            'ma50': 50,             # 50 H4 bars = 200 hours
            'atr': 14,
            'adx': 14,
            'macd': 26,             # Slow EMA
            'bb': 20,               # Bollinger period
        },
        'd1_features': {
            'd1_rsi_value': 14,     # 14 D1 bars = 14 days
            'd1_ma20': 20,          # 20 D1 bars = 20 days  
            'd1_ma50': 50,          # 50 D1 bars = 50 days (~300 H4 bars)
            'd1_atr': 14,
            'd1_adx': 14,
            'd1_roc_10': 10,
        },
        'total_h4_warmup': 300,     # Conservative: 50 D1 bars × 6 H4/day
        'safe_start_date': '50+ days from data start'
    }
```

---

# 29. FILE STRUCTURE

## 24.1 Complete Stella Alpha Directory

```
stella-alpha/
│
├── run_pure_ml_stella_alpha.py              # Main entry point
├── diagnose.py                    # Diagnostic analysis
├── compare_versions.py            # V4 vs Stella Alpha comparison
├── analyze_losses.py              # Loss analysis script (NEW)
├── recommend_filters.py           # Filter recommendations (NEW)
├── requirements.txt               # Dependencies
├── README.md                      # Documentation
│
├── config/
│   └── pure_ml_stella_alpha_settings.yaml   # Full configuration
│
├── src/
│   ├── __init__.py                # Package init
│   ├── data_merger.py             # D1 merge with leakage prevention
│   ├── feature_engineering.py     # H4 + D1 + MTF features
│   ├── statistical_validation.py  # Statistical tests (NEW)
│   ├── features.py                # RFE selection
│   ├── pure_ml_labels.py          # Labeling logic
│   ├── training.py                # Model training
│   ├── evaluation.py              # Evaluation metrics
│   ├── experiment.py              # Experiment runner
│   ├── checkpoint_db.py           # Checkpoint/resume
│   ├── trade_recorder.py          # Trade recording (NEW)
│   ├── loss_analysis.py           # Loss analysis (NEW)
│   └── filter_recommendations.py  # Filter engine (NEW)
│
├── artifacts/                     # Output directory
│   ├── pure_ml_stella_alpha.db              # Checkpoint database
│   ├── trades_stella_alpha.db               # Trade log database (NEW)
│   ├── pure_ml_stella_alpha_model.pkl       # Best model
│   ├── features_stella_alpha.json           # Selected features
│   ├── trading_config_stella_alpha.json     # Best config
│   ├── metrics_stella_alpha.json            # Metrics summary
│   ├── loss_analysis_stella_alpha.json      # Loss analysis report (NEW)
│   ├── filter_recommendations.json          # Filter recommendations (NEW)
│   ├── statistical_validation.json          # Statistical test results (NEW)
│   ├── feature_prefilter_report.json        # Pre-filter results (NEW)
│   ├── fold_stability_report.json           # Fold stability analysis (NEW)
│   └── training_stella_alpha.log            # Execution log
│
└── tests/                         # Unit tests
    ├── test_data_merger.py
    ├── test_features.py
    ├── test_statistical_validation.py  # (NEW)
    ├── test_loss_analysis.py      # (NEW)
    ├── test_filter_engine.py      # (NEW)
    └── test_pipeline.py
```

---

# 27. IMPLEMENTATION RISKS & MITIGATIONS

## 25.1 Risk Summary Table

```
┌────┬─────────────────────────────────────┬──────────┬────────────────────────────────┐
│ #  │ Risk                                │ Severity │ Mitigation                     │
├────┼─────────────────────────────────────┼──────────┼────────────────────────────────┤
│ 1  │ NaN in D1 rows at dataset start     │ HIGH     │ Drop first ~300 H4 rows        │
│ 2  │ Feature pre-filter data leakage     │ HIGH     │ Run inside each fold           │
│ 3  │ Filter impact is in-sample          │ MEDIUM   │ OOS validation on held-out fold│
│ 4  │ Model storage for export undefined  │ HIGH     │ Store in checkpoint DB BLOB    │
│ 5  │ GOLD/SILVER thresholds for high R:R │ MEDIUM   │ Use edge-above-breakeven       │
│ 6  │ D1 derived features NaN warmup      │ HIGH     │ Validate after feature eng     │
│ 7  │ Parallel trade recording thread     │ MEDIUM   │ SQLite WAL + per-worker conn   │
│ 8  │ Filter generator not exhaustive     │ LOW      │ Add percentile-based filters   │
│ 9  │ Sections 9-15, 19-24 missing        │ HIGH     │ ✅ RESOLVED - Now complete     │
└────┴─────────────────────────────────────┴──────────┴────────────────────────────────┘
```

## 25.2 Risk 1: NaN Handling for D1 Rows

```
PROBLEM:
First ~50-300 H4 rows will have no D1 data because:
- D1 features need warmup (MA50 needs 50 D1 bars)
- First H4 rows have no previous D1 bar available

SOLUTION:
```

```python
# In data_merger.py - MUST be called after merge

def handle_missing_d1_data(df_merged, logger):
    """Drop rows where D1 data is missing or has NaN."""
    initial = len(df_merged)
    
    # 1. Drop rows without D1 timestamp
    df_merged = df_merged.dropna(subset=['d1_timestamp'])
    
    # 2. Drop rows with NaN in D1 warmup features
    d1_features = [c for c in df_merged.columns if c.startswith('d1_')]
    df_merged = df_merged.dropna(subset=d1_features)
    
    dropped = initial - len(df_merged)
    logger.info(f"Dropped {dropped} rows without valid D1 data")
    
    return df_merged

# CALL THIS in pipeline:
df_merged = merge_h4_d1_safe(df_h4, df_d1)
df_merged = handle_missing_d1_data(df_merged, logger)  # CRITICAL!
```

## 25.3 Risk 2: Feature Pre-Filter Data Leakage

```
PROBLEM:
If statistical pre-filter runs on FULL dataset before CV split,
it sees test data → data leakage → overfit results

WRONG (leakage):
    kept_features = prefilter(full_data)  # Uses test data!
    for fold in folds:
        train, test = split(fold)
        model.fit(train[kept_features])

CORRECT (no leakage):
    for fold in folds:
        train, test = split(fold)
        kept_features = prefilter(train)  # Only training data!
        model.fit(train[kept_features])

SOLUTION:
```

```python
# In walk_forward_cv.py

def run_walk_forward_cv(df, labels, feature_columns, settings):
    for fold in folds:
        train_df, test_df = get_fold_data(df, fold)
        
        # CRITICAL: Pre-filter on TRAINING DATA ONLY
        stat_filter = StatisticalFeatureFilter(p_threshold=0.05)
        kept_features, _, _ = stat_filter.filter_features(
            train_df,           # <-- ONLY training data
            feature_columns,
            label_column='label'
        )
        
        # RFE on pre-filtered features
        selected = run_rfe(train_df[kept_features], y_train, settings)
        
        # Train and evaluate
        ...
```

## 25.4 Risk 3: Filter Impact Is In-Sample

```
PROBLEM:
Filter recommendations based on historical data may overfit.
"Avoid Asian session" might work in backtest but not forward.

SOLUTION:
Add out-of-sample validation for filters:
- Train filter rules on folds 1-3
- Test on held-out folds 4-5
- Report both in-sample and out-of-sample improvement
```

```python
# In filter_recommendations.py

def validate_filter_oos(filter_rule, trades_df):
    """Validate filter with out-of-sample data."""
    
    # Split by fold
    train_folds = [1, 2, 3]
    test_folds = [4, 5]
    
    train_trades = trades_df[trades_df['fold'].isin(train_folds)]
    test_trades = trades_df[trades_df['fold'].isin(test_folds)]
    
    # Calculate impact on both
    is_impact = calculate_filter_impact(filter_rule, train_trades)
    oos_impact = calculate_filter_impact(filter_rule, test_trades)
    
    # Check for overfit
    overfit_ratio = is_impact['net_improvement'] / oos_impact['net_improvement'] \
                    if oos_impact['net_improvement'] > 0 else float('inf')
    
    return {
        'in_sample': is_impact,
        'out_of_sample': oos_impact,
        'overfit_ratio': overfit_ratio,
        'is_robust': overfit_ratio < 2.0  # Less than 2x overfit
    }
```

## 25.5 Risk 4: Model Storage for Export

```
PROBLEM:
export_all_passing_models() calls load_model_from_checkpoint()
but this function was not defined → export will fail.

SOLUTION:
Store models in checkpoint DB during training:
```

```python
# In checkpoint_db.py (already added in Section 11)

def save_model(self, config_id, fold, model, threshold, precision, ev):
    """Save trained model to database as BLOB."""
    model_bytes = pickle.dumps(model)
    self.conn.execute("""
        INSERT OR REPLACE INTO models 
        (config_id, fold, model_blob, threshold, precision, ev, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (config_id, fold, model_bytes, threshold, precision, ev, 
          datetime.now().isoformat()))
    self.conn.commit()

def load_model(self, config_id, fold=None):
    """Load model from database."""
    if fold:
        result = self.conn.execute(
            "SELECT model_blob FROM models WHERE config_id=? AND fold=?",
            (config_id, fold)
        ).fetchone()
    else:
        # Get best fold
        result = self.conn.execute(
            "SELECT model_blob FROM models WHERE config_id=? ORDER BY precision DESC LIMIT 1",
            (config_id,)
        ).fetchone()
    
    return pickle.loads(result[0]) if result else None

# CALL THIS during training:
db.save_model(config_id, fold, model, threshold, precision, ev)
```

## 25.6 Risk 5: GOLD/SILVER Thresholds for High R:R

```
PROBLEM:
V4 thresholds (precision > 55%, EV > 2) don't make sense for Stella Alpha
because high R:R configs have LOWER precision by design.

TP=100 SL=30 might have 35% precision but still be excellent.

SOLUTION:
Use "edge above breakeven" instead of absolute precision:
```

```python
# In evaluation.py (already added in Section 16)

def classify_config_stella(result):
    """Stella Alpha classification using edge-above-breakeven."""
    
    # Calculate edge
    min_wr = result['min_winrate_required']  # e.g., 0.23 for TP100/SL30
    precision = result['precision_mean']     # e.g., 0.35
    edge = precision - min_wr                # e.g., 0.12 (12% edge)
    
    ev = result['ev_mean']
    cv = result['precision_cv']
    trades = result['total_trades']
    
    # GOLD: Strong edge + stable + volume
    if edge > 0.10 and cv < 0.12 and trades > 500 and ev > 8.0:
        return 'GOLD'
    
    # SILVER: Good edge + acceptable stability
    if edge > 0.05 and cv < 0.18 and ev > 3.0:
        return 'SILVER'
    
    # BRONZE: Passes minimum
    if edge > 0 and ev > 0:
        return 'BRONZE'
    
    return None
```

## 25.7 Risk 6: D1 Derived Features NaN Warmup

```
PROBLEM:
D1 derived features like d1_ma50 need 50 D1 bars of history.
This means first ~50 days of D1 data will have NaN.

WARMUP REQUIREMENTS:
─────────────────────
Feature          D1 Bars    H4 Rows Lost
d1_rsi_value     14         ~84
d1_ma20          20         ~120
d1_ma50          50         ~300
d1_adx           14         ~84
d1_roc_10        10         ~60

SOLUTION:
```

```python
# In feature_engineering.py

def validate_feature_nan(df, feature_columns, logger):
    """Validate no NaN in feature columns before training."""
    
    nan_report = {}
    for col in feature_columns:
        if col in df.columns:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                nan_report[col] = nan_count
    
    if nan_report:
        logger.error("NaN found in features after engineering:")
        for col, count in sorted(nan_report.items(), key=lambda x: x[1], reverse=True)[:10]:
            logger.error(f"  {col}: {count} NaN values")
        raise ValueError(f"NaN in {len(nan_report)} features - check warmup requirements")
    
    logger.success("No NaN in feature columns")
    return True

# CALL after feature engineering:
df = engineer_all_features(df_merged)
df = df.dropna()  # Drop warmup rows
validate_feature_nan(df, feature_columns, logger)
```

## 25.8 Risk 7: Parallel Trade Recording Thread Safety

```
PROBLEM:
Multiple workers writing to SQLite trades_stella_alpha.db simultaneously.
Default SQLite doesn't handle concurrent writes well.

SOLUTION:
1. Enable WAL (Write-Ahead Logging) mode
2. Use per-worker connections (not shared)
3. Batch inserts to reduce lock contention
```

```python
# In trade_recorder.py

import threading
import sqlite3

class ThreadSafeTradeRecorder:
    """Thread-safe trade recorder for parallel workers."""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _init_db(self):
        """Initialize with WAL mode."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY,
                config_id TEXT,
                fold INTEGER,
                ...
            )
        """)
        conn.close()
    
    def _get_conn(self):
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, timeout=30)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn
    
    def record_trades_batch(self, trades: list):
        """Record batch of trades (reduces lock contention)."""
        conn = self._get_conn()
        conn.executemany(
            "INSERT INTO trades (...) VALUES (...)",
            trades
        )
        conn.commit()
```

## 25.9 Risk 8: Filter Generator Not Exhaustive

```
PROBLEM:
Predefined filters might miss optimal thresholds.
E.g., filter "RSI > 70" might work, but "RSI > 72" could be better.

SOLUTION:
Add dynamic threshold discovery based on data distribution:
```

```python
# In filter_recommendations.py

def generate_dynamic_filters(df, feature_columns):
    """Generate filters based on data percentiles."""
    filters = []
    
    for feature in feature_columns:
        if feature not in df.columns:
            continue
        
        values = df[feature].dropna()
        if len(values) < 100:
            continue
        
        # Test percentile-based thresholds
        for pct in [25, 50, 75, 90]:
            threshold = np.percentile(values, pct)
            
            filters.append(FilterRule(
                feature=feature,
                operator='>=',
                threshold=round(threshold, 4),
                description=f"{feature} >= {pct}th percentile ({threshold:.2f})"
            ))
            
            filters.append(FilterRule(
                feature=feature,
                operator='<',
                threshold=round(threshold, 4),
                description=f"{feature} < {pct}th percentile ({threshold:.2f})"
            ))
    
    return filters
```

## 25.10 Risk Resolution Summary

```
STATUS AFTER MITIGATIONS:
─────────────────────────

✅ Risk 1: NaN handling - handle_missing_d1_data() added
✅ Risk 2: Pre-filter leakage - Runs inside each fold
✅ Risk 3: In-sample filters - OOS validation added
✅ Risk 4: Model storage - save_model/load_model in checkpoint DB
✅ Risk 5: GOLD thresholds - Edge-above-breakeven classification
✅ Risk 6: D1 NaN warmup - validate_feature_nan() added
✅ Risk 7: Thread safety - WAL mode + per-worker connections
✅ Risk 8: Filter exhaustive - Dynamic percentile filters
✅ Risk 9: Missing sections - All 12 sections now complete
```

---

# 28. IMPLEMENTATION CHECKLIST

## Phase 1: Core Infrastructure (Days 1-2)

```
□ Create stella-alpha directory structure
□ Copy V4 files as starting point
□ Create data_merger.py with safe merge logic
□ Implement validate_no_leakage() function
□ Write unit tests for merge logic
□ Test merge with sample H4/D1 data
```

## Phase 2: Feature Engineering (Days 2-3)

```
□ Add D1 base feature handling
□ Implement D1 derived features (~40 features)
□ Implement cross-timeframe features (~20 features)
□ Update FeatureEngineering class
□ Test feature calculation on merged data
□ Verify no NaN/inf in new features
```

## Phase 3: Statistical Validation Framework (Days 3-4) - NEW

```
□ Create src/statistical_validation.py module
□ Implement StatisticalFeatureFilter class
□ Implement T-test and effect size calculations
□ Implement feature pre-filtering before RFE
□ Implement ValidatedFeatureImportance class
□ Implement fold stability testing (CV analysis)
□ Implement config comparison significance testing
□ Test statistical functions on sample data
□ Integrate pre-filter into pipeline
□ Add statistical reports to output
```

## Phase 4: Pipeline Integration (Days 4-5)

```
□ Update run_pure_ml_stella_alpha.py with D1 loading
□ Add --d1-input CLI argument
□ Update configuration system
□ Integrate merge step into pipeline
□ Test single config end-to-end
□ Verify checkpoint/resume works
□ Verify parallel processing works
```

## Phase 4: Loss Analysis System (Days 4-5) - NEW

```
□ Create trade_recorder.py module
□ Create trades_stella_alpha.db schema
□ Integrate trade recording into experiment loop
□ Create loss_analysis.py module
□ Implement feature comparison (wins vs losses)
□ Implement session analysis
□ Implement confidence analysis
□ Implement D1 alignment analysis
□ Create analyze_losses.py CLI script
□ Test loss analysis on sample data
```

## Phase 5: Filter Recommendations (Days 5-6) - NEW

```
□ Create filter_recommendations.py module
□ Implement FilterRule class
□ Implement FilterImpact evaluation
□ Implement candidate filter generation
□ Implement filter combination testing
□ Create recommend_filters.py CLI script
□ Test filter recommendations
□ Verify net P&L calculations
```

## Phase 6: Diagnostics (Day 6)

```
□ Update diagnose.py with D1 feature analysis
□ Add MTF confluence analysis
□ Add loss analysis summary to diagnostics
□ Add filter recommendations summary
□ Add V4 vs Stella Alpha comparison
□ Create compare_versions.py
```

## Phase 7: Full Testing (Day 7)

```
□ Run full config space (128 configs)
□ Verify trade recording works
□ Run loss analysis
□ Generate filter recommendations
□ Verify all artifacts created
□ Document findings
□ Create final README
```

---

# 30. SUCCESS METRICS

## 26.1 Quantitative Goals

```
METRIC                          V4 BASELINE    STELLA TARGET   STRETCH
─────────────────────────────────────────────────────────────────────────
Pass Rate                       39.6%          50%+            60%+
GOLD Configs                    1              3+              5+
Best EV (pips)                  +4.17          +8.0+           +15.0+
Best Precision                  66.9%          70%+            75%+

RUNNER TARGETS (NEW - HIGH R:R):
─────────────────────────────────────────────────────────────────────────
TP >= 80 configs passing        0              3+              5+
TP >= 100 configs passing       0              1+              3+
Best R:R ratio passing          0.6:1          2:1+            3:1+
  (TP/SL with >45% precision)

D1/MTF IMPACT:
─────────────────────────────────────────────────────────────────────────
D1 Features in Top 20           N/A            3+              5+
MTF Features in Top 20          N/A            2+              3+

LOSS ANALYSIS TARGETS:
─────────────────────────────────────────────────────────────────────────
Trades Recorded                 N/A            10,000+         ALL
Loss Patterns Identified        N/A            5+              10+
Filters with >10% improvement   N/A            3+              5+
Best Filter Net Improvement     N/A            +5,000 pips     +10,000 pips
Win Rate After Best Filter      66.9%          72%+            78%+
```

## 26.2 Loss Analysis Success Criteria

```
LOSS ANALYSIS IS SUCCESSFUL IF:
───────────────────────────────
□ At least 5 features show statistically significant differences (p<0.05)
□ Session analysis identifies at least 1 problematic session
□ D1 alignment shows measurable impact on win rate
□ MTF confluence shows higher win rate for high-confluence trades

FILTER RECOMMENDATIONS ARE SUCCESSFUL IF:
─────────────────────────────────────────
□ At least 3 filters show >1,000 pips net improvement
□ At least 1 filter has efficiency ratio > 3:1 (losses removed per win missed)
□ Combined filters show >15% P&L improvement
□ Recommended filters are implementable in live trading
```

## 26.3 Overall Stella Alpha Success Criteria

```
Stella Alpha IS SUCCESSFUL IF ANY OF:
────────────────────────────
□ Find config with TP > SL and precision > 55%
□ Find config with R:R >= 1.25 and EV > +4 pips
□ Identify filters that improve win rate from 67% to 75%+
□ Generate actionable recommendations to avoid 20%+ of losses
□ Net P&L improvement of >30% through loss filtering
```

---

# 31. APPENDICES

## Appendix A: Example Loss Analysis Output

```
================================================================================
  LOSS ANALYSIS REPORT
================================================================================

    Config: TP30_SL50_H36
    ─────────────────────────────────────────
    Total Trades:    10,268
    Wins:            6,869 (66.9%)
    Losses:          3,399 (33.1%)

    SIGNIFICANT FEATURES (p < 0.05):
    ────────────────────────────────────────────────────────────────
    Feature                        Wins Mean  Loss Mean     Effect
    ────────────────────────────────────────────────────────────────
    model_probability                  0.672      0.583     -0.45
    d1_trend_direction                 0.125      0.387     +0.52
    mtf_confluence_score               0.682      0.521     -0.38
    h4_rsi_value                      74.200     68.500     -0.31
    d1_rsi_value                      62.100     55.800     -0.28

    SESSION ANALYSIS:
    ──────────────────────────────────────────────────────────
    Asian           Win Rate:  58.2%  (1,245 trades) ⚠️ PROBLEMATIC
    London          Win Rate:  69.1%  (3,890 trades) ✓ OK
    NY              Win Rate:  68.5%  (3,420 trades) ✓ OK
    Overlap         Win Rate:  72.3%  (1,713 trades) ✓ OK

    D1 ALIGNMENT IMPACT:
    ──────────────────────────────────────────────────────────
    D1 SUPPORTS SHORT:  Win Rate:  74.2%  (4,521 trades)
    D1 OPPOSES SHORT:   Win Rate:  52.1%  (2,103 trades)

    KEY FINDINGS:
    ──────────────────────────────────────────────────────────
    • Top loss predictors: d1_trend_direction, model_probability, mtf_confluence_score
    • Problematic sessions: Asian
    • Optimal confidence threshold: 0.60
    • D1 alignment is CRITICAL: +22% win rate difference

================================================================================
```

## Appendix B: Example Filter Recommendations Output

```
================================================================================
  FILTER RECOMMENDATIONS
================================================================================

    #1 🟢 STRONG
    ─────────────────────────────────────────────────────
    Filter: Skip when D1 opposes short
    Rule:   d1_opposes_short == 0
    
    Impact:
    • Trades: 10,268 → 8,165 (-2,103)
    • Losses avoided: 1,007 (saves 50,350 pips)
    • Wins missed: 412 (costs 12,360 pips)
    • Net improvement: +37,990 pips (+105.2%)
    • Win rate: 66.9% → 74.2%
    • Efficiency: 2.4:1 (losses removed per win missed)
    
    Reasoning: Removes 1,007 losses for only 412 missed wins (2.4:1 ratio)

    #2 🟢 STRONG
    ─────────────────────────────────────────────────────
    Filter: Require confidence >= 0.60
    Rule:   model_probability >= 0.60
    
    Impact:
    • Trades: 10,268 → 7,845 (-2,423)
    • Losses avoided: 1,156 (saves 57,800 pips)
    • Wins missed: 523 (costs 15,690 pips)
    • Net improvement: +42,110 pips (+116.6%)
    • Win rate: 66.9% → 72.8%
    • Efficiency: 2.2:1

    #3 🟢 STRONG
    ─────────────────────────────────────────────────────
    Filter: Avoid Asian session
    Rule:   h4_is_asian_session == 0
    
    Impact:
    • Trades: 10,268 → 9,023 (-1,245)
    • Losses avoided: 520 (saves 26,000 pips)
    • Wins missed: 203 (costs 6,090 pips)
    • Net improvement: +19,910 pips (+55.1%)
    • Win rate: 66.9% → 69.8%
    • Efficiency: 2.6:1

================================================================================
```

## Appendix C: Quick Start Commands

```powershell
# 1. Setup
cd stella-alpha
pip install -r requirements.txt

# 2. Run pipeline
python run_pure_ml_stella_alpha.py -c config/pure_ml_stella_alpha_settings.yaml -w 6

# 3. Diagnose results
python diagnose.py --db artifacts/pure_ml_stella_alpha.db

# 4. Analyze losses (NEW)
python analyze_losses.py --trades artifacts/trades_stella_alpha.db

# 5. Get filter recommendations (NEW)
python recommend_filters.py --trades artifacts/trades_stella_alpha.db --tp 30 --sl 50

# 6. Compare with V4
python compare_versions.py --v4 ../version-4/artifacts/pure_ml.db --stella_alpha artifacts/pure_ml_stella_alpha.db
```

---

# END OF SPECIFICATION

```
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║  STELLA ALPHA SPECIFICATION COMPLETE                                     ║
║  WITH LOSS ANALYSIS & FILTER RECOMMENDATIONS                          ║
║                                                                       ║
║  Document Version: 3.0                                                ║
║  Total Sections: 27                                                   ║
║  Total Lines: ~3500                                                   ║
║                                                                       ║
║  KEY ADDITIONS:                                                       ║
║  • Trade-level recording for every win/loss                          ║
║  • Statistical analysis of losing trades                             ║
║  • Automatic filter recommendations                                   ║
║  • Net P&L improvement calculations                                   ║
║  • Filter combination testing                                         ║
║                                                                       ║
║  TO IMPLEMENT:                                                        ║
║  Provide this document and say:                                       ║
║  "Implement Stella Alpha based on this specification.                    ║
║   Start with Phase 1: Core Infrastructure."                           ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
```
