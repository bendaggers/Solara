#!/usr/bin/env python3
"""
CSV to JSON Converter for Solara Trading System
Converts your training CSV into JSON format for testing
"""

import pandas as pd
import json
from datetime import datetime

def convert_csv_to_json(csv_path, json_path, timeframe="PERIOD_H4"):
    """
    Convert CSV file to Solara JSON format
    """
    print(f"📊 Loading CSV from: {csv_path}")
    
    # Load CSV
    df = pd.read_csv(csv_path)
    print(f"   Loaded {len(df)} rows")
    
    # Convert timestamp to string format
    df['timestamp'] = df['timestamp'].astype(str)
    
    # Prepare JSON structure
    current_time = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    
    json_data = {
        "timestamp": current_time,
        "timeframe": timeframe,
        "data": []
    }
    
    # Convert each row to the JSON format
    for _, row in df.iterrows():
        symbol_data = {
            "pair": str(row['pair']),
            "timestamp": str(row['timestamp']),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": int(row['volume']),
            "lower_band": float(row['lower_band']),
            "middle_band": float(row['middle_band']),
            "upper_band": float(row['upper_band']),
            "bb_touch_strength": float(row['bb_touch_strength']),
            "bb_position": float(row['bb_position']),
            "bb_width_pct": float(row.get('bb_width_pct', 0.0)),  # Using .get for safety
            "rsi_value": float(row['rsi_value']),
            "rsi_divergence": int(row.get('rsi_divergence', 0)),
            "volume_ratio": float(row.get('volume_ratio', 1.0)),
            "candle_rejection": float(row['candle_rejection']),
            "candle_body_pct": float(row['candle_body_pct']),
            "atr_pct": float(row.get('atr_pct', 0.0)),
            "trend_strength": float(row.get('trend_strength', 0.0)),
            "prev_candle_body_pct": float(row['prev_candle_body_pct']),
            "prev_volume_ratio": float(row.get('prev_volume_ratio', 1.0)),
            "gap_from_prev_close": float(row.get('gap_from_prev_close', 0.0)),
            "price_momentum": float(row['price_momentum']),
            "prev_was_selloff": int(row.get('prev_was_selloff', 0)),
            "previous_touches": int(row.get('previous_touches', 0)),
            "time_since_last_touch": int(row.get('time_since_last_touch', 0)),
            "support_distance_pct": float(row.get('support_distance_pct', 0.0)),
            "session": int(row.get('session', 1))
        }
        
        # Add label if present (for testing)
        if 'label' in row:
            symbol_data['label'] = int(row['label'])
        
        json_data["data"].append(symbol_data)
    
    # Save to JSON file
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"✅ Saved JSON to: {json_path}")
    print(f"   Total symbols: {len(json_data['data'])}")
    
    return json_data

def create_sample_json(csv_path, sample_size=3):
    """
    Create a smaller sample JSON for testing
    """
    print(f"\n🎯 Creating sample JSON with {sample_size} rows...")
    
    df = pd.read_csv(csv_path)
    sample_df = df.head(sample_size).copy()
    
    current_time = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    
    json_data = {
        "timestamp": current_time,
        "timeframe": "PERIOD_H4",
        "data": []
    }
    
    for _, row in sample_df.iterrows():
        symbol_data = {
            "pair": str(row['pair']),
            "timestamp": str(row['timestamp']),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": int(row['volume']),
            "lower_band": float(row['lower_band']),
            "middle_band": float(row['middle_band']),
            "upper_band": float(row['upper_band']),
            "bb_touch_strength": float(row['bb_touch_strength']),
            "bb_position": float(row['bb_position']),
            "bb_width_pct": float(row.get('bb_width_pct', 0.0)),
            "rsi_value": float(row['rsi_value']),
            "rsi_divergence": int(row.get('rsi_divergence', 0)),
            "volume_ratio": float(row.get('volume_ratio', 1.0)),
            "candle_rejection": float(row['candle_rejection']),
            "candle_body_pct": float(row['candle_body_pct']),
            "atr_pct": float(row.get('atr_pct', 0.0)),
            "trend_strength": float(row.get('trend_strength', 0.0)),
            "prev_candle_body_pct": float(row['prev_candle_body_pct']),
            "prev_volume_ratio": float(row.get('prev_volume_ratio', 1.0)),
            "gap_from_prev_close": float(row.get('gap_from_prev_close', 0.0)),
            "price_momentum": float(row['price_momentum']),
            "prev_was_selloff": int(row.get('prev_was_selloff', 0)),
            "previous_touches": int(row.get('previous_touches', 0)),
            "time_since_last_touch": int(row.get('time_since_last_touch', 0)),
            "support_distance_pct": float(row.get('support_distance_pct', 0.0)),
            "session": int(row.get('session', 1)),
            "label": int(row['label']) if 'label' in row else 0
        }
        json_data["data"].append(symbol_data)
    
    sample_path = "sample_test_data.json"
    with open(sample_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"✅ Sample saved to: {sample_path}")
    
    # Print first entry for verification
    print("\n📋 First entry preview:")
    first_entry = json_data["data"][0]
    for key, value in list(first_entry.items())[:10]:  # First 10 items
        print(f"  {key}: {value}")
    
    return json_data

def verify_json_structure(json_path):
    """
    Verify the JSON structure matches Solara requirements
    """
    print(f"\n🔍 Verifying JSON structure: {json_path}")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Check required top-level keys
    required_keys = ['timestamp', 'timeframe', 'data']
    for key in required_keys:
        if key not in data:
            print(f"❌ Missing top-level key: {key}")
            return False
        print(f"  ✓ {key}: {data[key]}")
    
    # Check data array
    if not isinstance(data['data'], list):
        print("❌ 'data' is not a list")
        return False
    
    print(f"  ✓ data contains {len(data['data'])} entries")
    
    # Check first entry structure
    if len(data['data']) > 0:
        first_entry = data['data'][0]
        
        # Required features for BB reversal model
        required_features = [
            'bb_touch_strength', 'bb_position', 'rsi_value', 'rsi_divergence',
            'candle_rejection', 'candle_body_pct', 'prev_candle_body_pct',
            'prev_volume_ratio', 'price_momentum', 'time_since_last_touch'
        ]
        
        missing_features = []
        for feature in required_features:
            if feature not in first_entry:
                missing_features.append(feature)
            else:
                print(f"  ✓ {feature}: {first_entry[feature]}")
        
        if missing_features:
            print(f"❌ Missing features: {missing_features}")
            return False
    
    print("✅ JSON structure verified successfully!")
    return True

def main():
    """Main conversion function"""
    print("=" * 60)
    print("CSV to JSON Converter for Solara")
    print("=" * 60)
    
    # Configuration
    csv_file = "EURUSD_v4.csv"  # Update this path if needed
    json_file = "marketdata_PERIOD_H4.json"
    
    try:
        # 1. Create full JSON file
        json_data = convert_csv_to_json(csv_file, json_file)
        
        # 2. Create a small sample for testing
        create_sample_json(csv_file, sample_size=5)
        
        # 3. Verify the JSON structure
        verify_json_structure(json_file)
        
        print("\n" + "=" * 60)
        print("🎯 CONVERSION COMPLETE!")
        print("=" * 60)
        print(f"\n📁 Files created:")
        print(f"  1. {json_file} - Full dataset")
        print(f"  2. sample_test_data.json - Small sample")
        
        print(f"\n💡 Use these files to test your Solara system:")
        print(f"  - Update config.DATA_PATH to point to test_data.json")
        print(f"  - Run Solara in dry mode to verify predictions")
        print(f"  - Compare predictions with 'label' column")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print(f"   Please check if file exists: {csv_file}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()