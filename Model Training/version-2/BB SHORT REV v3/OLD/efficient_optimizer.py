"""
efficient_optimizer.py - VERSION 5.0 (DUAL FEATURE SELECTION)

Optimizer with TWO feature selection modes:
1. TP-SPECIFIC: One RFE per TP value (fast)
2. PER-CONFIG: RFE for each config (precise but slow)

Saves best model as .pkl and features as .csv
Fully reproducible results.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import warnings
import time
import pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from typing import Dict, List, Tuple
import json
import sys

# Set random seeds for reproducibility
np.random.seed(42)

warnings.filterwarnings('ignore')

class EfficientOptimizer:
    """
    Optimizer with DUAL feature selection modes.
    """
    
    def __init__(self, 
                data_path: str,
                sl_fixed: int = 30,
                output_dir: str = 'optimization_results',
                csv_name: str = 'optimization_results.csv',
                num_workers: int = None,
                feature_selection_mode: str = 'tp_specific',  # NEW: 'tp_specific' or 'per_config'
                min_features: int = 15,
                max_features: int = 50,
                seed: int = 42):
        
        self.data_path = data_path
        self.sl_fixed = sl_fixed
        self.output_dir = output_dir
        self.csv_path = os.path.join(output_dir, csv_name)
        self.seed = seed
        self.feature_selection_mode = feature_selection_mode.lower()  # NEW
        
        # Validate mode
        valid_modes = ['tp_specific', 'per_config']
        if self.feature_selection_mode not in valid_modes:
            raise ValueError(f"feature_selection_mode must be one of {valid_modes}")
        
        # Set global random seeds
        np.random.seed(self.seed)
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Search space
        self.tp_values = list(range(40, 81, 5))
        self.bb_position_values = [0.90, 0.91, 0.92, 0.93, 0.94, 0.95]
        self.rsi_value_values = [65, 66, 67, 68, 69, 70]
        self.threshold_values = [0.4, .41, .42, .43, .44, .45, .46, .47, .48, .49, .50]
        
        # Fixed parameters
        self.volume_ratio_fixed = 1.2
        self.lower_wick_fixed = 0.001
        self.max_bars_fixed = 18
        
        # CPU cores
        if num_workers is None:
            self.num_workers = multiprocessing.cpu_count() - 1
        else:
            self.num_workers = num_workers
        
        # Feature selection parameters
        self.min_features = min_features
        self.max_features = max_features
        
        # Cached data
        self.raw_df = None
        self.features_df = None
        self.train_indices = None
        self.test_indices = None
        
        # Caches
        self.tp_label_cache = {}            # {tp_pips: labels}
        self.tp_feature_cache = {}          # {tp_pips: features} - for tp_specific mode
        self.config_feature_cache = {}      # {config_key: features} - for per_config mode
        
        # Results
        self.results_df = pd.DataFrame()
        self.tested_configs = set()
        self.best_score = -np.inf
        self.best_row = None
        self.best_features = None
        self.best_model = None
        
        print(f"⚡ EFFICIENT OPTIMIZER v5.0 (Dual Feature Selection)")
        print(f"   Seed: {self.seed}")
        print(f"   Feature Selection Mode: {self.feature_selection_mode.upper()}")
        print(f"   Features: {self.min_features}-{self.max_features}")
        print(f"   Workers: {self.num_workers}")
        print(f"   Will save best model as .pkl and features as .csv")
    
    def load_or_compute_base_data(self):
        """Load or compute base data WITHOUT feature selection."""
        cache_file = os.path.join(self.output_dir, 'base_data_cache.pkl')
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                
                self.raw_df = cache_data['raw_df']
                self.features_df = cache_data['features_df']
                self.train_indices = cache_data['train_indices']
                self.test_indices = cache_data['test_indices']
                
                print(f"✅ Loaded data: {self.features_df.shape[0]:,} bars, {self.features_df.shape[1]} features")
                return True
                
            except Exception as e:
                print(f"⚠️ Cache load failed: {e}")
        
        # Compute from scratch
        print(f"🔧 Computing base data...")
        
        try:
            from data_loader import DataLoader
            from features import FeatureEngineering
            from data_splitting import TimeSeriesSplitter
            
            # Load data
            data_loader = DataLoader(data_dir=os.path.dirname(self.data_path))
            self.raw_df = data_loader.load_csv_to_dataframe(
                file_path=self.data_path,
                timestamp_format='%Y.%m.%d %H:%M:%S',
                sort_ascending=True
            )
            
            # Calculate features
            feature_engineer = FeatureEngineering()
            self.features_df = feature_engineer.calculate_features(self.raw_df)
            self.features_df['next_bar_open'] = self.features_df['open'].shift(-1)
            
            # Split data
            splitter = TimeSeriesSplitter(date_column='timestamp', verbose=False)
            dummy_df = self.features_df.copy()
            dummy_df['dummy'] = 1
            train_df, test_df = splitter.simple_split(dummy_df, test_size=0.2)
            
            self.train_indices = train_df.index
            self.test_indices = test_df.index
            
            # Save to cache
            cache_data = {
                'raw_df': self.raw_df,
                'features_df': self.features_df,
                'train_indices': self.train_indices,
                'test_indices': self.test_indices,
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            print(f"✅ Computed data: {self.features_df.shape[0]:,} bars, {self.features_df.shape[1]} features")
            return True
            
        except Exception as e:
            print(f"❌ Failed: {e}")
            return False
    
    def compute_labels_for_tp(self, tp_pips: int):
        """Compute labels for a specific TP value."""
        from labels import TripleBarrierLabeler
        
        if tp_pips in self.tp_label_cache:
            return self.tp_label_cache[tp_pips]
        
        labeler = TripleBarrierLabeler(
            tp_pips=tp_pips,
            sl_pips=self.sl_fixed,
            max_bars=self.max_bars_fixed,
            pip_factor=0.0001
        )
        
        labels = labeler.label_short_entries(
            self.features_df,
            entry_price_col='next_bar_open'
        )
        
        labels = labels.iloc[:-(labeler.max_bars + 1)].values
        self.tp_label_cache[tp_pips] = labels
        
        return labels
    
    def get_all_potential_features(self):
        """Get list of all potential feature columns."""
        non_feature_columns = {
            'timestamp', 'pair', 'dummy', 'open', 'high', 'low', 'close', 'volume',
            'next_bar_open', 'bb_position', 'rsi_value', 'volume_ratio', 'lower_wick',
            'time', 'date', 'hour', 'minute', 'day', 'month', 'year'
        }
        
        all_columns = set(self.features_df.columns)
        potential_features = [col for col in all_columns if col not in non_feature_columns]
        
        # Filter to numeric columns only
        numeric_cols = self.features_df[potential_features].select_dtypes(include=[np.number]).columns.tolist()
        
        return numeric_cols
    
    def select_features_tp_specific(self, tp_pips: int):
        """Select features once per TP value (OPTION 2)."""
        
        if tp_pips in self.tp_feature_cache:
            return self.tp_feature_cache[tp_pips]
        
        print(f"    Running RFE for TP={tp_pips} (shared by all BB/RSI combos)...")
        
        try:
            # Get labels for this TP
            labels = self.compute_labels_for_tp(tp_pips)
            
            # Get training indices for ALL data (not filtered by BB/RSI)
            train_indices = np.array([idx for idx in range(len(labels)) if idx in self.train_indices])
            
            if len(train_indices) < 200:
                print(f"    Warning: Only {len(train_indices)} training samples for TP={tp_pips}")
                return None
            
            # Get all potential features
            all_features = self.get_all_potential_features()
            
            if not all_features:
                return None
            
            X_train = self.features_df[all_features].iloc[train_indices].values
            y_train = labels[train_indices]
            
            # Run RFE
            selected_features = self._run_rfe(X_train, y_train, all_features)
            
            if selected_features:
                self.tp_feature_cache[tp_pips] = selected_features
                print(f"    TP={tp_pips}: Selected {len(selected_features)} features")
            
            return selected_features
            
        except Exception as e:
            print(f"    Error in TP-specific feature selection for TP={tp_pips}: {e}")
            return None
    
    def select_features_per_config(self, tp_pips: int, bb_position: float, rsi_value: int, config_key: str):
        """Select features for each individual config (OPTION 3)."""
        
        if config_key in self.config_feature_cache:
            return self.config_feature_cache[config_key]
        
        print(f"    Running RFE for config {config_key}...")
        
        try:
            # Get labels
            labels = self.compute_labels_for_tp(tp_pips)
            
            # Filter to signal bars
            mask = (
                (self.features_df['bb_position'].iloc[:len(labels)] > bb_position) &
                (self.features_df['rsi_value'].iloc[:len(labels)] > rsi_value) &
                (self.features_df['volume_ratio'].iloc[:len(labels)] > self.volume_ratio_fixed) &
                (self.features_df['lower_wick'].iloc[:len(labels)] > self.lower_wick_fixed)
            )
            
            signal_indices = np.where(mask)[0]
            
            if len(signal_indices) < 200:
                return None
            
            # Get training indices for this specific configuration
            train_mask = np.isin(signal_indices, self.train_indices)
            train_signal_indices = signal_indices[train_mask]
            
            if len(train_signal_indices) < 100:
                print(f"    Warning: Only {len(train_signal_indices)} training signals for {config_key}")
                return None
            
            # Get all potential features
            all_features = self.get_all_potential_features()
            
            if not all_features:
                return None
            
            X_train = self.features_df[all_features].iloc[train_signal_indices].values
            y_train = labels[train_signal_indices]
            
            # Run RFE
            selected_features = self._run_rfe(X_train, y_train, all_features)
            
            if selected_features:
                self.config_feature_cache[config_key] = selected_features
                print(f"    {config_key}: Selected {len(selected_features)} features")
            
            return selected_features
            
        except Exception as e:
            print(f"    Error in per-config feature selection for {config_key}: {e}")
            return None
    
    def _run_rfe(self, X_train, y_train, feature_names):
        """Run Recursive Feature Elimination."""
        from sklearn.feature_selection import RFE
        from sklearn.ensemble import RandomForestClassifier
        
        # Skip if too few samples
        if len(y_train) < 100:
            print(f"      Too few samples ({len(y_train)}) for RFE")
            return None
        
        # Ensure we have positive samples
        if np.sum(y_train) < 20:
            print(f"      Too few positive samples ({np.sum(y_train)}) for RFE")
            return None
        
        # Start with base estimator
        estimator = RandomForestClassifier(
            n_estimators=50,  # Smaller for speed
            max_depth=8,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight='balanced',
            random_state=self.seed,
            n_jobs=1
        )
        
        # Determine number of features to select
        n_features_to_select = min(self.max_features, 
                                  max(self.min_features, 
                                      min(len(feature_names) // 3, 30)))
        
        try:
            # Run RFE
            selector = RFE(
                estimator=estimator,
                n_features_to_select=n_features_to_select,
                step=5,  # Remove 5 features at a time for speed
                verbose=0
            )
            
            selector.fit(X_train, y_train)
            
            # Get selected features
            selected_mask = selector.support_
            selected_features = [feature_names[i] for i in range(len(feature_names)) if selected_mask[i]]
            
            # If RFE selects too few features, fall back to correlation
            if len(selected_features) < self.min_features:
                print(f"      RFE selected only {len(selected_features)} features, using correlation...")
                selected_features = self._select_by_correlation(X_train, y_train, feature_names)
            
            return selected_features
            
        except Exception as e:
            print(f"      RFE failed: {e}, using correlation...")
            # Fall back to correlation if RFE fails
            return self._select_by_correlation(X_train, y_train, feature_names)
    
    def _select_by_correlation(self, X_train, y_train, feature_names):
        """Fallback: select features by correlation."""
        correlations = []
        for i in range(X_train.shape[1]):
            corr = np.corrcoef(X_train[:, i], y_train)[0, 1]
            if np.isnan(corr):
                corr = 0
            correlations.append((feature_names[i], abs(corr)))
        
        correlations.sort(key=lambda x: x[1], reverse=True)
        
        n_features = min(self.max_features, max(self.min_features, len(correlations)))
        selected = [col for col, _ in correlations[:n_features]]
        
        print(f"      Correlation selected {len(selected)} features")
        return selected
    
    def select_features_for_config(self, tp_pips: int, bb_position: float, rsi_value: int, config_key: str):
        """Select features based on the chosen mode."""
        
        if self.feature_selection_mode == 'tp_specific':
            return self.select_features_tp_specific(tp_pips)
        elif self.feature_selection_mode == 'per_config':
            return self.select_features_per_config(tp_pips, bb_position, rsi_value, config_key)
        else:
            raise ValueError(f"Unknown mode: {self.feature_selection_mode}")
    
    def evaluate_config_fast(self, config: Dict):
        """Evaluate a single configuration."""
        
        config_key = config['config_key']
        
        try:
            # 1. Feature selection (mode-specific)
            print(f"  {config_key}: Feature selection...", end="")
            selected_features = self.select_features_for_config(
                config['tp_pips'], 
                config['bb_position'], 
                config['rsi_value'],
                config_key
            )
            
            if selected_features is None:
                print(" ❌ Failed")
                return None
            
            print(f" ✅ {len(selected_features)} features")
            
            # 2. Get labels
            labels = self.compute_labels_for_tp(config['tp_pips'])
            
            # 3. Get signal indices for THIS config
            mask = (
                (self.features_df['bb_position'].iloc[:len(labels)] > config['bb_position']) &
                (self.features_df['rsi_value'].iloc[:len(labels)] > config['rsi_value']) &
                (self.features_df['volume_ratio'].iloc[:len(labels)] > self.volume_ratio_fixed) &
                (self.features_df['lower_wick'].iloc[:len(labels)] > self.lower_wick_fixed)
            )
            
            signal_indices = np.where(mask)[0]
            
            if len(signal_indices) < 200:
                print(f"  ⚠️ {config_key}: Only {len(signal_indices)} signals")
                return None
            
            # 4. Train/test split
            X = self.features_df[selected_features].iloc[:len(labels)].values
            y = labels
            
            train_mask = np.isin(signal_indices, self.train_indices)
            test_mask = np.isin(signal_indices, self.test_indices)
            
            X_train = X[signal_indices[train_mask]]
            y_train = y[signal_indices[train_mask]]
            X_test = X[signal_indices[test_mask]]
            y_test = y[signal_indices[test_mask]]
            
            if len(X_train) < 100 or len(X_test) < 50:
                print(f"  ⚠️ {config_key}: Insufficient data (train={len(X_train)}, test={len(X_test)})")
                return None
            
            # 5. Train model
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=10,
                min_samples_leaf=5,
                class_weight='balanced',
                random_state=self.seed,
                n_jobs=1
            )
            
            model.fit(X_train, y_train)
            
            # 6. Predict and find best threshold
            y_pred_proba = model.predict_proba(X_test)[:, 1]
            optimal_threshold, threshold_metrics = self._find_optimal_threshold(y_test, y_pred_proba)
            
            # 7. Calculate AUC-PR
            from sklearn.metrics import precision_recall_curve, auc, accuracy_score
            precision_curve, recall_curve, _ = precision_recall_curve(y_test, y_pred_proba)
            auc_pr = auc(recall_curve, precision_curve)
            
            # 8. Final predictions with optimal threshold
            y_pred = (y_pred_proba >= optimal_threshold).astype(int)
            accuracy = accuracy_score(y_test, y_pred)
            
            # 9. Calculate score
            score = self._calculate_score({
                'auc_pr': auc_pr,
                'f1': threshold_metrics['f1'],
                'precision': threshold_metrics['precision'],
                'recall': threshold_metrics['recall']
            }, len(signal_indices), y_train.mean())
            
            # 10. One-line result display
            emoji = "🟢" if score > 0.7 else "🟡" if score > 0.6 else "⚪"
            print(f"{emoji} TP={config['tp_pips']} BB={config['bb_position']:.2f} RSI={config['rsi_value']} "
                  f"Th={optimal_threshold:.1f} | "
                  f"F1={threshold_metrics['f1']:.3f} P={threshold_metrics['precision']:.3f} "
                  f"R={threshold_metrics['recall']:.3f} AP={auc_pr:.3f} S={len(signal_indices):4d}")
            
            # 11. Create result
            result = {
                'config_key': config_key,
                'tp_pips': config['tp_pips'],
                'bb_position': config['bb_position'],
                'rsi_value': config['rsi_value'],
                'sl_pips': self.sl_fixed,
                'volume_ratio': self.volume_ratio_fixed,
                'lower_wick': self.lower_wick_fixed,
                'max_bars': self.max_bars_fixed,
                'threshold': optimal_threshold,
                'optimal_threshold': optimal_threshold,
                'signal_filter': 'all',
                'signal_bars': len(signal_indices),
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'train_positive_rate': y_train.mean(),
                'test_positive_rate': y_test.mean(),
                'selected_features': selected_features,
                'selected_features_count': len(selected_features),
                'feature_selection_mode': self.feature_selection_mode,  # Track which mode was used
                'score': score,
                'auc_pr': auc_pr,
                'f1_score': threshold_metrics['f1'],
                'precision': threshold_metrics['precision'],
                'recall': threshold_metrics['recall'],
                'accuracy': accuracy,
                # Store the model for best config
                'model': model if score > 0.7 else None,
            }
            
            return result
            
        except Exception as e:
            print(f"  ❌ {config_key}: Failed - {str(e)[:100]}")
            return None


    def _find_optimal_threshold(self, y_val, y_pred_proba_val):
        """Find optimal threshold from predefined list - FIXED VERSION."""
        from sklearn.metrics import f1_score, precision_score, recall_score
        
        # Make sure threshold_values is defined
        if not hasattr(self, 'threshold_values') or not self.threshold_values:
            self.threshold_values = [0.4, .41, .42, .43, .44, .45, .46, .47, .48, .49, .50]
        
        best_score = -1
        best_threshold = 0.5
        best_metrics = {}
        
        thresholds_tested = 0
        
        for threshold in self.threshold_values:
            y_pred = (y_pred_proba_val >= threshold).astype(int)
            
            # Skip if no positive predictions or all predictions are positive
            if y_pred.sum() == 0 or y_pred.sum() == len(y_pred):
                continue
                
            thresholds_tested += 1
            
            # Calculate metrics
            f1 = f1_score(y_val, y_pred, zero_division=0)
            precision = precision_score(y_val, y_pred, zero_division=0)
            recall = recall_score(y_val, y_pred, zero_division=0)
            
            # Score = weighted combination - FIXED!
            # Higher precision weight = more conservative (fewer false signals)
            score = (f1 * 0.3) + (precision * 0.5) + (recall * 0.2)
            
            if score > best_score:
                best_score = score
                best_threshold = threshold
                best_metrics = {'f1': f1, 'precision': precision, 'recall': recall}
        
        # If no threshold worked
        if best_score == -1:
            # Use threshold that gives ~30% positive rate
            sorted_proba = np.sort(y_pred_proba_val)
            idx = int(len(sorted_proba) * 0.7)  # 30% positive rate
            if idx < len(sorted_proba):
                best_threshold = sorted_proba[idx]
            else:
                best_threshold = 0.5
            
            y_pred = (y_pred_proba_val >= best_threshold).astype(int)
            best_metrics = {
                'f1': f1_score(y_val, y_pred, zero_division=0),
                'precision': precision_score(y_val, y_pred, zero_division=0),
                'recall': recall_score(y_val, y_pred, zero_division=0)
            }
        
        return best_threshold, best_metrics


    def _calculate_score(self, metrics, signal_bars, positive_rate):
        """Calculate composite score - UPDATED to emphasize precision."""
        score = (
            metrics['auc_pr'] * 0.30 +           # Model discrimination ability
            metrics['f1'] * 0.20 +              # Balance between precision and recall
            metrics['precision'] * 0.40 +       # MOST IMPORTANT: Signal quality
            metrics['recall'] * 0.10           # Less important for trading
        )
        
        if metrics['auc_pr'] > positive_rate * 1.5:
            score *= 1.2
        elif metrics['auc_pr'] > positive_rate * 1.2:
            score *= 1.1
        
        if signal_bars < 300:
            score *= 0.7
        elif signal_bars < 500:
            score *= 0.9
        
        return min(max(score, 0), 1)



    def save_best_model_and_features(self):
        """Save the best model as .pkl and features as .csv"""
        if self.best_row is None or self.best_features is None:
            print("⚠️ No best configuration found to save")
            return
        
        # Create filename based on parameters AND mode
        tp_val = int(self.best_row['tp_pips'])
        bb_val = float(self.best_row['bb_position'])
        rsi_val = int(self.best_row['rsi_value'])
        thresh_val = float(self.best_row['optimal_threshold'])
        mode = self.feature_selection_mode
        
        # Format values for filenames
        bb_str = f"{bb_val:.2f}".replace('.', '')
        thresh_str = f"{thresh_val:.2f}".replace('.', '')
        
        base_filename = f"{mode}_TP{tp_val:02d}BB{bb_str}RSI{rsi_val:02d}Thresh{thresh_str}"
        pkl_filename = f"{base_filename}.pkl"
        csv_filename = f"{base_filename}.csv"
        
        pkl_path = os.path.join(self.output_dir, pkl_filename)
        csv_path = os.path.join(self.output_dir, csv_filename)
        
        # 1. Save the model
        if self.best_model is None:
            print(f"⚠️ Best model not stored, training new model for {base_filename}...")
            
            # Retrain model on full training data
            labels = self.compute_labels_for_tp(tp_val)
            
            mask = (
                (self.features_df['bb_position'].iloc[:len(labels)] > bb_val) &
                (self.features_df['rsi_value'].iloc[:len(labels)] > rsi_val) &
                (self.features_df['volume_ratio'].iloc[:len(labels)] > self.volume_ratio_fixed) &
                (self.features_df['lower_wick'].iloc[:len(labels)] > self.lower_wick_fixed)
            )
            
            signal_indices = np.where(mask)[0]
            X = self.features_df[self.best_features].iloc[:len(labels)].values
            y = labels
            
            # Use only training data
            train_mask = np.isin(signal_indices, self.train_indices)
            X_train = X[signal_indices[train_mask]]
            y_train = y[signal_indices[train_mask]]
            
            from sklearn.ensemble import RandomForestClassifier
            self.best_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=10,
                min_samples_leaf=5,
                class_weight='balanced',
                random_state=self.seed,
                n_jobs=1
            )
            
            self.best_model.fit(X_train, y_train)
        
        # Save model as .pkl
        with open(pkl_path, 'wb') as f:
            pickle.dump(self.best_model, f)
        
        print(f"✅ Model saved: {pkl_path}")
        
        # 2. Save features as .csv
        features_df = pd.DataFrame({
            'feature_name': self.best_features,
            'feature_type': ['numeric'] * len(self.best_features),
            'importance': self.best_model.feature_importances_ if hasattr(self.best_model, 'feature_importances_') else [1.0] * len(self.best_features)
        })
        
        # Sort by importance
        if 'importance' in features_df.columns:
            features_df = features_df.sort_values('importance', ascending=False)
        
        features_df.to_csv(csv_path, index=False)
        print(f"✅ Features saved: {csv_path}")
        print(f"   Total features: {len(self.best_features)}")
        
        # 3. Save configuration file
        config_filename = f"{base_filename}_config.json"
        config_path = os.path.join(self.output_dir, config_filename)
        
        config_dict = {
            'config': {
                'tp_pips': tp_val,
                'sl_pips': int(self.best_row['sl_pips']),
                'threshold': thresh_val,
                'bb_position': bb_val,
                'rsi_value': rsi_val,
                'volume_ratio': float(self.best_row['volume_ratio']),
                'lower_wick': float(self.best_row['lower_wick']),
                'max_bars': int(self.best_row['max_bars']),
            },
            'feature_selection': {
                'mode': mode,
                'min_features': self.min_features,
                'max_features': self.max_features,
                'features_count': len(self.best_features)
            },
            'model_info': {
                'algorithm': 'RandomForest',
                'n_estimators': 100,
                'max_depth': 10,
                'random_state': self.seed,
                'class_weight': 'balanced'
            },
            'features': self.best_features,
            'performance': {
                'score': float(self.best_row['score']),
                'auc_pr': float(self.best_row['auc_pr']),
                'f1_score': float(self.best_row['f1_score']),
                'precision': float(self.best_row['precision']),
                'recall': float(self.best_row['recall']),
                'accuracy': float(self.best_row['accuracy']),
                'signal_bars': int(self.best_row['signal_bars']),
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        print(f"✅ Config saved: {config_path}")
        
        return base_filename



    def run_optimization(self, max_configs: int = None):
        """Run optimization with minimal logging."""
        
        print(f"\n{'='*60}")
        print(f"🚀 OPTIMIZATION v5.0 - {self.feature_selection_mode.upper()} MODE")
        print(f"{'='*60}")
        
        if not self.load_or_compute_base_data():
            return
        
        # Generate configurations
        configs = []
        for tp in self.tp_values:
            if tp <= self.sl_fixed:
                continue
            for bb in self.bb_position_values:
                for rsi in self.rsi_value_values:
                    config_key = f"{tp}_{bb:.2f}_{rsi}"
                    configs.append({
                        'config_key': config_key,
                        'tp_pips': tp,
                        'bb_position': bb,
                        'rsi_value': rsi,
                    })
        
        total_configs = len(configs)
        print(f"📊 Search space: {total_configs} configs")
        print(f"⚡ Workers: {self.num_workers}")
        print(f"🔒 Seed: {self.seed}")
        print(f"🎯 Feature Selection: {self.feature_selection_mode.upper()}")
        print(f"💾 Will save best model (.pkl) and features (.csv)")
        print()
        
        # Check existing results
        if os.path.exists(self.csv_path):
            existing_df = pd.read_csv(self.csv_path)
            if 'config_key' in existing_df.columns:
                self.tested_configs = set(existing_df['config_key'].tolist())
                print(f"📖 Found {len(existing_df)} existing results")
        
        # Filter out already tested
        new_configs = [c for c in configs if c['config_key'] not in self.tested_configs]
        
        if not new_configs:
            print(f"✅ All configurations already tested!")
            self._load_and_show_best()
            
            if self.best_row:
                self.save_best_model_and_features()
            
            return
        
        print(f"🔄 Testing {len(new_configs)} new configurations")
        print()
        
        # Prepare data for workers
        data_info = {
            'features_df': self.features_df,
            'train_indices': self.train_indices,
            'test_indices': self.test_indices,
            'tp_label_cache': self.tp_label_cache,
            'feature_selection_mode': self.feature_selection_mode,
            'min_features': self.min_features,
            'max_features': self.max_features,
            'sl_fixed': self.sl_fixed,
            'volume_ratio_fixed': self.volume_ratio_fixed,
            'lower_wick_fixed': self.lower_wick_fixed,
            'max_bars_fixed': self.max_bars_fixed,
            'threshold_values': self.threshold_values,
        }
        
        # Pickle the data for multiprocessing
        import pickle
        pickled_data_info = pickle.dumps(data_info)
        
        # Run optimization
        start_time = time.time()
        completed = 0
        successful = 0
        
        # Import the worker function
        from optimizer_utils import evaluate_config_worker
        
        # Use ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            
            # Submit all tasks
            futures = {}
            for config in new_configs:
                future = executor.submit(evaluate_config_worker, (config, self.seed, pickled_data_info))
                futures[future] = config
            
            for future in as_completed(futures):
                completed += 1
                config = futures[future]
                
                try:
                    result = future.result(timeout=300)  # 5 minute timeout
                    
                    if result:
                        successful += 1
                        
                        # Save to DataFrame
                        self.results_df = pd.concat([
                            self.results_df,
                            pd.DataFrame([result])
                        ], ignore_index=True)
                        
                        # Check if this is new best
                        if result['score'] > self.best_score:
                            self.best_score = result['score']
                            self.best_row = result
                            self.best_features = result['selected_features']
                            self.best_model = result.get('model')
                            
                            print(f"\n{'⭐'*30}")
                            print(f"🏆 NEW BEST! Score: {result['score']:.4f}")
                            print(f"⭐ TP={result['tp_pips']} BB={result['bb_position']:.2f} RSI={result['rsi_value']}")
                            print(f"⭐ F1={result['f1_score']:.3f} P={result['precision']:.3f} R={result['recall']:.3f}")
                            print(f"⭐ Th={result['optimal_threshold']:.1f} Sig={result['signal_bars']}")
                            print(f"⭐ Mode={self.feature_selection_mode} Features={len(self.best_features)}")
                            print(f"{'⭐'*30}\n")
                        
                        # Periodic save
                        if successful % 20 == 0:
                            self.results_df.to_csv(self.csv_path, index=False)
                    
                except Exception as e:
                    print(f"❌ {config['config_key']}: Failed - {str(e)[:100]}")
                    import traceback
                    traceback.print_exc()
                
                # Progress every 10 configs
                if completed % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = (len(new_configs) - completed) / rate if rate > 0 else 0
                    
                    print(f"📊 Progress: {completed}/{len(new_configs)} "
                          f"({completed/len(new_configs)*100:.1f}%) | "
                          f"ETA: {remaining/60:.1f}min | "
                          f"Successful: {successful}/{completed}")
        
        # Final save and summary
        if not self.results_df.empty:
            self.results_df.to_csv(self.csv_path, index=False)
            self._save_best_config_with_features()
            self._show_detailed_summary()
            
            # Save the best model and features
            saved_filename = self.save_best_model_and_features()
            if saved_filename:
                print(f"\n💾 Best model and features saved as: {saved_filename}")
        
        total_time = time.time() - start_time
        print(f"\n✅ Complete: {total_time/60:.1f} min | Successful: {successful}/{len(new_configs)}")



    def _evaluate_config_wrapper(self, config: Dict):
        """Wrapper method for multiprocessing."""
        # Re-seed in each process for safety
        np.random.seed(self.seed)
        return self.evaluate_config_fast(config)


    def _save_best_config_with_features(self):
        """Save best configuration with features."""
        if self.best_row is None or self.best_features is None:
            return
        
        config_dict = {
            'config': {
                'tp_pips': int(self.best_row['tp_pips']),
                'sl_pips': int(self.best_row['sl_pips']),
                'threshold': float(self.best_row['optimal_threshold']),
                'bb_position': float(self.best_row['bb_position']),
                'rsi_value': int(self.best_row['rsi_value']),
                'volume_ratio': float(self.best_row['volume_ratio']),
                'lower_wick': float(self.best_row['lower_wick']),
                'max_bars': int(self.best_row['max_bars']),
            },
            'feature_selection': {
                'mode': self.feature_selection_mode,
                'features_count': len(self.best_features)
            },
            'selected_features': list(self.best_features),
            'performance': {
                'score': float(self.best_row['score']),
                'auc_pr': float(self.best_row['auc_pr']),
                'f1_score': float(self.best_row['f1_score']),
                'precision': float(self.best_row['precision']),
                'recall': float(self.best_row['recall']),
                'accuracy': float(self.best_row['accuracy']),
                'signal_bars': int(self.best_row['signal_bars']),
            }
        }
        
        config_path = os.path.join(self.output_dir, 'best_config.json')
        with open(config_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        print(f"\n💾 Saved best config to: {config_path}")
        print(f"   Mode: {self.feature_selection_mode}")
        print(f"   Features: {len(self.best_features)}")

    def _show_detailed_summary(self):
        """Show best configuration summary."""
        if self.best_row is None:
            return
        
        print(f"\n{'='*60}")
        print(f"🏆 BEST CONFIGURATION - {self.feature_selection_mode.upper()} MODE")
        print(f"{'='*60}")
        
        # EXACT CONFIGURATION VALUES
        print(f"📋 EXACT PARAMETERS TESTED:")
        print(f"  TP Pips: {self.best_row['tp_pips']}")
        print(f"  SL Pips: {self.best_row['sl_pips']}")
        print(f"  BB Threshold: {self.best_row['bb_position']:.2f}")
        print(f"  RSI Threshold: {self.best_row['rsi_value']}")
        print(f"  Volume Ratio: {self.best_row['volume_ratio']:.1f}")
        print(f"  Lower Wick: {self.best_row['lower_wick']:.3f}")
        print(f"  Max Bars: {self.best_row['max_bars']}")
        print(f"  Model Threshold: {self.best_row['optimal_threshold']:.1f}")
        print(f"  Feature Selection Mode: {self.feature_selection_mode}")
        print(f"  Features Selected: {len(self.best_features)}")
        
        print(f"\n🎯 ENTRY CONDITIONS (actual trading rules):")
        print(f"  IF: BB_position > {self.best_row['bb_position']:.2f}")
        print(f"  AND: RSI > {self.best_row['rsi_value']}")
        print(f"  AND: volume_ratio > {self.best_row['volume_ratio']:.1f}")
        print(f"  AND: lower_wick > {self.best_row['lower_wick']:.3f}")
        print(f"  THEN: Consider short entry with TP={self.best_row['tp_pips']}p, SL={self.best_row['sl_pips']}p")
        
        print(f"\n📊 PERFORMANCE METRICS:")
        print(f"  Score: {self.best_row['score']:.4f}")
        print(f"  F1: {self.best_row['f1_score']:.3f}")
        print(f"  Precision: {self.best_row['precision']:.3f}")
        print(f"  Recall: {self.best_row['recall']:.3f}")
        print(f"  AUC-PR: {self.best_row['auc_pr']:.3f}")
        
        print(f"\n📈 DATA STATISTICS:")
        print(f"  Total Signals: {self.best_row['signal_bars']:,}")
        print(f"  Positive Rate: {self.best_row.get('train_positive_rate', 0):.1%}")
        
        print(f"\n💾 SINGLE MODE COMMAND:")
        print(f"  python main.py --mode=single --tp_pips={self.best_row['tp_pips']} ")
        print(f"                  --bb_position={self.best_row['bb_position']:.2f} ")
        print(f"                  --rsi_value={self.best_row['rsi_value']}")
        print(f"                  --threshold={self.best_row['optimal_threshold']:.1f}")
        
        print(f"\n💾 MODEL FILES CREATED:")
        tp_val = int(self.best_row['tp_pips'])
        bb_val = float(self.best_row['bb_position'])
        rsi_val = int(self.best_row['rsi_value'])
        thresh_val = float(self.best_row['optimal_threshold'])
        bb_str = f"{bb_val:.2f}".replace('.', '')
        thresh_str = f"{thresh_val:.2f}".replace('.', '')
        mode = self.feature_selection_mode
        
        print(f"  {self.output_dir}/{mode}_TP{tp_val:02d}BB{bb_str}RSI{rsi_val:02d}Thresh{thresh_str}.pkl")
        print(f"  {self.output_dir}/{mode}_TP{tp_val:02d}BB{bb_str}RSI{rsi_val:02d}Thresh{thresh_str}.csv")
        print(f"  {self.output_dir}/{mode}_TP{tp_val:02d}BB{bb_str}RSI{rsi_val:02d}Thresh{thresh_str}_config.json")
        
        print(f"{'='*60}")

    def _load_and_show_best(self):
        """Load and show best from existing results."""
        if not os.path.exists(self.csv_path):
            print("📭 No existing results found")
            return
        
        try:
            df = pd.read_csv(self.csv_path)
            if len(df) == 0:
                print("📭 No results in CSV file")
                return
            
            # Find best score
            if 'score' in df.columns:
                best_idx = df['score'].idxmax()
                self.best_row = df.loc[best_idx].to_dict()
                self.best_score = self.best_row['score']
                
                print(f"\n{'='*60}")
                print(f"📖 BEST FROM EXISTING RESULTS")
                print(f"{'='*60}")
                print(f"TP: {self.best_row['tp_pips']}p | SL: {self.best_row['sl_pips']}p")
                print(f"BB > {self.best_row['bb_position']:.2f} | RSI > {self.best_row['rsi_value']}")
                print(f"Threshold: {self.best_row.get('optimal_threshold', 0.5):.1f}")
                print(f"Score: {self.best_row['score']:.4f}")
                
                if 'f1_score' in self.best_row:
                    print(f"F1: {self.best_row['f1_score']:.3f} | "
                          f"P: {self.best_row.get('precision', 0):.3f} | "
                          f"R: {self.best_row.get('recall', 0):.3f}")
                
                if 'signal_bars' in self.best_row:
                    print(f"Signals: {self.best_row['signal_bars']:,}")
                
                # Try to load features from best config if it exists
                best_config_path = os.path.join(self.output_dir, 'best_config.json')
                if os.path.exists(best_config_path):
                    with open(best_config_path, 'r') as f:
                        best_config = json.load(f)
                    if 'selected_features' in best_config:
                        self.best_features = best_config['selected_features']
                        print(f"Features: {len(self.best_features)}")
                        if 'feature_selection' in best_config:
                            print(f"Mode: {best_config['feature_selection'].get('mode', 'unknown')}")
                
                print(f"{'='*60}")
                
            else:
                print("⚠️ CSV doesn't have 'score' column")
                
        except Exception as e:
            print(f"❌ Error loading best results: {e}")

def main():
    """Main function."""
    
    DATA_PATH = r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Model Training\version-2\BB SHORT REV v3\data\EURUSD - RAW Data.csv"
    
    print(f"\n{'='*60}")
    print(f"⚡ BB REVERSAL OPTIMIZER v5.0 (Dual Feature Selection)")
    print(f"{'='*60}")
    
    if not os.path.exists(DATA_PATH):
        print(f"❌ Data file not found!")
        return
    
    # Choose mode: 'tp_specific' or 'per_config'
    feature_selection_mode = 'tp_specific'  # Change to 'per_config' for precise mode
    
    optimizer = EfficientOptimizer(
        data_path=DATA_PATH,
        sl_fixed=30,
        output_dir='optimization_results',
        csv_name='optimization_results.csv',
        feature_selection_mode=feature_selection_mode,  # NEW parameter
        min_features=15,
        max_features=50,
        seed=42
    )
    
    optimizer.run_optimization()

if __name__ == "__main__":
    main()