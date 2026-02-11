"""
deploy.py - Simple model deployment
Usage: python deploy.py --model=models/deployed_model_20250210_120000.pkl --data=new_data.csv
"""

import pickle
import pandas as pd
import numpy as np
import argparse
from datetime import datetime
import json

def deploy_model(model_path: str, data_path: str, output_path: str = None):
    """Deploy trained model on new data."""
    
    print(f"\n🚀 DEPLOYING MODEL")
    print(f"Model: {model_path}")
    print(f"Data: {data_path}")
    
    # Load deployment package
    with open(model_path, 'rb') as f:
        deployment = pickle.load(f)
    
    model = deployment['model']
    config = deployment['config']
    features = deployment['selected_features']
    threshold = deployment['threshold']
    feature_means = deployment['feature_means']
    
    print(f"\n📦 Model Info:")
    print(f"  TP: {config['tp_pips']} pips, SL: {config['sl_pips']} pips")
    print(f"  BB Position > {config['bb_position']:.2f}")
    print(f"  RSI > {config['rsi_value']}")
    print(f"  Threshold: {threshold:.3f}")
    print(f"  Features: {len(features)}")
    
    # Load new data
    print(f"\n📊 Loading data...")
    data = pd.read_csv(data_path)
    print(f"  Data shape: {data.shape}")
    
    # Check if features exist
    missing_features = [f for f in features if f not in data.columns]
    if missing_features:
        print(f"⚠️ Missing features: {len(missing_features)}")
        print(f"  First 5 missing: {missing_features[:5]}")
        return None
    
    # Prepare features
    X_new = data[features].copy()
    
    # Fill missing values with training means
    for feature in features:
        if feature in feature_means:
            X_new[feature] = X_new[feature].fillna(feature_means[feature])
        else:
            X_new[feature] = X_new[feature].fillna(0)
    
    # Make predictions
    print(f"\n🎯 Making predictions...")
    probabilities = model.predict_proba(X_new)[:, 1]
    signals = probabilities >= threshold
    
    # Create results
    results = pd.DataFrame({
        'timestamp': data.get('timestamp', data.index),
        'probability': probabilities,
        'signal': signals.astype(int),
        'predicted_class': ['SELL' if s else 'HOLD' for s in signals]
    })
    
    # Add original data if available
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in data.columns:
            results[col] = data[col].values
    
    # Save results
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"deployment_results_{timestamp}.csv"
    
    results.to_csv(output_path, index=False)
    
    print(f"\n✅ DEPLOYMENT COMPLETE!")
    print(f"📊 Results:")
    print(f"  Total bars: {len(results):,}")
    print(f"  Signals generated: {signals.sum():,} ({signals.mean():.1%})")
    print(f"  Average probability: {probabilities.mean():.3f}")
    print(f"  Results saved to: {output_path}")
    
    # Create summary
    summary = {
        'deployment_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'model_used': model_path,
        'data_used': data_path,
        'results_file': output_path,
        'statistics': {
            'total_bars': len(results),
            'signals_generated': int(signals.sum()),
            'signal_percentage': float(signals.mean()),
            'avg_probability': float(probabilities.mean()),
            'threshold_used': float(threshold)
        }
    }
    
    summary_path = output_path.replace('.csv', '_summary.json')
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"📄 Summary saved to: {summary_path}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Deploy trained model')
    parser.add_argument('--model', type=str, required=True,
                       help='Path to deployed model (.pkl file)')
    parser.add_argument('--data', type=str, required=True,
                       help='Path to new data CSV file')
    parser.add_argument('--output', type=str, default=None,
                       help='Output path for results (default: auto-generated)')
    
    args = parser.parse_args()
    
    results = deploy_model(args.model, args.data, args.output)
    
    if results is not None:
        print("\n🎯 Ready for trading!")
        print("Use the 'signal' column for trade decisions:")
        print("  signal=1 → SELL")
        print("  signal=0 → HOLD")

if __name__ == "__main__":
    main()