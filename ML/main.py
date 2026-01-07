#!/usr/bin/env python3
"""
Simple Bollinger Band Reversal Trading Model
Loads your 1,068 samples, trains model, and evaluates performance
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, 
    f1_score, confusion_matrix, classification_report
)
import pickle
import warnings
warnings.filterwarnings('ignore')

# Import configuration
from config import CONFIG

def load_and_validate_data():
    """Load your CSV data and validate it"""
    print("📂 LOADING DATA...")
    
    try:
        df = pd.read_csv(CONFIG['data']['file_path'])
        print(f"   ✓ Loaded {len(df)} samples from {CONFIG['data']['file_path']}")
    except FileNotFoundError:
        print(f"   ✗ ERROR: File not found: {CONFIG['data']['file_path']}")
        print("   Please place your CSV file in the 'data/' folder")
        exit(1)
    
    # Check required columns
    required = [CONFIG['data']['timestamp_col'], CONFIG['data']['label_col']]
    missing = [col for col in required if col not in df.columns]
    if missing:
        print(f"   ✗ ERROR: Missing columns: {missing}")
        exit(1)
    
    # Check features exist
    missing_features = [f for f in CONFIG['features'] if f not in df.columns]
    if missing_features:
        print(f"   ⚠️  WARNING: Some features not found: {missing_features[:3]}")
        print("   Using available features only")
        CONFIG['features'] = [f for f in CONFIG['features'] if f in df.columns]
    
    # Basic statistics
    n_positives = df[CONFIG['data']['label_col']].sum()
    pos_rate = n_positives / len(df)
    
    print(f"\n📊 DATA STATISTICS:")
    print(f"   Total samples: {len(df)}")
    print(f"   Positive samples: {n_positives} ({pos_rate:.1%})")
    print(f"   Negative samples: {len(df) - n_positives} ({1-pos_rate:.1%})")
    print(f"   Features to use: {len(CONFIG['features'])}")
    
    # Show sample rows
    print(f"\n   Sample data (first 2 rows):")
    sample_cols = [CONFIG['data']['timestamp_col']] + CONFIG['features'][:3] + [CONFIG['data']['label_col']]
    print(df[sample_cols].head(2).to_string(index=False))
    
    return df

def prepare_features(df):
    """Prepare features and labels for training"""
    print("\n⚙️  PREPARING FEATURES...")
    
    # Ensure timestamp is datetime
    df['date'] = pd.to_datetime(df[CONFIG['data']['timestamp_col']])
    df = df.sort_values('date')
    
    # Time-based split (simple 80/20)
    split_idx = int(len(df) * CONFIG['data']['train_test_split'])
    
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    
    print(f"   Training set: {len(train_df)} samples ({train_df[CONFIG['data']['label_col']].mean():.1%} positive)")
    print(f"   Test set: {len(test_df)} samples ({test_df[CONFIG['data']['label_col']].mean():.1%} positive)")
    
    # Prepare X and y
    X_train = train_df[CONFIG['features']]
    y_train = train_df[CONFIG['data']['label_col']]
    X_test = test_df[CONFIG['features']]
    y_test = test_df[CONFIG['data']['label_col']]
    
    print(f"   Feature matrix shape: {X_train.shape}")
    
    return X_train, y_train, X_test, y_test, test_df, train_df

def check_overfitting(model, X_train, y_train, X_test, y_test):
    """Check if model is overfitting by comparing train vs test accuracy"""
    print("\n" + "=" * 60)
    print("🔍 OVERFITTING CHECK")
    print("=" * 60)
    
    # Get predictions for both sets
    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)
    
    # Calculate accuracies
    train_acc = accuracy_score(y_train, train_pred)
    test_acc = accuracy_score(y_test, test_pred)
    
    # Calculate precision (win rate)
    train_precision = precision_score(y_train, train_pred, zero_division=0)
    test_precision = precision_score(y_test, test_pred, zero_division=0)
    
    # Calculate recall
    train_recall = recall_score(y_train, train_pred, zero_division=0)
    test_recall = recall_score(y_test, test_pred, zero_division=0)
    
    print(f"   Training Accuracy:  {train_acc:.1%}")
    print(f"   Test Accuracy:      {test_acc:.1%}")
    print(f"   Accuracy Difference: {abs(train_acc - test_acc):.2%}")
    print()
    print(f"   Training Precision: {train_precision:.1%} (win rate on train)")
    print(f"   Test Precision:     {test_precision:.1%} (win rate on test)")
    print(f"   Precision Difference: {abs(train_precision - test_precision):.2%}")
    print()
    print(f"   Training Recall:    {train_recall:.1%} (catch rate on train)")
    print(f"   Test Recall:        {test_recall:.1%} (catch rate on test)")
    print(f"   Recall Difference:   {abs(train_recall - test_recall):.2%}")
    
    # Rule of thumb: Difference should be < 10%
    accuracy_diff = abs(train_acc - test_acc)
    precision_diff = abs(train_precision - test_precision)
    recall_diff = abs(train_recall - test_recall)
    
    print(f"\n   📊 OVERFITTING ASSESSMENT:")
    
    if accuracy_diff > 0.10 or precision_diff > 0.15:
        print(f"   ⚠️  WARNING: Possible overfitting!")
        print(f"      Large gap between train and test performance")
        
        if accuracy_diff > 0.10:
            print(f"      Accuracy gap: {accuracy_diff:.2%} (max allowed: 10%)")
        if precision_diff > 0.15:
            print(f"      Win rate gap: {precision_diff:.2%} (max allowed: 15%)")
            
        print(f"\n   💡 SUGGESTION: Simplify model in config.py:")
        print(f"      - Reduce max_depth from {CONFIG['model']['params']['max_depth']} to 3")
        print(f"      - Increase min_samples_split from {CONFIG['model']['params']['min_samples_split']} to 30")
        print(f"      - Add 'min_samples_leaf': 10")
        return False, accuracy_diff, precision_diff
    else:
        print(f"   ✅ Good: Model generalizes well")
        print(f"      Accuracy gap: {accuracy_diff:.2%} (under 10% threshold)")
        print(f"      Win rate gap: {precision_diff:.2%} (under 15% threshold)")
        return True, accuracy_diff, precision_diff

def train_model(X_train, y_train):
    """Train the machine learning model"""
    print("\n🤖 TRAINING MODEL...")
    
    model = RandomForestClassifier(**CONFIG['model']['params'])
    model.fit(X_train, y_train)
    
    print(f"   ✓ Model trained: {CONFIG['model']['type']}")
    print(f"   Parameters: {CONFIG['model']['params']}")
    
    return model

def evaluate_model(model, X_test, y_test):
    """Evaluate model performance"""
    print("\n📈 EVALUATING MODEL...")
    
    # Make predictions
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]  # Probability of positive class
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    
    print(f"   📊 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['No Reversal', 'Reversal']))
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    print(f"   🎯 Confusion Matrix:")
    print(f"                Predicted")
    print(f"               No     Yes")
    print(f"   Actual No   {tn:4d}  {fp:4d}")
    print(f"          Yes  {fn:4d}  {tp:4d}")
    
    print(f"\n   📈 Key Metrics:")
    print(f"   Accuracy:   {accuracy:.1%}  (Min target: {CONFIG['thresholds']['min_accuracy']:.0%})")
    print(f"   Precision:  {precision:.1%}  (Of signals, how many win?)")
    print(f"   Recall:     {recall:.1%}  (Of actual wins, how many caught?)")
    print(f"   F1-Score:   {f1:.1%}  (Balance of precision/recall)")
    
    # Check against thresholds
    passes = (
        accuracy >= CONFIG['thresholds']['min_accuracy'] and
        precision >= CONFIG['thresholds']['min_precision'] and
        recall >= CONFIG['thresholds']['min_recall']
    )
    
    return y_pred, y_prob, passes, {'accuracy': accuracy, 'precision': precision, 'recall': recall}

def feature_importance(model):
    """Display feature importance"""
    print("\n🔍 FEATURE IMPORTANCE:")
    importance = pd.DataFrame({
        'feature': CONFIG['features'],
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for _, row in importance.iterrows():
        stars = '★' * int(row['importance'] * 100 / 5)  # Visual indicator
        print(f"   {row['feature']:20s} {row['importance']:6.1%} {stars}")
    
    return importance

def trading_simulation(test_df, y_prob, y_pred):
    """Simple trading simulation"""
    print("\n💰 TRADING SIMULATION...")
    
    # Add predictions to test data
    test_df = test_df.copy()
    test_df['prediction'] = y_pred
    test_df['probability'] = y_prob
    
    # Apply confidence threshold
    min_conf = CONFIG['trading']['min_confidence']
    test_df['signal'] = (test_df['probability'] >= min_conf).astype(int)
    
    # Analyze high-confidence signals
    high_conf = test_df[test_df['signal'] == 1]
    
    if len(high_conf) == 0:
        print("   ⚠️  No signals meet confidence threshold!")
        return
    
    # Calculate metrics for high-confidence trades
    n_signals = len(high_conf)
    win_rate = high_conf[CONFIG['data']['label_col']].mean()
    
    # Estimate trading frequency
    days_in_test = (test_df['date'].max() - test_df['date'].min()).days
    trades_per_month = n_signals / (days_in_test / 30.44)
    
    print(f"   🎯 Trading with confidence > {min_conf:.0%}:")
    print(f"   High-confidence signals: {n_signals} ({n_signals/len(test_df):.1%} of test period)")
    print(f"   Win rate on these: {win_rate:.1%}")
    print(f"   Expected trades/month: {trades_per_month:.1f}")
    
    # Expected return calculation
    rr_ratio = CONFIG['trading']['reward_risk_ratio']
    expected_return = (win_rate * rr_ratio) - ((1 - win_rate) * 1)
    
    print(f"\n   📈 Expected Performance (assuming {rr_ratio}:1 reward:risk):")
    print(f"   Expected return per trade: {expected_return:.2f}R")
    if expected_return > 0:
        print(f"   Kelly fraction: {expected_return/rr_ratio:.1%} of capital per trade")
    else:
        print(f"   ⚠️  Negative expected value!")
    
    return high_conf, expected_return

def save_results(model, test_df, y_pred, y_prob, importance):
    """Save model and results"""
    print("\n💾 SAVING RESULTS...")
    
    # Save model
    model_path = 'BB_LONG_REVERSAL_Model.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"   ✓ Model saved to: {model_path}")
    
    # Save predictions
    results_df = test_df.copy()
    results_df['prediction'] = y_pred
    results_df['probability'] = y_prob
    
    # Add some derived columns
    results_df['correct'] = (results_df['prediction'] == results_df[CONFIG['data']['label_col']]).astype(int)
    results_df['high_confidence'] = (results_df['probability'] >= CONFIG['trading']['min_confidence']).astype(int)
    
    results_path = 'predictions.csv'
    results_df[[CONFIG['data']['timestamp_col'], 'probability', 'prediction', 
                CONFIG['data']['label_col'], 'correct', 'high_confidence']].to_csv(results_path, index=False)
    print(f"   ✓ Predictions saved to: {results_path}")
    
    # Save feature importance
    importance_path = 'feature_importance.csv'
    importance.to_csv(importance_path, index=False)
    print(f"   ✓ Feature importance saved to: {importance_path}")
    
    # Save summary report
    with open('model_summary.txt', 'w') as f:
        f.write(f"Bollinger Band Reversal Model Summary\n")
        f.write(f"====================================\n")
        f.write(f"Training samples: {len(test_df) / (1-CONFIG['data']['train_test_split']) * CONFIG['data']['train_test_split']:.0f}\n")
        f.write(f"Test samples: {len(test_df)}\n")
        f.write(f"Accuracy: {accuracy_score(test_df[CONFIG['data']['label_col']], y_pred):.1%}\n")
        f.write(f"Precision: {precision_score(test_df[CONFIG['data']['label_col']], y_pred, zero_division=0):.1%}\n")
        f.write(f"Recall: {recall_score(test_df[CONFIG['data']['label_col']], y_pred, zero_division=0):.1%}\n")
    
    print(f"   ✓ Summary saved to: model_summary.txt")

def main():
    """Main execution function"""
    print("=" * 60)
    print("BOLLINGER BAND REVERSAL TRADING MODEL")
    print("=" * 60)
    
    # Step 1: Load data
    df = load_and_validate_data()
    
    # Step 2: Prepare features
    X_train, y_train, X_test, y_test, test_df, train_df = prepare_features(df)
    
    # Step 3: Train model
    model = train_model(X_train, y_train)
    
    # Step 4: Check for overfitting
    is_generalized, acc_diff, prec_diff = check_overfitting(model, X_train, y_train, X_test, y_test)
    
    # Step 5: Evaluate on test set
    print("\n" + "=" * 60)
    print("TEST SET PERFORMANCE")
    print("=" * 60)
    y_pred, y_prob, passes, metrics = evaluate_model(model, X_test, y_test)
    
    # Step 6: Feature importance
    importance = feature_importance(model)
    
    # Step 7: Trading simulation
    sim_results = trading_simulation(test_df, y_prob, y_pred)
    
    # Step 8: Save results
    save_results(model, test_df, y_pred, y_prob, importance)
    
    # Final recommendation
    print("\n" + "=" * 60)
    print("🎯 FINAL RECOMMENDATION")
    print("=" * 60)
    
    if not is_generalized:
        print("❌ MODEL MAY BE OVERFITTED")
        print(f"   Accuracy gap: {acc_diff:.2%} (should be <10%)")
        print(f"   Win rate gap: {prec_diff:.2%} (should be <15%)")
        print(f"\n   ⚠️  Do not trade with this model yet!")
        print(f"   Update config.py to simplify model:")
        print(f"      'max_depth': 3")
        print(f"      'min_samples_split': 30")
        print(f"      'min_samples_leaf': 10")
        print(f"   Then run again.")
    
    elif passes and metrics['precision'] >= 0.4:
        if sim_results:
            high_conf, expected_return = sim_results
            if expected_return > 0:
                print("✅ STRONG BUY SIGNAL")
                print(f"   Model passes all thresholds")
                print(f"   Model generalizes well (not overfit)")
                print(f"   Expected win rate: {metrics['precision']:.1%}")
                print(f"   High-confidence win rate: {high_conf[CONFIG['data']['label_col']].mean():.1%}")
                print(f"   Positive expected value: {expected_return:.2f}R per trade")
                print(f"\n   NEXT STEP: Paper trade for 1-2 months")
                print(f"   Use BB_LONG_REVERSAL_Model.pkl for predictions")
            else:
                print("⚠️  CAUTIOUS SIGNAL")
                print(f"   Model passes thresholds but negative expected value")
                print(f"   Check your risk:reward assumption ({CONFIG['trading']['reward_risk_ratio']}:1)")
        else:
            print("⚠️  INCONCLUSIVE")
            print(f"   Model passes thresholds but no high-confidence signals")
            print(f"   Lower confidence threshold or get more data")
    else:
        print("❌ NOT READY FOR TRADING")
        print(f"   Model fails one or more thresholds:")
        print(f"   - Accuracy: {metrics['accuracy']:.1%} (target: {CONFIG['thresholds']['min_accuracy']:.0%})")
        print(f"   - Precision: {metrics['precision']:.1%} (target: {CONFIG['thresholds']['min_precision']:.0%})")
        print(f"   - Recall: {metrics['recall']:.1%} (target: {CONFIG['thresholds']['min_recall']:.0%})")
        print(f"\n   NEXT STEP: Improve features or get more data")
    
    print("\n📁 Files created:")
    print("   - BB_LONG_REVERSAL_Model.pkl (trained model)")
    print("   - predictions.csv (all test predictions)")
    print("   - feature_importance.csv (which features matter)")
    print("   - model_summary.txt (performance summary)")
    print("\nGood luck with your trading! 🚀")

if __name__ == "__main__":
    main()