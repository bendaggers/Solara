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


class BBReversalLongPredictor:
    """Clean predictor - minimal output, exact backtesting logic"""
    
    def __init__(self, models_path=None):
        self.models_path = models_path or config.MODELS_PATH
        self.model = None
        self.model_loaded = False
        
        # Backtesting configuration
        self.CONFIG = {
            'model_path': os.path.join(self.models_path, config.BB_REVERSAL_LONG_MODEL),
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
            'min_confidence': config.BB_MIN_CONFIDENCE,
            'min_signal_strength': config.MIN_SIGNAL_STRENGTH
        }
        
        self.SIGNAL_STRENGTH_ORDER = {
            'None': 0, 'Weak': 1, 'Medium': 2, 'Strong': 3
        }
    
    def load_model(self):
        """Load model - minimal output"""
        model_path = self.CONFIG['model_path']
        
        try:
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            self.model_loaded = True
        except Exception as e:
            raise Exception(f"Model error: {e}")
    
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
        """Process predictions - minimal output"""
        # Ensure all features exist
        for feature in self.CONFIG['features']:
            if feature not in df.columns:
                df[feature] = 0
        
        X = df[self.CONFIG['features']].fillna(0)
        
        # Get predictions
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)[:, 1]
        
        # Add prediction columns
        df['model_prediction'] = predictions
        df['model_confidence'] = probabilities
        df['model_signal_raw'] = (probabilities >= self.CONFIG['min_confidence']).astype(int)
        
        # Signal strength
        df['signal_strength'] = df['model_confidence'].apply(
            lambda x: 'Strong' if x >= 0.75 else 
                     'Medium' if x >= 0.65 else 
                     'Weak' if x >= 0.50 else 'None'
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
        
        return df[
            (df['model_signal'] == 1) & 
            (df['signal_strength_value'] >= min_strength_value) &
            (df['model_prediction'] == 1)
        ].copy()
    
    def generate_clean_summary(self, df, filtered_df):
        """Generate clean summary - minimal output"""
        total_rows = len(df)
        raw_signals = df['model_signal_raw'].sum()
        total_signals = len(filtered_df)
        
        if total_signals > 0:
            strong_count = len(filtered_df[filtered_df['signal_strength'] == 'Strong'])
            medium_count = len(filtered_df[filtered_df['signal_strength'] == 'Medium'])
            avg_confidence = filtered_df['model_confidence'].mean()
            
            print(f"📊 Signals: {total_signals} of {total_rows} setups")
            print(f"   Strong: {strong_count}, Medium: {medium_count}")
            print(f"   Avg Confidence: {avg_confidence:.1%}")
        else:
            print(f"📊 No Medium+ signals found")
    
    def predict(self, processed_data):
        """Main prediction - clean output"""
        if not self.model_loaded:
            self.load_model()
        
        # Load and process data
        df = self.load_json_data(processed_data)
        df_with_predictions = self.process_predictions(df)
        filtered_df = self.get_filtered_signals(df_with_predictions)
        
        # Generate clean summary
        self.generate_clean_summary(df_with_predictions, filtered_df)
        
        # Create predictions dict
        predictions = {}
        
        for _, row in filtered_df.iterrows():
            unique_key = row['unique_key']
            symbol = row['symbol']
            
            predictions[unique_key] = {
                'prediction': int(row['model_prediction']),
                'probability': float(row['model_confidence']),
                'confidence': float(row['model_confidence']),
                'signal_strength': row['signal_strength'],
                'timestamp': row['timestamp'],
                'price': row['price'],
                'symbol': symbol,
                'unique_key': unique_key,
                'features_used': self.CONFIG['features']
            }
        
        return predictions