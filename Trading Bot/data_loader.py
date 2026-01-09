"""
Data Loader - The Information Gatherer
"""

import json
import pandas as pd
from datetime import datetime
import config


class DataLoader:
    """Handles loading and basic validation of market data"""
    
    def __init__(self, data_path=None):
        self.data_path = data_path or config.DATA_PATH
        
    def load_json(self):
        """
        Load JSON data from file
        Returns: dict with market data
        """
        try:
            with open(self.data_path, 'r') as f:
                data = json.load(f)
            
            # Validate data structure
            self._validate_data(data)
            print(f"✅ Loaded data for {len(data.get('data', []))} symbols")
            
            return data
            
        except FileNotFoundError:
            raise Exception(f"Data file not found: {self.data_path}")
        except json.JSONDecodeError:
            raise Exception(f"Invalid JSON format in: {self.data_path}")
    
    def get_all_symbols(self, data):
        """
        Extract all symbols from the loaded data
        Returns: List of symbol names
        """
        symbols = []
        if 'data' in data:
            for symbol_data in data['data']:
                if 'pair' in symbol_data:
                    symbols.append(symbol_data['pair'])
        return symbols
    
    def get_symbol_data(self, data, symbol):
        """
        Get data for a specific symbol
        Returns: Dictionary with symbol data or None if not found
        """
        if 'data' in data:
            for symbol_data in data['data']:
                if symbol_data.get('pair') == symbol:
                    return symbol_data
        return None
    
    def _validate_data(self, data):
        """Validate data structure and required fields"""
        required_keys = ['timestamp', 'timeframe', 'data']
        for key in required_keys:
            if key not in data:
                raise Exception(f"Missing required key in data: {key}")
        
        # Check if data array has entries
        if not isinstance(data['data'], list) or len(data['data']) == 0:
            raise Exception("No symbol data found in JSON")
        
        # Check required fields in each symbol's data
        required_symbol_fields = ['pair', 'timestamp', 'open', 'high', 'low', 'close', 'volume']
        for symbol_data in data['data']:
            for field in required_symbol_fields:
                if field not in symbol_data:
                    raise Exception(f"Missing field {field} in symbol data: {symbol_data.get('pair', 'unknown')}")
    
    def to_dataframe(self, data):
        """
        Convert JSON data to pandas DataFrame
        Args:
            data: dict from load_json()
        Returns: pandas DataFrame
        """
        # Extract symbol data
        symbols_data = data['data']
        
        # Create DataFrame
        df = pd.DataFrame(symbols_data)
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Set index
        df.set_index(['pair', 'timestamp'], inplace=True)
        
        return df