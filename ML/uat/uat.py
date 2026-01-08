#!/usr/bin/env python3
"""
GBPUSD Signal Generator
Loads your EURUSD-trained model and applies it to GBPUSD data
Outputs only BUY signals with timestamps and confidence
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime
import warnings
import sys
import os

warnings.filterwarnings('ignore')

# Import your configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

def load_and_validate_gbpusd_data(gbpusd_file_path):
    """Load GBPUSD data and validate it has required features"""
    print("📂 LOADING GBPUSD DATA...")
    
    # Get absolute path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    # Try multiple possible locations
    possible_paths = [
        gbpusd_file_path,  # Direct path
        os.path.join(current_dir, gbpusd_file_path),  # Relative to uat folder
        os.path.join(project_root, gbpusd_file_path),  # Relative to project root
        os.path.join(project_root, 'data', 'uat', 'GBPUSD.csv'),  # Your exact path
        os.path.join(project_root, 'data', 'GBPUSD.csv'),  # Common location
    ]
    
    df = None
    found_path = None
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                found_path = path
                print(f"   ✓ Loaded {len(df)} samples from {path}")
                break
            except Exception as e:
                print(f"   ⚠️  Could not read {path}: {e}")
                continue
    
    if df is None:
        print(f"   ✗ ERROR: File not found: {gbpusd_file_path}")
        print("\n   Tried these locations:")
        for path in possible_paths:
            exists = "✓" if os.path.exists(path) else "✗"
            print(f"     {exists} {path}")
        print("\n   Please place your GBPUSD CSV file in one of these locations.")
        exit(1)
    
    # Check required features exist
    required_features = CONFIG['features']
    missing_features = [f for f in required_features if f not in df.columns]
    
    if missing_features:
        print(f"   ✗ ERROR: Missing required features in GBPUSD data:")
        for feat in missing_features:
            print(f"     - {feat}")
        print(f"\n   Your GBPUSD CSV must have these columns:")
        for feat in required_features:
            print(f"     - {feat}")
        exit(1)
    
    # Check for timestamp column
    if CONFIG['data']['timestamp_col'] not in df.columns:
        print(f"   ✗ ERROR: Missing timestamp column: {CONFIG['data']['timestamp_col']}")
        exit(1)
    
    print(f"   ✅ All {len(required_features)} required features found")
    print(f"   ✅ Timestamp column found: {CONFIG['data']['timestamp_col']}")
    
    # Show data summary
    print(f"\n📊 GBPUSD DATA SUMMARY:")
    print(f"   Date range: {df[CONFIG['data']['timestamp_col']].iloc[0]} to {df[CONFIG['data']['timestamp_col']].iloc[-1]}")
    print(f"   Features used: {len(required_features)}")
    
    return df

def generate_gbpusd_signals(gbpusd_df):
    """Generate buy signals for GBPUSD using trained model"""
    print("\n🤖 GENERATING GBPUSD SIGNALS...")
    
    # Get model path (should be in project root)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    model_paths = [
        'BB_LONG_REVERSAL_Model.pkl',
        os.path.join(project_root, 'BB_LONG_REVERSAL_Model.pkl'),
        os.path.join(current_dir, 'BB_LONG_REVERSAL_Model.pkl'),
    ]
    
    model = None
    found_path = None
    
    for path in model_paths:
        if os.path.exists(path):
            try:
                model = pickle.load(open(path, 'rb'))
                found_path = path
                print(f"   ✓ Loaded trained model: {path}")
                break
            except Exception as e:
                print(f"   ⚠️  Could not load model from {path}: {e}")
                continue
    
    if model is None:
        print("   ✗ ERROR: Model file not found: BB_LONG_REVERSAL_Model.pkl")
        print("\n   Tried these locations:")
        for path in model_paths:
            exists = "✓" if os.path.exists(path) else "✗"
            print(f"     {exists} {path}")
        print("\n   Please place your trained model in one of these locations.")
        print("   Train your model first using main.py")
        exit(1)
    
    # Extract only the features your model was trained on
    required_features = CONFIG['features']
    X_gbpusd = gbpusd_df[required_features]
    
    # Make predictions
    predictions = model.predict(X_gbpusd)
    probabilities = model.predict_proba(X_gbpusd)[:, 1]  # Probability of BUY
    
    # Add predictions to dataframe
    gbpusd_df = gbpusd_df.copy()
    gbpusd_df['prediction'] = predictions
    gbpusd_df['probability'] = probabilities
    
    # Apply confidence threshold
    min_confidence = CONFIG['trading']['min_confidence']
    gbpusd_df['signal'] = (gbpusd_df['probability'] >= min_confidence).astype(int)
    
    # Get only BUY signals (signal = 1)
    buy_signals = gbpusd_df[gbpusd_df['signal'] == 1].copy()
    
    # Sort by probability (highest confidence first)
    buy_signals = buy_signals.sort_values('probability', ascending=False)
    
    print(f"   ✅ Predictions generated")
    print(f"   Confidence threshold: {min_confidence:.0%}")
    print(f"   Total BUY signals found: {len(buy_signals)}")
    print(f"   Signal rate: {len(buy_signals)/len(gbpusd_df):.1%} of all candles")
    
    if len(buy_signals) > 0:
        print(f"   Highest confidence: {buy_signals['probability'].iloc[0]:.1%}")
        print(f"   Average confidence: {buy_signals['probability'].mean():.1%}")
        print(f"   Lowest confidence: {buy_signals['probability'].iloc[-1]:.1%}")
    
    return buy_signals

def create_signal_report(buy_signals):
    """Create comprehensive signal report"""
    print("\n📋 CREATING SIGNAL REPORT...")
    
    if len(buy_signals) == 0:
        print("   ⚠️  No BUY signals found above confidence threshold")
        return pd.DataFrame()  # Empty dataframe
    
    # Create clean report with essential columns
    report_columns = [
        CONFIG['data']['timestamp_col'],  # timestamp
        'probability',                     # confidence
        'prediction',                      # 1 = BUY
    ]
    
    # Add top features for context
    top_features = ['candle_body_pct', 'price_momentum', 'bb_position']
    for feat in top_features:
        if feat in buy_signals.columns:
            report_columns.append(feat)
    
    signal_report = buy_signals[report_columns].copy()
    
    # Rename columns for clarity
    signal_report = signal_report.rename(columns={
        CONFIG['data']['timestamp_col']: 'timestamp',
        'probability': 'confidence',
        'prediction': 'signal',
        'candle_body_pct': 'candle_body',
        'price_momentum': 'momentum',
        'bb_position': 'bb_pos'
    })
    
    # Add signal strength category
    def categorize_signal(conf):
        if conf >= 0.80:
            return 'STRONG'
        elif conf >= 0.70:
            return 'MEDIUM'
        elif conf >= 0.65:
            return 'WEAK'
        else:
            return 'VERY_WEAK'
    
    signal_report['strength'] = signal_report['confidence'].apply(categorize_signal)
    
    # Sort by timestamp
    signal_report = signal_report.sort_values('timestamp')
    
    print(f"   ✅ Report created with {len(signal_report)} signals")
    print(f"   Signal strength breakdown:")
    for strength in ['STRONG', 'MEDIUM', 'WEAK', 'VERY_WEAK']:
        count = len(signal_report[signal_report['strength'] == strength])
        if count > 0:
            print(f"     {strength}: {count} signals")
    
    return signal_report

def save_signal_report(signal_report, output_file):
    """Save signal report to CSV"""
    print("\n💾 SAVING SIGNAL REPORT...")
    
    if len(signal_report) == 0:
        print("   ⚠️  No signals to save")
        return
    
    # Save to CSV (in uat folder)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_dir, output_file)
    signal_report.to_csv(output_path, index=False)
    print(f"   ✅ Signal report saved to: {output_path}")
    
    # Show sample of saved data
    print(f"\n📄 SAMPLE SIGNALS (first 5):")
    print(signal_report.head().to_string(index=False))
    
    # Summary statistics
    print(f"\n📊 SIGNAL DISTRIBUTION:")
    print(f"   Total signals: {len(signal_report)}")
    print(f"   Date range: {signal_report['timestamp'].iloc[0]} to {signal_report['timestamp'].iloc[-1]}")
    print(f"   Average confidence: {signal_report['confidence'].mean():.1%}")
    
    # Monthly signal count estimate
    if 'timestamp' in signal_report.columns:
        try:
            # Convert to datetime
            signal_report['date'] = pd.to_datetime(signal_report['timestamp'])
            days_covered = (signal_report['date'].max() - signal_report['date'].min()).days
            if days_covered > 0:
                signals_per_month = len(signal_report) / (days_covered / 30.44)
                print(f"   Estimated signals/month: {signals_per_month:.1f}")
        except:
            pass

def main():
    """Main execution function"""
    print("=" * 60)
    print("GBPUSD SIGNAL GENERATOR")
    print("=" * 60)
    print("Using EURUSD-trained model to identify GBPUSD buy opportunities")
    print(f"Confidence threshold: {CONFIG['trading']['min_confidence']:.0%}")
    print("=" * 60)
    
    # Configuration - SET YOUR EXACT FILE PATH HERE
    # Try these options:
    GBPUSD_DATA_FILE = '../data/uat/GBPUSD.csv'  # Your exact path
    # GBPUSD_DATA_FILE = 'data/uat/GBPUSD.csv'  # Alternative
    
    OUTPUT_FILE = 'gbpusd_buy_signals.csv'
    
    # Step 1: Load GBPUSD data
    gbpusd_data = load_and_validate_gbpusd_data(GBPUSD_DATA_FILE)
    
    # Step 2: Generate signals
    buy_signals = generate_gbpusd_signals(gbpusd_data)
    
    if len(buy_signals) == 0:
        print("\n" + "=" * 60)
        print("❌ NO SIGNALS FOUND")
        print("=" * 60)
        print("No GBPUSD candles met the confidence threshold.")
        print("Try:")
        print("  1. Lower confidence threshold in config.py")
        print("  2. Check GBPUSD data quality")
        print("  3. Model may not transfer well to GBPUSD")
        return
    
    # Step 3: Create report
    signal_report = create_signal_report(buy_signals)
    
    # Step 4: Save report
    save_signal_report(signal_report, OUTPUT_FILE)
    
    # Step 5: Recommendations
    print("\n" + "=" * 60)
    print("🎯 NEXT STEPS")
    print("=" * 60)
    print("1. Open gbpusd_buy_signals.csv")
    print("2. For each timestamp, check GBPUSD 4HR chart in MT5")
    print("3. Ask: 'Would I manually take this trade?'")
    print("4. Rate each signal (A=Perfect, B=Good, C=Marginal, D=Bad)")
    print("5. If >60% are A/B → Model transfers well to GBPUSD")
    print("6. If <40% are A/B → Model doesn't work on GBPUSD")
    
    print("\n📁 Files created:")
    print(f"   - {OUTPUT_FILE} (all buy signals)")
    print("\nGood luck with your analysis! 🔍")

if __name__ == "__main__":
    main()