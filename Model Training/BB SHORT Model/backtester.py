import pandas as pd
import numpy as np
import pickle
import json
import os
from pathlib import Path
import sys

# Add current directory to path to import pipeline
sys.path.append('.')

try:
    from pipeline import DataPipeline
    PIPELINE_AVAILABLE = True
    print("✓ Successfully imported DataPipeline from pipeline.py")
except ImportError as e:
    print(f"❌ Error importing pipeline: {e}")
    PIPELINE_AVAILABLE = False


class BollingerBandsPredictor:
    """
    Predictor that uses your existing DataPipeline for feature calculation.
    """
    
    def __init__(self):
        """
        Initialize predictor with hardcoded file paths.
        """
        # Define hardcoded paths
        self.base_path = r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Model Training\BB SHORT Model"
        
        self.model_path = os.path.join(self.base_path, "BB_SHORT_REVERSAL_Model.pkl")
        self.feature_columns_path = os.path.join(self.base_path, "feature_columns.txt")
        self.model_info_path = os.path.join(self.base_path, "model_info.json")
        self.input_csv = os.path.join(self.base_path, "GBPUSD_2024-2025.csv")
        
        print("="*60)
        print("BOLLINGER BANDS SHORT PREDICTOR")
        print("="*60)
        print(f"Base path: {self.base_path}")
        print(f"Model: {self.model_path}")
        print(f"Input data: {self.input_csv}")
        
        self.model = None
        self.feature_columns = None
        self.model_info = None
        self.optimal_threshold = 0.5357
        self.pipeline = None
        self.model_metadata = None  # To store the full dictionary
        
        # Initialize pipeline if available
        if PIPELINE_AVAILABLE:
            self.pipeline = DataPipeline()
            print("✓ DataPipeline initialized for feature calculation")
        
        # Load model and metadata
        self.load_model()
        self.load_feature_columns()
        self.load_model_info()
        
        # Check if input file exists
        if not os.path.exists(self.input_csv):
            print(f"\n❌ ERROR: Input file not found!")
            print(f"Looking for: {self.input_csv}")
            print("\nAvailable files in directory:")
            for file in os.listdir(self.base_path):
                if file.endswith('.csv'):
                    print(f"  - {file}")
            raise FileNotFoundError(f"Input file not found: {self.input_csv}")
    
    def load_model(self):
        """Load trained model from pickle file - handles dictionary format."""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
        print(f"Loading model from {self.model_path}...")
        with open(self.model_path, 'rb') as f:
            loaded_data = pickle.load(f)
        
        print(f"Loaded object type: {type(loaded_data)}")
        
        # Check if it's a dictionary (as saved by your training script)
        if isinstance(loaded_data, dict):
            print("✓ Detected dictionary format (as expected from training script)")
            self.model_metadata = loaded_data  # Save full metadata
            
            # Extract the model from the dictionary
            if 'model' in loaded_data:
                self.model = loaded_data['model']
                print("✓ Extracted model from dictionary['model']")
            else:
                # Try other possible keys
                for key in ['estimator', 'classifier', 'rf_model', 'random_forest']:
                    if key in loaded_data:
                        self.model = loaded_data[key]
                        print(f"✓ Extracted model from dictionary['{key}']")
                        break
            
            # Also extract feature names if available
            if 'feature_names' in loaded_data:
                self.feature_columns = loaded_data['feature_names']
                print(f"✓ Loaded {len(self.feature_columns)} feature names from metadata")
        else:
            # Assume it's the model itself
            self.model = loaded_data
            print("✓ Loaded model directly (not a dictionary)")
        
        if self.model is None:
            raise ValueError("Could not extract model from pickle file")
        
        print(f"✓ Model type: {type(self.model)}")
        
        # Verify the model has predict method
        if hasattr(self.model, 'predict'):
            print("✓ Model has 'predict' method")
        else:
            raise ValueError("Loaded object doesn't have 'predict' method")
    
    def load_feature_columns(self):
        """Load feature columns from text file."""
        # If we already loaded feature columns from model metadata, use those
        if self.feature_columns is not None:
            print(f"Using {len(self.feature_columns)} feature columns from model metadata")
            return
            
        if not os.path.exists(self.feature_columns_path):
            print(f"Warning: Feature columns file not found: {self.feature_columns_path}")
            
            # Try to get feature names from model if available
            if hasattr(self.model, 'feature_names_in_'):
                self.feature_columns = list(self.model.feature_names_in_)
                print(f"  Using {len(self.feature_columns)} features from model.feature_names_in_")
            else:
                # Use known features from your training
                self.feature_columns = [
                    'ret_lag1', 'rsi_slope_lag3', 'rsi_slope_lag1', 'ret_lag3',
                    'close_pos_in_candle_lag3', 'rsi_slope_lag2', 'close_pos_in_candle_lag2',
                    'RSI_slope_3', 'close_pos_in_candle_lag1', 'ret_lag2',
                    'price_slope_3', 'body_size_lag2', 'bb_position_lag2', 'body_size_lag3',
                    'body_vs_bb_lag2', 'bb_position_lag3', 'body_vs_bb_lag1', 'bb_position_lag1',
                    'body_vs_bb_lag3', 'dist_bb_upper_lag2'
                ]
                print(f"  Using {len(self.feature_columns)} default features")
        else:
            with open(self.feature_columns_path, 'r') as f:
                self.feature_columns = [line.strip() for line in f if line.strip()]
            print(f"✓ Loaded {len(self.feature_columns)} feature columns from file")
    
    def load_model_info(self):
        """Load model metadata from JSON file."""
        if os.path.exists(self.model_info_path):
            with open(self.model_info_path, 'r') as f:
                self.model_info = json.load(f)
            
            # Update optimal threshold if available in model_info
            if 'optimal_threshold' in self.model_info:
                self.optimal_threshold = self.model_info['optimal_threshold']
                print(f"✓ Using optimal threshold from model_info: {self.optimal_threshold}")
            else:
                print(f"Using default threshold: {self.optimal_threshold}")
        else:
            print(f"⚠ Model info file not found. Using default threshold: {self.optimal_threshold}")
    
    def create_features(self, df):
        """
        Create features using DataPipeline.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with calculated features
        """
        if not PIPELINE_AVAILABLE or self.pipeline is None:
            raise ValueError("DataPipeline not available. Cannot calculate features.")
        
        print("\n" + "="*50)
        print("CREATING FEATURES USING DATAPIPELINE")
        print("="*50)
        
        # Use the pipeline's data loading and feature creation
        try:
            # First load the data into pipeline
            self.pipeline.data = df.copy()
            
            # Create features
            self.pipeline.create_features()
            
            features_df = self.pipeline.features
            
            print(f"✓ Generated {features_df.shape[1]} columns")
            print(f"✓ Features shape: {features_df.shape}")
            
            return features_df
            
        except Exception as e:
            print(f"❌ Error creating features with pipeline: {e}")
            raise
    
    def prepare_features(self, df):
        """
        Prepare features for prediction.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Tuple of (feature_matrix, available_features, processed_df)
        """
        print("\n" + "="*50)
        print("PREPARING FEATURES FOR PREDICTION")
        print("="*50)
        
        # Check what columns we have
        print(f"Input data columns: {list(df.columns)}")
        
        # Determine if we have OHLC data or pre-calculated features
        has_ohlc = all(col in df.columns for col in ['open', 'high', 'low', 'close'])
        has_some_features = any('lag' in col for col in df.columns)
        
        if has_some_features:
            print("✓ Found some pre-calculated features")
            processed_df = df.copy()
        elif has_ohlc:
            print("✓ Found OHLC data, creating features...")
            processed_df = self.create_features(df)
        else:
            raise ValueError("Data must contain either OHLC columns or pre-calculated features")
        
        # Check which features we have available
        available_features = []
        missing_features = []
        
        for feature in self.feature_columns:
            if feature in processed_df.columns:
                available_features.append(feature)
            else:
                missing_features.append(feature)
        
        print(f"\nFeature Analysis:")
        print(f"  Available: {len(available_features)}/{len(self.feature_columns)}")
        print(f"  Missing: {len(missing_features)}")
        
        if missing_features:
            print(f"  First 5 missing: {missing_features[:5]}")
            print(f"  Note: Model was trained with {len(self.feature_columns)} features")
            
        if not available_features:
            raise ValueError("No required features found in data!")
        
        # Create feature matrix
        X = processed_df[available_features].copy()
        
        # Handle missing values
        nan_count = X.isna().sum().sum()
        if nan_count > 0:
            print(f"⚠ Found {nan_count} NaN values. Filling with 0...")
            X = X.fillna(0)
        
        # Handle infinite values
        inf_count = np.isinf(X.values).sum()
        if inf_count > 0:
            print(f"⚠ Found {inf_count} infinite values. Replacing with 0...")
            X = X.replace([np.inf, -np.inf], 0)
        
        print(f"✓ Feature matrix shape: {X.shape}")
        
        return X, available_features, processed_df
    
    def get_signal_strength(self, probability):
        """Convert probability to signal strength."""
        if probability < self.optimal_threshold:
            return "No Signal"
        elif probability < 0.6:
            return "Moderate"
        elif probability < 0.8:
            return "Strong"
        else:
            return "Very Strong"
    
    def make_predictions(self):
        """
        Main function to load data and make predictions.
        """
        print("\n" + "="*60)
        print("LOADING DATA")
        print("="*60)
        
        # Load the data
        print(f"Loading {self.input_csv}...")
        df = pd.read_csv(self.input_csv)
        
        print(f"✓ Loaded {len(df)} rows, {df.shape[1]} columns")
        print(f"Data columns: {list(df.columns)}")
        
        # Prepare features
        X, available_features, processed_df = self.prepare_features(df)
        
        print("\n" + "="*60)
        print("MAKING PREDICTIONS")
        print("="*60)
        
        # Get probabilities
        if hasattr(self.model, 'predict_proba'):
            probabilities = self.model.predict_proba(X)[:, 1]
            print("✓ Generated probability predictions")
        else:
            predictions = self.model.predict(X)
            probabilities = predictions.astype(float)
            print("⚠ Using binary predictions (no probabilities available)")
        
        # Add predictions to dataframe
        processed_df['prediction_probability'] = probabilities
        processed_df['prediction_binary'] = (probabilities >= self.optimal_threshold).astype(int)
        processed_df['signal_strength'] = [self.get_signal_strength(p) for p in probabilities]
        
        print(f"✓ Added prediction columns to dataframe")
        
        return processed_df
    
    def save_results(self, results_df):
        """
        Save prediction results to CSV files.
        """
        print("\n" + "="*60)
        print("SAVING RESULTS")
        print("="*60)
        
        # Create output filenames
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        
        # Full results
        output_full = os.path.join(self.base_path, f"GBPUSD_2024-2025_predictions_{timestamp}.csv")
        results_df.to_csv(output_full, index=False)
        print(f"✓ Full results saved to: {output_full}")
        
        # Simple results (key columns only)
        simple_cols = []
        for col in ['timestamp', 'open', 'high', 'low', 'close', 
                   'prediction_probability', 'prediction_binary', 'signal_strength']:
            if col in results_df.columns:
                simple_cols.append(col)
        
        if simple_cols:
            output_simple = os.path.join(self.base_path, f"GBPUSD_2024-2025_predictions_simple_{timestamp}.csv")
            results_df[simple_cols].to_csv(output_simple, index=False)
            print(f"✓ Simple results saved to: {output_simple}")
        
        # Summary file
        summary_path = os.path.join(self.base_path, f"prediction_summary_{timestamp}.txt")
        self.create_summary(results_df, summary_path)
        
        return output_full
    
    def create_summary(self, df, summary_path):
        """Create a summary text file."""
        with open(summary_path, 'w') as f:
            f.write("="*60 + "\n")
            f.write("BOLLINGER BANDS SHORT PREDICTIONS SUMMARY\n")
            f.write("="*60 + "\n\n")
            
            f.write(f"Data file: {self.input_csv}\n")
            f.write(f"Total samples: {len(df)}\n")
            f.write(f"Prediction date: {pd.Timestamp.now()}\n")
            f.write(f"Threshold: {self.optimal_threshold}\n\n")
            
            if self.model_metadata:
                f.write("MODEL METADATA:\n")
                f.write(f"  Training date: {self.model_metadata.get('training_date', 'Unknown')}\n")
                f.write(f"  Train shape: {self.model_metadata.get('train_shape', 'Unknown')}\n")
                f.write(f"  Test shape: {self.model_metadata.get('test_shape', 'Unknown')}\n\n")
            
            # Short signals
            short_signals = df['prediction_binary'].sum()
            short_pct = short_signals / len(df) * 100
            f.write(f"SHORT SIGNALS:\n")
            f.write(f"  Total: {short_signals} ({short_pct:.1f}%)\n\n")
            
            # Signal strength distribution
            f.write(f"SIGNAL STRENGTH DISTRIBUTION:\n")
            for strength in ['Very Strong', 'Strong', 'Moderate', 'No Signal']:
                count = (df['signal_strength'] == strength).sum()
                pct = count / len(df) * 100
                f.write(f"  {strength:12s}: {count:5d} ({pct:5.1f}%)\n")
            
            # Probability statistics
            if 'prediction_probability' in df.columns:
                probs = df['prediction_probability']
                f.write(f"\nPROBABILITY STATISTICS:\n")
                f.write(f"  Mean: {probs.mean():.3f}\n")
                f.write(f"  Min:  {probs.min():.3f}\n")
                f.write(f"  Max:  {probs.max():.3f}\n")
                f.write(f"  Std:  {probs.std():.3f}\n")
        
        print(f"✓ Summary saved to: {summary_path}")
    
    def print_results_summary(self, df):
        """Print summary to console."""
        print("\n" + "="*60)
        print("PREDICTION RESULTS SUMMARY")
        print("="*60)
        
        print(f"\nData file: {os.path.basename(self.input_csv)}")
        print(f"Total samples: {len(df)}")
        
        if self.model_metadata:
            print(f"Model trained on: {self.model_metadata.get('training_date', 'Unknown')}")
        
        # Short signals
        short_signals = df['prediction_binary'].sum()
        short_pct = short_signals / len(df) * 100
        print(f"\nShort signals predicted: {short_signals} ({short_pct:.1f}%)")
        
        # Signal strength
        print(f"\nSignal Strength Distribution:")
        for strength in ['Very Strong', 'Strong', 'Moderate', 'No Signal']:
            count = (df['signal_strength'] == strength).sum()
            pct = count / len(df) * 100
            print(f"  {strength:12s}: {count:5d} ({pct:5.1f}%)")
        
        # Sample predictions
        print(f"\nSample predictions (first 10 rows):")
        sample_cols = []
        for col in ['timestamp', 'close', 'prediction_probability', 'prediction_binary', 'signal_strength']:
            if col in df.columns:
                sample_cols.append(col)
        
        if sample_cols:
            print(df[sample_cols].head(10).to_string(index=False))
    
    def run(self):
        """
        Run the complete prediction pipeline.
        """
        print("\n" + "="*60)
        print("STARTING PREDICTION PIPELINE")
        print("="*60)
        
        try:
            # Make predictions
            results_df = self.make_predictions()
            
            # Save results
            output_file = self.save_results(results_df)
            
            # Print summary
            self.print_results_summary(results_df)
            
            print("\n" + "="*60)
            print("PREDICTION COMPLETE!")
            print("="*60)
            print(f"\nOutput files created:")
            print(f"  1. Full predictions: {os.path.basename(output_file)}")
            print(f"  2. Simple predictions: GBPUSD_2024-2025_predictions_simple_*.csv")
            print(f"  3. Summary: prediction_summary_*.txt")
            
            return results_df
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return None


# Main execution
if __name__ == "__main__":
    # Create and run predictor
    predictor = BollingerBandsPredictor()
    results = predictor.run()
    
    if results is not None:
        print("\n✅ Prediction pipeline completed successfully!")
    else:
        print("\n❌ Prediction pipeline failed!")