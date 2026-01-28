#!/usr/bin/env python3
"""
BB_LONG_REVERSAL Model Assessment Script
Processes CSV data row-by-row and adds model predictions
Outputs both CSV and JSON formats - Only Medium and Strong signals
"""

import pandas as pd
import numpy as np
import pickle
import warnings
import json
from pathlib import Path
from datetime import datetime
warnings.filterwarnings('ignore')

# Configuration
CONFIG = {
    'model_path': '../Model Training\BB SHORT Model\BB_SHORT_REVERSAL_Model.pkl',
    'input_csv': 'GBPUSD_2024-2025_backtest.csv',
    'output_csv': 'GBPUSD_2024-2025_backtest_RESULTS.csv',
    'output_json': 'GBPUSD_2024-2025_backtest_RESULTS.json',
    'output_signals_json': 'trading_signals_GBPUSD.json',
    'timestamp_col': 'timestamp',
    'features' : [
        'close_lag1',
        'close_lag2',
        'close_lag3',
        'open_lag1',
        'open_lag2',
        'open_lag3',
        'high_lag1',
        'high_lag2',
        'high_lag3',
        'low_lag1',
        'low_lag2',
        'low_lag3',
        'volume_lag1',
        'volume_lag2',
        'volume_lag3',
        'ret_lag1',
        'ret_lag2',
        'ret_lag3',
        'bb_position_lag1',
        'bb_position_lag2',
        'bb_position_lag3',
        'bb_width_pct_lag1',
        'bb_width_pct_lag2',
        'bb_width_pct_lag3',
        'dist_bb_upper_lag1',
        'dist_bb_upper_lag2',
        'dist_bb_upper_lag3',
        'bb_upper_touch_lag1',
        'bb_upper_touch_lag2',
        'bb_upper_touch_lag3',
        'bb_mid_rejection_lag1',
        'bb_mid_rejection_lag2',
        'bb_mid_rejection_lag3',
        'rsi_value_lag1',
        'rsi_value_lag2',
        'rsi_value_lag3',
        'rsi_slope_lag1',
        'rsi_slope_lag2',
        'rsi_slope_lag3',
        'rsi_overbought_lag1',
        'rsi_overbought_lag2',
        'rsi_overbought_lag3',
        'body_size_lag1',
        'body_size_lag2',
        'body_size_lag3',
        'upper_wick_lag1',
        'upper_wick_lag2',
        'upper_wick_lag3',
        'lower_wick_lag1',
        'lower_wick_lag2',
        'lower_wick_lag3',
        'wick_ratio_lag1',
        'wick_ratio_lag2',
        'wick_ratio_lag3',
        'close_pos_in_candle_lag1',
        'close_pos_in_candle_lag2',
        'close_pos_in_candle_lag3',
        'upper_rejection_lag1',
        'upper_rejection_lag2',
        'upper_rejection_lag3',
        'lower_high_lag1',
        'lower_high_lag2',
        'lower_high_lag3',
        'atr_norm_lag1',
        'atr_norm_lag2',
        'atr_norm_lag3',
        'ema_50_slope_lag1',
        'ema_50_slope_lag2',
        'ema_50_slope_lag3',
        'price_below_ema50_lag1',
        'price_below_ema50_lag2',
        'price_below_ema50_lag3',
        'candle_vs_bb_lag1',
        'candle_vs_bb_lag2',
        'candle_vs_bb_lag3',
        'body_vs_bb_lag1',
        'body_vs_bb_lag2',
        'body_vs_bb_lag3',
        'RSI_slope_3',
        'price_slope_3',
        'upper_rejection_score',
        'reversal_signal'
    ],
    'min_confidence': 0.65,
    'min_signal_strength': 'Medium'  # New: Only include Medium or stronger signals
}

# Signal strength mapping for filtering
SIGNAL_STRENGTH_ORDER = {
    'None': 0,
    'Weak': 1,
    'Medium': 2,
    'Strong': 3,
    'Very Strong': 4,
}

def load_model():
    """Load the trained model from pickle file"""
    print("🤖 LOADING TRAINED MODEL...")
    
    model_path = Path(CONFIG['model_path'])
    if not model_path.exists():
        print(f"   ✗ ERROR: Model file not found at {CONFIG['model_path']}")
        exit(1)
    
    try:
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        print(f"   ✓ Model loaded successfully")
        print(f"   Model type: {type(model).__name__}")
        return model
    except Exception as e:
        print(f"   ✗ ERROR loading model: {e}")
        exit(1)

def load_data():
    """Load the input CSV data"""
    print("\n📂 LOADING INPUT DATA...")
    
    input_path = Path(CONFIG['input_csv'])
    if not input_path.exists():
        print(f"   ✗ ERROR: Input CSV not found at {CONFIG['input_csv']}")
        exit(1)
    
    try:
        df = pd.read_csv(input_path)
        print(f"   ✓ Loaded {len(df)} rows from {CONFIG['input_csv']}")
        
        # Check if timestamp column exists
        if CONFIG['timestamp_col'] not in df.columns:
            print(f"   ⚠️ Warning: Timestamp column '{CONFIG['timestamp_col']}' not found")
        
        return df
    except Exception as e:
        print(f"   ✗ ERROR loading data: {e}")
        exit(1)

def process_predictions(model, df):
    """Process all predictions and return complete dataframe"""
    print("\n⚙️  PROCESSING PREDICTIONS...")
    
    # Make sure all required features exist
    for feature in CONFIG['features']:
        if feature not in df.columns:
            print(f"   ⚠️ Warning: Feature '{feature}' not found, setting to 0")
            df[feature] = 0
    
    # Prepare features
    X = df[CONFIG['features']].fillna(0)
    
    # Get predictions
    print("   Running model predictions...")
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)[:, 1]
    
    # Add prediction columns to dataframe
    df['model_prediction'] = predictions
    df['model_confidence'] = probabilities
    
    # First, mark all signals based on confidence threshold
    df['model_signal_raw'] = (probabilities >= CONFIG['min_confidence']).astype(int)
    
    # Calculate signal strength with numeric value for filtering
    df['signal_strength'] = df['model_confidence'].apply(
        lambda x: 'Strong' if x >= 0.75 else 
                 'Medium' if x >= 0.65 else 
                 'Weak' if x >= 0.50 else 'None'
    )
    
    # Add numeric strength for easy filtering
    df['signal_strength_value'] = df['signal_strength'].map(SIGNAL_STRENGTH_ORDER)
    
    # Filter signals: only Medium or Strong, AND above confidence threshold
    min_strength_value = SIGNAL_STRENGTH_ORDER[CONFIG['min_signal_strength']]
    df['model_signal'] = (
        (df['model_confidence'] >= CONFIG['min_confidence']) & 
        (df['signal_strength_value'] >= min_strength_value)
    ).astype(int)
    
    # If label exists, add accuracy
    if 'label' in df.columns:
        df['prediction_correct'] = (df['model_prediction'] == df['label']).astype(int)
    
    print(f"   ✓ Predictions processed: {len(df)} rows")
    
    return df

def get_filtered_signals(df):
    """Get only Medium and Strong signals"""
    min_strength_value = SIGNAL_STRENGTH_ORDER[CONFIG['min_signal_strength']]
    filtered_signals = df[
        (df['model_signal'] == 1) & 
        (df['signal_strength_value'] >= min_strength_value)
    ].copy()
    
    return filtered_signals

def save_results(df):
    """Save the complete assessment in multiple formats"""
    print("\n💾 SAVING ASSESSMENTS...")
    
    # 1. Save CSV with ALL data (for analysis)
    df.to_csv(CONFIG['output_csv'], index=False)
    print(f"   ✓ CSV: {len(df)} rows to {CONFIG['output_csv']}")
    
    # 2. Save full JSON with all data
    json_data = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'model_name': 'BB_SHORT_REVERSAL',
            'input_file': CONFIG['input_csv'],
            'total_rows': len(df),
            'config': CONFIG
        },
        'data': df.to_dict(orient='records')
    }
    
    with open(CONFIG['output_json'], 'w') as f:
        json.dump(json_data, f, indent=2, default=str)
    print(f"   ✓ JSON: Full data to {CONFIG['output_json']}")
    
    # 3. Get filtered signals (Medium and Strong only)
    signals_df = get_filtered_signals(df)
    
    # Create signals JSON with filtered data
    signals_json = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'model_name': 'BB_LONG_REVERSAL',
            'min_confidence': CONFIG['min_confidence'],
            'min_signal_strength': CONFIG['min_signal_strength'],
            'total_signals_filtered': len(signals_df),
            'strong_signals': len(signals_df[signals_df['signal_strength'] == 'Strong']),
            'medium_signals': len(signals_df[signals_df['signal_strength'] == 'Medium']),
            'signal_rate': f"{len(signals_df)/len(df):.1%}"
        },
        'signals': signals_df.to_dict(orient='records')
    }
    
    with open(CONFIG['output_signals_json'], 'w') as f:
        json.dump(signals_json, f, indent=2, default=str)
    print(f"   ✓ JSON: {len(signals_df)} filtered signals to {CONFIG['output_signals_json']}")
    print(f"      - Strong: {len(signals_df[signals_df['signal_strength'] == 'Strong'])}")
    print(f"      - Medium: {len(signals_df[signals_df['signal_strength'] == 'Medium'])}")
    
    # Show sample of filtered signals
    if len(signals_df) > 0:
        print(f"\n   Sample filtered signals (first 3):")
        sample_cols = ['timestamp', 'model_confidence', 'signal_strength']
        if 'label' in df.columns:
            sample_cols.append('label')
        print(signals_df[sample_cols].head(3).to_string(index=False))
    else:
        print(f"\n   ⚠️  No Medium or Strong signals found!")
    
    return df, signals_df

def generate_summary(df, filtered_signals_df):
    """Generate summary statistics with JSON output"""
    print("\n📊 GENERATING SUMMARY...")
    
    total_rows = len(df)
    
    # All signals (raw, before filtering)
    raw_signals = df['model_signal_raw'].sum()
    
    # Filtered signals
    total_signals = len(filtered_signals_df)
    strong_signals = len(filtered_signals_df[filtered_signals_df['signal_strength'] == 'Strong'])
    medium_signals = len(filtered_signals_df[filtered_signals_df['signal_strength'] == 'Medium'])
    avg_confidence = filtered_signals_df['model_confidence'].mean() if total_signals > 0 else 0
    
    # Use ASCII symbols instead of Unicode for Windows compatibility
    print(f"   Total rows: {total_rows}")
    print(f"   Raw signals (>= {CONFIG['min_confidence']}): {raw_signals} ({raw_signals/total_rows:.1%})")
    print(f"   Filtered signals (Medium+): {total_signals} ({total_signals/total_rows:.1%})")
    print(f"     - Strong signals: {strong_signals}")
    print(f"     - Medium signals: {medium_signals}")
    if total_signals > 0:
        print(f"   Average confidence of filtered signals: {avg_confidence:.1%}")
    
    # Performance metrics if labels exist
    if 'label' in df.columns and total_signals > 0:
        win_rate = filtered_signals_df['prediction_correct'].mean()
        print(f"   Win rate on filtered signals: {win_rate:.1%}")
    
    # Create comprehensive summary data
    summary_data = {
        'summary': {
            'generated_at': datetime.now().isoformat(),
            'total_rows': total_rows,
            'raw_signals_count': int(raw_signals),
            'raw_signal_rate': float(raw_signals/total_rows),
            'filtered_signals_count': int(total_signals),
            'filtered_signal_rate': float(total_signals/total_rows),
            'average_confidence': float(avg_confidence),
            'min_confidence': CONFIG['min_confidence'],
            'min_signal_strength': CONFIG['min_signal_strength']
        },
        'signal_distribution': {
            'strong': int(strong_signals),
            'medium': int(medium_signals),
            'weak': int(len(df[df['signal_strength'] == 'Weak'])),
            'none': int(len(df[df['signal_strength'] == 'None'])),
            'raw_signals': int(raw_signals),
            'filtered_signals': int(total_signals)
        },
        'confidence_thresholds': {
            'strong': 0.75,
            'medium': 0.65,
            'weak': 0.50,
            'none': 0.0
        }
    }
    
    if 'label' in df.columns and total_signals > 0:
        summary_data['performance'] = {
            'win_rate': float(win_rate),
            'filtered_correct_predictions': int(filtered_signals_df['prediction_correct'].sum()),
            'filtered_accuracy': float(filtered_signals_df['prediction_correct'].mean()),
            'total_accuracy': float(df['prediction_correct'].mean()) if 'prediction_correct' in df.columns else None
        }
    
    # Save summary as JSON
    with open('model_summary.json', 'w') as f:
        json.dump(summary_data, f, indent=2, default=str)
    
    # Also keep the text summary for quick viewing - use ASCII symbols for Windows
    with open('model_assessment_summary.txt', 'w', encoding='utf-8') as f:
        f.write(f"Model Assessment Summary\n")
        f.write(f"=======================\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Input file: {CONFIG['input_csv']}\n")
        f.write(f"Output files:\n")
        f.write(f"  - CSV: {CONFIG['output_csv']}\n")
        f.write(f"  - Full JSON: {CONFIG['output_json']}\n")
        f.write(f"  - Signals JSON: {CONFIG['output_signals_json']} (Medium+ only)\n")
        f.write(f"  - Summary JSON: model_summary.json\n")
        f.write(f"\nStatistics:\n")
        f.write(f"  Total rows: {total_rows}\n")
        f.write(f"  Raw signals (>= {CONFIG['min_confidence']}): {raw_signals} ({raw_signals/total_rows:.1%})\n")
        f.write(f"  Filtered signals (Medium+): {total_signals} ({total_signals/total_rows:.1%})\n")
        f.write(f"    - Strong signals: {strong_signals}\n")
        f.write(f"    - Medium signals: {medium_signals}\n")
        if 'label' in df.columns and total_signals > 0:
            f.write(f"  Win rate on filtered signals: {win_rate:.1%}\n")
    
    print(f"\n   ✓ Summary saved to: model_assessment_summary.txt")
    print(f"   ✓ Detailed summary saved to: model_summary.json")

def main():
    """Main execution function"""
    print("=" * 70)
    print("BB_LONG_REVERSAL MODEL ASSESSMENT")
    print(f"Min Confidence: {CONFIG['min_confidence']}")
    print(f"Min Signal Strength: {CONFIG['min_signal_strength']}+")
    print("=" * 70)
    
    # Load model
    model = load_model()
    
    # Load data
    df = load_data()
    
    # Process predictions
    df_with_predictions = process_predictions(model, df)
    
    # Save results (now in multiple formats)
    df_full, df_signals = save_results(df_with_predictions)
    
    # Generate summary
    generate_summary(df_full, df_signals)
    
    print("\n" + "=" * 70)
    print("✅ COMPLETE - FILTERED SIGNALS ONLY")
    print("=" * 70)
    print(f"\nOutput files created:")
    print(f"  📄 {CONFIG['output_csv']} - Full data with predictions")
    print(f"  📄 {CONFIG['output_json']} - Complete JSON with metadata")
    print(f"  📄 {CONFIG['output_signals_json']} - Medium & Strong signals only")
    print(f"  📄 model_summary.json - Performance statistics")
    print(f"  📄 model_assessment_summary.txt - Human-readable summary")
    
    if len(df_signals) > 0:
        print(f"\n🎯 TRADING SIGNALS READY:")
        print(f"   Total: {len(df_signals)} signals")
        print(f"   Strong: {len(df_signals[df_signals['signal_strength'] == 'Strong'])}")
        print(f"   Medium: {len(df_signals[df_signals['signal_strength'] == 'Medium'])}")
        print(f"\nTo use filtered signals in trading systems, import from:")
        print(f"  {CONFIG['output_signals_json']}")
    else:
        print(f"\n⚠️  NO TRADING SIGNALS FOUND")
        print(f"   No Medium or Strong signals detected with current parameters.")

if __name__ == "__main__":
    main()