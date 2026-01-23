import pandas as pd
import numpy as np
from features.feature_engineering import BollingerBandsFeatureEngineer
import pickle
import os

class DataPipeline:
    """
    Main data pipeline for Bollinger Bands Reversal Short model
    """
    
    def __init__(self, data_path: str = None):
        """
        Initialize pipeline
        
        Args:
            data_path: Path to CSV data file
        """
        self.data_path = data_path
        self.feature_engineer = BollingerBandsFeatureEngineer()
        self.data = None
        self.features = None
        
    def load_data(self, data_path: str = None):
        """
        Load data from CSV file
        
        Args:
            data_path: Path to CSV file (optional, uses self.data_path if not provided)
        """
        path = data_path or self.data_path
        if not path:
            raise ValueError("No data path provided")
        
        print(f"Loading data from {path}")
        self.data = pd.read_csv(path)
        
        # Clean up any extra columns
        self.data = self.data.loc[:, ~self.data.columns.str.contains('^Unnamed')]
        
        # Ensure timestamp is datetime
        if 'timestamp' in self.data.columns:
            self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
            self.data = self.data.sort_values('timestamp').reset_index(drop=True)
        
        # Convert label to numeric if it's string
        if 'label' in self.data.columns:
            print(f"Label column dtype before conversion: {self.data['label'].dtype}")
            print(f"Unique label values: {self.data['label'].unique()[:10]}")  # Show first 10 unique values
            
            # Convert to numeric, forcing errors to NaN
            self.data['label'] = pd.to_numeric(self.data['label'], errors='coerce')
            
            # Check if we have NaN values after conversion
            nan_count = self.data['label'].isna().sum()
            if nan_count > 0:
                print(f"Warning: {nan_count} NaN values in label after conversion")
                # Option 1: Fill NaN with 0 (assuming no signal)
                self.data['label'] = self.data['label'].fillna(0)
                # Option 2: Drop rows with NaN labels
                # self.data = self.data.dropna(subset=['label'])
            
            # Convert to integer (0 or 1)
            self.data['label'] = self.data['label'].astype(int)
            print(f"Label column dtype after conversion: {self.data['label'].dtype}")
            print(f"Label distribution: 0={sum(self.data['label']==0)}, 1={sum(self.data['label']==1)}")
        
        print(f"Data shape: {self.data.shape}")
        print(f"Columns: {list(self.data.columns)}")
        
        return self.data
    
    def create_features(self):
        """
        Create all features from loaded data
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        print("Creating features...")
        self.features = self.feature_engineer.create_all_features(self.data)
        
        # Keep original columns that might be useful
        keep_cols = ['timestamp', 'pair', 'label']
        for col in keep_cols:
            if col in self.data.columns:
                # Ensure we don't have duplicates
                if col not in self.features.columns:
                    self.features[col] = self.data[col]
        
        print(f"Features shape: {self.features.shape}")
        print(f"Number of features created: {len(self.feature_engineer.get_feature_columns())}")
        
        # Show label distribution in features
        if 'label' in self.features.columns:
            label_counts = self.features['label'].value_counts()
            print(f"Label distribution in features:")
            print(f"  0 (No Short): {label_counts.get(0, 0)}")
            print(f"  1 (Short): {label_counts.get(1, 0)}")
            if len(self.features) > 0:
                print(f"  Positive ratio: {self.features['label'].mean():.3f}")
        
        return self.features
    
    def prepare_training_data(self, test_size: float = 0.2):
        """
        Prepare train/test split (time-series aware)
        
        Args:
            test_size: Proportion of data to use for testing
            
        Returns:
            X_train, X_test, y_train, y_test, feature_names
        """
        if self.features is None:
            self.create_features()
        
        # Get feature columns
        feature_cols = self.feature_engineer.get_feature_columns()
        
        # Filter to only columns that exist
        existing_feature_cols = [col for col in feature_cols if col in self.features.columns]
        
        print(f"Using {len(existing_feature_cols)} features for training")
        print(f"Total samples with features: {len(self.features)}")
        
        # Ensure we have the label column
        if 'label' not in self.features.columns:
            raise ValueError("'label' column not found in features")
        
        # Ensure label is numeric
        if not np.issubdtype(self.features['label'].dtype, np.number):
            print("Converting label to numeric...")
            self.features['label'] = pd.to_numeric(self.features['label'], errors='coerce').fillna(0).astype(int)
        
        # Time-series split (no shuffle)
        split_idx = int(len(self.features) * (1 - test_size))
        
        X_train = self.features[existing_feature_cols].iloc[:split_idx]
        X_test = self.features[existing_feature_cols].iloc[split_idx:]
        
        y_train = self.features['label'].iloc[:split_idx]
        y_test = self.features['label'].iloc[split_idx:]
        
        # Get timestamps for reference
        if 'timestamp' in self.features.columns:
            timestamps_train = self.features['timestamp'].iloc[:split_idx]
            timestamps_test = self.features['timestamp'].iloc[split_idx:]
            print(f"Train period: {timestamps_train.min()} to {timestamps_train.max()}")
            print(f"Test period: {timestamps_test.min()} to {timestamps_test.max()}")
        
        print(f"Train shape: {X_train.shape}, Test shape: {X_test.shape}")
        
        # Check label distribution
        if len(y_train) > 0:
            print(f"Positive labels in train: {y_train.mean():.3f} ({y_train.sum()}/{len(y_train)})")
        if len(y_test) > 0:
            print(f"Positive labels in test: {y_test.mean():.3f} ({y_test.sum()}/{len(y_test)})")
        
        # Check for any NaN values in features
        print(f"NaN values in X_train: {X_train.isna().sum().sum()}")
        print(f"NaN values in X_test: {X_test.isna().sum().sum()}")
        
        return X_train, X_test, y_train, y_test, existing_feature_cols
    
    def save_features(self, output_path: str = "features_data.pkl"):
        """
        Save processed features to file
        
        Args:
            output_path: Path to save features
        """
        if self.features is None:
            raise ValueError("No features created. Call create_features() first.")
        
        with open(output_path, 'wb') as f:
            pickle.dump(self.features, f)
        
        print(f"Features saved to {output_path}")
        
    def save_feature_columns(self, output_path: str = "feature_columns.txt"):
        """
        Save feature column names to file
        
        Args:
            output_path: Path to save feature columns
        """
        feature_cols = self.feature_engineer.get_feature_columns()
        
        with open(output_path, 'w') as f:
            for col in feature_cols:
                f.write(f"{col}\n")
        
        print(f"Feature columns saved to {output_path}")
    
    def save_training_data(self, output_dir: str = "training_data"):
        """
        Save training data to CSV files for inspection
        
        Args:
            output_dir: Directory to save CSV files
        """
        if self.features is None:
            raise ValueError("No features created. Call create_features() first.")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save full features
        self.features.to_csv(f"{output_dir}/full_features.csv", index=False)
        print(f"Full features saved to {output_dir}/full_features.csv")
        
        # Save sample of features for inspection
        sample_cols = ['timestamp', 'close', 'bb_position', 'rsi_value', 'label']
        sample_cols = [col for col in sample_cols if col in self.features.columns]
        if sample_cols:
            self.features[sample_cols].head(100).to_csv(f"{output_dir}/features_sample.csv", index=False)
            print(f"Features sample saved to {output_dir}/features_sample.csv")

def main():
    """
    Main function to run the pipeline
    """
    # Initialize pipeline
    pipeline = DataPipeline()
    
    # Load data (update path to your file)
    data_path = "EURUSD_Training_Data_v1.csv"
    pipeline.load_data(data_path)
    
    # Create features
    features = pipeline.create_features()
    
    # Prepare training data
    X_train, X_test, y_train, y_test, feature_names = pipeline.prepare_training_data()
    
    # Save features for later use
    pipeline.save_features("processed_features.pkl")
    pipeline.save_feature_columns("feature_columns.txt")
    pipeline.save_training_data()
    
    # Show some statistics
    print("\n" + "="*50)
    print("FEATURE ENGINEERING COMPLETE")
    print("="*50)
    print(f"Total samples: {len(features)}")
    print(f"Feature matrix: {X_train.shape[1]} features")
    print(f"Training samples: {X_train.shape[0]}")
    print(f"Testing samples: {X_test.shape[0]}")
    
    # Show feature categories
    print(f"\nFeature Categories:")
    categories = {}
    for col in feature_names:
        if '_lag' in col:
            base = col.split('_lag')[0]
            categories[base] = categories.get(base, 0) + 1
    
    print(f"Total unique base features: {len(categories)}")
    print(f"\nTop 10 base features:")
    for base, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {base}: {count} lagged versions")
    
    return X_train, X_test, y_train, y_test, feature_names

if __name__ == "__main__":
    X_train, X_test, y_train, y_test, feature_names = main()