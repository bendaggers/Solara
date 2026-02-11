"""
train_model.py - FIXED VERSION v3.2

Model training with TRUE iterative feature selection and Random Forest.

Key fixes in v3.2:
1. REMOVED StandardScaler - RF doesn't need scaling, and it caused
   inconsistency between feature selection (unscaled) and training (scaled)
2. FIXED threshold optimization - now uses CalibratedClassifierCV in folds
   to match the actual trained model's probability distribution
3. INCREASED CV folds from 3 to 5 with purged walk-forward validation
4. Added embargo period between train/val folds to prevent leakage
"""

import pandas as pd
import numpy as np
import pickle
import os
import json
from datetime import datetime
from typing import Tuple, Dict, List, Optional, Union

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import RFECV, SelectFromModel, SelectKBest, mutual_info_classif
from sklearn.model_selection import cross_val_score, TimeSeriesSplit, StratifiedKFold
from sklearn.metrics import (precision_score, recall_score, f1_score, 
                           accuracy_score, confusion_matrix, classification_report,
                           precision_recall_curve, auc)
from sklearn.calibration import CalibratedClassifierCV
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

import warnings
warnings.filterwarnings('ignore')


class PurgedTimeSeriesSplit:
    """
    Time series cross-validation with purge/embargo.
    
    Adds a gap (embargo) between training and validation sets to prevent
    information leakage from overlapping label windows.
    
    For example, with max_bars=18, if train ends at index 1000,
    validation should start at index 1000 + embargo (e.g., 1020)
    to ensure no label from the training set looks into the validation period.
    """
    
    def __init__(self, n_splits=5, embargo_pct=0.01):
        """
        Args:
            n_splits: Number of CV splits
            embargo_pct: Percentage of training set to use as embargo gap
        """
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct
    
    def split(self, X, y=None, groups=None):
        """Generate purged train/val indices."""
        n_samples = len(X) if hasattr(X, '__len__') else X.shape[0]
        
        # Minimum test size
        test_size = n_samples // (self.n_splits + 1)
        
        for i in range(self.n_splits):
            # Training end
            train_end = test_size * (i + 1)
            
            # Embargo gap
            embargo = int(train_end * self.embargo_pct)
            embargo = max(embargo, 20)  # At least 20 bars embargo
            
            # Validation start (after embargo)
            val_start = train_end + embargo
            val_end = min(val_start + test_size, n_samples)
            
            if val_start >= n_samples or val_end <= val_start:
                continue
            
            train_indices = np.arange(0, train_end)
            val_indices = np.arange(val_start, val_end)
            
            yield train_indices, val_indices
    
    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits


class ModelTrainer:
    """
    Professional model trainer with TRUE iterative feature selection.
    
    Key fixes v3.2:
    1. No scaling (RF is scale-invariant, removes train/select mismatch)
    2. Calibrated threshold optimization (fold models match actual model)
    3. 5-fold purged walk-forward CV (prevents label leakage)
    4. Minimum feature count enforcement
    """
    
    def __init__(self, 
                 model_dir: str = 'models',
                 feature_selection_method: str = 'iterative_rfe',
                 min_features: int = 10,
                 max_features: int = 30,
                 random_state: int = 42,
                 verbose: bool = True, 
                 forced_threshold: float = None):
        """
        Initialize the professional model trainer.
        """
        self.model_dir = model_dir
        self.feature_selection_method = feature_selection_method
        self.min_features = min_features
        self.max_features = max_features
        self.random_state = random_state
        self.verbose = verbose
        self.forced_threshold = forced_threshold
        
        # Create model directory if it doesn't exist
        os.makedirs(model_dir, exist_ok=True)
        
        # Initialize attributes
        self.model = None
        self.selector = None
        self.selected_features = None
        self.feature_importances = None
        self.best_threshold = 0.5
        self.metadata = {}
        # FIX #3: REMOVED self.scaler - RF doesn't need scaling
        
        # Store training data
        self.X_train_selected = None
        self.y_train = None
        
        # Whether model is calibrated (needed for threshold optimization)
        self.is_calibrated = False
        
        # Optimized Random Forest parameters (tuned for trading)
        self.rf_params = {
            'n_estimators': 200,
            'max_depth': 15,
            'min_samples_split': 10,
            'min_samples_leaf': 5,
            'max_features': 'sqrt',
            'class_weight': 'balanced',
            'bootstrap': True,
            'oob_score': True,
            'random_state': random_state,
            'n_jobs': -1,
            'verbose': 0
        }
        
        if verbose:
            print(f"ModelTrainer initialized (v3.2 FIXED):")
            print(f"  Model directory: {model_dir}")
            print(f"  Feature selection: {feature_selection_method}")
            print(f"  Min features: {min_features}, Max features: {max_features}")
            print(f"  Random state: {random_state}")
            print(f"  Scaling: DISABLED (RF is scale-invariant)")
            print(f"  CV: 5-fold purged walk-forward")
    
    def prepare_data(self, train_df: pd.DataFrame, test_df: pd.DataFrame, 
                    label_col: str = 'label', 
                    exclude_cols: list = None) -> Tuple[pd.DataFrame, pd.Series, 
                                                    pd.DataFrame, pd.Series, List[str]]:
        """
        Prepare data for training and testing.
        """
        if self.verbose:
            print("\n" + "="*60)
            print("PREPARING DATA")
            print("="*60)
        
        # Default columns to exclude
        if exclude_cols is None:
            exclude_cols = ['timestamp', 'date', 'time', 'datetime']
        
        # Separate features and labels
        feature_cols = [col for col in train_df.columns 
                       if col != label_col and col not in exclude_cols]
        
        # Ensure we only use numeric columns
        numeric_cols = []
        for col in feature_cols:
            if pd.api.types.is_numeric_dtype(train_df[col]):
                numeric_cols.append(col)
            else:
                if self.verbose:
                    print(f"  WARNING: Skipping non-numeric column: {col}")
        
        X_train = train_df[numeric_cols].copy()
        y_train = train_df[label_col].copy()
        X_test = test_df[numeric_cols].copy()
        y_test = test_df[label_col].copy()
        
        # Handle NaN values
        X_train = X_train.fillna(X_train.mean())
        X_test = X_test.fillna(X_train.mean())  # Use training means
        
        if self.verbose:
            print(f"Training set: {X_train.shape[0]} samples, {X_train.shape[1]} features")
            print(f"Test set: {X_test.shape[0]} samples, {X_test.shape[1]} features")
            print(f"Label distribution (train):")
            print(f"  Positive (1): {y_train.sum()} ({y_train.mean():.1%})")
            print(f"  Negative (0): {len(y_train) - y_train.sum()} ({(1 - y_train.mean()):.1%})")
        
        return X_train, y_train, X_test, y_test, numeric_cols
    
    def _identify_feature_categories(self, feature_names: List[str]) -> Dict[str, List[str]]:
        """Identify trading indicator categories from feature names."""
        categories = {
            'price': [],
            'bollinger': [],
            'momentum': [],
            'volatility': [],
            'volume': [],
            'trend': [],
            'other': []
        }
        
        bollinger_keywords = ['band', 'bb', 'bollinger', 'upper', 'middle', 'lower']
        momentum_keywords = ['rsi', 'macd', 'stochastic', 'momentum', 'oscillator']
        volatility_keywords = ['atr', 'volatility', 'range', 'std', 'deviation']
        volume_keywords = ['volume', 'vol']
        trend_keywords = ['trend', 'slope', 'ema', 'sma', 'ma']
        price_keywords = ['close', 'high', 'low', 'open', 'price']
        
        for feature in feature_names:
            feature_lower = feature.lower()
            
            if any(keyword in feature_lower for keyword in price_keywords):
                categories['price'].append(feature)
            elif any(keyword in feature_lower for keyword in bollinger_keywords):
                categories['bollinger'].append(feature)
            elif any(keyword in feature_lower for keyword in momentum_keywords):
                categories['momentum'].append(feature)
            elif any(keyword in feature_lower for keyword in volatility_keywords):
                categories['volatility'].append(feature)
            elif any(keyword in feature_lower for keyword in volume_keywords):
                categories['volume'].append(feature)
            elif any(keyword in feature_lower for keyword in trend_keywords):
                categories['trend'].append(feature)
            else:
                categories['other'].append(feature)
        
        return categories
    
    def _remove_highly_correlated_features(self, X: pd.DataFrame, threshold: float = 0.95) -> List[str]:
        """Remove highly correlated features to reduce redundancy."""
        if self.verbose:
            print(f"  Removing features with correlation > {threshold}")
        
        corr_matrix = X.corr().abs()
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        
        # Find features to drop
        to_drop = []
        for column in upper.columns:
            if any(upper[column] > threshold):
                to_drop.append(column)
        
        if to_drop and self.verbose:
            print(f"  Dropping {len(to_drop)} highly correlated features: {to_drop}")
        
        # Keep features that are NOT in to_drop
        keep_features = [col for col in X.columns if col not in to_drop]
        return keep_features

    def select_features_iterative_rfe(self, X_train: pd.DataFrame, y_train: pd.Series) -> List[str]:
        """
        TRUE iterative RFE with performance tracking at each step.
        
        FIX #5: Uses 5-fold purged walk-forward CV instead of 3-fold.
        FIX #3: No scaling applied (consistent with training).
        """
        if self.verbose:
            print("\n" + "="*60)
            print("TRUE ITERATIVE RFE - FIXED VERSION")
            print("="*60)
        
        # Step 1: Remove highly correlated features first
        uncorrelated_features = self._remove_highly_correlated_features(X_train)
        X_current = X_train[uncorrelated_features].copy()
        
        if self.verbose:
            print(f"  Starting with {X_current.shape[1]} uncorrelated features")
        
        # Store history
        feature_history = []
        performance_history = []
        importance_history = []
        
        # Initial feature set
        current_features = X_current.columns.tolist()
        
        # FIX #5: Use 5-fold purged walk-forward CV
        cv = PurgedTimeSeriesSplit(n_splits=5, embargo_pct=0.01)
        
        iteration = 0
        while len(current_features) > self.min_features:
            iteration += 1
            n_features = len(current_features)
            
            if self.verbose:
                print(f"\n  --- Iteration {iteration}: {n_features} features ---")
            
            # FIX #3: No scaling - pass raw features to RF
            rf_temp = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                class_weight='balanced',
                random_state=self.random_state,
                n_jobs=-1
            )
            
            try:
                cv_scores = cross_val_score(rf_temp, X_current[current_features], y_train,
                                          cv=cv, scoring='f1', n_jobs=-1)
                mean_score = np.mean(cv_scores)
                std_score = np.std(cv_scores)
            except Exception as e:
                if self.verbose:
                    print(f"    CV failed ({e}), using simple split")
                from sklearn.model_selection import train_test_split
                X_tr, X_val, y_tr, y_val = train_test_split(
                    X_current[current_features], y_train,
                    test_size=0.2, random_state=self.random_state, shuffle=False
                )
                rf_temp.fit(X_tr, y_tr)
                y_pred = rf_temp.predict(X_val)
                mean_score = f1_score(y_val, y_pred)
                std_score = 0.0
            
            # Store history
            feature_history.append(current_features.copy())
            performance_history.append({
                'n_features': n_features,
                'mean_f1': mean_score,
                'std_f1': std_score
            })
            
            if self.verbose:
                print(f"    CV F1 Score: {mean_score:.4f} (±{std_score:.4f})")
            
            # Fit model to get feature importances
            rf_temp.fit(X_current[current_features], y_train)
            
            if hasattr(rf_temp, 'feature_importances_'):
                importances = rf_temp.feature_importances_
            else:
                importances = np.ones(len(current_features)) / len(current_features)
            
            importance_df = pd.DataFrame({
                'feature': current_features,
                'importance': importances
            }).sort_values('importance', ascending=False)
            
            importance_history.append(importance_df)
            
            if self.verbose and n_features <= 20:
                print(f"    Top 5 features:")
                for i, (_, row) in enumerate(importance_df.head(5).iterrows(), 1):
                    print(f"      {i}. {row['feature']}: {row['importance']:.4f}")
            
            # Remove the LEAST important feature
            worst_feature = importance_df.iloc[-1]['feature']
            current_features.remove(worst_feature)
            
            if self.verbose:
                print(f"    Removed: {worst_feature} (importance: {importance_df.iloc[-1]['importance']:.6f})")
            
            if len(current_features) <= self.min_features:
                break
        
        # Add final state
        if current_features:
            feature_history.append(current_features.copy())
            rf_temp = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                class_weight='balanced',
                random_state=self.random_state,
                n_jobs=-1
            )
            cv_scores = cross_val_score(rf_temp, X_current[current_features], y_train,
                                      cv=cv, scoring='f1', n_jobs=-1)
            performance_history.append({
                'n_features': len(current_features),
                'mean_f1': np.mean(cv_scores),
                'std_f1': np.std(cv_scores)
            })
        
        # Find the best performing feature set
        f1_scores = [p['mean_f1'] for p in performance_history]
        best_idx = np.argmax(f1_scores)
        best_features = feature_history[best_idx]
        best_performance = performance_history[best_idx]
        
        if self.verbose:
            print(f"\n  --- RESULTS ---")
            print(f"  Best performance at {best_performance['n_features']} features")
            print(f"  Best F1 Score: {best_performance['mean_f1']:.4f}")
            print(f"  Selected {len(best_features)} features")
            
            self._plot_iterative_rfe_results(performance_history, importance_history)
            
            categories = self._identify_feature_categories(best_features)
            print(f"\n  Feature categories in selection:")
            for category, features in categories.items():
                if features:
                    print(f"    {category}: {len(features)} features")
        
        # Train final model on best features for accurate importances
        X_best = X_current[best_features]
        rf_final = RandomForestClassifier(**self.rf_params)
        rf_final.fit(X_best, y_train)
        
        self.selected_features = best_features
        self.feature_importances = pd.DataFrame({
            'feature': best_features,
            'importance': rf_final.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return self.selected_features
    
    def select_features_none(self, X_train: pd.DataFrame, y_train: pd.Series) -> List[str]:
        """Use all features without selection."""
        if self.verbose:
            print("\n" + "="*60)
            print("NO FEATURE SELECTION - USING ALL FEATURES")
            print("="*60)
        
        # Just return all numeric columns (after correlation filtering)
        uncorrelated_features = self._remove_highly_correlated_features(X_train)
        self.selected_features = uncorrelated_features
        
        # Get importances for reporting
        rf_temp = RandomForestClassifier(
            n_estimators=50,
            max_depth=10,
            class_weight='balanced',
            random_state=self.random_state,
            n_jobs=-1
        )
        rf_temp.fit(X_train[uncorrelated_features], y_train)
        
        self.feature_importances = pd.DataFrame({
            'feature': uncorrelated_features,
            'importance': rf_temp.feature_importances_
        }).sort_values('importance', ascending=False)
        
        if self.verbose:
            print(f"  Using {len(uncorrelated_features)} features")
            print(f"  Top 10 most important features:")
            for i, (_, row) in enumerate(self.feature_importances.head(10).iterrows(), 1):
                print(f"    {i}. {row['feature']}: {row['importance']:.4f}")
        
        return self.selected_features


    def select_features_correlation(self, X_train: pd.DataFrame, y_train: pd.Series) -> List[str]:
        """Select features based on correlation with target."""
        import numpy as np
        
        # Calculate correlations
        correlations = []
        for col in X_train.columns:
            try:
                # Remove NaN values for correlation calculation
                valid_mask = ~np.isnan(X_train[col]) & ~np.isnan(y_train)
                if valid_mask.sum() > 10:  # Need enough samples
                    corr = np.corrcoef(X_train[col][valid_mask], y_train[valid_mask])[0, 1]
                    correlations.append((col, abs(corr)))
                else:
                    correlations.append((col, 0))
            except:
                correlations.append((col, 0))
        
        # Sort by correlation (highest first)
        correlations.sort(key=lambda x: x[1], reverse=True)
        
        # Select top features
        n_features = min(self.max_features, len(correlations))
        n_features = max(self.min_features, n_features)
        
        selected = [col for col, _ in correlations[:n_features]]
        
        print(f"  Correlation-based selection: {len(selected)} features")
        print(f"  Top 5 features by correlation:")
        for i, (col, corr) in enumerate(correlations[:5], 1):
            print(f"    {i}. {col}: {corr:.4f}")
        
        return selected



    def _plot_iterative_rfe_results(self, performance_history, importance_history):
        """Plot iterative RFE results."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        n_features = [p['n_features'] for p in performance_history]
        f1_scores = [p['mean_f1'] for p in performance_history]
        f1_stds = [p['std_f1'] for p in performance_history]
        
        axes[0, 0].plot(n_features, f1_scores, 'o-', linewidth=2)
        axes[0, 0].fill_between(n_features, 
                               np.array(f1_scores) - np.array(f1_stds),
                               np.array(f1_scores) + np.array(f1_stds),
                               alpha=0.2)
        axes[0, 0].set_xlabel('Number of Features')
        axes[0, 0].set_ylabel('F1 Score')
        axes[0, 0].set_title('Performance vs Feature Count')
        axes[0, 0].grid(True, alpha=0.3)
        
        best_idx = np.argmax(f1_scores)
        axes[0, 0].plot(n_features[best_idx], f1_scores[best_idx], 'ro', markersize=10)
        axes[0, 0].text(n_features[best_idx], f1_scores[best_idx], 
                       f' Best: {n_features[best_idx]} features', 
                       verticalalignment='bottom')
        
        if len(importance_history) > 1:
            all_features = set()
            for imp_df in importance_history:
                all_features.update(imp_df['feature'].tolist())
            
            importance_matrix = pd.DataFrame(index=sorted(all_features))
            for i, imp_df in enumerate(importance_history):
                importance_matrix[f'iter_{i}'] = imp_df.set_index('feature')['importance']
            
            top_features = importance_matrix.mean(axis=1).sort_values(ascending=False).head(15).index
            
            axes[0, 1].barh(range(len(top_features)), 
                           importance_matrix.loc[top_features].mean(axis=1).values)
            axes[0, 1].set_yticks(range(len(top_features)))
            axes[0, 1].set_yticklabels(top_features)
            axes[0, 1].set_xlabel('Average Importance')
            axes[0, 1].set_title('Top 15 Most Important Features')
            axes[0, 1].invert_yaxis()
        
        if len(importance_history) > 1:
            removal_order = []
            for i in range(min(10, len(importance_history) - 1)):
                current_feats = set(importance_history[i]['feature'])
                next_feats = set(importance_history[i + 1]['feature'])
                removed = list(current_feats - next_feats)
                if removed:
                    removal_order.append(removed[0])
            
            if removal_order:
                axes[1, 0].barh(range(len(removal_order)), range(1, len(removal_order) + 1))
                axes[1, 0].set_yticks(range(len(removal_order)))
                axes[1, 0].set_yticklabels(removal_order)
                axes[1, 0].set_xlabel('Removal Order (1 = first removed)')
                axes[1, 0].set_title('Last 10 Features Removed')
                axes[1, 0].invert_yaxis()
        
        if len(f1_scores) > 1:
            improvements = [f1_scores[i] - f1_scores[i-1] for i in range(1, len(f1_scores))]
            axes[1, 1].bar(range(len(improvements)), improvements)
            axes[1, 1].axhline(0, color='black', linewidth=0.5)
            axes[1, 1].set_xlabel('Iteration')
            axes[1, 1].set_ylabel('F1 Improvement')
            axes[1, 1].set_title('Performance Change After Each Removal')
            axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plot_path = os.path.join(self.model_dir, 'iterative_rfe_results.png')
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        if self.verbose:
            print(f"  Iterative RFE plot saved to: {plot_path}")
    
    def select_features_mutual_info(self, X_train: pd.DataFrame, y_train: pd.Series) -> List[str]:
        """Select features using mutual information."""
        if self.verbose:
            print("\n" + "="*60)
            print("MUTUAL INFORMATION FEATURE SELECTION")
            print("="*60)
        
        uncorrelated_features = self._remove_highly_correlated_features(X_train)
        X_train_filtered = X_train[uncorrelated_features].copy()
        
        selector = SelectKBest(mutual_info_classif, k=self.min_features)
        selector.fit(X_train_filtered, y_train)
        
        mask = selector.get_support()
        self.selected_features = X_train_filtered.columns[mask].tolist()
        
        scores = selector.scores_[mask]
        feature_scores = pd.DataFrame({
            'feature': self.selected_features,
            'score': scores
        }).sort_values('score', ascending=False)
        
        if self.verbose:
            print(f"\n  Selected {len(self.selected_features)} features:")
            print(f"\n  Top feature scores:")
            print(feature_scores.head(10).to_string(index=False))
        
        return self.selected_features
    
    def select_features_rfe(self, X_train: pd.DataFrame, y_train: pd.Series) -> List[str]:
        """Standard RFE feature selection with purged CV."""
        if self.verbose:
            print("\n" + "="*60)
            print("STANDARD RFE FEATURE SELECTION")
            print("="*60)
        
        base_estimator = RandomForestClassifier(
            n_estimators=50,
            max_depth=10,
            class_weight='balanced',
            random_state=self.random_state,
            n_jobs=-1
        )
        
        # FIX #5: Use purged CV
        cv = PurgedTimeSeriesSplit(n_splits=5, embargo_pct=0.01)
        
        self.selector = RFECV(
            estimator=base_estimator,
            step=1,
            cv=cv,
            scoring='f1',
            min_features_to_select=self.min_features,
            n_jobs=-1,
            verbose=1 if self.verbose else 0
        )
        
        self.selector.fit(X_train, y_train)
        
        self.selected_features = X_train.columns[self.selector.support_].tolist()
        
        if self.verbose:
            print(f"\n  Selected {len(self.selected_features)} features:")
            for i, feature in enumerate(self.selected_features, 1):
                print(f"    {i:2d}. {feature}")
        
        return self.selected_features
    
    def select_features_hybrid(self, X_train: pd.DataFrame, y_train: pd.Series) -> List[str]:
        """Hybrid feature selection."""
        if self.verbose:
            print("\n" + "="*60)
            print("HYBRID FEATURE SELECTION")
            print("="*60)
        
        return self.select_features_iterative_rfe(X_train, y_train)
    
    def select_features(self, X_train: pd.DataFrame, y_train: pd.Series) -> List[str]:
        """Main feature selection method."""
        if self.feature_selection_method == 'none':
            return self.select_features_none(X_train, y_train)
        elif self.feature_selection_method == 'iterative_rfe':
            return self.select_features_iterative_rfe(X_train, y_train)
        elif self.feature_selection_method == 'mutual_info':
            return self.select_features_mutual_info(X_train, y_train)
        elif self.feature_selection_method == 'rfe':
            return self.select_features_rfe(X_train, y_train)
        elif self.feature_selection_method == 'hybrid':
            return self.select_features_hybrid(X_train, y_train)
        elif self.feature_selection_method == 'correlation':
            self.selected_features = self.select_features_correlation(X_train, y_train)
            return self.selected_features 
        else:
            raise ValueError(f"Unknown feature selection method: {self.feature_selection_method}")
    
    def train_model(self, X_train: pd.DataFrame, y_train: pd.Series, 
                    calibrate: bool = True) -> RandomForestClassifier:
        """
        Train Random Forest model on selected features.
        
        FIX #3: No scaling applied. RF is scale-invariant.
        """
        if self.verbose:
            print("\n" + "=" * 60)
            print("TRAINING RANDOM FOREST MODEL")
            print("=" * 60)
        
        if self.selected_features is None:
            raise ValueError("Run select_features first!")
        
        X_train_selected = X_train[self.selected_features].copy()
        
        if self.verbose:
            print(f"Training on {len(self.selected_features)} selected features")
            print(f"Training set shape: {X_train_selected.shape}")
            print(f"Scaling: DISABLED (RF is scale-invariant)")
        
        # Store for later use
        self.X_train_selected = X_train_selected
        self.y_train = y_train.copy()
        
        # FIX #3: NO SCALING - pass raw features directly
        # RF splits on feature values, scaling doesn't change split points
        
        # Create and train Random Forest
        rf_model = RandomForestClassifier(**self.rf_params)
        
        if calibrate:
            if self.verbose:
                print("Calibrating probabilities with purged CV...")
            # FIX #2: Use purged CV for calibration too
            rf_model = CalibratedClassifierCV(
                rf_model,
                method='sigmoid',
                cv=PurgedTimeSeriesSplit(n_splits=3, embargo_pct=0.01),
                n_jobs=-1
            )
            self.is_calibrated = True
        else:
            self.is_calibrated = False
        
        # Train the model (no scaling!)
        rf_model.fit(X_train_selected, y_train)
        self.model = rf_model
        
        # Extract feature importances
        self._extract_feature_importances(rf_model, X_train_selected.columns, 
                                          X_train_selected, y_train)
        
        if self.verbose:
            print("Model training completed!")
            if self.feature_importances is not None:
                print(f"\nTop 20 feature importances:")
                print(self.feature_importances.head(20).to_string(index=False))
                self._plot_feature_importances()
        
        return rf_model
    
    def _extract_feature_importances(self, model, feature_names, X_train, y_train):
        """Extract feature importances from trained model."""
        try:
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
            elif hasattr(model, 'calibrated_classifiers_'):
                try:
                    calibrated_clf = model.calibrated_classifiers_[0]
                    if hasattr(calibrated_clf, 'base_estimator'):
                        base_estimator = calibrated_clf.base_estimator
                    elif hasattr(calibrated_clf, 'estimator'):
                        base_estimator = calibrated_clf.estimator
                    else:
                        base_estimator = calibrated_clf
                    
                    if hasattr(base_estimator, 'feature_importances_'):
                        importances = base_estimator.feature_importances_
                    else:
                        raise AttributeError("No feature_importances_")
                except:
                    rf_fallback = RandomForestClassifier(**self.rf_params)
                    rf_fallback.fit(X_train, y_train)
                    importances = rf_fallback.feature_importances_
            else:
                rf_fallback = RandomForestClassifier(**self.rf_params)
                rf_fallback.fit(X_train, y_train)
                importances = rf_fallback.feature_importances_
        except Exception as e:
            if self.verbose:
                print(f"  Warning extracting importances: {e}")
            importances = np.ones(len(feature_names)) / len(feature_names)
        
        self.feature_importances = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)
    
    def _plot_feature_importances(self, top_n: int = 20):
        """Plot feature importances."""
        if self.feature_importances is None:
            return
        
        plt.figure(figsize=(12, 8))
        top_features = self.feature_importances.head(top_n)
        
        plt.barh(range(len(top_features)), top_features['importance'], alpha=0.7)
        plt.yticks(range(len(top_features)), top_features['feature'])
        plt.xlabel('Feature Importance')
        plt.title(f'Top {top_n} Feature Importances')
        plt.grid(True, alpha=0.3, axis='x')
        plt.tight_layout()
        
        plot_path = os.path.join(self.model_dir, 'feature_importances.png')
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        if self.verbose:
            print(f"Feature importances plot saved to: {plot_path}")
    
    def optimize_threshold(self, X_train: pd.DataFrame, y_train: pd.Series, 
                          n_splits: int = 5) -> float:
        """
        Optimize prediction threshold using cross-validation.
        
        FIX #2: Now trains CALIBRATED models in each fold to match the actual
        model's probability distribution. Previously trained raw RF per fold
        but the actual model was CalibratedClassifierCV, causing a mismatch
        that produced meaningless thresholds (like 0.1).
        
        FIX #3: No scaling.
        FIX #5: Uses purged walk-forward CV.
        """
        if self.verbose:
            print("\n" + "="*60)
            print("OPTIMIZING PREDICTION THRESHOLD (FIXED)")
            print("="*60)
            print(f"  Using {'calibrated' if self.is_calibrated else 'raw'} fold models")
            print(f"  Purged walk-forward CV with {n_splits} splits")
        
        X_train_selected = X_train[self.selected_features].copy()
        # FIX #3: No scaling
        
        # FIX #5: Purged walk-forward CV
        cv = PurgedTimeSeriesSplit(n_splits=n_splits, embargo_pct=0.01)
        thresholds = np.linspace(0.15, 0.85, 15)

        
        scores = []
        
        # Also track precision at each threshold to avoid degenerate solutions
        precision_scores = []
        
        for threshold in thresholds:
            threshold_f1 = []
            threshold_prec = []
            
            for train_idx, val_idx in cv.split(X_train_selected):
                X_tr = X_train_selected.iloc[train_idx]
                X_val = X_train_selected.iloc[val_idx]
                y_tr = y_train.iloc[train_idx]
                y_val = y_train.iloc[val_idx]
                
                # FIX #2: Match the actual model type!
                # If the real model is calibrated, calibrate fold models too
                fold_model = RandomForestClassifier(**self.rf_params)
                
                if self.is_calibrated:
                    # Use inner CV for calibration within the fold
                    # Use 2-fold since each fold is already smaller
                    fold_model = CalibratedClassifierCV(
                        fold_model,
                        method='sigmoid',
                        cv=2,  # Simpler inner CV for speed
                        n_jobs=-1
                    )
                
                fold_model.fit(X_tr, y_tr)
                
                y_proba = fold_model.predict_proba(X_val)[:, 1]
                y_pred = (y_proba >= threshold).astype(int)
                
                # Only count if we have both classes in predictions
                if len(np.unique(y_pred)) > 1:
                    f1 = f1_score(y_val, y_pred)
                    prec = precision_score(y_val, y_pred, zero_division=0)
                    threshold_f1.append(f1)
                    threshold_prec.append(prec)
                elif np.unique(y_pred)[0] == 0:
                    # All predicted as 0 - score is 0
                    threshold_f1.append(0.0)
                    threshold_prec.append(0.0)
                else:
                    # All predicted as 1 - degenerate, penalize
                    threshold_f1.append(0.0)
                    threshold_prec.append(0.0)
            
            if threshold_f1:
                scores.append(np.mean(threshold_f1))
                precision_scores.append(np.mean(threshold_prec))
            else:
                scores.append(0)
                precision_scores.append(0)
        
        # Find best threshold: maximize F1 but require minimum precision
        # This prevents degenerate solutions where threshold is too low
        MIN_PRECISION = 0.35  # At least 35% precision required
        
        valid_scores = []
        for i, (f1, prec) in enumerate(zip(scores, precision_scores)):
            if prec >= MIN_PRECISION:
                valid_scores.append((f1, i))
            else:
                valid_scores.append((0, i))  # Penalize low-precision thresholds
        
        if any(s[0] > 0 for s in valid_scores):
            best_idx = max(valid_scores, key=lambda x: x[0])[1]
        else:
            # Fallback: just use best F1 if nothing meets precision requirement
            best_idx = np.argmax(scores)
            if self.verbose:
                print(f"  ⚠ No threshold meets minimum precision {MIN_PRECISION:.0%}")
                print(f"  ⚠ Falling back to best F1 threshold")
        
        self.best_threshold = thresholds[best_idx]
        
        if self.verbose:
            print(f"\n  Threshold search results:")
            print(f"  {'Threshold':>10} | {'F1':>8} | {'Precision':>10}")
            print(f"  {'-'*10}-+-{'-'*8}-+-{'-'*10}")
            for i, (t, f1, prec) in enumerate(zip(thresholds, scores, precision_scores)):
                marker = " <-- BEST" if i == best_idx else ""
                print(f"  {t:>10.3f} | {f1:>8.4f} | {prec:>10.4f}{marker}")
            
            print(f"\n  Optimal threshold: {self.best_threshold:.3f}")
            print(f"  F1 score at optimal: {scores[best_idx]:.4f}")
            print(f"  Precision at optimal: {precision_scores[best_idx]:.4f}")
            self._plot_threshold_optimization(thresholds, scores, precision_scores)
        
        return self.best_threshold
    
    def _plot_threshold_optimization(self, thresholds, f1_scores, precision_scores=None):
        """Plot threshold optimization results."""
        plt.figure(figsize=(10, 6))
        plt.plot(thresholds, f1_scores, 'o-', linewidth=2, label='F1 Score')
        if precision_scores:
            plt.plot(thresholds, precision_scores, 's--', linewidth=1.5, 
                    alpha=0.7, label='Precision')
        plt.axvline(self.best_threshold, color='red', linestyle='--', alpha=0.7,
                   label=f'Best Threshold = {self.best_threshold:.3f}')
        plt.xlabel('Threshold')
        plt.ylabel('Score')
        plt.title('Threshold Optimization (Fixed - Calibrated Fold Models)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plot_path = os.path.join(self.model_dir, 'threshold_optimization.png')
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        if self.verbose:
            print(f"Threshold optimization plot saved to: {plot_path}")

    def evaluate_model(self, X_test: pd.DataFrame, y_test: pd.Series, 
                    threshold: float = None, forced_threshold: float = None) -> Dict:
        """
        Evaluate model performance on test set.
        FIX #3: No scaling.
        """

        if self.forced_threshold is not None:
            use_threshold = self.forced_threshold
            threshold_source = "FORCED (from CONFIG)"
        elif threshold is not None:
            use_threshold = threshold
            threshold_source = "passed parameter"
        else:
            use_threshold = self.best_threshold
            threshold_source = "optimized"

        # FORCE threshold = 0.300 for TP=65
        # threshold = 0.33  # <-- ADD THIS LINE (FORCE IT!)
        
        if self.verbose:
            print("\n" + "="*60)
            print("MODEL EVALUATION ON TEST SET")
            print("="*60)
            print(f"Test set: {X_test.shape[0]} samples")
            print(f"Threshold: {use_threshold:.3f} ({threshold_source})")
            if self.best_threshold != use_threshold:
                print(f"Optimized threshold was: {self.best_threshold:.3f}")
        
        X_test_selected = X_test[self.selected_features].copy()
        # FIX #3: No scaling
        
        # Get predictions
        y_proba = self.model.predict_proba(X_test_selected)[:, 1]
        y_pred = (y_proba >= use_threshold).astype(int)
        
        # Calculate metrics
        metrics = self._calculate_metrics(y_test, y_pred, y_proba)
        
        if self.verbose:
            self._print_evaluation_results(metrics, y_test, y_pred)
            self._plot_evaluation_results(y_test, y_proba, y_pred, metrics)
        
        return metrics


    def _calculate_metrics(self, y_true, y_pred, y_proba):
        """Calculate comprehensive evaluation metrics."""
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'confusion_matrix': [[tn, fp], [fn, tp]],
            'true_negatives': tn,
            'false_positives': fp,
            'false_negatives': fn,
            'true_positives': tp,
            'prediction_distribution': {
                'class_0': int((y_pred == 0).sum()),
                'class_1': int((y_pred == 1).sum())
            },
            'true_distribution': {
                'class_0': int((y_true == 0).sum()),
                'class_1': int((y_true == 1).sum())
            }
        }
        
        metrics.update({
            'false_positive_rate': fp / (fp + tn) if (fp + tn) > 0 else 0,
            'true_positive_rate': tp / (tp + fn) if (tp + fn) > 0 else 0,
            'positive_predictive_value': tp / (tp + fp) if (tp + fp) > 0 else 0,
            'negative_predictive_value': tn / (tn + fn) if (tn + fn) > 0 else 0
        })
        
        precision_vals, recall_vals, _ = precision_recall_curve(y_true, y_proba)
        metrics['auc_pr'] = auc(recall_vals, precision_vals)
        
        return metrics
    

    def _print_evaluation_results(self, metrics: Dict, y_true: np.ndarray, y_pred: np.ndarray):
        """Print evaluation results."""
        tn, fp, fn, tp = metrics['true_negatives'], metrics['false_positives'], \
                        metrics['false_negatives'], metrics['true_positives']
        
        print(f"\nEvaluation Metrics:")
        print(f"  Accuracy:    {metrics['accuracy']:.3f}")
        print(f"  Precision:   {metrics['precision']:.3f}")
        print(f"  Recall:      {metrics['recall']:.3f}")
        print(f"  F1 Score:    {metrics['f1']:.3f}")
        print(f"  AUC-PR:      {metrics['auc_pr']:.3f}")
        print(f"\nConfusion Matrix:")
        print(f"  TN: {tn:6d}  |  FP: {fp:6d}")
        print(f"  FN: {fn:6d}  |  TP: {tp:6d}")
        print(f"\nDistribution:")
        print(f"  Predicted 0: {metrics['prediction_distribution']['class_0']:6d}")
        print(f"  Predicted 1: {metrics['prediction_distribution']['class_1']:6d}")
        print(f"  Actual 0:    {metrics['true_distribution']['class_0']:6d}")
        print(f"  Actual 1:    {metrics['true_distribution']['class_1']:6d}")
        
        print(f"\nClassification Report:")
        print(classification_report(y_true, y_pred, target_names=['Bad Short', 'Good Short']))


    def _plot_evaluation_results(self, y_test: pd.Series, y_proba: np.ndarray, 
                                y_pred: np.ndarray, metrics: Dict):
        """Plot evaluation results."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        
        # 1. Confusion Matrix
        sns.heatmap(metrics['confusion_matrix'], annot=True, fmt='d', 
                   cmap='Blues', ax=axes[0, 0])
        axes[0, 0].set_title('Confusion Matrix')
        axes[0, 0].set_xlabel('Predicted')
        axes[0, 0].set_ylabel('Actual')
        
        # 2. Precision-Recall Curve
        precision, recall, _ = precision_recall_curve(y_test, y_proba)
        axes[0, 1].plot(recall, precision, linewidth=2)
        axes[0, 1].fill_between(recall, precision, alpha=0.2)
        axes[0, 1].set_xlabel('Recall')
        axes[0, 1].set_ylabel('Precision')
        axes[0, 1].set_title(f'Precision-Recall Curve (AUC = {metrics["auc_pr"]:.3f})')
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Prediction Distribution
        pred_counts = [metrics['prediction_distribution']['class_0'], 
                      metrics['prediction_distribution']['class_1']]
        true_counts = [metrics['true_distribution']['class_0'], 
                      metrics['true_distribution']['class_1']]
        
        x = np.arange(2)
        width = 0.35
        axes[1, 0].bar(x - width/2, true_counts, width, label='Actual', alpha=0.7)
        axes[1, 0].bar(x + width/2, pred_counts, width, label='Predicted', alpha=0.7)
        axes[1, 0].set_xlabel('Class')
        axes[1, 0].set_ylabel('Count')
        axes[1, 0].set_title('Prediction vs Actual Distribution')
        axes[1, 0].set_xticks(x)
        axes[1, 0].set_xticklabels(['Bad Short (0)', 'Good Short (1)'])
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3, axis='y')
        
        # 4. Probability Distribution
        axes[1, 1].hist(y_proba[y_test == 0], bins=30, alpha=0.5, 
                       label='Bad Short (0)', density=True)
        axes[1, 1].hist(y_proba[y_test == 1], bins=30, alpha=0.5, 
                       label='Good Short (1)', density=True)
        axes[1, 1].axvline(self.best_threshold, color='red', linestyle='--', 
                          label=f'Threshold = {self.best_threshold:.2f}')
        axes[1, 1].set_xlabel('Predicted Probability')
        axes[1, 1].set_ylabel('Density')
        axes[1, 1].set_title('Probability Distribution by True Class')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plot_path = os.path.join(self.model_dir, 'evaluation_results.png')
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        if self.verbose:
            print(f"Evaluation plots saved to: {plot_path}")
    
    def save_model(self, X_train: pd.DataFrame, metadata: Dict = None) -> Dict:
        """Save trained model and metadata."""
        if self.verbose:
            print("\n" + "="*60)
            print("SAVING MODEL AND METADATA")
            print("="*60)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.metadata = {
            'timestamp': timestamp,
            'version': 'v3.2_fixed',
            'model_type': 'RandomForestClassifier',
            'is_calibrated': self.is_calibrated,
            'scaling': 'NONE (RF is scale-invariant)',
            'feature_selection_method': self.feature_selection_method,
            'n_features_selected': len(self.selected_features),
            'selected_features': self.selected_features,
            'best_threshold': float(self.best_threshold),
            'rf_params': self.rf_params,
            'feature_importances': self.feature_importances.to_dict('records') if self.feature_importances is not None else None,
            'training_info': {
                'n_samples': X_train.shape[0] if X_train is not None else None,
                'n_features_total': X_train.shape[1] if X_train is not None else None,
                'selected_features_count': len(self.selected_features)
            },
            'fixes_applied': [
                'No scaling for RF',
                'Calibrated threshold optimization',
                'Purged walk-forward CV',
                'Next-bar open entry price',
                'Excluded non-stationary features'
            ]
        }
        
        if metadata:
            self.metadata.update(metadata)
        
        saved_files = self._save_model_files(timestamp)
        
        return saved_files
    
    def _save_model_files(self, timestamp: str) -> Dict:
        """Save all model files."""
        saved_files = {}
        
        # FIX #3: No scaler saved (not needed)
        model_data = {
            'model': self.model,
            'selected_features': self.selected_features,
            'best_threshold': self.best_threshold,
            'is_calibrated': self.is_calibrated,
            'feature_importances': self.feature_importances
            # NO scaler - RF doesn't need scaling
        }
        
        model_path = os.path.join(self.model_dir, f'model_{timestamp}.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        saved_files['model'] = model_path
        
        metadata_path = os.path.join(self.model_dir, f'metadata_{timestamp}.json')
        with open(metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)
        saved_files['metadata'] = metadata_path
        
        if self.feature_importances is not None:
            features_path = os.path.join(self.model_dir, f'features_{timestamp}.csv')
            self.feature_importances.to_csv(features_path, index=False)
            saved_files['features'] = features_path
        
        selected_path = os.path.join(self.model_dir, f'selected_features_{timestamp}.txt')
        with open(selected_path, 'w') as f:
            for feature in self.selected_features:
                f.write(f"{feature}\n")
        saved_files['selected_features'] = selected_path
        
        if self.verbose:
            print(f"Model saved to: {model_path}")
            print(f"Metadata saved to: {metadata_path}")
            if 'features' in saved_files:
                print(f"Feature importances saved to: {saved_files['features']}")
            print(f"Selected features saved to: {selected_path}")
        
        return saved_files
    
    def predict(self, X_new: pd.DataFrame, threshold: float = None) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions on new data. FIX #3: No scaling."""
        if threshold is None:
            threshold = self.best_threshold
        
        if self.selected_features is None:
            raise ValueError("No features selected. Load or train a model first.")
        
        missing_features = set(self.selected_features) - set(X_new.columns)
        if missing_features:
            raise ValueError(f"Missing features: {missing_features}")
        
        X_new_selected = X_new[self.selected_features].copy()
        # FIX #3: No scaling
        
        y_proba = self.model.predict_proba(X_new_selected)[:, 1]
        y_pred = (y_proba >= threshold).astype(int)
        
        return y_pred, y_proba
    
    def load_model(self, model_path: str):
        """Load a trained model."""
        with open(model_path, 'rb') as f:
            saved_data = pickle.load(f)
        
        self.model = saved_data['model']
        self.selected_features = saved_data['selected_features']
        self.best_threshold = saved_data.get('best_threshold', 0.5)
        self.is_calibrated = saved_data.get('is_calibrated', False)
        self.feature_importances = saved_data.get('feature_importances')
        # FIX #3: No scaler to load
        
        if self.verbose:
            print(f"Model loaded from: {model_path}")
            print(f"Selected features: {len(self.selected_features)}")
            print(f"Best threshold: {self.best_threshold}")
            print(f"Calibrated: {self.is_calibrated}")


def train_full_pipeline(train_df: pd.DataFrame, test_df: pd.DataFrame, 
                        model_dir: str = 'models', label_col: str = 'label',
                        feature_selection_method: str = 'iterative_rfe',
                        min_features: int = 10, max_features: int = 30,
                        calibrate: bool = True, forced_threshold: float = None) -> Dict:
    """Complete training pipeline."""
    print("="*70)
    print("PROFESSIONAL MODEL TRAINING PIPELINE (v3.2 FIXED)")
    print("="*70)
    
    trainer = ModelTrainer(
        model_dir=model_dir,
        feature_selection_method=feature_selection_method,
        min_features=min_features,
        max_features=max_features,
        verbose=True,
        forced_threshold=forced_threshold
    )
    
    exclude_cols = ['timestamp']
    X_train, y_train, X_test, y_test, feature_names = trainer.prepare_data(
        train_df, test_df, label_col, exclude_cols
    )
    
    selected_features = trainer.select_features(X_train, y_train)
    model = trainer.train_model(X_train, y_train, calibrate=calibrate)
    best_threshold = trainer.optimize_threshold(X_train, y_train)
    evaluation_threshold = forced_threshold if forced_threshold is not None else best_threshold
    metrics = trainer.evaluate_model(X_test, y_test, evaluation_threshold)
    
    metadata = {
        'training_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'train_samples': len(train_df),
        'test_samples': len(test_df),
        'total_features': len(feature_names),
        'selected_features_count': len(selected_features),
        'feature_selection_method': feature_selection_method,
        'evaluation_metrics': metrics,
        'label_distribution': {
            'train_positive': float(y_train.mean()),
            'train_negative': float(1 - y_train.mean()),
            'test_positive': float(y_test.mean()),
            'test_negative': float(1 - y_test.mean())
        }
    }
    
    saved_files = trainer.save_model(X_train, metadata)
    
    print("\n" + "="*70)
    print("TRAINING COMPLETE - SUMMARY")
    print("="*70)
    print(f"Feature Selection Method: {feature_selection_method}")
    print(f"Selected Features: {len(selected_features)}")
    print(f"Best Threshold: {best_threshold:.3f}")
    print(f"Test Performance:")
    print(f"  Precision: {metrics['precision']:.3f}")
    print(f"  Recall:    {metrics['recall']:.3f}")
    print(f"  F1 Score:  {metrics['f1']:.3f}")
    print(f"  AUC-PR:    {metrics['auc_pr']:.3f}")
    print(f"\nModel saved to: {saved_files['model']}")
    print("="*70)
    
    return {
        'trainer': trainer,
        'metrics': metrics,
        'saved_files': saved_files,
        'selected_features': selected_features,
        'best_threshold': best_threshold
    }