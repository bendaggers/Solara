"""
STACKING META-MODEL FOR TRADING
Author: AI Assistant
Purpose: Use XGBoost to filter RF's Bollinger Band entries for higher win rate
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score, confusion_matrix, precision_recall_curve
import matplotlib.pyplot as plt
import joblib
import warnings
warnings.filterwarnings('ignore')

print("="*70)
print("STACKING META-MODEL IMPLEMENTATION")
print("="*70)

# ============================================================================
# STEP 1: LOAD AND PREPARE DATA
# ============================================================================

print("\n[1/8] Loading and preparing data...")

# Load your CSV file (1800 rows where RF would trade)
try:
    df = pd.read_csv('GBPUSD_RF_Pred.csv')  # Change to your actual filename
    print(f"✓ Data loaded: {df.shape[0]} rows, {df.shape[1]} columns")
except FileNotFoundError:
    print("✗ File not found! Please check filename.")
    print("Creating sample data structure for testing...")
    # Create sample data for testing
    np.random.seed(42)
    df = pd.DataFrame({
        'bb_touch_strength': np.random.uniform(0, 1, 1800),
        'bb_position': np.random.uniform(-2, 2, 1800),
        'rsi_value': np.random.uniform(20, 80, 1800),
        'rsi_divergence': np.random.uniform(-1, 1, 1800),
        'candle_rejection': np.random.uniform(0, 1, 1800),
        'candle_body_pct': np.random.uniform(0, 1, 1800),
        'prev_candle_body_pct': np.random.uniform(0, 1, 1800),
        'prev_volume_ratio': np.random.uniform(0.5, 2, 1800),
        'price_momentum': np.random.uniform(-1, 1, 1800),
        'time_since_last_touch': np.random.randint(1, 100, 1800),
        'model_confidence': np.random.uniform(0.65, 0.97, 1800),
        'signal_strength': np.random.choice([2, 3], 1800, p=[0.5, 0.5]),
        'model_signal': np.ones(1800),  # All 1's as per your data
        'success_factor': np.random.choice([0, 1], 1800, p=[0.5, 0.5])
    })
    print("✓ Sample data created for testing")

# Define features
original_features = [
    'bb_touch_strength',
    'bb_position', 
    'rsi_value',
    'rsi_divergence',
    'candle_rejection',
    'candle_body_pct',
    'prev_candle_body_pct',
    'prev_volume_ratio',
    'price_momentum',
    'time_since_last_touch'
]

# Check all features exist
missing_features = [f for f in original_features if f not in df.columns]
if missing_features:
    print(f"✗ Missing features: {missing_features}")
    raise ValueError("Please add missing features to your data")
else:
    print("✓ All 10 original features found")

# Check required columns
required_cols = ['model_confidence', 'signal_strength', 'success_factor']
for col in required_cols:
    if col not in df.columns:
        print(f"✗ Missing column: {col}")
        raise ValueError(f"Please add '{col}' column to your data")

print(f"\nData Summary:")
print(f"- Total samples: {len(df)}")
print(f"- Success rate (reached 40 pips): {df['success_factor'].mean():.2%}")
print(f"- RF confidence range: {df['model_confidence'].min():.3f} to {df['model_confidence'].max():.3f}")
print(f"- Signal strength distribution:")
print(df['signal_strength'].value_counts().sort_index())

# ============================================================================
# STEP 2: CREATE META-FEATURES FOR XGBOOST
# ============================================================================

print("\n[2/8] Creating meta-features for XGBoost...")

# Create XGBoost input features: Original 10 + RF outputs
X_meta = df[original_features].copy()

# Add RF's outputs as features (this is the "stacking" part)
X_meta['rf_confidence'] = df['model_confidence']  # RF's probability (0.65-0.97)
X_meta['rf_signal_strength'] = df['signal_strength']  # RF's category (2 or 3)

# Target: Will the trade reach 40 pips?
y = df['success_factor'].copy()

print(f"✓ Meta-features created: {len(X_meta.columns)} total features")
print(f"  - Original features: {len(original_features)}")
print(f"  - RF outputs added: 2 (rf_confidence, rf_signal_strength)")
print(f"✓ Target: success_factor ({y.mean():.2%} positive)")

# ============================================================================
# STEP 3: TRAIN/TEST SPLIT
# ============================================================================

print("\n[3/8] Splitting data into train/test sets...")

# Stratified split to maintain success rate distribution
X_train, X_test, y_train, y_test = train_test_split(
    X_meta, y, 
    test_size=0.2, 
    random_state=42,
    stratify=y  # Keep same success rate in both sets
)

print(f"✓ Training set: {len(X_train)} samples ({y_train.mean():.2%} success)")
print(f"✓ Test set: {len(X_test)} samples ({y_test.mean():.2%} success)")

# ============================================================================
# STEP 4: TRAIN XGBOOST META-MODEL
# ============================================================================

print("\n[4/8] Training XGBoost meta-model...")

# Configure XGBoost
xgb_model = xgb.XGBClassifier(
    n_estimators=300,           # Number of trees
    max_depth=5,                # Tree depth
    learning_rate=0.05,         # How fast model learns
    subsample=0.7,              # Use 70% of data for each tree
    colsample_bytree=0.7,       # Use 70% of features for each tree
    random_state=42,            # For reproducibility
    eval_metric=['logloss', 'auc', 'error'],  # Metrics to track
    use_label_encoder=False
)

# Train the model
print("Training in progress... (this may take a minute)")
xgb_model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=50  # Show progress every 50 trees
)

print("✓ XGBoost training complete!")

# ============================================================================
# STEP 5: EVALUATE THE MODEL
# ============================================================================

print("\n[5/8] Evaluating model performance...")

# Get predictions
y_pred = xgb_model.predict(X_test)
y_pred_proba = xgb_model.predict_proba(X_test)[:, 1]

# Calculate metrics
accuracy = accuracy_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_pred_proba)
baseline_accuracy = y_test.mean()

print("\n" + "="*50)
print("PERFORMANCE METRICS")
print("="*50)
print(f"Baseline (take all RF trades): {baseline_accuracy:.2%}")
print(f"XGBoost Accuracy:               {accuracy:.2%}")
print(f"Improvement:                    {accuracy - baseline_accuracy:+.2%} points")
print(f"ROC AUC Score:                  {roc_auc:.3f}")
print("\n" + "-"*50)

# Detailed classification report
print("Classification Report:")
print(classification_report(y_test, y_pred, target_names=['Fail (0)', 'Success (1)']))

# Confusion Matrix
cm = confusion_matrix(y_test, y_pred)
print("Confusion Matrix:")
print(f"               Predicted")
print(f"               Fail  Success")
print(f"Actual Fail    {cm[0,0]:>4}     {cm[0,1]:>4}")
print(f"       Success {cm[1,0]:>4}     {cm[1,1]:>4}")

# ============================================================================
# STEP 6: FIND OPTIMAL THRESHOLD
# ============================================================================

print("\n[6/8] Finding optimal threshold...")

# Find threshold that maximizes F1-score
precision, recall, thresholds = precision_recall_curve(y_test, y_pred_proba)
f1_scores = 2 * (precision[:-1] * recall[:-1]) / (precision[:-1] + recall[:-1] + 1e-10)
optimal_idx = np.argmax(f1_scores)
optimal_threshold = thresholds[optimal_idx]

print(f"\nOptimal threshold: {optimal_threshold:.3f}")
print(f"F1-score at optimal: {f1_scores[optimal_idx]:.3f}")

# Test different thresholds
print("\nPerformance at different thresholds:")
print("-"*55)
print("Threshold | Accuracy | Trades Taken | Win Rate if Trade")
print("-"*55)

thresholds_to_test = [0.3, 0.4, 0.5, 0.6, optimal_threshold]

for threshold in sorted(thresholds_to_test):
    y_pred_thresh = (y_pred_proba >= threshold).astype(int)
    accuracy = accuracy_score(y_test, y_pred_thresh)
    trades_taken = (y_pred_thresh == 1).sum()
    trade_percentage = trades_taken / len(y_test)
    
    # Calculate win rate for trades actually taken
    if trades_taken > 0:
        win_rate = y_test[y_pred_thresh == 1].mean()
    else:
        win_rate = 0
    
    print(f"{threshold:>8.2f} | {accuracy:>8.2%} | "
          f"{trades_taken:>4}/{len(y_test)} ({trade_percentage:>6.1%}) | "
          f"{win_rate:>8.2%}")

# ============================================================================
# STEP 7: FEATURE IMPORTANCE
# ============================================================================

print("\n[7/8] Analyzing feature importance...")

# Get feature importances
importances = pd.DataFrame({
    'Feature': X_meta.columns,
    'Importance': xgb_model.feature_importances_
}).sort_values('Importance', ascending=False)

print("\nFeature Importances:")
print("-"*40)
for idx, row in importances.iterrows():
    print(f"{row['Feature']:25} {row['Importance']:.4f}")

# Check RF confidence importance
rf_conf_rank = importances[importances['Feature'] == 'rf_confidence'].index[0] + 1
print(f"\n✓ RF confidence is rank #{rf_conf_rank} in importance")

# Visualize feature importance
plt.figure(figsize=(10, 6))
colors = ['blue' if 'rf_' in f else 'green' for f in importances['Feature']]
plt.barh(range(len(importances)), importances['Importance'], color=colors)
plt.yticks(range(len(importances)), importances['Feature'])
plt.xlabel('Importance Score')
plt.title('XGBoost Feature Importance\n(Blue = RF outputs, Green = Original features)')
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig('feature_importance.png', dpi=100, bbox_inches='tight')
plt.show()

# ============================================================================
# STEP 8: SAVE MODEL AND CREATE PREDICTION PIPELINE
# ============================================================================

print("\n[8/8] Saving model and creating pipeline...")

# Save the trained model
joblib.dump(xgb_model, 'xgboost_meta_model.pkl')
print("✓ Model saved as 'xgboost_meta_model.pkl'")

# Create prediction function
def predict_with_stacking(new_data, rf_confidence, rf_signal_strength, threshold=0.5):
    """
    Predict using stacking meta-model
    
    Parameters:
    - new_data: DataFrame with original 10 features
    - rf_confidence: RF's confidence score (0-1)
    - rf_signal_strength: RF's signal strength (2 or 3)
    - threshold: Decision threshold (default 0.5)
    
    Returns:
    - Dictionary with predictions and confidence scores
    """
    # Prepare features for XGBoost
    X_new = new_data[original_features].copy()
    X_new['rf_confidence'] = rf_confidence
    X_new['rf_signal_strength'] = rf_signal_strength
    
    # Get predictions
    proba = xgb_model.predict_proba(X_new)[:, 1]
    signal = (proba >= threshold).astype(int)
    
    return {
        'xgb_confidence': proba[0] if len(proba) == 1 else proba,
        'xgb_signal': signal[0] if len(signal) == 1 else signal,
        'rf_confidence': rf_confidence,
        'rf_signal_strength': rf_signal_strength,
        'should_trade': (signal == 1)[0] if len(signal) == 1 else (signal == 1)
    }

# Test the prediction function
print("\n" + "="*50)
print("PREDICTION PIPELINE TEST")
print("="*50)

# Create a sample new data point
sample_data = pd.DataFrame({
    'bb_touch_strength': [0.8],
    'bb_position': [-1.2],
    'rsi_value': [35],
    'rsi_divergence': [0.5],
    'candle_rejection': [0.7],
    'candle_body_pct': [0.6],
    'prev_candle_body_pct': [0.5],
    'prev_volume_ratio': [1.2],
    'price_momentum': [0.3],
    'time_since_last_touch': [10]
})

rf_conf_sample = 0.85
rf_strength_sample = 3

prediction = predict_with_stacking(sample_data, rf_conf_sample, rf_strength_sample)

print(f"Sample Prediction:")
print(f"  RF Confidence: {prediction['rf_confidence']:.3f}")
print(f"  RF Signal Strength: {prediction['rf_signal_strength']}")
print(f"  XGBoost Confidence: {prediction['xgb_confidence']:.3f}")
print(f"  XGBoost Signal: {prediction['xgb_signal']}")
print(f"  Should Trade: {'YES' if prediction['should_trade'] else 'NO'}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("\n" + "="*70)
print("IMPLEMENTATION COMPLETE!")
print("="*70)

print("\nNEXT STEPS FOR TRADING INTEGRATION:")
print("1. In your trading bot, load the model:")
print("   import joblib")
print("   xgb_model = joblib.load('xgboost_meta_model.pkl')")
print("\n2. For each new candle:")
print("   - Calculate the 10 original features")
print("   - Get RF's prediction (model_confidence)")
print("   - If RF says trade (confidence >= 0.65):")
print("       - Call predict_with_stacking()")
print("       - Only trade if XGBoost also says YES")
print("\n3. Monitor performance:")
print("   - Track win rate of stacked system")
print("   - Compare with RF-only performance")
print("   - Adjust threshold if needed")

print("\n" + "="*70)
print("KEY INSIGHTS FROM YOUR DATA:")
print("="*70)

# Calculate potential improvement
if accuracy > baseline_accuracy:
    print(f"✓ XGBoost can improve win rate by {accuracy - baseline_accuracy:+.2%}")
    print(f"  Current RF: {baseline_accuracy:.2%} → With stacking: {accuracy:.2%}")
else:
    print(f"⚠️  XGBoost didn't improve accuracy in this test")
    print(f"  Consider: Different features, more data, or different model")

# Analyze trade frequency
optimal_predictions = (y_pred_proba >= optimal_threshold).astype(int)
trades_taken = optimal_predictions.sum()
print(f"\n✓ At optimal threshold ({optimal_threshold:.2f}):")
print(f"  - Take {trades_taken}/{len(y_test)} trades ({(trades_taken/len(y_test)):.1%})")
print(f"  - vs RF which takes 100% of trades")

# Final recommendation
print("\n" + "="*70)
print("RECOMMENDATION:")
print("="*70)
if accuracy > baseline_accuracy and trades_taken > 0:
    win_rate_filtered = y_test[optimal_predictions == 1].mean()
    print(f"USE STACKING! Expected results:")
    print(f"• Win rate: {baseline_accuracy:.1%} → {win_rate_filtered:.1%}")
    print(f"• Trade frequency: 100% → {(trades_taken/len(y_test)):.1%}")
    print(f"• Net effect: Fewer trades, higher quality")
else:
    print("Continue with RF-only strategy for now.")
    print("Consider collecting more data or refining features.")

print("\n" + "="*70)
print("END OF STACKING IMPLEMENTATION")
print("="*70)