"""
time_splitter.py

Time-based splitting for time series data.
Never uses random splitting to avoid lookahead bias.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Union, Optional
from datetime import datetime, timedelta


class TimeSeriesSplitter:
    """
    Time-based splitting for time series data.
    
    Critical for trading ML to avoid lookahead bias.
    Never uses random splits - always respects temporal order.
    
    Methods:
    1. Simple percentage split (e.g., 80% train, 20% test)
    2. Date-based split (e.g., train before 2024-01-01, test after)
    3. Walk-forward validation (multiple train/test periods)
    """
    
    def __init__(self, 
                 date_column: str = 'timestamp',
                 sort_data: bool = True,
                 verbose: bool = False):
        """
        Initialize the time series splitter.
        
        Args:
            date_column: Name of the datetime column
            sort_data: If True, sort data by date before splitting
            verbose: If True, print detailed information
        """
        self.date_column = date_column
        self.sort_data = sort_data
        self.verbose = verbose
        
    def simple_split(self, 
                     df: pd.DataFrame, 
                     test_size: float = 0.2,
                     holdout_size: float = 0.0) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        """
        Simple time-based split by percentage.
        
        Args:
            df: DataFrame with time series data
            test_size: Proportion of data for test set (0.0 to 1.0)
            holdout_size: Proportion for holdout/validation set (0.0 to 1.0)
                         If > 0, returns (train, val, test), else (train, test)
        
        Returns:
            Tuple of DataFrames: (train, test) or (train, val, test)
        """
        if self.sort_data:
            df = df.sort_values(self.date_column).reset_index(drop=True)
        
        n_samples = len(df)
        test_start = int(n_samples * (1 - test_size - holdout_size))
        val_start = int(n_samples * (1 - holdout_size)) if holdout_size > 0 else None
        
        train = df.iloc[:test_start].copy()
        
        if holdout_size > 0:
            val = df.iloc[test_start:val_start].copy()
            test = df.iloc[val_start:].copy()
            
            if self.verbose:
                self._print_split_summary(train, val, test)
            return train, val, test
        else:
            test = df.iloc[test_start:].copy()
            
            if self.verbose:
                self._print_split_summary(train, test)
            return train, test
    
    def date_split(self, 
                   df: pd.DataFrame, 
                   split_date: Union[str, datetime],
                   val_end_date: Optional[Union[str, datetime]] = None) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        """
        Split by specific date(s).
        
        Args:
            df: DataFrame with time series data
            split_date: Date to split train/test (or train/val if val_end_date provided)
            val_end_date: If provided, creates validation set between split_date and val_end_date
        
        Returns:
            Tuple of DataFrames: (train, test) or (train, val, test)
        """
        # Convert to datetime if strings
        if isinstance(split_date, str):
            split_date = pd.to_datetime(split_date)
        if val_end_date and isinstance(val_end_date, str):
            val_end_date = pd.to_datetime(val_end_date)
        
        # Ensure date column is datetime
        df = df.copy()
        df[self.date_column] = pd.to_datetime(df[self.date_column])
        
        if val_end_date:
            # Three-way split: train, validation, test
            train = df[df[self.date_column] < split_date].copy()
            val = df[(df[self.date_column] >= split_date) & 
                     (df[self.date_column] < val_end_date)].copy()
            test = df[df[self.date_column] >= val_end_date].copy()
            
            if self.verbose:
                self._print_split_summary(train, val, test)
            return train, val, test
        else:
            # Two-way split: train, test
            train = df[df[self.date_column] < split_date].copy()
            test = df[df[self.date_column] >= split_date].copy()
            
            if self.verbose:
                self._print_split_summary(train, test)
            return train, test
    
    def walk_forward_split(self,
                          df: pd.DataFrame,
                          train_size: Union[int, str],
                          test_size: Union[int, str],
                          step_size: Union[int, str] = None,
                          n_splits: int = None) -> list:
        """
        Walk-forward validation splits.
        
        Args:
            df: DataFrame with time series data
            train_size: Size of training window (int for rows, str for time like '30D')
            test_size: Size of test window (int for rows, str for time like '7D')
            step_size: Step to move forward each iteration (defaults to test_size)
            n_splits: Number of splits to create (if None, creates maximum possible)
        
        Returns:
            List of tuples: [(train_idx1, test_idx1), (train_idx2, test_idx2), ...]
        """
        df = df.sort_values(self.date_column).reset_index(drop=True)
        
        # Convert time strings to number of rows if needed
        if isinstance(train_size, str):
            train_size = self._time_period_to_rows(df, train_size)
        if isinstance(test_size, str):
            test_size = self._time_period_to_rows(df, test_size)
        if step_size is None:
            step_size = test_size
        elif isinstance(step_size, str):
            step_size = self._time_period_to_rows(df, step_size)
        
        n_samples = len(df)
        splits = []
        
        start_train = 0
        split_count = 0
        
        while True:
            end_train = start_train + train_size
            end_test = end_train + test_size
            
            # Check if we have enough data for this split
            if end_test > n_samples:
                break
            
            # Create split indices
            train_indices = list(range(start_train, end_train))
            test_indices = list(range(end_train, end_test))
            splits.append((train_indices, test_indices))
            
            # Move forward
            start_train += step_size
            split_count += 1
            
            # Stop if we've created enough splits
            if n_splits and split_count >= n_splits:
                break
        
        if self.verbose:
            print(f"Created {len(splits)} walk-forward splits")
            print(f"Train size: {train_size} rows/bars")
            print(f"Test size: {test_size} rows/bars")
            print(f"Step size: {step_size} rows/bars")
        
        return splits
    
    def _time_period_to_rows(self, df: pd.DataFrame, time_period: str) -> int:
        """Convert time period string to approximate number of rows."""
        # Simple implementation - assumes regular time intervals
        # In practice, you might want more sophisticated logic
        time_map = {
            '1D': 1, '7D': 7, '30D': 30, '90D': 90,
            '1M': 30, '3M': 90, '6M': 180, '1Y': 365
        }
        
        if time_period in time_map:
            return time_map[time_period]
        else:
            # Try to parse
            try:
                num = int(time_period[:-1])
                unit = time_period[-1]
                if unit == 'D':
                    return num
                elif unit == 'M':
                    return num * 30
                elif unit == 'Y':
                    return num * 365
            except:
                raise ValueError(f"Unsupported time period format: {time_period}")
    
    def _print_split_summary(self, train: pd.DataFrame, *other_sets):
        """Print summary of the split."""
        total_samples = len(train) + sum(len(s) for s in other_sets)
        
        print("\n" + "="*60)
        print("TIME-BASED SPLIT SUMMARY")
        print("="*60)
        
        # Print date ranges
        print(f"\nDate Ranges:")
        print(f"  Training:   {train[self.date_column].min()} to {train[self.date_column].max()}")
        
        for i, dataset in enumerate(other_sets):
            name = ["Validation", "Test"][i] if len(other_sets) > 1 else "Test"
            print(f"  {name}:      {dataset[self.date_column].min()} to {dataset[self.date_column].max()}")
        
        # Print sample counts
        print(f"\nSample Counts:")
        print(f"  Training:   {len(train):,} samples ({len(train)/total_samples:.1%})")
        
        for i, dataset in enumerate(other_sets):
            name = ["Validation", "Test"][i] if len(other_sets) > 1 else "Test"
            print(f"  {name}:      {len(dataset):,} samples ({len(dataset)/total_samples:.1%})")
        
        # Print label distributions (if label column exists)
        if 'label' in train.columns:
            print(f"\nLabel Distribution:")
            
            sets = [("Training", train)] + [(name, dataset) for name, dataset in 
                   zip(["Validation", "Test"][:len(other_sets)], other_sets)]
            
            for name, dataset in sets:
                if 'label' in dataset.columns:
                    pos = (dataset['label'] == 1).sum()
                    neg = (dataset['label'] == 0).sum()
                    total = len(dataset)
                    print(f"  {name}:")
                    print(f"    Positive (1): {pos:,} ({pos/total:.1%})")
                    print(f"    Negative (0): {neg:,} ({neg/total:.1%})")
        
        print("="*60)
    
    def get_split_statistics(self, train: pd.DataFrame, *other_sets) -> dict:
        """
        Get detailed statistics about the split.
        
        Returns:
            Dictionary with split statistics
        """
        stats = {
            'total_samples': len(train) + sum(len(s) for s in other_sets),
            'train_samples': len(train),
            'train_percentage': len(train) / (len(train) + sum(len(s) for s in other_sets)),
            'train_date_range': (train[self.date_column].min(), train[self.date_column].max()),
        }
        
        if len(other_sets) == 1:
            stats.update({
                'test_samples': len(other_sets[0]),
                'test_percentage': len(other_sets[0]) / stats['total_samples'],
                'test_date_range': (other_sets[0][self.date_column].min(), 
                                   other_sets[0][self.date_column].max()),
            })
        elif len(other_sets) == 2:
            stats.update({
                'val_samples': len(other_sets[0]),
                'val_percentage': len(other_sets[0]) / stats['total_samples'],
                'val_date_range': (other_sets[0][self.date_column].min(), 
                                  other_sets[0][self.date_column].max()),
                'test_samples': len(other_sets[1]),
                'test_percentage': len(other_sets[1]) / stats['total_samples'],
                'test_date_range': (other_sets[1][self.date_column].min(), 
                                   other_sets[1][self.date_column].max()),
            })
        
        return stats


# Example usage function
def example_usage():
    """Example of how to use the TimeSeriesSplitter."""
    
    # Create sample data
    dates = pd.date_range(start='2020-01-01', end='2024-12-31', freq='D')
    data = pd.DataFrame({
        'timestamp': dates,
        'close': np.random.randn(len(dates)).cumsum() + 100,
        'label': np.random.choice([0, 1], len(dates), p=[0.7, 0.3])
    })
    
    print("Sample data created:")
    print(f"Shape: {data.shape}")
    print(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"Label distribution: {data['label'].value_counts().to_dict()}")
    
    # Initialize splitter
    splitter = TimeSeriesSplitter(date_column='timestamp', verbose=True)
    
    print("\n" + "="*60)
    print("EXAMPLE 1: Simple percentage split (80% train, 20% test)")
    print("="*60)
    train, test = splitter.simple_split(data, test_size=0.2)
    
    print("\n" + "="*60)
    print("EXAMPLE 2: Date-based split (train before 2024, test after)")
    print("="*60)
    train, test = splitter.date_split(data, split_date='2024-01-01')
    
    print("\n" + "="*60)
    print("EXAMPLE 3: Three-way split with validation")
    print("="*60)
    train, val, test = splitter.date_split(
        data, 
        split_date='2023-07-01',
        val_end_date='2024-01-01'
    )
    
    print("\n" + "="*60)
    print("EXAMPLE 4: Walk-forward splits")
    print("="*60)
    splits = splitter.walk_forward_split(
        data,
        train_size=365,  # 1 year of training
        test_size=90,    # 3 months of testing
        step_size=30,    # Move forward 1 month each time
        n_splits=3       # Create 3 splits
    )
    
    print(f"\nCreated {len(splits)} walk-forward splits")
    for i, (train_idx, test_idx) in enumerate(splits):
        train_dates = data.iloc[train_idx]['timestamp']
        test_dates = data.iloc[test_idx]['timestamp']
        print(f"\nSplit {i+1}:")
        print(f"  Train: {len(train_idx)} rows ({train_dates.min()} to {train_dates.max()})")
        print(f"  Test:  {len(test_idx)} rows ({test_dates.min()} to {test_dates.max()})")


if __name__ == "__main__":
    example_usage()