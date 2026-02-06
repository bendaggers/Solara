"""
BB Reversal Long Predictor - The AI Advisor

This is your trading system's AI consultant, the module that actually looks 
at market data and says "I think this is a buying opportunity" or "let's 
stay away from this one." It loads your trained machine learning model 
(which learned from thousands of historical examples) and asks it to analyze 
the current market situation. The predictor doesn't just give a simple yes/no 
answer - it provides a confidence score, telling you how sure the model is 
about its recommendation. It's like having an experienced trader who's studied 
patterns for years, but available instantly and without emotion, evaluating 
whether current market conditions match the profitable setups it learned 
during training.
"""

"""
BB Reversal Long Predictor - BACKTESTING LOGIC WITH JSON INPUT
Exact same logic as backtesting script, but processes JSON instead of CSV
"""

"""
BB Reversal Long Predictor - CLEAN VERSION
Exact backtesting logic with clean terminal output
"""

import pickle
import numpy as np
import pandas as pd
import os
import json
import config
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')
from typing import Dict
from volume.volume_manager import VolumeManager


class BBReversalLongPredictor:
    """Clean predictor - minimal output, exact backtesting logic"""
    
    def __init__(self, models_path=None, predictor_config=None, debug=False):
        self.models_path = models_path or config.MODELS_PATH
        self.predictor_config = predictor_config or {}
        self.model = None
        self.model_loaded = False
        self.debug = debug
        self.volume_manager = VolumeManager()
        
        # Get values from predictor_config if available, otherwise use defaults
        model_filename = self.predictor_config.get('model_file', "BB_LONG_REVERSAL_Model_v2.pkl")
        min_conf = self.predictor_config.get('min_confidence', 0.60)
        
        # Backtesting configuration
        self.CONFIG = {
            'model_path': os.path.join(self.models_path, model_filename),
            'model_name': self.predictor_config.get('name', "BB Long Reversal"),
            'features': [
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
            ],
            'model_file': model_filename,
            'min_confidence': min_conf
        }
        
        # Simple one-line initialization message
        if self.debug:
            print(f"📊 Initialized: {self.predictor_config.get('name', 'Unknown')}")
            print(f"  Model: {self.CONFIG['model_file']}")
            print(f"  Type: {self.predictor_config.get('model_type', 'LONG')}")
            print(f"  Magic: {self.predictor_config.get('magic', 'N/A')}")
    
    def load_model(self):
        """Load model - minimal output"""
        model_path = self.CONFIG['model_path']
        
        try:
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found: {model_path}")
            
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            self.model_loaded = True
            
            if self.debug:
                print(f"✅ Model loaded successfully: {os.path.basename(model_path)}")
           
        except Exception as e:
            print(f"❌ Error loading model: {str(e)}")
            raise Exception(f"Error loading model: {str(e)}")
    
    def load_json_data(self, processed_data):
        """Convert JSON to DataFrame - no distribution prints"""
        rows = []
        
        for idx, (unique_key, symbol_data) in enumerate(processed_data.items()):
            row = {
                'unique_key': unique_key,
                'symbol': symbol_data['symbol'],
                'timestamp': symbol_data.get('timestamp', ''),
                'price': symbol_data['price'],
                'original_index': idx
            }
            
            # Add features
            features = symbol_data['features']
            feature_names = symbol_data.get('feature_names', self.CONFIG['features'])
            
            for i, feature_name in enumerate(feature_names):
                row[feature_name] = features[i] if i < len(features) else 0.0
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df = df.sort_values('original_index').reset_index(drop=True)
        
        return df
    
    def process_predictions(self, df):
        """Process predictions using pre-calculated features"""
        # Ensure all features exist
        missing_features = [f for f in self.CONFIG['features'] if f not in df.columns]
        if missing_features:
            print(f"⚠️ Missing features in input: {missing_features}")
            for feature in missing_features:
                df[feature] = 0.0
        
        # Extract only the required features
        X = df[self.CONFIG['features']].fillna(0)
        
        # Minimal feature validation
        X_normalized = X.copy()
        
        # RSI values should be between 0-100 (clip if needed)
        if 'rsi_value' in X_normalized.columns:
            X_normalized['rsi_value'] = X_normalized['rsi_value'].clip(0, 100)
        
        # Debug: Show feature statistics
        if self.debug and not X_normalized.empty:
            print(f"\n🔍 FEATURE STATISTICS:")
            for feature in self.CONFIG['features'][:5]:  # Show first 5
                if feature in X_normalized.columns:
                    print(f"  {feature}: min={X_normalized[feature].min():.6f}, "
                        f"max={X_normalized[feature].max():.6f}, "
                        f"mean={X_normalized[feature].mean():.6f}")
        
        # Get predictions
        try:
            predictions = self.model.predict(X_normalized)
            probabilities = self.model.predict_proba(X_normalized)[:, 1]
          
        except Exception as e:
            print(f"❌ Model prediction error: {e}")
            print(f"  Feature matrix shape: {X_normalized.shape}")
            print(f"  Feature columns: {list(X_normalized.columns)}")
            raise
        
        # Add prediction columns
        df['model_prediction'] = predictions
        df['model_confidence'] = probabilities
        
        # Simplified: Just use confidence threshold
        df['model_signal'] = (probabilities >= self.CONFIG['min_confidence']).astype(int)
        
        return df
    
    def get_filtered_signals(self, df):
        """Get filtered signals"""
        filtered = df[df['model_signal'] == 1].copy()
        return filtered
    
    def predict(self, processed_data):
        """Main prediction - clean output"""
        if not self.model_loaded:
            self.load_model()
        
        # Get predictor config from global config
        predictor_config = self._get_predictor_config()
        
        # Debug: Check input data
        if self.debug:
            print(f"\n🔍 PREDICTOR INPUT CHECK:")
            print(f"  Type: {type(processed_data)}")
            
            if isinstance(processed_data, pd.DataFrame):
                print(f"  DataFrame shape: {processed_data.shape}")
                print(f"  Columns ({len(processed_data.columns)}): {list(processed_data.columns)}")
                
                # Check for required columns
                missing_model_features = [f for f in self.CONFIG['features'] if f not in processed_data.columns]
                if missing_model_features:
                    print(f"  ⚠️ Missing model features: {missing_model_features}")
                else:
                    print(f"  ✅ All model features present")
                
                # Show sample data
                if not processed_data.empty:
                    print(f"  Sample symbol: {processed_data.iloc[0].get('pair', processed_data.iloc[0].get('symbol', 'Unknown'))}")
        
        # Expect either JSON dict or DataFrame
        if isinstance(processed_data, dict):
            # JSON format (legacy)
            df = self.load_json_data(processed_data)
        elif isinstance(processed_data, pd.DataFrame):
            # DataFrame format (from UniversalPreprocessor)
            df = processed_data.copy()
        else:
            return {}
        
        if df.empty:
            return {}
        
        # Ensure we have required columns
        if 'symbol' not in df.columns:
            if 'pair' in df.columns:
                df['symbol'] = df['pair']
            else:
                df['symbol'] = [f'SYMBOL_{i}' for i in range(len(df))]
        
        if 'price' not in df.columns:
            if 'close' in df.columns:
                df['price'] = df['close']
            else:
                price_cols = [col for col in df.columns if 'price' in col.lower() or 'close' in col.lower()]
                if price_cols:
                    df['price'] = df[price_cols[0]]
                else:
                    df['price'] = 0.0
        
        # Make predictions
        df_with_predictions = self.process_predictions(df)
        filtered_df = self.get_filtered_signals(df_with_predictions)
        
        # Create predictions dict
        predictions = {}
        
        for _, row in filtered_df.iterrows():
            symbol = row['symbol']
            confidence = float(row['model_confidence'])
            
            volume = self.volume_manager.calculate_volume(confidence)
            magic = self.predictor_config.get('magic', 201000)
            
            volume_manager = VolumeManager(magic=magic)
            volume = volume_manager.calculate_volume(confidence)
            
            predictions[symbol] = {
                'prediction': int(row['model_signal']),
                'probability': float(row['model_confidence']),
                'confidence': float(row['model_confidence']),
                'timestamp': row.get('timestamp', ''),
                'price': float(row.get('price', 0)),
                'symbol': symbol,
                'model_type': self.predictor_config.get('model_type', 'LONG'),
                'model_file': self.predictor_config.get('model_file', self.CONFIG['model_file']),
                'min_confidence': self.predictor_config.get('min_confidence', self.CONFIG['min_confidence']),
                'features_present': all(feat in row for feat in self.CONFIG['features']),
                'comment': f"{self.predictor_config.get('comment', 'ML Model Signal')} {(row['model_confidence']):.2f}",
                'magic': magic,
                'volume': volume
            }
        
        return predictions
    
    def _get_predictor_config(self):
        """Get predictor config from global config by matching model file"""
        try:
            # Import config here to avoid circular imports
            import config
            
            # Find config that matches this predictor's model file
            for predictor_config in getattr(config, 'PREDICTOR_CONFIGS', []):
                if predictor_config.get('model_file') == self.CONFIG['model_file']:
                    return predictor_config
            
            # If not found, return default based on model type
            default_config = {
                'model_type': 'SHORT' if 'SHORT' in self.CONFIG['model_file'] else 'LONG',
                'model_file': self.CONFIG['model_file'],
                'min_confidence': self.CONFIG['min_confidence'],
                'description': 'BB Reversal Signal',
                'magic': 100001 if 'SHORT' in self.CONFIG['model_file'] else 100002
            }
            return default_config
            
        except Exception as e:
            print(f"⚠️ Error getting predictor config: {e}")
            return {}