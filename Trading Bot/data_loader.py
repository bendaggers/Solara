"""
Data Loader - Simple CSV Loader
MINIMAL VERSION: Only loads data, no processing
"""

import pandas as pd
import os


class DataLoader:
    """Minimal CSV loader - just reads data and returns it"""
    
    def __init__(self, data_path=None):
        self.data_path = data_path
    
    def load(self):
        """
        Load CSV data (MINIMAL - just reads and returns)
        Returns: DataFrame with raw data
        """
        if not self.data_path:
            raise Exception("No data path provided")
        
        if not os.path.exists(self.data_path):
            raise Exception(f"Data file not found: {self.data_path}")
        
        try:
            # Load CSV file - NO PROCESSING
            df = pd.read_csv(self.data_path)
            
            print(f"✅ Loaded {len(df)} rows from {self.data_path}")
            # print(f"📊 Shape: {df.shape}")
            
            return df
            
        except pd.errors.EmptyDataError:
            raise Exception(f"CSV file is empty: {self.data_path}")
        except pd.errors.ParserError as e:
            raise Exception(f"Error parsing CSV: {str(e)}")
        except Exception as e:
            raise Exception(f"Error loading CSV: {str(e)}")
    
    def get_symbols(self, df):
        """
        Get list of symbols from data (optional helper)
        """
        if 'pair' in df.columns:
            return df['pair'].unique().tolist()
        elif 'symbol' in df.columns:
            return df['symbol'].unique().tolist()
        return []
    
    def detect_timeframe(self, df=None):
        """
        Try to detect timeframe from filename (optional helper)
        """
        if self.data_path:
            filename = os.path.basename(self.data_path).lower()
            if 'h4' in filename:
                return 'H4'
            elif 'h1' in filename:
                return 'H1'
            elif 'd1' in filename:
                return 'D1'
            elif 'w1' in filename:
                return 'W1'
            elif 'm15' in filename:
                return 'M15'
            elif 'm30' in filename:
                return 'M30'
            elif 'm5' in filename:
                return 'M5'
            elif 'm1' in filename:
                return 'M1'
        return None


# Even simpler version if you want it super minimal
class SimpleDataLoader:
    """Ultra-minimal CSV loader"""
    
    @staticmethod
    def load_csv(filepath):
        """
        Just load the CSV, that's it
        """
        return pd.read_csv(filepath)


# Usage examples
if __name__ == "__main__":
    # Option 1: Use the class
    loader = DataLoader(data_path="marketdata_H4.csv")
    df = loader.load()
    
    # Option 2: Just use pandas directly (simplest)
    df = pd.read_csv("marketdata_H4.csv")