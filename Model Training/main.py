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
    
    return X_train, y_train, X_test, y_test, test_df

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
    model_path = 'model.pkl'
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
    
    # TEMPORARY
    analyze_training_data_distributions()

    # Step 1: Load data
    df = load_and_validate_data()
    
    # Step 2: Prepare features
    X_train, y_train, X_test, y_test, test_df = prepare_features(df)
    
    # Step 3: Train model
    model = train_model(X_train, y_train)
    
    # Step 4: Evaluate
    y_pred, y_prob, passes, metrics = evaluate_model(model, X_test, y_test)
    
    # Step 5: Feature importance
    importance = feature_importance(model)
    
    # Step 6: Trading simulation
    sim_results = trading_simulation(test_df, y_prob, y_pred)
    
    # Step 7: Save results
    save_results(model, test_df, y_pred, y_prob, importance)
    
    # Final recommendation
    print("\n" + "=" * 60)
    print("🎯 FINAL RECOMMENDATION")
    print("=" * 60)
    
    if passes and metrics['precision'] >= 0.4:
        if sim_results:
            high_conf, expected_return = sim_results
            if expected_return > 0:
                print("✅ STRONG BUY SIGNAL")
                print(f"   Model passes all thresholds")
                print(f"   Expected win rate: {metrics['precision']:.1%}")
                print(f"   Positive expected value: {expected_return:.2f}R per trade")
                print(f"\n   NEXT STEP: Paper trade for 1-2 months")
                print(f"   Use model.pkl for predictions")
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
    print("   - model.pkl (trained model)")
    print("   - predictions.csv (all test predictions)")
    print("   - feature_importance.csv (which features matter)")
    print("   - model_summary.txt (performance summary)")
    print("\nGood luck with your trading! 🚀")

def analyze_training_data_distributions():
    """
    ONE-TIME ANALYSIS: Check feature distributions in training data
    This tells us EXACTLY what the model was trained on
    """
    print("=" * 60)
    print("📊 TRAINING DATA FEATURE ANALYSIS (One-time check)")
    print("=" * 60)
    
    # Load the data
    df = pd.read_csv(CONFIG['data']['file_path'])
    
    print(f"\nAnalyzing {len(CONFIG['features'])} features from: {CONFIG['data']['file_path']}")
    print(f"Total samples: {len(df)}")
    
    # Create analysis table
    analysis_data = []
    
    for feature in CONFIG['features']:
        if feature in df.columns:
            values = df[feature].dropna()
            if len(values) > 0:
                min_val = values.min()
                max_val = values.max()
                mean_val = values.mean()
                std_val = values.std()
                
                # Determine if normalized (0-1 range)
                is_normalized = (min_val >= 0 and max_val <= 1.1)  # Allow slight overflow
                
                # Determine data type
                if feature in ['rsi_divergence', 'prev_was_selloff']:
                    data_type = 'Binary (0/1)'
                elif feature == 'rsi_value':
                    data_type = 'RSI (0-100)'
                elif feature == 'time_since_last_touch':
                    data_type = f'Count (max {int(max_val)})'
                elif min_val >= 0 and max_val <= 1:
                    data_type = 'Normalized (0-1)'
                else:
                    data_type = 'Raw value'
                
                analysis_data.append({
                    'Feature': feature,
                    'Min': f"{min_val:.4f}",
                    'Max': f"{max_val:.4f}",
                    'Mean': f"{mean_val:.4f}",
                    'Std': f"{std_val:.4f}",
                    'Type': data_type,
                    'Normalized?': '✓' if is_normalized else '✗'
                })
    
    # Create and display analysis table
    analysis_df = pd.DataFrame(analysis_data)
    print("\n" + analysis_df.to_string(index=False))
    
    # Specific checks for critical features
    print("\n🔍 CRITICAL FEATURE CHECKS:")
    
    # Check RSI
    if 'rsi_value' in df.columns:
        rsi_min = df['rsi_value'].min()
        rsi_max = df['rsi_value'].max()
        print(f"RSI Value: {rsi_min:.1f} to {rsi_max:.1f}")
        if rsi_min >= 0 and rsi_max <= 100:
            print("  → Model trained on RAW RSI (0-100)")
        elif rsi_min >= 0 and rsi_max <= 1:
            print("  → Model trained on NORMALIZED RSI (0-1)")
        else:
            print("  ⚠️  RSI in unusual range!")
    
    # Check time_since_last_touch
    if 'time_since_last_touch' in df.columns:
        time_min = df['time_since_last_touch'].min()
        time_max = df['time_since_last_touch'].max()
        time_mean = df['time_since_last_touch'].mean()
        print(f"Time Since Last Touch: {time_min:.1f} to {time_max:.1f} (mean: {time_mean:.1f})")
        
        if time_max <= 20:
            print(f"  → Likely raw count (0-{int(time_max)})")
        elif time_max <= 1:
            print(f"  → Already normalized (0-1)")
        else:
            print(f"  ⚠️  Unusual range - check calculation")
    
    # Check binary features
    binary_features = ['rsi_divergence']
    for feature in binary_features:
        if feature in df.columns:
            unique = sorted(df[feature].dropna().unique())
            print(f"{feature}: Unique values {unique}")
    
    print("\n✅ ANALYSIS COMPLETE")
    print("   Use these findings to configure Solara preprocessor")
    
    # Save analysis to file for reference
    analysis_df.to_csv('training_data_analysis.csv', index=False)
    print("   📄 Saved detailed analysis to: training_data_analysis.csv")
    
    return analysis_df

if __name__ == "__main__":
    main()