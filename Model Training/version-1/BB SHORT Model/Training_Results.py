PS C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Model Training\BB SHORT Model> python train_model.py
======================================================================
BOLLINGER BANDS REVERSAL SHORT - MODEL TRAINING
======================================================================
Loading features...
Features shape: (2211, 131)
Label distribution: 0=1326, 1=885
Positive ratio: 0.400

Using 82 features

Data Split:
  Train: (1768, 82) (712/1768 positive)
  Test:  (443, 82) (173/443 positive)
  Train period: 2009-02-04 04:00:00 to 2021-10-25 12:00:00
  Test period:  2021-10-28 20:00:00 to 2025-12-24 12:00:00

============================================================
TRAINING RANDOM FOREST CLASSIFIER
============================================================
Model parameters:
  n_estimators: 200
  max_depth: 15
  class_weight: balanced_subsample
  max_features: sqrt

Training model...

Out-of-bag score: 0.8462

============================================================
MODEL EVALUATION
============================================================

Classification Report:
              precision    recall  f1-score   support

    No Short     0.8901    0.9296    0.9094       270
       Short     0.8820    0.8208    0.8503       173

    accuracy                         0.8871       443
   macro avg     0.8860    0.8752    0.8799       443
weighted avg     0.8869    0.8871    0.8863       443


Confusion Matrix:
                Predicted
                No Short  Short
Actual No Short      251      19
Actual Short          31     142

Detailed Metrics:
  Accuracy:    0.8871
  Precision:   0.8820
  Recall:      0.8208
  F1-Score:    0.8503
  Specificity: 0.9296
  AUC-ROC:     0.9464

Predictions saved to 'model_predictions.csv'

============================================================
FEATURE IMPORTANCE ANALYSIS
============================================================

Top 20 Most Important Features:
--------------------------------------------------
 1. ret_lag1                       : 0.0898
 2. rsi_slope_lag3                 : 0.0697
 3. rsi_slope_lag1                 : 0.0676
 4. ret_lag3                       : 0.0623
 5. close_pos_in_candle_lag3       : 0.0537
 6. rsi_slope_lag2                 : 0.0474
 7. close_pos_in_candle_lag2       : 0.0459
 8. RSI_slope_3                    : 0.0310
 9. close_pos_in_candle_lag1       : 0.0283
10. ret_lag2                       : 0.0259
11. price_slope_3                  : 0.0192
12. body_size_lag2                 : 0.0164
13. bb_position_lag2               : 0.0157
14. body_size_lag3                 : 0.0157
15. body_vs_bb_lag2                : 0.0147
16. bb_position_lag3               : 0.0138
17. body_vs_bb_lag1                : 0.0136
18. bb_position_lag1               : 0.0129
19. body_vs_bb_lag3                : 0.0128
20. dist_bb_upper_lag2             : 0.0128

Full feature importance saved to 'feature_importance.csv'

Feature Importance by Category:
--------------------------------------------------
  BB Features         : 0.1764
  RSI Features        : 0.2175
  Price Features      : 0.2207
  Volume Features     : 0.0259
  Candle Features     : 0.3059
  Trend Features      : 0.2565
  Derived Features    : 0.0121

Feature importance plot saved to 'feature_importance_plot.png'

============================================================
THRESHOLD OPTIMIZATION
============================================================

Optimal threshold based on F1-score: 0.5357
Maximum F1-score: 0.8589

Performance at different thresholds:
--------------------------------------------------
Threshold | Precision | Recall   | F1-Score
--------------------------------------------------
     0.30 |    0.6962 |   0.9538 |   0.8049
     0.40 |    0.7949 |   0.8960 |   0.8424
     0.50 |    0.8820 |   0.8208 |   0.8503
     0.60 |    0.9371 |   0.7746 |   0.8481
     0.70 |    0.9917 |   0.6879 |   0.8123

Model saved to 'BB_SHORT_REVERSAL_Model.pkl'
Feature names saved to 'feature_columns.txt'
Model info saved to 'model_info.json'

============================================================
TRADING SIGNAL GENERATION
============================================================

Signal Statistics:
  Total signals generated: 153
  Correct signals: 140
  Signal accuracy: 91.50%

Trading signals saved to 'trading_signals.csv'

Signal Strength Distribution:
  Very Weak   :   0 signals
  Weak        :   0 signals
  Moderate    :  33 signals
  Strong      :  53 signals
  Very Strong :  67 signals

======================================================================
MODEL TRAINING COMPLETE
======================================================================

Generated Files:
  1. bb_rev_short_model.pkl    - Trained model
  2. model_info.json           - Model metadata
  3. feature_importance.csv    - Feature rankings
  4. feature_importance_plot.png - Feature importance visualization
  5. model_predictions.csv     - Test set predictions
  6. trading_signals.csv       - Trading signals

Next Steps:
  1. Review feature importance to understand what drives predictions
  2. Adjust threshold based on risk tolerance (current optimal: 0.536)
  3. Test model on new data
  4. Integrate with trading system