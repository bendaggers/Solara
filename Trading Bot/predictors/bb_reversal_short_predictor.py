"""
BB Reversal Short Predictor - Compatible with Long Predictor Output
Returns EXACT same structure as BBReversalLongPredictor
FIXED VERSION: Uses features pre-calculated by UniversalPreprocessor
"""

import pickle
import numpy as np
import pandas as pd
import os
import config
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')
from typing import Dict
from volume.volume_manager import VolumeManager


class BBReversalShortPredictor:
    """Predictor for BB Reversal Short model - Same output structure as Long Predictor"""
    
    def __init__(self, models_path=None, predictor_config=None, debug=False):
        self.models_path = models_path or config.MODELS_PATH
        self.predictor_config = predictor_config or {}
        self.model = None
        self.model_loaded = False
        self.debug = debug
        self.volume_manager = VolumeManager()
        
        # Get values from predictor_config if available, otherwise use defaults
        model_filename = self.predictor_config.get('model_file', "BB_SHORT_REVERSAL_Model_v2.pkl")
        min_conf = self.predictor_config.get('min_confidence', 0.85)
        min_strength = self.predictor_config.get('min_signal_strength', "Strong")
        
        # SHORT MODEL configuration - 13 HARDCODED FEATURES
        self.CONFIG = {
            'model_path': os.path.join(self.models_path, model_filename),
            'model_name': self.predictor_config.get('name', "BB Short Reversal"),
            'features': [
                "candle_body_pct",      # 0. Candle body as % of range (0-1)
                "ret_lag1",             # 1. Return lag 1 period (t-2 to t-1)
                "rsi_slope_lag2",       # 2. RSI slope lag 2 periods
                "ret",                  # 3. Current return (t-1 to t)
                "body_size",            # 4. Absolute candle body size
                "RSI_slope_3",          # 5. RSI slope over 3 periods (t-3 to t-1)
                "rsi_slope_lag3",       # 6. RSI slope lag 3 periods
                "ret_lag2",             # 7. Return lag 2 periods (t-3 to t-2)
                "price_momentum",       # 8. Price momentum (3-period return)
                "rsi_slope",            # 9. Current RSI slope (t-1 to t)
                "dist_bb_upper_lag3",   # 10. Distance to upper BB lag 3
                "rsi_slope_lag1",       # 11. RSI slope lag 1 period
                "rsi_value"             # 12. Current RSI value
            ],
            'model_file': model_filename,
            'min_confidence': min_conf,
            'min_signal_strength': min_strength
        }
        
        # Signal strength mapping (5 levels for short model)
        self.SIGNAL_STRENGTH_ORDER = {
            'Very Weak': 0,
            'Weak': 1,
            'Moderate': 2,
            'Strong': 3,
            'Very Strong': 4
        }
        
        # Simple one-line initialization message
        if self.debug:
            print(f"📊 Initialized: {self.predictor_config.get('name', 'Unknown')}")
            print(f"  Model: {self.CONFIG['model_file']}")
            print(f"  Type: {self.predictor_config.get('model_type', 'SHORT')}")
            print(f"  Magic: {self.predictor_config.get('magic', 'N/A')}")
    
    def load_model(self):
        """Load the short model from pickle file"""
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


    def process_predictions(self, df):
        """Process predictions using pre-calculated features"""
        # Ensure all 13 features exist
        missing_features = [f for f in self.CONFIG['features'] if f not in df.columns]
        if missing_features:
            print(f"⚠️ Missing features in input: {missing_features}")
            for feature in missing_features:
                df[feature] = 0.0
        
        # Extract only the 13 required features
        X = df[self.CONFIG['features']].fillna(0)
        
        # Minimal feature validation (no normalization - features should already be correct)
        X_normalized = X.copy()
        
        # Only do minimal sanity checks - UniversalPreprocessor should have calculated correctly
        # RSI values should be between 0-100 (clip if needed)
        if 'rsi_value' in X_normalized.columns:
            X_normalized['rsi_value'] = X_normalized['rsi_value'].clip(0, 100)
        
        # Returns should be reasonable (not extreme outliers)
        for ret_col in ['ret', 'ret_lag1', 'ret_lag2']:
            if ret_col in X_normalized.columns:
                # Clip extreme returns (±20%)
                X_normalized[ret_col] = X_normalized[ret_col].clip(-0.2, 0.2)
        
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
        df['model_signal_raw'] = (probabilities >= self.CONFIG['min_confidence']).astype(int)
        
        # Signal strength
        df['signal_strength'] = df['model_confidence'].apply(
            lambda x: 'Very Strong' if x >= 0.90 else
                    'Strong' if x >= 0.70 else
                    'Moderate' if x >= 0.50 else
                    'Weak' if x >= 0.30 else 'Very Weak'
        )
        
        df['signal_strength_value'] = df['signal_strength'].map(self.SIGNAL_STRENGTH_ORDER)
        
        # Filter signals
        min_strength_value = self.SIGNAL_STRENGTH_ORDER[self.CONFIG['min_signal_strength']]
        
        
        df['model_signal'] = (
            (df['model_confidence'] >= self.CONFIG['min_confidence']) & 
            (df['signal_strength_value'] >= min_strength_value)
        ).astype(int)
        
        return df


    def get_filtered_signals(self, df):
        """Get filtered signals"""
        min_strength_value = self.SIGNAL_STRENGTH_ORDER[self.CONFIG['min_signal_strength']]
        
        filtered = df[
            (df['model_signal'] == 1) & 
            (df['signal_strength_value'] >= min_strength_value)
        ].copy()
        
        return filtered
    
    def generate_clean_summary(self, df, filtered_df):
        """Generate clean summary"""

        total_signals = len(filtered_df)
        
        if total_signals > 0:
            avg_confidence = filtered_df['model_confidence'].mean()
            print(f"📊 Found {total_signals} signals (avg confidence: {avg_confidence:.1%})")
        else:
            print(f"📊 No signals meeting criteria")
            

    def predict(self, processed_data):
        """Main prediction - expects DataFrame with pre-calculated features from UniversalPreprocessor"""
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
                    print(f"  ✅ All 13 model features present")
                
                # Show sample data
                if not processed_data.empty:
                    print(f"  Sample symbol: {processed_data.iloc[0].get('pair', processed_data.iloc[0].get('symbol', 'Unknown'))}")
        
        # Expect DataFrame from UniversalPreprocessor
        if not isinstance(processed_data, pd.DataFrame):
            print(f"❌ Error: Predictor expects DataFrame from UniversalPreprocessor, got {type(processed_data)}")
            return {}
        
        if processed_data.empty:
            print("❌ No data to process")
            return {}
        
        print(f"📊 Processing DataFrame with {len(processed_data)} rows...")
        
        # Create a clean working copy
        df = processed_data.copy()
        
        # Ensure we have a symbol column
        if 'symbol' not in df.columns:
            if 'pair' in df.columns:
                df['symbol'] = df['pair']
            else:
                # Create default symbol names
                df['symbol'] = [f'SYMBOL_{i}' for i in range(len(df))]
        
        # Ensure we have a price/close column
        if 'price' not in df.columns:
            if 'close' in df.columns:
                df['price'] = df['close']
            else:
                # Try to find any price column
                price_cols = [col for col in df.columns if 'price' in col.lower() or 'close' in col.lower()]
                if price_cols:
                    df['price'] = df[price_cols[0]]
                else:
                    df['price'] = 0.0
        
        # Make predictions using the pre-calculated features
        df_with_predictions = self.process_predictions(df)

        filtered_df = self.get_filtered_signals(df_with_predictions)
        
        # Generate clean summary
        self.generate_clean_summary(df_with_predictions, filtered_df)
        
        # Create predictions dict with trimmed data using config values
        predictions = {}
        
        for _, row in filtered_df.iterrows():
            symbol = row['symbol']
            confidence = float(row['model_confidence'])

            volume = self.volume_manager.calculate_volume(confidence)

            predictions[symbol] = {
                'prediction': int(row['model_signal']),
                'probability': float(row['model_confidence']),
                'confidence': float(row['model_confidence']),
                'signal_strength': row['signal_strength'],
                'timestamp': row.get('timestamp', ''),
                'price': float(row.get('price', 0)),
                'symbol': symbol,
                'model_type': self.predictor_config.get('model_type', 'SHORT'),
                'model_file': self.predictor_config.get('model_file', self.CONFIG['model_file']),
                'min_confidence': self.predictor_config.get('min_confidence', self.CONFIG['min_confidence']),
                'features_present': all(feat in row for feat in self.CONFIG['features']),
                'comment': f"{self.predictor_config.get('comment', 'ML Model Signal')} {(row['model_confidence']):.2f}",
                'magic': self.predictor_config.get('magic', 100000),
                'volume': volume
            }
        
            print(f"{self.predictor_config.get('comment', 'ML Model Signal')} - {float(row['model_confidence']):.2f}",)
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
