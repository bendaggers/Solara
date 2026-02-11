"""
main.py - VERSION 5.0 (DUAL FEATURE SELECTION SUPPORT)

Single mode can use optimizer's selected features for identical results.
Supports both TP-specific and per-config feature selection modes.
"""

import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime
from typing import Dict, Optional
import argparse

from data_loader import DataLoader
from features import FeatureEngineering
from labels import TripleBarrierLabeler
from data_splitting import TimeSeriesSplitter
from train_model import ModelTrainer
from efficient_optimizer import EfficientOptimizer  # Will be v5.0


class PipelineOrchestrator:
    """Orchestrator that can use optimizer's features."""
    
    def __init__(self, 
                tp_pips: int = 50, 
                sl_pips: int = 30, 
                max_bars: int = 18,
                data_dir: str = 'data', 
                model_dir: str = 'models',
                bb_position: float = 0.85, 
                rsi_value: int = 55,
                forced_features: Optional[list] = None,
                forced_threshold: Optional[float] = None,
                feature_selection_mode: str = 'tp_specific'):  # NEW: Track mode
        
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.data_loader = DataLoader(data_dir=data_dir)
        self.feature_engineer = FeatureEngineering()
        
        # Trading parameters
        self.tp_pips = tp_pips
        self.sl_pips = sl_pips
        self.max_bars = max_bars
        self.pip_factor = 0.0001
        
        # Signal filter
        self.bb_position = bb_position
        self.rsi_value = rsi_value
        self.volume_ratio = 1.2
        self.lower_wick = 0.001
        
        # NEW: Feature selection mode
        self.feature_selection_mode = feature_selection_mode
        
        # Forced settings from optimizer
        self.forced_features = forced_features
        self.use_forced_features = forced_features is not None
        
        self.forced_threshold = forced_threshold
        self.use_forced_threshold = forced_threshold is not None
        
        # Data storage
        self.raw_df = None
        self.features_df = None
        self.signal_df = None
        self.train_df = None
        self.test_df = None
        
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(model_dir, exist_ok=True)
        
        if self.use_forced_features:
            print(f"🔧 Will use {len(self.forced_features)} features from optimizer ({self.feature_selection_mode} mode)")
        
        if self.use_forced_threshold:
            print(f"🔧 Will use threshold: {self.forced_threshold:.3f}")
    
    def load_optimizer_config(self, config_path: str):
        """Load optimizer configuration including features and mode."""
        if not os.path.exists(config_path):
            print(f"❌ Config file not found: {config_path}")
            return False
        
        print(f"\n📖 Loading optimizer configuration...")
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Load configuration
            self.tp_pips = config['config']['tp_pips']
            self.sl_pips = config['config']['sl_pips']
            self.bb_position = config['config']['bb_position']
            self.rsi_value = config['config']['rsi_value']
            
            # Load feature selection mode
            if 'feature_selection' in config:
                self.feature_selection_mode = config['feature_selection'].get('mode', 'tp_specific')
                print(f"✅ Loaded feature selection mode: {self.feature_selection_mode}")
            elif 'feature_selection_mode' in config:
                self.feature_selection_mode = config['feature_selection_mode']
                print(f"✅ Loaded feature selection mode: {self.feature_selection_mode}")
            
            # Load threshold if available
            if 'config' in config and 'threshold' in config['config']:
                self.forced_threshold = config['config']['threshold']
                self.use_forced_threshold = True
                print(f"✅ Loaded threshold: {self.forced_threshold:.3f}")
            elif 'config' in config and 'optimal_threshold' in config['config']:
                self.forced_threshold = config['config']['optimal_threshold']
                self.use_forced_threshold = True
                print(f"✅ Loaded optimal threshold: {self.forced_threshold:.3f}")
            
            # Load features if available
            if 'selected_features' in config:
                self.forced_features = config['selected_features']
                self.use_forced_features = True
                print(f"✅ Loaded {len(self.forced_features)} features")
            elif 'features' in config:
                self.forced_features = config['features']
                self.use_forced_features = True
                print(f"✅ Loaded {len(self.forced_features)} features")
            
            print(f"   TP: {self.tp_pips}, SL: {self.sl_pips}")
            print(f"   BB Position > {self.bb_position:.2f}")
            print(f"   RSI > {self.rsi_value}")
            print(f"   Mode: {self.feature_selection_mode}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return False
    
    def find_latest_model_files(self, config_dir: str = 'optimization_results'):
        """Find the latest model files based on parameters."""
        if not os.path.exists(config_dir):
            print(f"❌ Config directory not found: {config_dir}")
            return None
        
        # Build expected filename pattern based on current parameters
        bb_str = f"{self.bb_position:.2f}".replace('.', '')
        thresh_str = f"{self.forced_threshold:.2f}".replace('.', '') if self.forced_threshold else ""
        
        # Look for files matching our parameters
        model_files = []
        for file in os.listdir(config_dir):
            if file.endswith('.pkl'):
                # Check if file matches our TP/BB/RSI
                if (f"TP{self.tp_pips:02d}" in file and 
                    f"BB{bb_str}" in file and 
                    f"RSI{self.rsi_value:02d}" in file):
                    model_files.append(os.path.join(config_dir, file))
        
        if not model_files:
            print(f"⚠️ No model files found for TP={self.tp_pips}, BB={self.bb_position:.2f}, RSI={self.rsi_value}")
            return None
        
        # Get the most recent file
        latest_file = max(model_files, key=os.path.getmtime)
        print(f"✅ Found model file: {os.path.basename(latest_file)}")
        
        # Find corresponding config file
        base_name = os.path.splitext(os.path.basename(latest_file))[0]
        config_file = os.path.join(config_dir, f"{base_name}_config.json")
        
        if os.path.exists(config_file):
            return {
                'model_path': latest_file,
                'config_path': config_file,
                'features_path': latest_file.replace('.pkl', '.csv')
            }
        else:
            print(f"⚠️ Config file not found: {config_file}")
            return {
                'model_path': latest_file,
                'config_path': None,
                'features_path': latest_file.replace('.pkl', '.csv')
            }
    
    def load_optimizer_model(self, config_dir: str = 'optimization_results'):
        """Load the actual trained model from optimizer."""
        files = self.find_latest_model_files(config_dir)
        if not files:
            return None
        
        try:
            # Load the model
            with open(files['model_path'], 'rb') as f:
                import pickle
                model = pickle.load(f)
            
            print(f"✅ Loaded optimizer model from: {os.path.basename(files['model_path'])}")
            
            # Load features if available
            if os.path.exists(files['features_path']):
                features_df = pd.read_csv(files['features_path'])
                features = features_df['feature_name'].tolist()
                print(f"✅ Loaded {len(features)} features from CSV")
            elif files['config_path'] and os.path.exists(files['config_path']):
                with open(files['config_path'], 'r') as f:
                    config = json.load(f)
                if 'features' in config:
                    features = config['features']
                elif 'selected_features' in config:
                    features = config['selected_features']
                else:
                    features = None
            else:
                features = None
            
            return {
                'model': model,
                'features': features,
                'model_path': files['model_path'],
                'config_path': files['config_path']
            }
            
        except Exception as e:
            print(f"❌ Error loading optimizer model: {e}")
            return None
    
    def run_single_pipeline(self, data_path: str, test_size: float = 0.2):
        """Run single pipeline (with optional forced features)."""
        print("\n" + "="*70)
        print("SINGLE PIPELINE RUN")
        if self.use_forced_features:
            print(f"USING OPTIMIZER'S FEATURES ({self.feature_selection_mode.upper()} MODE)")
        if self.use_forced_threshold:
            print(f"USING FORCED THRESHOLD: {self.forced_threshold:.3f}")
        print("="*70)
        
        # 1. Load and prepare data
        self.raw_df = self.data_loader.load_csv_to_dataframe(
            file_path=data_path,
            timestamp_format='%Y.%m.%d %H:%M:%S',
            sort_ascending=True
        )
        print(f"Data loaded: {self.raw_df.shape}")
        
        # 2. Calculate features
        self.features_df = self.feature_engineer.calculate_features(self.raw_df)
        self.features_df['next_bar_open'] = self.features_df['open'].shift(-1)
        print(f"Features calculated: {self.features_df.shape}")
        
        # 3. Generate labels
        labeler = TripleBarrierLabeler(
            tp_pips=self.tp_pips,
            sl_pips=self.sl_pips,
            max_bars=self.max_bars,
            pip_factor=self.pip_factor
        )
        
        labels = labeler.label_short_entries(
            self.features_df,
            entry_price_col='next_bar_open'
        )
        
        self.features_df['label'] = labels
        self.features_df = self.features_df.iloc[:-(labeler.max_bars + 1)].copy()
        self.features_df = self.features_df.drop(columns=['next_bar_open'])
        
        # 4. Filter to signal bars
        mask = (
            (self.features_df['bb_position'] > self.bb_position) &
            (self.features_df['rsi_value'] > self.rsi_value) &
            (self.features_df['volume_ratio'] > self.volume_ratio) &
            (self.features_df['lower_wick'] > self.lower_wick)
        )
        
        self.signal_df = self.features_df[mask].copy()
        print(f"Signal bars: {len(self.signal_df):,} ({len(self.signal_df)/len(self.features_df):.1%})")
        print(f"Positive rate: {self.signal_df['label'].mean():.1%}")
        
        # 5. Split data
        splitter = TimeSeriesSplitter(date_column='timestamp', verbose=True)
        self.train_df, self.test_df = splitter.simple_split(self.signal_df, test_size=test_size)
        
        print(f"Train: {len(self.train_df):,}, Test: {len(self.test_df):,}")
        
        return {
            'total_bars': len(self.features_df),
            'signal_bars': len(self.signal_df),
            'positive_rate': self.signal_df['label'].mean()
        }
    
    def train_and_evaluate(self, 
                         feature_selection_method: str = 'iterative_rfe',
                         min_features: int = 15, 
                         max_features: int = 50):
        """Train and evaluate model (with optional forced features/threshold)."""
        
        # Prepare features
        numeric_cols = self.train_df.select_dtypes(include=[np.number]).columns.tolist()
        EXCLUDE_FEATURES = ['open', 'high', 'low', 'close', 'lower_band', 
                          'middle_band', 'upper_band', 'volume', 'timestamp', 
                          'date', 'time', 'pair']
        
        if self.use_forced_features:
            # USE OPTIMIZER'S FEATURES
            print(f"\n🔧 Using {len(self.forced_features)} features from optimizer")
            print(f"   Mode: {self.feature_selection_mode}")
            
            # Check if all forced features exist
            missing = [f for f in self.forced_features if f not in numeric_cols]
            if missing:
                print(f"⚠️ {len(missing)} features missing from data:")
                print(f"   Missing: {missing[:5]}")
                # Use only available features
                available_features = [f for f in self.forced_features if f in numeric_cols]
                print(f"   Using {len(available_features)} available features")
                feature_cols = available_features
            else:
                feature_cols = self.forced_features
            
            # Skip feature selection
            selected_features = feature_cols
            do_feature_selection = False
            
        else:
            # Do fresh feature selection
            feature_cols = [col for col in numeric_cols 
                          if col != 'label' and col not in EXCLUDE_FEATURES]
            selected_features = None
            do_feature_selection = True
        
        # Prepare data
        X_train = self.train_df[feature_cols].copy()
        y_train = self.train_df['label'].copy()
        X_test = self.test_df[feature_cols].copy()
        y_test = self.test_df['label'].copy()
        
        # Fill NaN
        train_means = X_train.mean()
        X_train = X_train.fillna(train_means)
        X_test = X_test.fillna(train_means)
        
        # Create trainer
        trainer = ModelTrainer(
            model_dir=self.model_dir,
            feature_selection_method=feature_selection_method,
            min_features=min_features,
            max_features=max_features,
            verbose=True
        )
        
        # Feature selection (if needed)
        if do_feature_selection:
            print(f"\n🔍 Performing feature selection...")
            selected_features = trainer.select_features(X_train, y_train)
            print(f"   Selected {len(selected_features)} features")
        else:
            print(f"\n🔍 Skipping feature selection (using optimizer's features)")
            # Set selected features for trainer
            trainer.selected_features = selected_features
        
        # Train model
        print(f"\n🎯 Training model...")
        model = trainer.train_model(X_train[selected_features] if selected_features else X_train, 
                                  y_train, calibrate=True)
        
        # Determine threshold (forced or optimized)
        if self.use_forced_threshold:
            print(f"\n📊 Using forced threshold: {self.forced_threshold:.3f}")
            best_threshold = self.forced_threshold
        else:
            print(f"\n📊 Optimizing threshold...")
            best_threshold = trainer.optimize_threshold(X_train[selected_features] if selected_features else X_train, 
                                                      y_train)
        
        # Evaluate
        print(f"\n📈 Evaluating model...")
        metrics = trainer.evaluate_model(X_test[selected_features] if selected_features else X_test, 
                                       y_test, best_threshold)
        
        # Results
        print(f"\n{'='*60}")
        print(f"RESULTS")
        if self.use_forced_features:
            print(f"(USING OPTIMIZER FEATURES - {self.feature_selection_mode.upper()} MODE)")
        if self.use_forced_threshold:
            print(f"(USING FORCED THRESHOLD)")
        print(f"{'='*60}")
        print(f"Features: {len(selected_features) if selected_features else len(feature_cols)}")
        print(f"Threshold: {best_threshold:.3f}")
        print(f"AUC-PR:    {metrics['auc_pr']:.4f}")
        print(f"F1 Score:  {metrics['f1']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall:    {metrics['recall']:.4f}")
        
        # Compare with optimizer if using forced features
        if self.use_forced_features:
            print(f"\n📊 FEATURE COMPARISON:")
            print(f"   Optimizer provided: {len(self.forced_features)} features")
            print(f"   Actually used: {len(selected_features) if selected_features else len(feature_cols)} features")
            print(f"   Mode: {self.feature_selection_mode}")
        
        return {
            'model': model,
            'selected_features': selected_features,
            'best_threshold': best_threshold,
            'metrics': metrics,
            'trainer': trainer,
            'used_optimizer_features': self.use_forced_features,
            'used_forced_threshold': self.use_forced_threshold,
            'feature_selection_mode': self.feature_selection_mode
        }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='BB Reversal Model - v5.0 (Dual Feature Selection Support)'
    )
    
    parser.add_argument('--mode', type=str, default='single',
                       choices=['single', 'optimize'],
                       help='Pipeline mode')
    
    # Use optimizer config
    parser.add_argument('--use_optimizer_config', action='store_true',
                       help='Use optimizer configuration and features')
    parser.add_argument('--config_path', type=str, 
                       default='optimization_results/best_config.json',
                       help='Path to optimizer config file')
    
    # Feature selection mode for optimization
    parser.add_argument('--feature_selection_mode', type=str, default='tp_specific',
                       choices=['tp_specific', 'per_config'],
                       help='Feature selection mode for optimization (tp_specific or per_config)')
    
    # Manual parameters
    parser.add_argument('--data_path', type=str, 
                       default=r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Model Training\version-2\BB SHORT REV v3\data\EURUSD - RAW Data.csv",
                       help='Path to data file')
    
    parser.add_argument('--tp_pips', type=int, default=50,
                       help='Take profit in pips')
    parser.add_argument('--sl_pips', type=int, default=30,
                       help='Stop loss in pips')
    parser.add_argument('--bb_position', type=float, default=0.85,
                       help='BB position threshold')
    parser.add_argument('--rsi_value', type=int, default=55,
                       help='RSI threshold')
    
    # Threshold argument
    parser.add_argument('--threshold', type=float, default=None,
                       help='Force use specific threshold (default: auto-optimize)')
    
    # Optimization parameters
    parser.add_argument('--max_configs', type=int, default=None,
                       help='Maximum configurations to test')
    parser.add_argument('--workers', type=int, default=None,
                       help='Number of parallel workers')
    
    # Model loading
    parser.add_argument('--load_optimizer_model', action='store_true',
                       help='Load actual trained model from optimizer files')
    parser.add_argument('--model_dir', type=str, default='optimization_results',
                       help='Directory containing optimizer model files')
    
    return parser.parse_args()


def main():
    args = parse_arguments()
    
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("\n" + "="*70)
    print("BB REVERSAL MODEL v5.0 - DUAL FEATURE SELECTION SUPPORT")
    print("="*70)
    
    if args.mode == 'single':
        forced_threshold = args.threshold
        
        if args.load_optimizer_model:
            # Mode 1A: Load actual trained model from optimizer files
            print(f"Mode: SINGLE (Loading optimizer model)")
            
            # First create orchestrator with basic params
            orchestrator = PipelineOrchestrator(
                tp_pips=args.tp_pips,
                sl_pips=args.sl_pips,
                bb_position=args.bb_position,
                rsi_value=args.rsi_value,
                forced_threshold=forced_threshold
            )
            
            # Try to load optimizer model
            model_info = orchestrator.load_optimizer_model(args.model_dir)
            if model_info:
                print(f"✅ Loaded optimizer model")
                if model_info['features']:
                    orchestrator.forced_features = model_info['features']
                    orchestrator.use_forced_features = True
                
                # Run pipeline
                data_info = orchestrator.run_single_pipeline(args.data_path)
                
                # Use the loaded model directly
                print(f"\n🔧 Using pre-trained optimizer model...")
                
                # Prepare test data
                feature_cols = orchestrator.forced_features or []
                X_test = orchestrator.test_df[feature_cols].copy()
                y_test = orchestrator.test_df['label'].copy()
                
                # Fill NaN
                test_means = X_test.mean()
                X_test = X_test.fillna(test_means)
                
                # Make predictions
                model = model_info['model']
                y_pred_proba = model.predict_proba(X_test)[:, 1]
                
                # Use forced threshold or default
                if forced_threshold:
                    best_threshold = forced_threshold
                else:
                    # Try to get threshold from config
                    if model_info['config_path'] and os.path.exists(model_info['config_path']):
                        with open(model_info['config_path'], 'r') as f:
                            config = json.load(f)
                        if 'config' in config and 'threshold' in config['config']:
                            best_threshold = config['config']['threshold']
                        elif 'config' in config and 'optimal_threshold' in config['config']:
                            best_threshold = config['config']['optimal_threshold']
                        else:
                            best_threshold = 0.5
                    else:
                        best_threshold = 0.5
                
                # Evaluate
                y_pred = (y_pred_proba >= best_threshold).astype(int)
                
                from sklearn.metrics import precision_recall_curve, auc, f1_score, precision_score, recall_score
                precision_curve, recall_curve, _ = precision_recall_curve(y_test, y_pred_proba)
                auc_pr = auc(recall_curve, precision_curve)
                f1 = f1_score(y_test, y_pred, zero_division=0)
                precision = precision_score(y_test, y_pred, zero_division=0)
                recall = recall_score(y_test, y_pred, zero_division=0)
                
                print(f"\n{'='*60}")
                print(f"RESULTS (USING OPTIMIZER MODEL)")
                print(f"{'='*60}")
                print(f"Model: {os.path.basename(model_info['model_path'])}")
                print(f"Features: {len(feature_cols)}")
                print(f"Threshold: {best_threshold:.3f}")
                print(f"AUC-PR:    {auc_pr:.4f}")
                print(f"F1 Score:  {f1:.4f}")
                print(f"Precision: {precision:.4f}")
                print(f"Recall:    {recall:.4f}")
                
                return {
                    'model': model,
                    'metrics': {'auc_pr': auc_pr, 'f1': f1, 'precision': precision, 'recall': recall},
                    'threshold': best_threshold,
                    'used_optimizer_model': True
                }
            
            else:
                print(f"❌ Could not load optimizer model, falling back to training...")
        
        if args.use_optimizer_config:
            # Mode 1B: Use optimizer configuration
            print(f"Mode: SINGLE (Using optimizer configuration)")
            
            orchestrator = PipelineOrchestrator(
                tp_pips=50,  # Will be overridden
                sl_pips=30,
                bb_position=0.85,
                rsi_value=55,
                forced_threshold=forced_threshold
            )
            
            # Load optimizer config
            if not orchestrator.load_optimizer_config(args.config_path):
                print("Falling back to manual parameters")
                orchestrator = PipelineOrchestrator(
                    tp_pips=args.tp_pips,
                    sl_pips=args.sl_pips,
                    bb_position=args.bb_position,
                    rsi_value=args.rsi_value,
                    forced_threshold=forced_threshold
                )
        
        else:
            # Mode 2: Manual parameters
            print(f"Mode: SINGLE (Manual parameters)")
            print(f"TP: {args.tp_pips}, SL: {args.sl_pips}")
            print(f"BB Position > {args.bb_position}, RSI > {args.rsi_value}")
            if args.threshold is not None:
                print(f"Threshold: {args.threshold:.3f} (forced)")
            
            orchestrator = PipelineOrchestrator(
                tp_pips=args.tp_pips,
                sl_pips=args.sl_pips,
                bb_position=args.bb_position,
                rsi_value=args.rsi_value,
                forced_threshold=forced_threshold
            )
        
        # Run pipeline
        data_info = orchestrator.run_single_pipeline(args.data_path)
        results = orchestrator.train_and_evaluate()
        
        print(f"\n✅ Single run complete!")
        if orchestrator.use_forced_features:
            print(f"   Used optimizer's features ({orchestrator.feature_selection_mode} mode)")
        if orchestrator.use_forced_threshold:
            print(f"   Used forced threshold: {results['best_threshold']:.3f}")
        else:
            print(f"   Used auto-optimized threshold: {results['best_threshold']:.3f}")
        
        return results
    
    elif args.mode == 'optimize':
        print(f"Mode: OPTIMIZATION")
        print(f"Feature Selection Mode: {args.feature_selection_mode.upper()}")
        print(f"Will save features for single mode use")
        
        optimizer = EfficientOptimizer(
            data_path=args.data_path,
            sl_fixed=args.sl_pips,
            output_dir='optimization_results',
            csv_name='optimization_results.csv',
            num_workers=args.workers,
            feature_selection_mode=args.feature_selection_mode,  # NEW parameter
            min_features=15,
            max_features=50,
            seed=42
        )
        
        optimizer.run_optimization(max_configs=args.max_configs)
        
        print(f"\n✅ Optimization complete!")
        print(f"\n📋 COMMANDS TO USE OPTIMIZER RESULTS:")
        print(f"="*60)
        print(f"1. Use optimizer configuration:")
        print(f"   python main.py --mode=single --use_optimizer_config")
        print(f"\n2. Load actual trained model:")
        print(f"   python main.py --mode=single --load_optimizer_model --tp_pips=XX --bb_position=X.XX --rsi_value=XX")
        print(f"\n3. Manual parameters with threshold:")
        print(f"   python main.py --mode=single --tp_pips=XX --bb_position=X.XX --rsi_value=XX --threshold=X.XX")
        print(f"\n4. Run optimization with different mode:")
        print(f"   python main.py --mode=optimize --feature_selection_mode=per_config")
        print(f"="*60)
        
        return optimizer


if __name__ == "__main__":
    results = main()
    if results:
        print("\n✓ Pipeline completed successfully")
    else:
        print("\n✗ Pipeline failed")
        sys.exit(1)