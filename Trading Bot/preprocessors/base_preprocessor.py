"""
Base Preprocessor - The Blueprint

Think of this as the architectural blueprint that all specialized 
preprocessors follow. It defines the fundamental operations every data 
preprocessor needs: checking for missing information, organizing features, 
and providing a consistent structure. Other preprocessors (like the 
BB reversal one) inherit from this blueprint, adding their specific 
requirements while keeping the core functionality consistent. It's the 
foundation that ensures all data preparation follows the same quality 
standards, much like how all houses in a neighborhood follow the same 
building codes while having unique interior designs.
"""

import pandas as pd
import numpy as np


class BasePreprocessor:
    """Base class for all data preprocessors"""
    
    def __init__(self):
        self.required_features = []
        self.feature_names = []
    
    def process(self, raw_data):
        """
        Main processing method - to be implemented by subclasses
        Args:
            raw_data: dict from DataLoader
        Returns: processed data ready for model prediction
        """
        raise NotImplementedError("Subclasses must implement process() method")
    
    def validate_features(self, data_dict):
        """
        Validate that all required features are present
        Args:
            data_dict: dict with symbol data
        """
        missing_features = []
        for feature in self.required_features:
            if feature not in data_dict:
                missing_features.append(feature)
        
        if missing_features:
            raise ValueError(f"Missing required features: {missing_features}")
    
    def normalize_features(self, features_dict):
        """
        Normalize features (optional - implement in subclasses if needed)
        Args:
            features_dict: dict of features
        Returns: normalized features
        """
        # Default implementation - no normalization
        return features_dict
    
    def handle_missing_values(self, features_dict):
        """
        Handle missing values in features
        Args:
            features_dict: dict of features
        Returns: features with missing values handled
        """
        processed = {}
        for key, value in features_dict.items():
            if value is None or (isinstance(value, float) and np.isnan(value)):
                # Default handling: use 0 for missing values
                processed[key] = 0.0
            else:
                processed[key] = value
        
        return processed