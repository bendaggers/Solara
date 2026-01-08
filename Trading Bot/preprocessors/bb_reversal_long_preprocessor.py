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


class LongPreprocessor(BasePreprocessor):
    """Preprocessor for long entry model predictions"""
    
    def __init__(self):
        super().__init__()
        # Define features required by the long model
        self.required_features = [
            'rsi_value',
            'bb_position',
            'bb_width_pct',
            'volume_ratio',
            'candle_body_pct',
            'atr_pct',
            'trend_strength',
            'previous_touches',
            'time_since_last_touch',
            'session'
        ]
        
        # Define feature names for model input
        self.feature_names = [
            'rsi',
            'bb_pos',
            'bb_width',
            'volume_ratio',
            'candle_body',
            'atr',
            'trend',
            'prev_touches',
            'time_since_touch',
            'session'
        ]
    
    def process(self, raw_data):
        """
        Process raw JSON data for long model prediction
        Args:
            raw_data: dict from DataLoader
        Returns: dict with processed data for each symbol
        """
        processed_symbols = {}
        
        for symbol_data in raw_data['data']:
            symbol = symbol_data['pair']
            
            # Validate required features
            self.validate_features(symbol_data)
            
            # Extract and process features
            features = self.extract_features(symbol_data)
            
            # Handle missing values
            features = self.handle_missing_values(features)
            
            # Normalize features (if needed)
            features = self.normalize_features(features)
            
            # Convert to array in correct order
            feature_array = self.to_feature_array(features)
            
            # Store processed data
            processed_symbols[symbol] = {
                'features': feature_array,
                'feature_names': self.feature_names,
                'timestamp': symbol_data['timestamp'],
                'price': symbol_data['close']
            }
        
        return processed_symbols
    
    def extract_features(self, symbol_data):
        """Extract and transform features from raw data"""
        features = {}
        
        # Direct mapping for most features
        feature_map = {
            'rsi': 'rsi_value',
            'bb_pos': 'bb_position',
            'bb_width': 'bb_width_pct',
            'volume_ratio': 'volume_ratio',
            'candle_body': 'candle_body_pct',
            'atr': 'atr_pct',
            'trend': 'trend_strength',
            'prev_touches': 'previous_touches',
            'time_since_touch': 'time_since_last_touch',
            'session': 'session'
        }
        
        for new_name, old_name in feature_map.items():
            features[new_name] = symbol_data.get(old_name)
        
        return features
    
    def normalize_features(self, features_dict):
        """Apply normalization to specific features"""
        normalized = features_dict.copy()
        
        # Normalize RSI from 0-100 to 0-1
        if 'rsi' in normalized and normalized['rsi'] is not None:
            normalized['rsi'] = normalized['rsi'] / 100.0
        
        # Normalize session (1,2,3) to one-hot encoding
        if 'session' in normalized and normalized['session'] is not None:
            # Convert to one-hot: [London, NY, Asian]
            session = int(normalized['session'])
            normalized['session_london'] = 1 if session == 1 else 0
            normalized['session_ny'] = 1 if session == 2 else 0
            normalized['session_asian'] = 1 if session == 3 else 0
        
        return normalized
    
    def to_feature_array(self, features_dict):
        """Convert features dict to numpy array in correct order"""
        # Update feature names if we added one-hot encoded session
        if 'session_london' in features_dict:
            self.feature_names = [
                'rsi', 'bb_pos', 'bb_width', 'volume_ratio', 'candle_body',
                'atr', 'trend', 'prev_touches', 'time_since_touch',
                'session_london', 'session_ny', 'session_asian'
            ]
        
        # Create array in correct order
        feature_array = []
        for feature_name in self.feature_names:
            if feature_name in features_dict:
                feature_array.append(features_dict[feature_name])
            else:
                feature_array.append(0.0)  # Default value
        
        return np.array(feature_array, dtype=np.float32)