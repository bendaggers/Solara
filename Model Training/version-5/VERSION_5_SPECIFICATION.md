# VERSION 5: MULTI-TIMEFRAME PURE ML PIPELINE
## Comprehensive Development Prompt

---

# EXECUTIVE SUMMARY

You are tasked with creating **Version 5** of a Pure ML trading pipeline that introduces **Multi-Timeframe Analysis (MTF)** by combining H4 (4-hour) and D1 (Daily) timeframe data. This builds upon the existing Version 4 pipeline, which achieved marginal profitability with TP=30 SL=30 configurations but failed to find profitable high Risk:Reward setups.

The hypothesis is that **Daily timeframe context will enable the model to predict larger price moves**, allowing for better Risk:Reward ratios (TP >= SL) while maintaining high precision.

---

# TABLE OF CONTENTS

1. [Background & Context](#1-background--context)
2. [Problem Statement](#2-problem-statement)
3. [Version 5 Objectives](#3-version-5-objectives)
4. [Data Architecture](#4-data-architecture)
5. [Critical: Data Leakage Prevention](#5-critical-data-leakage-prevention)
6. [Feature Engineering Specifications](#6-feature-engineering-specifications)
7. [Pipeline Modifications](#7-pipeline-modifications)
8. [Configuration Space](#8-configuration-space)
9. [Acceptance Criteria](#9-acceptance-criteria)
10. [File Structure](#10-file-structure)
11. [Implementation Checklist](#11-implementation-checklist)
12. [Testing Requirements](#12-testing-requirements)
13. [Success Metrics](#13-success-metrics)

---

# 1. BACKGROUND & CONTEXT

## 1.1 Project History

| Version | Description | Outcome |
|---------|-------------|---------|
| v1-v2 | Initial explorations | Learning phase |
| v3 | Signal Filter approach (BB touch → ML filter) | Moderate success |
| v4 | Pure ML approach (ML predicts everything) | 214 features, TP=30 works, high R:R fails |
| v5 | Multi-Timeframe Pure ML (THIS VERSION) | Add D1 context to enable high R:R |

## 1.2 Version 4 Results Summary

```
Best Configs Found (V4):
─────────────────────────
TP=30 SL=30 H=36: EV=+4.17, Precision=57.0%, Edge=+7.0%
TP=30 SL=50 H=36: EV=+3.55, Precision=66.9%, Edge=+4.4% (GOLD)

Key Finding:
- ML reliably predicts 30-pip moves
- ML CANNOT predict 50+ pip moves with H4 data alone
- All high R:R configs (TP >= 50) failed with <10% precision

Root Cause Analysis:
- H4 timeframe lacks context for larger moves
- Daily trend/structure not visible in H4 features
- Need higher timeframe confirmation for larger targets
```

## 1.3 Trading Strategy

```
STRATEGY: SHORT positions on EUR/USD H4 timeframe

ENTRY LOGIC:
- Price touches/exceeds Bollinger Band upper band
- ML model predicts high probability of downward move
- D1 timeframe confirms bearish context (NEW in V5)

EXIT LOGIC:
- Take Profit: Fixed pips below entry
- Stop Loss: Fixed pips above entry
- Max Holding Period: N bars before forced exit

DIRECTION: SHORT only (selling at upper BB)
```

## 1.4 Data Sources

```
PRIMARY DATA (H4):
- Source: MetaTrader 5 EA export
- File: EURUSD_H4_features.csv
- Timeframe: H4 (4-hour candles)
- History: ~25 years (2000-2025)
- Rows: ~41,000 H4 candles
- Features: 22 base features from EA

SECONDARY DATA (D1) - NEW:
- Source: MetaTrader 5 EA export (new)
- File: EURUSD_D1_features.csv
- Timeframe: D1 (Daily candles)
- History: Same period as H4
- Rows: ~6,500 daily candles
- Features: Similar structure to H4
```

---

# 2. PROBLEM STATEMENT

## 2.1 Core Problem

```
CURRENT STATE (V4):
- Model predicts 30-pip moves accurately (57-67% precision)
- Model FAILS on 50+ pip moves (<10% precision)
- Best R:R achievable: 1:1 (TP=30, SL=30)
- Cannot achieve favorable R:R (TP > SL)

DESIRED STATE (V5):
- Model predicts 50-80 pip moves accurately (55%+ precision)
- Achieve favorable R:R (TP=50, SL=30 or better)
- Maintain stability across folds (CV < 15%)
- Find GOLD configurations with high R:R
```

## 2.2 Hypothesis

```
HYPOTHESIS:
Adding Daily timeframe context will enable the model to:
1. Identify when H4 signals align with D1 trend exhaustion
2. Predict larger moves when D1 confirms reversal setup
3. Filter out H4 signals that go against D1 trend
4. Achieve higher R:R by trading only high-confluence setups

RATIONALE:
- D1 upper BB touch + H4 upper BB touch = STRONG reversal signal
- D1 RSI overbought + H4 RSI overbought = CONFLUENCE
- D1 bearish divergence visible = Larger move likely
- H4 signal against D1 trend = Lower probability, avoid
```

---

# 3. VERSION 5 OBJECTIVES

## 3.1 Primary Objectives

| # | Objective | Success Criteria |
|---|-----------|------------------|
| 1 | Integrate D1 data without leakage | Zero future data used |
| 2 | Engineer D1 + cross-TF features | 60+ new features |
| 3 | Find high R:R configs | TP >= SL with 55%+ precision |
| 4 | Improve best EV | > +5 pips per trade |
| 5 | Maintain stability | Precision CV < 15% |

## 3.2 Secondary Objectives

| # | Objective | Success Criteria |
|---|-----------|------------------|
| 6 | Identify which D1 features matter | Feature importance analysis |
| 7 | Compare V4 vs V5 performance | Side-by-side metrics |
| 8 | Maintain checkpoint/resume capability | Same as V4 |
| 9 | Parallel processing support | Same as V4 |

## 3.3 Non-Objectives (Out of Scope)

```
NOT IN SCOPE FOR V5:
- Trailing stop implementation (future version)
- Multiple take profit levels (future version)
- Other timeframes (H1, W1) (future version)
- Other currency pairs (future version)
- LONG positions (keep SHORT only)
```

---

# 4. DATA ARCHITECTURE

## 4.1 H4 Data Schema (Existing)

```
EURUSD_H4_features.csv
──────────────────────

Columns (22 base features):
├── timestamp (datetime)
├── open, high, low, close, volume (OHLCV)
├── lower_band, middle_band, upper_band (Bollinger Bands)
├── bb_touch_strength (high / upper_band ratio)
├── bb_position (0-1, where price is within BB)
├── bb_width_pct (BB width as % of price)
├── rsi_value (14-period RSI)
├── volume_ratio (volume / avg volume)
├── candle_rejection (upper wick ratio)
├── candle_body_pct (body size ratio)
├── atr_pct (ATR as % of price)
├── trend_strength (momentum indicator)
├── prev_candle_body_pct
├── prev_volume_ratio
├── gap_from_prev_close
├── price_momentum
├── previous_touches (count of recent BB touches)
├── time_since_last_touch (bars since last touch)
└── resistance_distance_pct

Sample Row:
2024-01-15 08:00:00,1.0850,1.0890,1.0840,1.0875,1250,1.0820,1.0855,1.0890,1.02,0.85,0.65,72.5,1.3,0.4,0.6,0.35,1.2,0.5,1.1,0.02,2,5,0.15
```

## 4.2 D1 Data Schema (NEW)

```
EURUSD_D1_features.csv
──────────────────────

Columns (MUST MATCH H4 structure with d1_ prefix):
├── timestamp (datetime, daily close time)
├── open, high, low, close, volume (OHLCV)
├── lower_band, middle_band, upper_band (D1 Bollinger Bands)
├── bb_touch_strength (D1 high / D1 upper_band)
├── bb_position (D1 position within D1 BB)
├── bb_width_pct (D1 BB width)
├── rsi_value (D1 RSI)
├── volume_ratio (D1 volume ratio)
├── candle_rejection (D1 upper wick ratio)
├── candle_body_pct (D1 body size)
├── atr_pct (D1 ATR %)
├── trend_strength (D1 trend)
├── prev_candle_body_pct (D1 previous candle)
├── prev_volume_ratio (D1 previous volume)
├── gap_from_prev_close (D1 gap)
├── price_momentum (D1 momentum)
├── previous_touches (D1 BB touches)
├── time_since_last_touch (D1 bars since touch)
└── resistance_distance_pct (D1 resistance)

Sample Row:
2024-01-15 00:00:00,1.0820,1.0900,1.0810,1.0878,45000,1.0750,1.0825,1.0900,1.01,0.78,0.55,68.5,1.1,0.35,0.55,0.42,0.8,0.45,0.9,0.015,1,3,0.12
```

## 4.3 Merged Data Schema

```
MERGED H4 + D1 Data
───────────────────

Each H4 row contains:
├── [All H4 columns as-is]
├── [All D1 columns with d1_ prefix]
└── [Cross-timeframe derived features]

CRITICAL MERGE RULE:
For H4 candle at time T, use D1 candle from PREVIOUS COMPLETED day

Example:
┌────────────────────┬─────────────────────┬─────────────────────┐
│ H4 Timestamp       │ Uses D1 From        │ Reason              │
├────────────────────┼─────────────────────┼─────────────────────┤
│ 2024-01-15 04:00   │ 2024-01-14          │ Jan 15 D1 not done  │
│ 2024-01-15 08:00   │ 2024-01-14          │ Jan 15 D1 not done  │
│ 2024-01-15 12:00   │ 2024-01-14          │ Jan 15 D1 not done  │
│ 2024-01-15 16:00   │ 2024-01-14          │ Jan 15 D1 not done  │
│ 2024-01-15 20:00   │ 2024-01-14          │ Jan 15 D1 not done  │
│ 2024-01-16 00:00   │ 2024-01-15          │ Jan 15 D1 NOW done  │
│ 2024-01-16 04:00   │ 2024-01-15          │ Jan 16 D1 not done  │
└────────────────────┴─────────────────────┴─────────────────────┘
```

---

# 5. CRITICAL: DATA LEAKAGE PREVENTION

## 5.1 The Problem

```
DATA LEAKAGE SCENARIO:
──────────────────────

WRONG APPROACH (causes leakage):
At H4 2024-01-15 08:00, using D1 2024-01-15 values

WHY IT'S WRONG:
- D1 2024-01-15 candle closes at 2024-01-16 00:00
- At 08:00, the D1 close/RSI/BB are NOT YET KNOWN
- Using them = using FUTURE information
- Model will backtest perfectly, FAIL in live trading

CORRECT APPROACH (no leakage):
At H4 2024-01-15 08:00, using D1 2024-01-14 values
- D1 2024-01-14 closed at 2024-01-15 00:00
- This data IS available at 08:00
- No future information used
```

## 5.2 Merge Logic Implementation

```python
def merge_h4_with_d1_safe(df_h4: pd.DataFrame, df_d1: pd.DataFrame) -> pd.DataFrame:
    """
    Merge D1 data into H4 data WITHOUT data leakage.
    
    CRITICAL RULE: 
    For each H4 candle, use the PREVIOUS COMPLETED D1 candle only.
    
    Args:
        df_h4: H4 dataframe with 'timestamp' column
        df_d1: D1 dataframe with 'timestamp' column
        
    Returns:
        Merged dataframe with D1 features prefixed with 'd1_'
    """
    df_h4 = df_h4.copy()
    df_d1 = df_d1.copy()
    
    # Parse timestamps
    df_h4['timestamp'] = pd.to_datetime(df_h4['timestamp'])
    df_d1['timestamp'] = pd.to_datetime(df_d1['timestamp'])
    
    # Get the DATE portion of H4 timestamp
    df_h4['_h4_date'] = df_h4['timestamp'].dt.normalize()
    
    # D1 data becomes available the NEXT day after it closes
    # So shift the "available from" date by +1 day
    df_d1['_available_from'] = df_d1['timestamp'].dt.normalize() + pd.Timedelta(days=1)
    
    # Rename D1 columns with 'd1_' prefix (except timestamp and helper cols)
    d1_cols_to_rename = [c for c in df_d1.columns if c not in ['timestamp', '_available_from']]
    df_d1 = df_d1.rename(columns={c: f'd1_{c}' for c in d1_cols_to_rename})
    
    # Sort both dataframes
    df_h4 = df_h4.sort_values('timestamp').reset_index(drop=True)
    df_d1 = df_d1.sort_values('_available_from').reset_index(drop=True)
    
    # Merge using merge_asof: for each H4 row, find the most recent D1 
    # where _available_from <= _h4_date
    df_merged = pd.merge_asof(
        df_h4,
        df_d1.drop(columns=['timestamp']),
        left_on='_h4_date',
        right_on='_available_from',
        direction='backward'
    )
    
    # Clean up helper columns
    df_merged = df_merged.drop(columns=['_h4_date', '_available_from'])
    
    return df_merged
```

## 5.3 Validation Checks

```python
def validate_no_leakage(df_merged: pd.DataFrame) -> bool:
    """
    Validate that D1 data has no leakage.
    
    For every row, the d1_timestamp should be from a PREVIOUS day.
    """
    df = df_merged.copy()
    
    h4_date = pd.to_datetime(df['timestamp']).dt.date
    d1_date = pd.to_datetime(df['d1_timestamp']).dt.date
    
    # D1 date must be STRICTLY LESS than H4 date
    # (or equal only if H4 is at 00:00:00, the first candle of the day)
    violations = df[d1_date >= h4_date]
    
    if len(violations) > 0:
        print(f"DATA LEAKAGE DETECTED: {len(violations)} rows")
        print(violations[['timestamp', 'd1_timestamp']].head(10))
        return False
    
    print("✓ No data leakage detected")
    return True
```

---

# 6. FEATURE ENGINEERING SPECIFICATIONS

## 6.1 D1 Base Features (from EA export)

```
D1 features to be prefixed with 'd1_' after merge:

PRICE DATA:
- d1_open, d1_high, d1_low, d1_close, d1_volume

BOLLINGER BANDS:
- d1_lower_band, d1_middle_band, d1_upper_band
- d1_bb_touch_strength
- d1_bb_position
- d1_bb_width_pct

INDICATORS:
- d1_rsi_value
- d1_volume_ratio
- d1_atr_pct
- d1_trend_strength

CANDLE PATTERNS:
- d1_candle_rejection
- d1_candle_body_pct
- d1_prev_candle_body_pct
- d1_prev_volume_ratio

OTHER:
- d1_gap_from_prev_close
- d1_price_momentum
- d1_previous_touches
- d1_time_since_last_touch
- d1_resistance_distance_pct
```

## 6.2 D1 Derived Features (calculated in Python)

```python
D1 DERIVED FEATURES (calculate from D1 base):
─────────────────────────────────────────────

# D1 BINARY FLAGS
'd1_touched_upper_bb'      # D1 high >= D1 upper_band
'd1_rsi_overbought'        # D1 RSI > 70
'd1_rsi_extreme'           # D1 RSI > 80
'd1_bearish_candle'        # D1 close < D1 open
'd1_strong_bearish'        # D1 bearish with large body
'd1_bb_very_high'          # D1 bb_position > 0.95

# D1 MOMENTUM (calculated over multiple D1 bars)
'd1_rsi_slope_3'           # D1 RSI change over 3 days
'd1_rsi_slope_5'           # D1 RSI change over 5 days
'd1_price_roc_3'           # D1 price rate of change 3 days
'd1_price_roc_5'           # D1 price rate of change 5 days
'd1_price_roc_10'          # D1 price rate of change 10 days

# D1 MEAN REVERSION
'd1_dist_from_ma10'        # D1 close distance from D1 MA10
'd1_dist_from_ma20'        # D1 close distance from D1 MA20
'd1_overextension'         # How far D1 is above D1 MA

# D1 VOLATILITY
'd1_atr_percentile'        # D1 ATR percentile rank (0-1)
'd1_bb_squeeze'            # D1 BB width < 20th percentile
'd1_volatility_regime'     # Low/Medium/High classification

# D1 REGIME
'd1_adx'                   # D1 trend strength (ADX)
'd1_is_trending'           # D1 ADX > 25
'd1_is_ranging'            # D1 ADX < 20
'd1_trend_direction'       # +1 bullish, -1 bearish, 0 neutral

# D1 PATTERNS
'd1_consecutive_bullish'   # Count of consecutive D1 bullish candles
'd1_consecutive_bearish'   # Count of consecutive D1 bearish candles
'd1_near_d1_high'          # Close to 20-day high
'd1_bearish_divergence'    # Price up but RSI down (D1 level)

# D1 Z-SCORES
'd1_price_zscore'          # D1 price z-score (20-day)
'd1_rsi_zscore'            # D1 RSI z-score
```

## 6.3 Cross-Timeframe Features (H4 vs D1)

```python
CROSS-TIMEFRAME FEATURES (most important for V5):
─────────────────────────────────────────────────

# ALIGNMENT FEATURES (Do H4 and D1 agree?)
'mtf_rsi_aligned'          # Both H4 and D1 RSI overbought
'mtf_bb_aligned'           # Both H4 and D1 at upper BB
'mtf_trend_aligned'        # Both H4 and D1 showing same trend
'mtf_bearish_aligned'      # Both H4 and D1 candles bearish

# CONFLUENCE SCORE (0-1, higher = more alignment)
'mtf_confluence_score'     # Weighted combination of alignments:
                           # 0.25 * mtf_rsi_aligned +
                           # 0.25 * mtf_bb_aligned +
                           # 0.25 * mtf_trend_aligned +
                           # 0.25 * mtf_bearish_aligned

# DIVERGENCE FEATURES (H4 vs D1 disagreement)
'mtf_rsi_divergence'       # H4 RSI > 70 but D1 RSI < 50 (or vice versa)
'mtf_trend_divergence'     # H4 bullish but D1 bearish (or vice versa)

# RELATIVE POSITION
'h4_position_in_d1_range'  # Where H4 close is within D1 high-low range
                           # = (h4_close - d1_low) / (d1_high - d1_low)

'h4_vs_d1_bb_position'     # Difference: h4_bb_position - d1_bb_position
                           # Positive = H4 more overbought than D1

# MOMENTUM COMPARISON
'h4_vs_d1_rsi'             # h4_rsi - d1_rsi
'h4_vs_d1_trend'           # h4_trend_strength - d1_trend_strength

# VOLATILITY COMPARISON
'h4_vs_d1_atr'             # h4_atr_pct / d1_atr_pct
                           # >1 = H4 more volatile than D1

# D1 CONTEXT FLAGS
'd1_supports_short'        # D1 conditions favor SHORT:
                           # d1_rsi > 65 AND d1_bb_position > 0.7

'd1_opposes_short'         # D1 conditions oppose SHORT:
                           # d1_rsi < 40 AND d1_trend_direction > 0.5
```

## 6.4 Feature Count Summary

```
TOTAL EXPECTED FEATURES:
────────────────────────

H4 Base (from EA):              22
H4 Derived (from V4):          ~190
D1 Base (from EA):              22
D1 Derived (new):              ~40
Cross-Timeframe (new):         ~20
────────────────────────────────────
TOTAL:                        ~294

After RFE Selection:           15-25
```

---

# 7. PIPELINE MODIFICATIONS

## 7.1 Files to Modify (from V4)

```
version-5/
├── run_pure_ml.py              # MODIFY: Add D1 loading and merging
├── config/
│   └── pure_ml_settings.yaml   # MODIFY: Add D1 file path, new config space
├── src/
│   ├── __init__.py             # KEEP AS-IS
│   ├── feature_engineering.py  # MODIFY: Add D1 and cross-TF features
│   ├── features.py             # KEEP AS-IS (RFE logic)
│   ├── pure_ml_labels.py       # KEEP AS-IS
│   ├── training.py             # KEEP AS-IS
│   ├── evaluation.py           # KEEP AS-IS
│   ├── experiment.py           # KEEP AS-IS
│   ├── checkpoint_db.py        # KEEP AS-IS
│   └── data_merger.py          # NEW: D1 merge logic with leakage prevention
├── diagnose.py                 # MODIFY: Add D1 feature analysis
└── requirements.txt            # KEEP AS-IS
```

## 7.2 Configuration Changes

```yaml
# config/pure_ml_settings.yaml - V5 ADDITIONS

# DATA SOURCES
data:
  h4_file: "../version-3/data/EURUSD_H4_features.csv"
  d1_file: "../version-3/data/EURUSD_D1_features.csv"  # NEW
  
  # Timezone for proper day boundary handling
  timezone: "UTC"  # Adjust if broker uses different timezone

# MULTI-TIMEFRAME SETTINGS
multi_timeframe:
  enabled: true
  
  # D1 merge settings
  d1_lookback_shift: 1  # Use previous completed D1 (no leakage)
  
  # Feature computation
  compute_d1_derived: true
  compute_cross_tf: true

# EXPANDED CONFIG SPACE (focus on high R:R)
config_space:
  tp_pips:
    min: 30
    max: 100
    step: 10
  
  sl_pips:
    min: 20
    max: 50
    step: 10
  
  max_holding_bars:
    min: 12
    max: 48
    step: 6

# Target configs we want to find
target_configs:
  # These are the "holy grail" configs we hope D1 enables
  - { tp: 50, sl: 30 }  # 1.67:1 R:R (favorable)
  - { tp: 60, sl: 40 }  # 1.5:1 R:R (favorable)
  - { tp: 50, sl: 40 }  # 1.25:1 R:R (slightly favorable)
```

## 7.3 Pipeline Flow (V5)

```
V5 PIPELINE FLOW:
─────────────────

┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: LOAD DATA                                               │
├─────────────────────────────────────────────────────────────────┤
│ • Load H4 CSV (EURUSD_H4_features.csv)                         │
│ • Load D1 CSV (EURUSD_D1_features.csv)                         │
│ • Validate both files have required columns                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: MERGE D1 INTO H4 (NO LEAKAGE)                          │
├─────────────────────────────────────────────────────────────────┤
│ • For each H4 row, find PREVIOUS COMPLETED D1                  │
│ • Merge D1 columns with 'd1_' prefix                           │
│ • Validate no data leakage                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: FEATURE ENGINEERING                                     │
├─────────────────────────────────────────────────────────────────┤
│ • Calculate H4 derived features (same as V4)                   │
│ • Calculate D1 derived features (NEW)                          │
│ • Calculate Cross-TF features (NEW)                            │
│ • Total: ~294 features                                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: PRE-COMPUTE LABELS                                      │
├─────────────────────────────────────────────────────────────────┤
│ • Same as V4: label based on H4 price movement                 │
│ • TP/SL/MaxHold configurations from config_space               │
│ • Cache labels for all configs                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: WALK-FORWARD EXPERIMENTS                                │
├─────────────────────────────────────────────────────────────────┤
│ • Same as V4: 5-fold time-series CV                            │
│ • RFE feature selection (now from ~294 features)               │
│ • LightGBM training                                             │
│ • Threshold optimization                                        │
│ • Checkpoint/resume support                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: EVALUATION & DIAGNOSIS                                  │
├─────────────────────────────────────────────────────────────────┤
│ • Same metrics as V4                                            │
│ • NEW: Analyze which D1/cross-TF features selected             │
│ • NEW: Compare V4 vs V5 results                                │
│ • Find GOLD configs (especially high R:R)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

# 8. CONFIGURATION SPACE

## 8.1 Expanded Config Space for V5

```yaml
# Focus on finding high R:R configs

config_space:
  tp_pips:
    min: 30
    max: 100
    step: 10
    # Values: 30, 40, 50, 60, 70, 80, 90, 100
    
  sl_pips:
    min: 20
    max: 50
    step: 10
    # Values: 20, 30, 40, 50
    
  max_holding_bars:
    min: 12
    max: 48
    step: 12
    # Values: 12, 24, 36, 48

# Total combinations: 8 × 4 × 4 = 128 configs
```

## 8.2 Target R:R Ratios

```
CONFIG PRIORITY (what we hope to find):
───────────────────────────────────────

TIER 1 - EXCELLENT R:R (Holy Grail):
• TP=60 SL=30 → Risk $30 to make $60 (2:1)
• TP=50 SL=30 → Risk $30 to make $50 (1.67:1)
• TP=80 SL=40 → Risk $40 to make $80 (2:1)

TIER 2 - GOOD R:R:
• TP=50 SL=40 → Risk $40 to make $50 (1.25:1)
• TP=60 SL=50 → Risk $50 to make $60 (1.2:1)
• TP=40 SL=30 → Risk $30 to make $40 (1.33:1)

TIER 3 - FAIR R:R:
• TP=40 SL=40 → Risk $40 to make $40 (1:1)
• TP=30 SL=30 → Risk $30 to make $30 (1:1)

TIER 4 - POOR R:R (we have these already):
• TP=30 SL=40 → Risk $40 to make $30 (0.75:1)
• TP=30 SL=50 → Risk $50 to make $30 (0.6:1)
```

---

# 9. ACCEPTANCE CRITERIA

## 9.1 Model Acceptance Criteria

```python
# Same as V4, applied per config

acceptance_criteria:
  # Minimum precision across all folds
  min_precision: 0.55  # 55%
  
  # Minimum expected value (must be positive)
  min_ev: 0.0
  
  # Maximum precision coefficient of variation (stability)
  max_precision_cv: 0.20  # 20%
  
  # Minimum total trades across all folds
  min_total_trades: 100
```

## 9.2 V5 Success Criteria

```
V5 IS SUCCESSFUL IF:
────────────────────

MUST HAVE (at least one):
□ Find config with TP > SL and precision > 55%
□ Find config with R:R >= 1.25:1 and EV > +3 pips
□ Improve best EV from +4.17 to +5.0 or higher

NICE TO HAVE:
□ Find GOLD config with high R:R
□ D1/cross-TF features appear in top selected features
□ Pass rate improves from 39.6% to 50%+

IF FAILS:
□ Document which D1 features were tested
□ Analyze why high R:R still doesn't work
□ Conclude whether D1 context helps at all
```

---

# 10. FILE STRUCTURE

## 10.1 Version 5 Directory Structure

```
version-5/
├── run_pure_ml.py                 # Main entry point (modified)
├── requirements.txt               # Dependencies
├── README.md                      # Documentation
│
├── config/
│   └── pure_ml_settings.yaml      # Configuration (modified)
│
├── src/
│   ├── __init__.py
│   ├── data_merger.py             # NEW: D1 merge with leakage prevention
│   ├── feature_engineering.py     # Modified: Add D1 + cross-TF features
│   ├── features.py                # RFE selection (unchanged)
│   ├── pure_ml_labels.py          # Labeling logic (unchanged)
│   ├── training.py                # Model training (unchanged)
│   ├── evaluation.py              # Evaluation metrics (unchanged)
│   ├── experiment.py              # Experiment runner (unchanged)
│   └── checkpoint_db.py           # Checkpoint/resume (unchanged)
│
├── diagnose.py                    # Diagnostic analysis (modified)
│
└── artifacts/                     # Output directory
    ├── pure_ml_v5.db              # Checkpoint database
    ├── pure_ml_model.pkl          # Best model
    ├── features.json              # Selected features
    ├── trading_config.json        # Best config
    └── metrics.json               # Validation metrics
```

## 10.2 New File: data_merger.py

```python
"""
Data Merger Module - Version 5

Handles merging of D1 (Daily) data into H4 (4-hour) data
with strict data leakage prevention.

CRITICAL: For each H4 candle, only use D1 data from the 
PREVIOUS COMPLETED daily candle to avoid data leakage.
"""

# Full implementation as specified in Section 5.2
```

---

# 11. IMPLEMENTATION CHECKLIST

## 11.1 Phase 1: Data Infrastructure

```
□ Create data_merger.py with safe merge logic
□ Implement validate_no_leakage() function
□ Update config to include d1_file path
□ Modify run_pure_ml.py to load both H4 and D1
□ Add merge step after data loading
□ Test merge on sample data
□ Verify no leakage with validation function
```

## 11.2 Phase 2: Feature Engineering

```
□ Add D1 base features (from EA export)
□ Add D1 derived features (momentum, regime, etc.)
□ Add cross-timeframe features (alignment, confluence)
□ Update FeatureEngineering class with new methods
□ Test feature calculation on merged data
□ Verify no NaN/inf values in new features
□ Document total feature count
```

## 11.3 Phase 3: Pipeline Integration

```
□ Update run_pure_ml.py with full V5 pipeline
□ Update config with expanded config_space
□ Test checkpoint/resume with V5 data
□ Test parallel processing with V5 data
□ Run initial experiment (small config space)
□ Verify results are reasonable
```

## 11.4 Phase 4: Full Experiment

```
□ Run full config space (128 configs)
□ Generate diagnostic report
□ Analyze which D1/cross-TF features selected
□ Compare V4 vs V5 results
□ Document findings
□ Identify best configs
```

## 11.5 Phase 5: Documentation

```
□ Update README with V5 changes
□ Document D1 data requirements
□ Document merge logic and leakage prevention
□ Create comparison report (V4 vs V5)
□ Document recommended configs
```

---

# 12. TESTING REQUIREMENTS

## 12.1 Unit Tests

```python
# Test 1: Merge Logic
def test_merge_no_leakage():
    """Verify D1 data comes from previous day only."""
    # Create sample H4 and D1 data
    # Merge
    # Assert all d1_timestamp < h4_timestamp.date()

# Test 2: Feature Calculation
def test_d1_features_no_nan():
    """Verify D1 derived features have no NaN."""
    # Calculate features
    # Assert no NaN in new columns

# Test 3: Cross-TF Features
def test_cross_tf_features():
    """Verify cross-TF features calculated correctly."""
    # Known input -> expected output
    # Assert values match
```

## 12.2 Integration Tests

```python
# Test 4: Full Pipeline
def test_full_pipeline_single_config():
    """Run single config end-to-end."""
    # Load data
    # Merge
    # Feature engineering
    # Train
    # Evaluate
    # Assert reasonable results

# Test 5: Checkpoint Resume
def test_checkpoint_resume():
    """Verify checkpoint/resume works with V5 data."""
    # Run partial
    # Resume
    # Assert continuation correct
```

## 12.3 Validation Checks

```python
# During pipeline run, assert:
assert validate_no_leakage(df_merged), "DATA LEAKAGE DETECTED"
assert len(feature_columns) > 250, "Missing features"
assert df_merged['d1_rsi_value'].notna().all(), "D1 features have NaN"
```

---

# 13. SUCCESS METRICS

## 13.1 Quantitative Metrics

```
METRIC                      V4 BASELINE    V5 TARGET
──────────────────────────────────────────────────────
Pass Rate                   39.6%          50%+
Best EV (pips)              +4.17          +5.0+
Best Precision              66.9%          68%+
GOLD Configs Found          1              2+
High R:R Configs Passing    0              3+
  (TP > SL with 55%+ prec)
```

## 13.2 Qualitative Metrics

```
□ D1 features appear in top 20 selected features
□ Cross-TF confluence features show importance
□ Model can predict 50+ pip moves (not just 30)
□ Results are stable across folds (CV < 15%)
```

## 13.3 Comparison Report

```
FINAL DELIVERABLE: V4 vs V5 Comparison

| Metric              | V4 (H4 only) | V5 (H4 + D1) | Change |
|---------------------|--------------|--------------|--------|
| Total Features      | 214          | ~294         | +37%   |
| Pass Rate           | 39.6%        | ???          | ???    |
| Best EV             | +4.17        | ???          | ???    |
| Best Precision      | 66.9%        | ???          | ???    |
| GOLD Configs        | 1            | ???          | ???    |
| High R:R Passing    | 0            | ???          | ???    |
| Top D1 Feature      | N/A          | ???          | NEW    |
| Top Cross-TF Feature| N/A          | ???          | NEW    |
```

---

# APPENDIX A: EA EXPORT REQUIREMENTS

## A.1 D1 Data Export from MT5

```mql5
// The EA should export D1 data with same structure as H4
// File: EURUSD_D1_features.csv

// Required columns (same as H4 but calculated on D1):
// timestamp, open, high, low, close, volume
// lower_band, middle_band, upper_band (D1 BB)
// bb_touch_strength, bb_position, bb_width_pct
// rsi_value (D1 RSI 14)
// volume_ratio, candle_rejection, candle_body_pct
// atr_pct (D1 ATR)
// trend_strength
// prev_candle_body_pct, prev_volume_ratio
// gap_from_prev_close, price_momentum
// previous_touches, time_since_last_touch
// resistance_distance_pct
```

---

# APPENDIX B: KNOWN RISKS

```
RISK 1: D1 Data Not Available
- Mitigation: Provide clear EA export instructions
- Fallback: Calculate D1 from H4 (less accurate)

RISK 2: D1 Doesn't Help
- Mitigation: This is valid finding, document it
- Fallback: V4 remains best approach

RISK 3: Timezone Issues
- Mitigation: Clearly define broker timezone
- Validation: Check D1 timestamps match expected day boundaries

RISK 4: Increased Complexity
- Mitigation: Modular code, clear separation
- Testing: Comprehensive unit tests
```

---

# APPENDIX C: QUICK START COMMANDS

```powershell
# Setup
cd version-5
pip install -r requirements.txt

# Verify D1 data exists
dir ..\version-3\data\EURUSD_D1_features.csv

# Run pipeline
python run_pure_ml.py -c config/pure_ml_settings.yaml -w 6

# Diagnose results
python diagnose.py --db artifacts/pure_ml_v5.db

# Compare V4 vs V5
python compare_versions.py --v4 ..\version-4\artifacts\pure_ml.db --v5 artifacts\pure_ml_v5.db
```

---

# END OF VERSION 5 SPECIFICATION

```
Document Version: 1.0
Created: [Current Date]
Author: AI Assistant (Claude)
Status: Ready for Implementation

NEXT STEP: 
Provide this document to Claude and say:
"Implement Version 5 based on this specification."
```
