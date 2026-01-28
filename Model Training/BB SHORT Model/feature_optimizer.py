# feature_optimizer_fixed.py

import pandas as pd
import numpy as np
import pickle
import json
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
import warnings
warnings.filterwarnings('ignore')

class FeatureOptimizer15:
    """
    Optimize features down to 15, handling non-numeric columns properly
    """
    
    def __init__(self, features_file="processed_features.pkl", target_features=15):
        self.features_file = features_file
        self.target_features = target_features
        self.features = None
        self.numeric_features = None
        self.best_features = None
        self.best_score = -np.inf
        
    def load_features(self):
        """Load processed features and identify numeric columns"""
        print("Loading features...")
        with open(self.features_file, 'rb') as f:
            self.features = pickle.load(f)
        
        print(f"Features shape: {self.features.shape}")
        
        # Identify non-numeric columns
        non_numeric_cols = []
        for col in self.features.columns:
            if not pd.api.types.is_numeric_dtype(self.features[col]):
                non_numeric_cols.append(col)
        
        if non_numeric_cols:
            print(f"\n⚠️  Non-numeric columns found (will be excluded):")
            for col in non_numeric_cols:
                dtype = self.features[col].dtype
                sample = self.features[col].iloc[0] if len(self.features) > 0 else "N/A"
                print(f"  - {col}: {dtype} (sample: {sample})")
        
        # Get numeric features (exclude 'label' and non-numeric columns)
        self.numeric_features = []
        for col in self.features.columns:
            if col == 'label':
                continue
            if pd.api.types.is_numeric_dtype(self.features[col]):
                self.numeric_features.append(col)
            else:
                print(f"  Excluding non-numeric: {col}")
        
        print(f"\n✅ Numeric features available: {len(self.numeric_features)}")
        print(f"Label column found: {'label' in self.features.columns}")
        
        return self.features
    
    def get_feature_importance_ranking(self, n_estimators=100, max_depth=10):
        """Get initial feature importance ranking - FIXED VERSION"""
        print(f"\n🔍 Getting initial feature importance ranking...")
        
        if self.numeric_features is None:
            self.load_features()
        
        # Use only numeric features
        X = self.features[self.numeric_features].copy()
        y = self.features['label'].copy()
        
        print(f"X shape: {X.shape}")
        print(f"y shape: {y.shape}")
        
        # Handle any NaN values
        if X.isna().any().any():
            print(f"Handling NaN values in features...")
            X = X.fillna(0)
        
        # Check for any remaining non-numeric issues
        for col in X.columns:
            try:
                # Try to convert to numeric
                X[col] = pd.to_numeric(X[col], errors='coerce')
            except:
                print(f"Warning: Could not convert {col} to numeric")
        
        # Fill any new NaN values created during conversion
        X = X.fillna(0)
        
        # Train a quick RandomForest for importance
        rf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        )
        
        print("Training RandomForest for feature importance...")
        rf.fit(X, y)
        
        # Get importances
        importances = pd.DataFrame({
            'feature': self.numeric_features,
            'importance': rf.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print(f"\nTop 30 features by importance:")
        for i, (_, row) in enumerate(importances.head(30).iterrows()):
            print(f"  {i+1:2}. {row['feature']:30} : {row['importance']:.4f}")
        
        importances.to_csv('feature_importance_full.csv', index=False)
        print(f"\nFull feature importance saved to 'feature_importance_full.csv'")
        
        return importances
    
    def evaluate_feature_set(self, feature_set, cv_folds=5):
        """Evaluate a specific feature set using cross-validation"""
        # Filter to features that actually exist and are numeric
        valid_features = []
        for f in feature_set:
            if f in self.numeric_features:
                valid_features.append(f)
        
        if len(valid_features) < 2:
            print(f"  Warning: Only {len(valid_features)} valid features in set")
            return {
                'n_features': len(valid_features),
                'mean_f1': 0.0,
                'std_f1': 0.0,
                'cv_scores': [0.0] * cv_folds
            }
        
        X = self.features[valid_features].copy()
        y = self.features['label'].copy()
        
        # Handle NaN values
        X = X.fillna(0)
        
        # Convert all columns to numeric to be safe
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors='coerce')
        X = X.fillna(0)
        
        # Use time series cross-validation
        tscv = TimeSeriesSplit(n_splits=min(cv_folds, 5))
        
        model = RandomForestClassifier(
            n_estimators=50,
            max_depth=8,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        )
        
        # Cross-validate
        try:
            cv_scores = cross_val_score(model, X, y, cv=tscv, scoring='f1', n_jobs=-1)
            mean_score = cv_scores.mean()
        except Exception as e:
            print(f"  Cross-validation error: {e}")
            mean_score = 0.0
            cv_scores = [0.0] * cv_folds
        
        return {
            'n_features': len(valid_features),
            'mean_f1': mean_score,
            'std_f1': cv_scores.std() if len(cv_scores) > 1 else 0.0,
            'cv_scores': cv_scores.tolist()
        }
    
    def simple_top_n_selection(self):
        """Simple selection: just take top N features by importance"""
        print(f"\n📊 Simple top-{self.target_features} feature selection...")
        
        importance_df = self.get_feature_importance_ranking()
        top_features = importance_df['feature'].head(self.target_features).tolist()
        
        # Evaluate this simple selection
        scores = self.evaluate_feature_set(top_features)
        
        self.best_features = top_features
        self.best_score = scores['mean_f1']
        
        print(f"\n✅ Simple selection complete!")
        print(f"Selected {len(self.best_features)} features")
        print(f"F1 Score: {self.best_score:.4f}")
        
        return self.best_features
    
    def greedy_forward_selection_targeted(self):
        """Greedy forward selection targeting 15 features"""
        print(f"\n🚀 Starting greedy forward selection (target: {self.target_features} features)...")
        
        # Get initial importance ranking
        importance_df = self.get_feature_importance_ranking()
        top_features = importance_df['feature'].head(40).tolist()  # Start with top 40
        
        selected_features = []
        available_features = top_features.copy()
        best_score = -np.inf
        
        iteration = 0
        
        while len(selected_features) < self.target_features and available_features:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            print(f"Selected: {len(selected_features)}/{self.target_features} features")
            print(f"Available: {len(available_features)} features")
            
            best_candidate = None
            best_candidate_score = -np.inf
            
            # Try each available feature (limit to 20 for speed)
            test_features = available_features[:20]
            for i, feature in enumerate(test_features):
                candidate_set = selected_features + [feature]
                
                if i % 5 == 0:
                    print(f"  Testing candidate {i+1}/{len(test_features)}...")
                
                # Evaluate candidate set
                scores = self.evaluate_feature_set(candidate_set, cv_folds=3)
                
                if scores['mean_f1'] > best_candidate_score:
                    best_candidate_score = scores['mean_f1']
                    best_candidate = feature
            
            # Add best candidate to selected features
            if best_candidate:
                selected_features.append(best_candidate)
                available_features.remove(best_candidate)
                
                print(f"✓ Added: {best_candidate}")
                print(f"  Score: {best_candidate_score:.4f}")
                print(f"  Progress: {len(selected_features)}/{self.target_features} features")
                
                # Update best overall
                if best_candidate_score > best_score:
                    best_score = best_candidate_score
                    self.best_features = selected_features.copy()
                    self.best_score = best_score
            else:
                print("No candidate improved score. Stopping.")
                break
        
        print(f"\n✅ Greedy forward selection complete!")
        print(f"Selected {len(self.best_features)} features")
        print(f"Best F1 Score: {self.best_score:.4f}")
        
        return self.best_features
    
    def analyze_feature_categories(self, feature_set):
        """Analyze the distribution of features across categories"""
        print(f"\n📊 Feature Category Analysis:")
        print("-" * 40)
        
        categories = {
            'Bollinger Bands': ['bb_', 'bbw', 'dist_bb', 'bb_position'],
            'RSI': ['rsi_'],
            'Price Action': ['close_', 'ret_', 'price_'],
            'Volume': ['volume_'],
            'Candle Patterns': ['wick_', 'body_', 'candle_'],
            'Moving Averages': ['ema_', 'sma_'],
            'Lagged Features': ['lag', '_lag']
        }
        
        category_counts = {cat: 0 for cat in categories.keys()}
        categorized_features = {cat: [] for cat in categories.keys()}
        
        for feature in feature_set:
            feature_lower = feature.lower()
            categorized = False
            
            for category, keywords in categories.items():
                for keyword in keywords:
                    if keyword in feature_lower:
                        category_counts[category] += 1
                        categorized_features[category].append(feature)
                        categorized = True
                        break
                if categorized:
                    break
        
        # Print category distribution
        total = 0
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                total += count
                print(f"  {category:20}: {count:2d} features")
                for feat in categorized_features[category]:
                    print(f"    - {feat}")
        
        # Calculate percentages
        print(f"\n📈 Category Distribution:")
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                percentage = (count / total) * 100
                print(f"  {category:20}: {percentage:5.1f}%")
        
        return category_counts
    
    def save_optimized_features(self, output_file="optimized_features_15.txt"):
        """Save the optimized 15-feature set"""
        if not self.best_features:
            print("No features to save!")
            return
        
        with open(output_file, 'w') as f:
            f.write(f"# Optimized Feature Set - {len(self.best_features)} Features\n")
            f.write(f"# Generated: {pd.Timestamp.now()}\n")
            f.write(f"# Target Features: {self.target_features}\n")
            f.write(f"# Best F1 Score: {self.best_score:.4f}\n")
            f.write("#" * 60 + "\n\n")
            
            # Write features
            for i, feature in enumerate(self.best_features, 1):
                f.write(f"{feature}\n")
            
            # Add category analysis
            f.write("\n" + "#" * 60 + "\n")
            f.write("# Category Analysis\n")
            f.write("#" * 60 + "\n")
            
            # Get category counts
            categories = self.analyze_feature_categories(self.best_features)
            
            for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    f.write(f"\n# {category} ({count} features)\n")
        
        print(f"\n✅ Optimized feature set saved to '{output_file}'")
        
        # Save as JSON with more details
        metadata = {
            'optimization_date': pd.Timestamp.now().isoformat(),
            'target_features': self.target_features,
            'actual_features': len(self.best_features),
            'best_score': float(self.best_score),
            'features': self.best_features,
            'total_numeric_features': len(self.numeric_features) if self.numeric_features else 0
        }
        
        with open('optimization_metadata_15.json', 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        print(f"📊 Optimization metadata saved to 'optimization_metadata_15.json'")
    
    def run_optimization_pipeline(self):
        """Run the complete optimization pipeline for 15 features"""
        print("="*70)
        print(f"🎯 FEATURE OPTIMIZATION PIPELINE - TARGET: {self.target_features} FEATURES")
        print("="*70)
        
        # Load data
        self.load_features()
        
        print(f"\n{'='*60}")
        print("Strategy 1: Simple Top-N Selection")
        print(f"{'='*60}")
        simple_features = self.simple_top_n_selection()
        simple_score = self.best_score
        
        print(f"\n{'='*60}")
        print("Strategy 2: Greedy Forward Selection")
        print(f"{'='*60}")
        # Reset for second strategy
        temp_features = self.best_features.copy()
        temp_score = self.best_score
        self.best_features = None
        self.best_score = -np.inf
        
        greedy_features = self.greedy_forward_selection_targeted()
        greedy_score = self.best_score
        
        # Choose best strategy
        if greedy_score > simple_score:
            print(f"\n🏆 Greedy selection is better: {greedy_score:.4f} vs {simple_score:.4f}")
        else:
            print(f"\n🏆 Simple selection is better: {simple_score:.4f} vs {greedy_score:.4f}")
            self.best_features = temp_features
            self.best_score = temp_score
        
        # Analyze feature categories
        print(f"\n{'='*60}")
        print("Final Feature Category Distribution")
        print(f"{'='*60}")
        self.analyze_feature_categories(self.best_features)
        
        # Save results
        self.save_optimized_features()
        
        print(f"\n{'='*70}")
        print("✅ OPTIMIZATION COMPLETE!")
        print(f"{'='*70}")
        print(f"\n🎯 Target: {self.target_features} features")
        print(f"📈 Achieved: {len(self.best_features)} features")
        print(f"🏆 Best F1 Score: {self.best_score:.4f}")
        
        return self.best_features

def main():
    """Main function to run 15-feature optimization"""
    print("="*70)
    print("🎯 15-FEATURE OPTIMIZATION PIPELINE")
    print("="*70)
    
    # Initialize optimizer
    optimizer = FeatureOptimizer15(target_features=15)
    
    # Run optimization
    best_features = optimizer.run_optimization_pipeline()
    
    if best_features:
        print(f"\n📄 Output files created:")
        print("  1. optimized_features_15.txt - 15-feature set")
        print("  2. optimization_metadata_15.json - Detailed metadata")
        print("  3. feature_importance_full.csv - All feature importances")
        
        print(f"\n🔧 Next steps:")
        print("  1. Update your train_model.py CURATED_FEATURES list with these 15 features")
        print("  2. Retrain model with the optimized feature set")
        print("  3. Compare performance with the original 30 features")
        
        print(f"\n📋 Optimized Feature List:")
        for i, feature in enumerate(best_features, 1):
            print(f"  {i:2}. {feature}")
    else:
        print("\n❌ Optimization failed!")

if __name__ == "__main__":
    main()