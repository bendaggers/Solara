"""
Base Preprocessor - The Blueprint
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
        Validate that data can be processed
        Default implementation checks required_features
        
        Args:
            data_dict: dict with symbol data
        Returns:
            bool: True if valid, raises ValueError if not
        """
        if not self.required_features:
            # If no required features specified, assume all valid
            return True
            
        missing_features = []
        for feature in self.required_features:
            if feature not in data_dict:
                missing_features.append(feature)
        
        if missing_features:
            raise ValueError(f"Missing required features: {missing_features}")
        
        return True
    
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
    
    def get_feature_info(self):
        """
        Get information about features (optional)
        Returns: dict with feature information
        """
        return {
            'required_features': self.required_features.copy(),
            'feature_names': self.feature_names.copy(),
            'total_features': len(self.feature_names)
        }