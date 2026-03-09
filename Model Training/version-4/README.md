# Pure ML Short-Only Entry Model

A **Pure ML** approach for predicting profitable SHORT entries on EUR/USD 4H candles.

## Overview

Unlike the Signal Filter model (which pre-filters candles by BB/RSI thresholds), this Pure ML model:

- **Evaluates EVERY candle** as a potential SHORT entry
- **No pre-filtering** - the model learns what conditions predict profitable shorts
- **More data-driven** - less human bias in entry conditions
- **Simpler config space** - only TP/SL/Hold parameters to optimize

### Comparison with Signal Filter Model

| Aspect | Signal Filter Model | Pure ML Model |
|--------|---------------------|---------------|
| Pre-filter | BB >= 0.80, RSI >= 70 | None |
| Candles evaluated | ~5% of all candles | 100% of candles |
| What ML learns | "Is this signal good?" | "Is this candle a good SHORT?" |
| Feature importance | BB/RSI less important | BB/RSI may be top features |
| Trade frequency | Lower | Potentially higher |
| Class imbalance | ~10:1 | ~20:1 or higher |
| Interpretability | Higher | Lower |

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Your Data

Your CSV should have:
- Timestamp column
- OHLCV data (open, high, low, close, volume)
- Pre-computed technical features (bb_position, rsi_value, etc.)

### 3. Run the Pipeline

```bash
python run_pure_ml.py \
    --config config/pure_ml_settings.yaml \
    --input data/EURUSD_H4.csv
```

### 4. Check Artifacts

After successful training, find your artifacts in `artifacts/`:
- `pure_ml_model.pkl` - Trained model
- `features.json` - Selected features
- `trading_config.json` - TP/SL/threshold settings
- `metrics.json` - Validation metrics

## Configuration

Edit `config/pure_ml_settings.yaml` to customize:

### Trade Parameters (Config Space)

```yaml
config_space:
  tp_pips:
    min: 30
    max: 80
    step: 10
  sl_pips: 40  # Fixed SL for simplicity
  max_holding_bars:
    min: 12
    max: 30
    step: 6
```

### Acceptance Criteria

```yaml
acceptance_criteria:
  min_precision: 0.55      # Minimum win rate
  min_trades_per_fold: 30  # Statistical significance
  min_expected_value: 0.0  # Positive expectancy required
  max_precision_cv: 0.30   # Stability across folds
```

### Walk-Forward Validation

```yaml
walk_forward:
  n_folds: 5
  train_ratio: 0.60
  calibration_ratio: 0.20
  threshold_ratio: 0.20
  expanding_window: true
```

## Pipeline Stages

1. **Data Loading** - Load and validate CSV data
2. **Label Pre-computation** - Generate labels for all TP/SL/Hold combos
3. **Walk-Forward Splits** - Define train/calibration/threshold periods
4. **Experiments** - Test all configurations with RFE + hyperparameter tuning
5. **Selection** - Choose best config by Expected Value
6. **Final Training** - Train production model on all available data
7. **Artifact Export** - Save model and configs

## Production Usage

```python
import joblib

# Load model bundle
bundle = joblib.load('artifacts/pure_ml_model.pkl')

model = bundle['model']
features = bundle['features']
threshold = bundle['threshold']
tp_pips = bundle['tp_pips']
sl_pips = bundle['sl_pips']

# Make prediction
def predict_short_signal(candle_features: dict) -> dict:
    # Extract features in correct order
    X = [[candle_features[f] for f in features]]
    
    # Get probability
    prob = model.get_proba_positive(X)[0]
    
    return {
        'should_trade': prob >= threshold,
        'probability': prob,
        'tp_pips': tp_pips,
        'sl_pips': sl_pips
    }
```

## Ensemble with Signal Filter Model

Use both models together for higher confidence:

```python
def ensemble_predict(candle):
    # Signal Filter Model (if signal present)
    if candle['bb_position'] >= 0.80 and candle['rsi_value'] >= 70:
        signal_prob = signal_model.predict(candle)
    else:
        signal_prob = 0
    
    # Pure ML Model
    pure_ml_prob = pure_ml_model.predict(candle)
    
    # Ensemble logic
    if signal_prob >= 0.50 and pure_ml_prob >= 0.50:
        return 'STRONG_SHORT'  # Both agree
    elif signal_prob >= 0.50 or pure_ml_prob >= 0.60:
        return 'WEAK_SHORT'
    else:
        return 'NO_TRADE'
```

## Key Differences from V3 Signal Filter Pipeline

1. **No Signal Mask Pre-computation** - We don't pre-filter by BB/RSI
2. **Simpler Config Space** - No BB/RSI thresholds to search
3. **Higher Class Imbalance** - Model sees ALL candles, not just "signal" candles
4. **Feature Selection More Important** - BB/RSI may emerge as top features naturally

## Troubleshooting

### No Configurations Pass
- Check class imbalance (win rate should be at least 3-5%)
- Try relaxing acceptance criteria
- Consider different TP/SL ranges

### Low Precision
- Feature quality may be insufficient
- Try adding more technical indicators
- Consider longer training period

### High CV (Instability)
- Model may be overfitting
- Try reducing features or regularization
- Check for regime-specific performance

## Files Structure

```
pure_ml_pipeline/
├── config/
│   └── pure_ml_settings.yaml
├── src/
│   ├── __init__.py
│   ├── pure_ml_labels.py    # Label generation (no signal filtering)
│   ├── experiment.py        # Experiment runner
│   ├── features.py          # RFE feature selection
│   ├── training.py          # Model training
│   └── evaluation.py        # Metrics computation
├── run_pure_ml.py           # Main pipeline runner
├── requirements.txt
└── README.md
```

## License

Internal use only.
