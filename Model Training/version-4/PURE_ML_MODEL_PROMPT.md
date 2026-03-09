# ═══════════════════════════════════════════════════════════════════════════════
# PURE ML SHORT-ONLY ENTRY MODEL - DEVELOPMENT PROMPT
# ═══════════════════════════════════════════════════════════════════════════════
# 
# Save this file and provide it to Claude when you're ready to build the Pure ML model.
# This prompt contains all context, requirements, and specifications needed.
#
# ═══════════════════════════════════════════════════════════════════════════════

## ROLE & EXPERTISE

Act as an expert quantitative trader with 20+ years of institutional trading experience 
combined with senior ML engineering expertise specializing in financial machine learning.
You have deep knowledge of:
- Market microstructure and price action
- Statistical modeling and time series analysis
- Machine learning for alpha generation
- Walk-forward validation and avoiding lookahead bias
- Production ML systems for live trading

---

## PROJECT CONTEXT

### What Already Exists

I have an existing SHORT-ONLY entry model that uses a **Signal Filter + ML** approach:
- Pre-filters candles by BB position >= 0.80 AND RSI >= 70
- ML model predicts if filtered signals will be profitable
- This model is working and deployed

### What We're Building Now

A **Pure ML** approach that:
- Does NOT use pre-defined signal filters (no BB/RSI rules)
- Evaluates EVERY candle as a potential SHORT entry
- Model LEARNS what conditions predict profitable shorts
- More data-driven, less human bias

### Why Both Models

| Model | Strength | Weakness |
|-------|----------|----------|
| Signal Filter + ML | Interpretable, based on trading theory | May miss good trades outside filter |
| Pure ML | No human bias, finds hidden patterns | Less interpretable, needs more data |

Having both allows:
- Ensemble predictions (both agree = higher confidence)
- Compare performance (which approach works better?)
- Redundancy (if one fails, other still works)

---

## DATA SPECIFICATION

### Source Data

```yaml
instrument: EUR/USD
timeframe: 4H (4-hour candles)
history: 15 years (~32,850 candles)
format: Single CSV file
```

### Available Columns

```yaml
# Core OHLCV
- timestamp: ISO 8601 datetime
- open: float
- high: float  
- low: float
- close: float
- volume: float (tick volume)

# Pre-computed Technical Features (examples)
- bb_position: 0-1 scale (where price is within Bollinger Bands)
- bb_width: Bollinger Band width
- bb_width_slope_3: 3-bar slope of BB width
- rsi_value: 0-100 RSI
- rsi_slope_3: 3-bar slope of RSI
- rsi_velocity: Rate of change of RSI
- rsi_rolling_max: Rolling max RSI
- trend_strength: Trend strength indicator
- trend_slope_3: 3-bar trend slope
- trend_strength_lag1: Lagged trend strength
- trend_strength_lag2: Lagged trend strength
- volume_zscore: Normalized volume
- upper_wick_ratio: Upper wick as ratio of candle
- lower_wick_ratio: Lower wick as ratio of candle
- resistance_distance_pct: Distance to resistance level
- support_distance_pct: Distance to support level
- time_since_last_touch: Bars since last BB touch
- atr_14: 14-period ATR
- (additional features may be present)
```

### Data Characteristics

- NO missing values (pre-cleaned)
- NO lookahead bias in features (all use past data only)
- Covers multiple market regimes (2008 crisis, COVID, trending, ranging)
- ~32,850 total candles available

---

## CORE TRADING QUESTION

For EVERY candle, the model must answer:

> "If I enter a SHORT position at this candle's close, will the price reach 
> my Take Profit (TP) level BEFORE hitting my Stop Loss (SL) level, 
> within a maximum holding period of N bars?"

### Label Definition

```python
label = 1 (PROFITABLE SHORT):
    - Price drops by TP pips BEFORE rising by SL pips
    - Within max_holding_bars
    
label = 0 (UNPROFITABLE SHORT):
    - Price rises by SL pips first, OR
    - Neither TP nor SL hit within max_holding_bars
```

### Trade Parameters (To Be Optimized)

```yaml
tp_pips: [30, 40, 50, 60]      # Test range
sl_pips: [20, 30, 40]          # Test range  
max_holding_bars: [12, 18, 24] # Test range

# Or use ATR-based dynamic levels:
tp_multiplier: [1.0, 1.5, 2.0]  # TP = ATR × multiplier
sl_multiplier: [0.75, 1.0, 1.5] # SL = ATR × multiplier
```

---

## MODEL REQUIREMENTS

### Architecture

```yaml
model_type: Binary Classification
output: Probability of successful SHORT (0.0 to 1.0)
framework: Scikit-learn compatible (LightGBM preferred)
```

### Key Constraints

1. **NO Lookahead Bias**
   - Features must use only past data
   - Labels must be generated correctly (future price movement)
   - Walk-forward validation mandatory

2. **Handle Class Imbalance**
   - Most candles are NOT good shorts (~95% label=0)
   - Use: class_weight, SMOTE, or threshold optimization
   - Evaluate with: Precision, Recall, F1, AUC-PR (NOT accuracy)

3. **Regime Robustness**
   - Model must work across different market conditions
   - Validate on: trending up, trending down, ranging, volatile
   - Track performance stability (precision CV < 0.30)

4. **Production Ready**
   - Single model file (.pkl)
   - Clear feature list
   - Defined probability threshold
   - Fast inference (< 10ms per prediction)

---

## TRAINING PIPELINE SPECIFICATION

### Stage 1: Data Preprocessing

```python
Input: Raw CSV with OHLCV + pre-computed features
Output: Clean DataFrame ready for labeling

Steps:
1. Parse timestamps
2. Sort by time (ascending)
3. Validate no NaN in feature columns
4. Validate no lookahead bias
5. Identify feature columns (exclude OHLCV, timestamps, labels)
```

### Stage 2: Label Generation

```python
Input: Clean DataFrame, TP/SL/Hold parameters
Output: DataFrame with 'label' column

For EACH candle:
    entry_price = candle['close']
    tp_price = entry_price - (tp_pips * pip_value)  # SHORT = price goes DOWN
    sl_price = entry_price + (sl_pips * pip_value)  # SHORT = SL is UP
    
    Look forward up to max_holding_bars:
        if low <= tp_price:  # TP hit
            label = 1
            break
        if high >= sl_price:  # SL hit
            label = 0
            break
    else:
        label = 0  # Timeout
```

### Stage 3: Walk-Forward Validation

```yaml
method: Expanding or Rolling Window
n_folds: 5
train_ratio: 0.70
gap: 0 bars (or small gap to prevent leakage)

Example splits:
  Fold 1: Train [0-5000], Validate [5001-7000]
  Fold 2: Train [0-7000], Validate [7001-9000]
  Fold 3: Train [0-9000], Validate [9001-11000]
  ...
```

### Stage 4: Feature Selection (RFE)

```yaml
method: RFECV with cross-validation
estimator: LightGBM (fast)
min_features: 5
max_features: 20
scoring: average_precision
step: 1 (precise selection)

# Run ONCE on training data, apply to all folds
```

### Stage 5: Hyperparameter Optimization

```yaml
method: RandomizedSearchCV or Optuna
estimator: LightGBMClassifier
cv: TimeSeriesSplit (3 folds within training set)
n_iter: 50-100
scoring: average_precision

param_space:
  n_estimators: [100, 200, 300, 500]
  max_depth: [3, 4, 5, 6, 8]
  learning_rate: [0.01, 0.05, 0.1]
  num_leaves: [15, 31, 63]
  min_child_samples: [10, 20, 50, 100]
  subsample: [0.7, 0.8, 0.9, 1.0]
  colsample_bytree: [0.7, 0.8, 0.9, 1.0]
  class_weight: ['balanced', None]
```

### Stage 6: Probability Calibration

```yaml
method: CalibratedClassifierCV
calibration: 'isotonic' or 'sigmoid'
cv: 3-fold

# Ensures predicted probabilities are meaningful
# P=0.70 should mean ~70% actual success rate
```

### Stage 7: Threshold Optimization

```python
# Sweep thresholds to find optimal
for threshold in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
    predictions = (probabilities >= threshold).astype(int)
    
    precision = calculate_precision(y_true, predictions)
    recall = calculate_recall(y_true, predictions)
    n_trades = predictions.sum()
    
    # Calculate Expected Value
    win_rate = precision
    avg_win = tp_pips
    avg_loss = sl_pips
    ev = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    # Select threshold that maximizes EV with sufficient trades
    if n_trades >= min_trades and ev > best_ev:
        best_threshold = threshold
```

---

## EVALUATION METRICS

### Primary Metrics (Must Track)

| Metric | Target | Description |
|--------|--------|-------------|
| Precision | >= 0.55 | Win rate of predicted trades |
| Expected Value (EV) | > 0 | Average pips per trade |
| Profit Factor | >= 1.3 | Gross profit / Gross loss |
| Total Trades | >= 50 per fold | Statistical significance |
| Precision CV | < 0.30 | Stability across folds |

### Secondary Metrics (Diagnostic)

| Metric | Purpose |
|--------|---------|
| Recall | Coverage - are we missing good trades? |
| F1 Score | Balance of precision and recall |
| AUC-PR | Overall ranking ability |
| Sharpe Proxy | Risk-adjusted return estimate |
| Max Drawdown | Worst case scenario |

### Statistical Significance

```python
# t-test for EV > 0
t_statistic = ev_mean / (ev_std / sqrt(n_trades))
p_value = 1 - t.cdf(t_statistic, df=n_trades-1)

# Require p < 0.05 for deployment
```

---

## ACCEPTANCE CRITERIA

A model configuration is ACCEPTED for production only if:

```yaml
minimum_requirements:
  precision_mean: >= 0.55
  precision_cv: < 0.30          # Stable across folds
  ev_mean: > 0                  # Positive expectancy
  min_trades_per_fold: >= 30    # Statistical validity
  profit_factor: >= 1.2         # More wins than losses
  p_value: < 0.05               # Statistically significant
  
warnings_acceptable:
  ev_cv: < 0.50                 # Some EV variance OK
```

---

## OUTPUT ARTIFACTS

Upon successful training, produce:

```yaml
artifacts/
├── model.pkl                    # Trained model (joblib serialized)
├── features.csv                 # Selected feature list (ordered)
├── config.json                  # Trade parameters (TP, SL, Hold)
├── threshold.json               # Optimized probability threshold
├── hyperparameters.json         # Best model hyperparameters
├── metrics.json                 # Validation metrics per fold
├── calibrator.pkl               # Probability calibrator (if used)
└── training_report.json         # Full training summary
```

### Model File Contents

```python
# model.pkl should contain:
{
    'model': trained_lgbm_model,
    'features': ['feature1', 'feature2', ...],  # Ordered list
    'threshold': 0.55,
    'tp_pips': 40,
    'sl_pips': 30,
    'max_holding_bars': 18,
    'training_date': '2024-01-15',
    'metrics': {
        'precision': 0.58,
        'ev': 8.5,
        'profit_factor': 1.65
    }
}
```

---

## PRODUCTION INFERENCE

```python
def predict_short_signal(candle_features: dict) -> dict:
    """
    Pure ML prediction - no pre-filtering.
    
    Args:
        candle_features: Dict with all feature values
        
    Returns:
        {
            'should_trade': bool,
            'probability': float,
            'confidence': str,  # 'low', 'medium', 'high'
            'tp_pips': int,
            'sl_pips': int
        }
    """
    # Extract features in correct order
    X = [candle_features[f] for f in model['features']]
    
    # Get probability
    prob = model['model'].predict_proba([X])[0][1]
    
    # Apply threshold
    should_trade = prob >= model['threshold']
    
    # Confidence level
    if prob >= 0.70:
        confidence = 'high'
    elif prob >= 0.55:
        confidence = 'medium'
    else:
        confidence = 'low'
    
    return {
        'should_trade': should_trade,
        'probability': prob,
        'confidence': confidence,
        'tp_pips': model['tp_pips'],
        'sl_pips': model['sl_pips']
    }
```

---

## COMPARISON WITH SIGNAL FILTER MODEL

### Key Differences

| Aspect | Signal Filter Model | Pure ML Model |
|--------|---------------------|---------------|
| Pre-filter | BB >= 0.80, RSI >= 70 | None |
| Candles evaluated | ~5% of all candles | 100% of candles |
| What ML learns | "Is this signal good?" | "Is this candle a good SHORT?" |
| Feature importance | BB/RSI less important (already filtered) | BB/RSI may be top features |
| Trade frequency | Lower | Potentially higher |
| Interpretability | High | Lower |

### Ensemble Strategy (Future)

```python
def ensemble_predict(candle):
    # Signal Filter Model
    if candle['bb_position'] >= 0.80 and candle['rsi_value'] >= 70:
        signal_filter_prob = signal_model.predict_proba(candle)
    else:
        signal_filter_prob = 0
    
    # Pure ML Model
    pure_ml_prob = pure_ml_model.predict_proba(candle)
    
    # Ensemble logic
    if signal_filter_prob >= 0.50 and pure_ml_prob >= 0.50:
        return 'STRONG_SHORT'  # Both agree
    elif signal_filter_prob >= 0.50 or pure_ml_prob >= 0.60:
        return 'WEAK_SHORT'    # One model confident
    else:
        return 'NO_TRADE'
```

---

## DEVELOPMENT PHASES

### Phase 1: Baseline Model
- Use all features (no RFE)
- Fixed TP=40, SL=30, Hold=18
- Establish baseline metrics

### Phase 2: Feature Engineering
- Run RFE to identify top features
- Test feature combinations
- Analyze feature importance

### Phase 3: Hyperparameter Tuning
- Optimize LightGBM parameters
- Cross-validate thoroughly
- Check for overfitting

### Phase 4: Threshold Optimization
- Find optimal probability threshold
- Balance precision vs trade count
- Maximize Expected Value

### Phase 5: TP/SL Optimization
- Test different TP/SL combinations
- Consider ATR-based dynamic levels
- Find best risk:reward

### Phase 6: Final Validation
- Out-of-sample testing
- Regime analysis
- Statistical significance tests

### Phase 7: Production Preparation
- Export artifacts
- Document everything
- Create inference code

---

## CONSTRAINTS & WARNINGS

### Must NOT Do

```yaml
- NO random train/test splits (use time-based only)
- NO using future data in features
- NO optimizing on test data
- NO ignoring class imbalance
- NO deploying without statistical significance
- NO using accuracy as primary metric
```

### Watch Out For

```yaml
- Overfitting to recent data
- Regime-specific performance (works only in trending markets)
- Too few trades (statistical insignificance)
- Too many features (overfitting)
- Unstable probability estimates
```

---

## QUESTIONS TO ANSWER

After training, we need to answer:

1. **Does the Pure ML model find the same patterns as Signal Filter model?**
   - Are BB/RSI top features?
   - Or does it find completely different patterns?

2. **Which model performs better?**
   - Higher precision?
   - Higher EV?
   - More stable?

3. **Do they complement each other?**
   - Do they agree on the same trades?
   - Does ensemble improve performance?

4. **Is Pure ML worth the complexity?**
   - If similar performance, stick with interpretable Signal Filter
   - If significantly better, consider switching or ensembling

---

## DELIVERABLES CHECKLIST

When complete, provide:

- [ ] Trained model file (.pkl)
- [ ] Feature list (.csv)
- [ ] Configuration (.json)
- [ ] Validation metrics (.json)
- [ ] Training report (summary)
- [ ] Comparison with Signal Filter model
- [ ] Recommendation (deploy / don't deploy / needs more work)
- [ ] Production inference code
- [ ] Monitoring recommendations

---

## HOW TO USE THIS PROMPT

1. Start a new conversation with Claude
2. Upload this entire file as context
3. Upload your data file (CSV)
4. Say: "Please build the Pure ML model as specified in the prompt."
5. Claude will execute the training pipeline step by step

---

# END OF PROMPT
# ═══════════════════════════════════════════════════════════════════════════════
