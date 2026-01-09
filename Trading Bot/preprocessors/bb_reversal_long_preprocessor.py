"""
BB Reversal Long Preprocessor - The Data Translator

This module acts as a specialized translator that takes raw market data and 
converts it into a language your AI model understands. Imagine your model 
only speaks a specific technical analysis dialect - it needs exactly 10 
features like RSI values, Bollinger Band positions, and volume ratios, all 
formatted in a particular way. The preprocessor carefully extracts these 
specific ingredients from the broader market data, normalizes them (like 
converting temperatures from Fahrenheit to Celsius), arranges them in the 
exact order the model expects, and handles any missing values gracefully. 
It's the bridge between messy real-world data and the clean, structured 
input your model was trained on.
"""

import pandas as pd
import numpy as np
from .base_preprocessor import BasePreprocessor
import config


class BBReversalLongPreprocessor(BasePreprocessor):
    """Clean preprocessor"""
    
    def __init__(self):
        super().__init__()
        self.required_features = [
            'bb_touch_strength', 'bb_position', 'rsi_value', 'rsi_divergence',
            'candle_rejection', 'candle_body_pct', 'prev_candle_body_pct',
            'prev_volume_ratio', 'price_momentum', 'time_since_last_touch'
        ]
        self.feature_names = self.required_features.copy()
    
    def process(self, raw_data):
        """Process data - minimal output"""
        processed_entries = {}
        
        for idx, symbol_data in enumerate(raw_data['data']):
            symbol = symbol_data['pair']
            unique_key = f"{symbol}_{idx}"
            
            # Validate and extract features
            self.validate_features(symbol_data)
            features = self.extract_features(symbol_data)
            feature_array = self.to_feature_array(features)
            
            if len(feature_array) != 10:
                continue
            
            processed_entries[unique_key] = {
                'features': feature_array,
                'feature_names': self.feature_names.copy(),
                'symbol': symbol,
                'timestamp': symbol_data.get('timestamp', ''),
                'price': symbol_data['close']
            }
        
        return processed_entries
    
    def extract_features(self, symbol_data):
        """Extract features"""
        features = {}
        for feature in self.required_features:
            if feature in symbol_data:
                features[feature] = symbol_data[feature]
            elif feature == 'rsi_divergence':
                features[feature] = symbol_data.get('rsi_divergence', 0)
            else:
                features[feature] = 0.0
        return features
    
    def to_feature_array(self, features_dict):
        """Convert to array"""
        return np.array([float(features_dict.get(f, 0.0)) for f in self.feature_names], 
                       dtype=np.float32)