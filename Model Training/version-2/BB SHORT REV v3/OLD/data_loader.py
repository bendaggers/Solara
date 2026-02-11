"""
data_loader.py

Loads the raw csv and returns it as dataframe
"""

import pandas as pd
import os
from datetime import datetime


class DataLoader:
    """Data loader class for processing raw data."""
    
    def __init__(self, data_dir: str = 'data'):
        """
        Initialize DataLoader class.
        
        Args:
            data_dir: Directory containing data files, defaults to 'data'
        """
        self.data_dir = data_dir
        self.df = None
        self.csv_filename = 'your_data.csv'  # Default hardcoded filename
        
    def load_csv_to_dataframe(self, file_path: str = None, 
                             timestamp_column: str = 'timestamp',
                             timestamp_format: str = '%Y.%m.%d %H:%M:%S',
                             sort_ascending: bool = True) -> pd.DataFrame:
        """
        Load a CSV file into a pandas DataFrame with timestamp conversion and sorting.
        
        Args:
            file_path: Full path to CSV file or just filename. 
                      If provided, uses exact path. If None, uses default filename in data_dir.
            timestamp_column: Name of the timestamp column (default: 'timestamp')
            timestamp_format: Format string for parsing timestamps (default: '%Y.%m.%d %H:%M:%S')
            sort_ascending: If True, sort from oldest to newest (default: True)
            
        Returns:
            pandas.DataFrame: The loaded DataFrame with converted timestamps
        """
        if file_path:
            # Use the provided path directly
            filepath = file_path
        else:
            # Use default filename in the configured data directory
            filepath = os.path.join(self.data_dir, self.csv_filename)
        
        print(f"Loading data from: {filepath}")
        
        # Load the CSV file into a DataFrame
        df = pd.read_csv(filepath)
        
        # Store original shape
        original_shape = df.shape
        print(f"   Raw data shape: {original_shape}")
        
        # Convert timestamp if column exists
        if timestamp_column in df.columns:
            df = self._convert_timestamp(df, timestamp_column, timestamp_format)
            
            # Sort by timestamp
            df = self._sort_by_timestamp(df, timestamp_column, sort_ascending)
        else:
            print(f"   ⚠ Warning: '{timestamp_column}' column not found. No timestamp conversion performed.")
        
        # Store the processed DataFrame
        self.df = df
        
        # Print summary
        print(f"   Processed data shape: {df.shape}")
        
        if timestamp_column in df.columns:
            print(f"   Date range: {df[timestamp_column].min()} to {df[timestamp_column].max()}")
            print(f"   Total time period: {(df[timestamp_column].max() - df[timestamp_column].min()).days} days")
        
        return df
    
    def _convert_timestamp(self, df: pd.DataFrame, timestamp_column: str, 
                          timestamp_format: str) -> pd.DataFrame:
        """
        Convert timestamp column to pandas datetime.
        
        Args:
            df: Input DataFrame
            timestamp_column: Name of the timestamp column
            timestamp_format: Format string for parsing
            
        Returns:
            DataFrame with converted timestamp column
        """
        print(f"   Converting timestamp column '{timestamp_column}'...")
        
        # Check current dtype
        original_dtype = df[timestamp_column].dtype
        print(f"     Original dtype: {original_dtype}")
        
        # Convert to datetime
        try:
            # Try parsing with specified format
            df[timestamp_column] = pd.to_datetime(df[timestamp_column], 
                                                  format=timestamp_format)
            print(f"     ✓ Successfully parsed with format: {timestamp_format}")
        except ValueError as e:
            print(f"     ⚠ Format '{timestamp_format}' failed: {e}")
            print(f"     Trying automatic parsing...")
            
            # Try automatic parsing
            df[timestamp_column] = pd.to_datetime(df[timestamp_column], 
                                                  errors='coerce')
            
            # Check for NaT values (failed conversions)
            nat_count = df[timestamp_column].isna().sum()
            if nat_count > 0:
                print(f"     ⚠ Warning: {nat_count} timestamps failed to parse")
            
            print(f"     ✓ Automatic parsing completed")
        
        # Check for duplicate timestamps
        duplicates = df[timestamp_column].duplicated().sum()
        if duplicates > 0:
            print(f"     ⚠ Warning: {duplicates} duplicate timestamps found")
        
        return df
    
    def _sort_by_timestamp(self, df: pd.DataFrame, timestamp_column: str, 
                          ascending: bool = True) -> pd.DataFrame:
        """
        Sort DataFrame by timestamp column.
        
        Args:
            df: Input DataFrame
            timestamp_column: Name of the timestamp column
            ascending: If True, sort from oldest to newest
            
        Returns:
            Sorted DataFrame
        """
        direction = "oldest to newest" if ascending else "newest to oldest"
        print(f"   Sorting by '{timestamp_column}' ({direction})...")
        
        # Sort the DataFrame
        df = df.sort_values(by=timestamp_column, ascending=ascending).reset_index(drop=True)
        
        # Verify sorting
        if ascending:
            is_sorted = df[timestamp_column].is_monotonic_increasing
        else:
            is_sorted = df[timestamp_column].is_monotonic_decreasing
        
        if is_sorted:
            print(f"     ✓ Successfully sorted {direction}")
        else:
            print(f"     ⚠ Warning: DataFrame may not be properly sorted")
        
        return df
    
    def check_data_quality(self, df: pd.DataFrame = None) -> dict:
        """
        Check data quality issues.
        
        Args:
            df: DataFrame to check (uses self.df if None)
            
        Returns:
            Dictionary with data quality metrics
        """
        if df is None:
            df = self.df
        
        if df is None:
            return {"error": "No data loaded"}
        
        quality_report = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'missing_values': {},
            'data_types': {},
            'timestamp_info': {}
        }
        
        # Check for missing values
        missing = df.isnull().sum()
        quality_report['missing_values'] = missing[missing > 0].to_dict()
        
        # Get data types
        quality_report['data_types'] = df.dtypes.astype(str).to_dict()
        
        # Check timestamp column if it exists
        if 'timestamp' in df.columns:
            timestamp_col = df['timestamp']
            quality_report['timestamp_info'] = {
                'min_date': timestamp_col.min(),
                'max_date': timestamp_col.max(),
                'date_range_days': (timestamp_col.max() - timestamp_col.min()).days,
                'is_sorted': timestamp_col.is_monotonic_increasing,
                'has_duplicates': timestamp_col.duplicated().sum() > 0,
                'has_missing': timestamp_col.isna().sum() > 0
            }
        
        return quality_report
    
    def get_sample_data(self, n_samples: int = 5) -> pd.DataFrame:
        """
        Get sample rows from the loaded data.
        
        Args:
            n_samples: Number of sample rows to return
            
        Returns:
            DataFrame with sample rows
        """
        if self.df is None:
            raise ValueError("No data loaded. Call load_csv_to_dataframe first.")
        
        return self.df.head(n_samples)
    
    def get_data_info(self) -> str:
        """
        Get string summary of the loaded data.
        
        Returns:
            String with data information
        """
        if self.df is None:
            return "No data loaded"
        
        info_lines = [
            f"Data Shape: {self.df.shape}",
            f"Columns: {list(self.df.columns)}",
            f"Memory Usage: {self.df.memory_usage(deep=True).sum() / 1024**2:.2f} MB"
        ]
        
        if 'timestamp' in self.df.columns:
            info_lines.append(f"Date Range: {self.df['timestamp'].min()} to {self.df['timestamp'].max()}")
            info_lines.append(f"Time Period: {(self.df['timestamp'].max() - self.df['timestamp'].min()).days} days")
        
        return "\n".join(info_lines)


# Example usage function
def example_usage():
    """Example of how to use the DataLoader."""
    
    # Initialize the data loader
    loader = DataLoader(data_dir='data')
    
    # Example 1: Load with default timestamp conversion
    print("Example 1: Loading data with timestamp conversion")
    print("-" * 50)
    
    # Load data (using your timestamp format)
    df = loader.load_csv_to_dataframe(
        timestamp_format='%Y.%m.%d %H:%M:%S',  # Your format
        sort_ascending=True
    )
    
    # Check data quality
    quality = loader.check_data_quality()
    print("\nData Quality Report:")
    print(f"  Total rows: {quality['total_rows']}")
    print(f"  Total columns: {quality['total_columns']}")
    
    if quality['timestamp_info']:
        print(f"  Date range: {quality['timestamp_info']['min_date']} to {quality['timestamp_info']['max_date']}")
        print(f"  Is sorted: {quality['timestamp_info']['is_sorted']}")
    
    # Show sample data
    print("\nSample data (first 3 rows):")
    print(loader.get_sample_data(3))
    
    # Example 2: Load with different timestamp format
    print("\n\nExample 2: Different timestamp format")
    print("-" * 50)
    
    # If you had a different format, you could do:
    # df2 = loader.load_csv_to_dataframe(
    #     file_path='another_file.csv',
    #     timestamp_format='%d/%m/%Y %H:%M',  # Different format
    #     sort_ascending=True
    # )


if __name__ == "__main__":
    example_usage()