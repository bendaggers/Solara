import pandas as pd
import numpy as np
import pickle
import json
import itertools
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
import warnings
warnings.filterwarnings('ignore')

class FeatureOptimizer:
    """
    Automated feature optimization with systematic search
    """
    
    def __init__(self, features_file="processed_features.pkl"):
        self.features_file = features_file
        self.features = None
        self.model = None
        self.best_features = None
        self.best_score = -np.inf
        self.optimization_history = []
        
    def load_features(self):
        """Load processed features"""
        print("Loading features...")
        with open(self.features_file, 'rb') as f:
            self.features = pickle.load(f)
        
        print(f"Features shape: {self.features.shape}")
        print(f"Total features available: {self.features.shape[1] - 1}")  # minus label
        
        return self.features
    
    def get_feature_importance_ranking(self, n_estimators=100, max_depth=10):
        """Get initial feature importance ranking"""
        print("\n🔍 Getting initial feature importance ranking...")
        
        # Read feature columns
        with open('feature_columns.txt', 'r') as f:
            all_features = [line.strip() for line in f]
        
        # Filter to existing columns
        feature_names = [col for col in all_features if col in self.features.columns]
        
        X = self.features[feature_names]
        y = self.features['label']
        
        # Train a quick RandomForest for importance
        rf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        
        rf.fit(X, y)
        
        # Get importances
        importances = pd.DataFrame({
            'feature': feature_names,
            'importance': rf.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print(f"\nTop 20 features by importance:")
        for i, (_, row) in enumerate(importances.head(20).iterrows()):
            print(f"  {i+1:2}. {row['feature']:30} : {row['importance']:.4f}")
        
        importances.to_csv('initial_feature_importance.csv', index=False)
        print(f"\nInitial feature importance saved to 'initial_feature_importance.csv'")
        
        return importances
    
    def evaluate_feature_set(self, feature_set, cv_folds=5):

        """Evaluate a specific feature set using cross-validation"""
        # Filter to features that actually exist in the DataFrame
        valid_features = [f for f in feature_set if f in self.features.columns]
        
        if len(valid_features) < 2:  # Need at least 2 features
            return {
                'n_features': len(valid_features),
                'mean_f1': 0.0,
                'std_f1': 0.0,
                'cv_scores': [0.0] * cv_folds
            }
        
        X = self.features[valid_features]
        y = self.features['label']
        
        # Handle any NaN values
        if X.isna().any().any():
            X = X.fillna(0)

       
        # Use time series cross-validation
        tscv = TimeSeriesSplit(n_splits=cv_folds)
        
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        
        # Cross-validate
        cv_scores = cross_val_score(model, X, y, cv=tscv, scoring='f1', n_jobs=-1)
        
        return {
            'n_features': len(feature_set),
            'mean_f1': cv_scores.mean(),
            'std_f1': cv_scores.std(),
            'cv_scores': cv_scores.tolist()
        }
    
    def greedy_forward_selection(self, top_n_features=50, max_features=30):
        """Greedy forward feature selection"""
        print(f"\n🚀 Starting greedy forward selection (max {max_features} features)...")
        
        # Get initial importance ranking
        importance_df = self.get_feature_importance_ranking()
        top_features = importance_df['feature'].head(top_n_features).tolist()
        
        selected_features = []
        available_features = top_features.copy()
        best_score = -np.inf
        
        iteration = 0
        
        while len(selected_features) < max_features and available_features:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            print(f"Selected: {len(selected_features)} features")
            
            best_candidate = None
            best_candidate_score = -np.inf
            
            # Try each available feature
            for i, feature in enumerate(available_features):
                candidate_set = selected_features + [feature]
                
                if iteration % 5 == 0 and i % 10 == 0:
                    print(f"  Testing {i+1}/{len(available_features)}: {feature}")
                
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
                
                # Save this state
                self.optimization_history.append({
                    'iteration': iteration,
                    'feature_added': best_candidate,
                    'selected_features': selected_features.copy(),
                    'score': best_candidate_score,
                    'n_features': len(selected_features)
                })
                
                # Update best overall
                if best_candidate_score > best_score:
                    best_score = best_candidate_score
                    self.best_features = selected_features.copy()
                    self.best_score = best_score
        
        print(f"\n✅ Greedy forward selection complete!")
        print(f"Best F1 Score: {best_score:.4f}")
        print(f"Number of features: {len(self.best_features)}")
        
        return self.best_features
    
    def backward_elimination(self, initial_features, min_features=10):
        """Backward elimination from full feature set"""
        print(f"\n🔙 Starting backward elimination (min {min_features} features)...")
        
        current_features = initial_features.copy()
        best_score = self.evaluate_feature_set(current_features)['mean_f1']
        
        iteration = 0
        
        while len(current_features) > min_features:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            print(f"Current: {len(current_features)} features")
            
            worst_feature = None
            best_removal_score = -np.inf
            
            # Try removing each feature
            for i, feature in enumerate(current_features):
                candidate_set = [f for f in current_features if f != feature]
                
                if iteration % 5 == 0 and i % 10 == 0:
                    print(f"  Testing removal {i+1}/{len(current_features)}: {feature}")
                
                scores = self.evaluate_feature_set(candidate_set, cv_folds=3)
                
                if scores['mean_f1'] > best_removal_score:
                    best_removal_score = scores['mean_f1']
                    worst_feature = feature
            
            # If removing improves score, remove it
            if best_removal_score >= best_score and worst_feature:
                current_features.remove(worst_feature)
                best_score = best_removal_score
                
                print(f"✗ Removed: {worst_feature}")
                print(f"  New score: {best_score:.4f}")
                
                self.optimization_history.append({
                    'iteration': iteration,
                    'feature_removed': worst_feature,
                    'remaining_features': current_features.copy(),
                    'score': best_score,
                    'n_features': len(current_features)
                })
                
                # Update best overall
                if best_score > self.best_score:
                    self.best_features = current_features.copy()
                    self.best_score = best_score
            else:
                print(f"⏹️  No improvement from removal. Stopping.")
                break
        
        print(f"\n✅ Backward elimination complete!")
        print(f"Best F1 Score: {self.best_score:.4f}")
        print(f"Number of features: {len(self.best_features)}")
        
        return self.best_features
    
    def category_based_optimization(self):
        """Optimize features by category (more intelligent)"""
        print("\n🧠 Starting category-based optimization...")
        
        # Define feature categories (modify based on your actual features)
        categories = {
            'BB_Features': ['bb_width', 'bb_position', 'bb_pctB', 'bb_band_distance'],
            'RSI_Features': ['rsi', 'rsi_slope', 'rsi_divergence'],
            'Price_Action': ['close_ratio', 'high_low_ratio', 'body_size', 'wick_ratio'],
            'Volume': ['volume_change', 'volume_ratio', 'volume_slope'],
            'Trend': ['ema_slope', 'trend_strength', 'momentum'],
            'Patterns': ['hammer', 'doji', 'engulfing', 'pinbar'],
            'Support_Resistance': ['sr_distance', 'sr_touch_count'],
            'Time_Features': ['hour', 'day_of_week', 'month']
        }
        
        # Filter to existing features
        with open('feature_columns.txt', 'r') as f:
            all_features = [line.strip() for line in f]
        
        actual_categories = {}
        for category, possible_features in categories.items():
            actual_features = [f for f in possible_features if f in all_features]
            if actual_features:
                actual_categories[category] = actual_features
        
        print("\nFeature categories identified:")
        for category, features in actual_categories.items():
            print(f"  {category}: {len(features)} features")
        
        # Start with 1 best feature from each category
        initial_features = []
        importance_df = self.get_feature_importance_ranking()
        
        for category, features in actual_categories.items():
            # Find most important feature in this category
            category_importance = importance_df[importance_df['feature'].isin(features)]
            if not category_importance.empty:
                best_in_category = category_importance.iloc[0]['feature']
                initial_features.append(best_in_category)
                print(f"  Selected from {category}: {best_in_category}")
        
        print(f"\nInitial feature set: {len(initial_features)} features")
        
        # Now optimize within each category
        optimized_features = initial_features.copy()
        
        for category, features in actual_categories.items():
            print(f"\nOptimizing {category}...")
            
            # Evaluate current set
            current_score = self.evaluate_feature_set(optimized_features)['mean_f1']
            
            # Try adding other features from this category
            for feature in features:
                if feature not in optimized_features:
                    candidate_set = optimized_features + [feature]
                    candidate_score = self.evaluate_feature_set(candidate_set)['mean_f1']
                    
                    if candidate_score > current_score:
                        optimized_features.append(feature)
                        current_score = candidate_score
                        print(f"  ✓ Added {feature} (score: {candidate_score:.4f})")
        
        print(f"\n✅ Category-based optimization complete!")
        print(f"Final features: {len(optimized_features)}")
        
        # Update best
        final_score = self.evaluate_feature_set(optimized_features)['mean_f1']
        if final_score > self.best_score:
            self.best_features = optimized_features
            self.best_score = final_score
        
        return optimized_features
    
    def genetic_optimization(self, population_size=20, generations=10, elite_size=4):
        """Genetic algorithm for feature selection"""
        print(f"\n🧬 Starting genetic optimization...")
        
        importance_df = self.get_feature_importance_ranking()
        all_features = importance_df['feature'].head(50).tolist()  # Work with top 50
        
        # Initialize population
        population = []
        for _ in range(population_size):
            # Random feature set (10-25 features)
            n_features = np.random.randint(10, 26)
            features = list(np.random.choice(all_features, n_features, replace=False))
            score = self.evaluate_feature_set(features)['mean_f1']
            population.append((features, score))
        
        population.sort(key=lambda x: x[1], reverse=True)
        
        for generation in range(generations):
            print(f"\nGeneration {generation + 1}/{generations}")
            print(f"Best score: {population[0][1]:.4f} ({len(population[0][0])} features)")
            
            # Elitism: keep best individuals
            new_population = population[:elite_size]
            
            # Create next generation
            while len(new_population) < population_size:
                # Selection (tournament)
                parent1 = self._tournament_selection(population)
                parent2 = self._tournament_selection(population)
                
                # Crossover
                child = self._crossover(parent1[0], parent2[0], all_features)
                
                # Mutation
                if np.random.random() < 0.3:
                    child = self._mutate(child, all_features)
                
                # Evaluate child
                child_score = self.evaluate_feature_set(child)['mean_f1']
                new_population.append((child, child_score))
            
            population = sorted(new_population, key=lambda x: x[1], reverse=True)
        
        # Update best
        self.best_features = population[0][0]
        self.best_score = population[0][1]
        
        print(f"\n✅ Genetic optimization complete!")
        print(f"Best F1 Score: {self.best_score:.4f}")
        print(f"Number of features: {len(self.best_features)}")
        
        return self.best_features
    
    def _tournament_selection(self, population, tournament_size=3):
        """Tournament selection for genetic algorithm"""
        tournament = np.random.choice(len(population), tournament_size, replace=False)
        tournament = [population[i] for i in tournament]
        return max(tournament, key=lambda x: x[1])
    
    def _crossover(self, parent1, parent2, all_features):
        """Crossover for genetic algorithm"""
        # Union crossover
        child = list(set(parent1) | set(parent2))
        
        # Trim if too many features
        if len(child) > 30:
            child = list(np.random.choice(child, 30, replace=False))
        
        return child
    
    def _mutate(self, individual, all_features, mutation_rate=0.1):
        """Mutation for genetic algorithm"""
        mutated = individual.copy()
        
        # Add random feature
        if np.random.random() < mutation_rate and len(mutated) < 30:
            available = [f for f in all_features if f not in mutated]
            if available:
                mutated.append(np.random.choice(available))
        
        # Remove random feature
        if np.random.random() < mutation_rate and len(mutated) > 5:
            mutated.pop(np.random.randint(len(mutated)))
        
        return mutated
    
    def run_comprehensive_optimization(self):
        """Run all optimization strategies and select best"""
        print("="*70)
        print("🤖 AUTOMATED FEATURE OPTIMIZATION")
        print("="*70)
        
        # Load features
        self.load_features()
        
        # Run different optimization strategies
        strategies = {
            'greedy_forward': self.greedy_forward_selection,
            'backward': lambda: self.backward_elimination(
                self.get_feature_importance_ranking()['feature'].head(40).tolist()
            ),
            'category_based': self.category_based_optimization,
            'genetic': self.genetic_optimization
        }
        
        results = {}
        
        for strategy_name, strategy_func in strategies.items():
            print(f"\n{'='*60}")
            print(f"Running {strategy_name.replace('_', ' ').title()}...")
            print(f"{'='*60}")
            
            try:
                features = strategy_func()
                score = self.evaluate_feature_set(features)['mean_f1']
                results[strategy_name] = {
                    'features': features,
                    'score': score,
                    'n_features': len(features)
                }
                print(f"  Score: {score:.4f}, Features: {len(features)}")
            except Exception as e:
                print(f"  Error in {strategy_name}: {e}")
        
        # Select best strategy
        if results:
            best_strategy = max(results.items(), key=lambda x: x[1]['score'])
            best_name, best_result = best_strategy
            
            self.best_features = best_result['features']
            self.best_score = best_result['score']
            
            print(f"\n{'='*70}")
            print(f"🏆 BEST STRATEGY: {best_name.replace('_', ' ').title()}")
            print(f"{'='*70}")
            print(f"F1 Score: {self.best_score:.4f}")
            print(f"Number of features: {len(self.best_features)}")
            print(f"Features per category:")
            
            # Analyze feature categories
            categories = {}
            for feature in self.best_features:
                cat = self._categorize_feature(feature)
                categories[cat] = categories.get(cat, 0) + 1
            
            for cat, count in sorted(categories.items()):
                print(f"  {cat}: {count}")
            
            # Save results
            self._save_optimization_results(results)
            
            # Save best feature set
            self._save_best_features()
            
            return self.best_features
        else:
            print("No successful optimization strategies!")
            return None
    
    def _categorize_feature(self, feature_name):
        """Categorize a feature based on its name"""
        feature_name = feature_name.lower()
        
        if 'bb_' in feature_name or 'bollinger' in feature_name:
            return 'Bollinger_Bands'
        elif 'rsi' in feature_name:
            return 'RSI'
        elif any(x in feature_name for x in ['close', 'open', 'high', 'low', 'price']):
            return 'Price_Action'
        elif 'volume' in feature_name:
            return 'Volume'
        elif any(x in feature_name for x in ['ema', 'sma', 'ma', 'trend', 'momentum']):
            return 'Trend'
        elif any(x in feature_name for x in ['wick', 'body', 'candle', 'pattern']):
            return 'Candle_Patterns'
        elif any(x in feature_name for x in ['hour', 'day', 'week', 'month', 'time']):
            return 'Time_Features'
        else:
            return 'Other'
    
    def _save_optimization_results(self, results):
        """Save all optimization results"""
        output = {
            'optimization_date': pd.Timestamp.now().isoformat(),
            'best_score': self.best_score,
            'best_features': self.best_features,
            'all_strategies': {}
        }
        
        for strategy_name, result in results.items():
            output['all_strategies'][strategy_name] = {
                'score': result['score'],
                'n_features': result['n_features'],
                'features': result['features']
            }
        
        with open('feature_optimization_results.json', 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\n📊 Optimization results saved to 'feature_optimization_results.json'")
    
    def _save_best_features(self):
        """Save the best feature set to a text file"""
        with open('optimized_features.txt', 'w') as f:
            f.write("# Optimized Feature Set - Auto-generated\n")
            f.write(f"# Generated: {pd.Timestamp.now()}\n")
            f.write(f"# F1 Score: {self.best_score:.4f}\n")
            f.write(f"# Number of features: {len(self.best_features)}\n")
            f.write("#" * 50 + "\n\n")
            
            # Group by category
            categorized = {}
            for feature in self.best_features:
                cat = self._categorize_feature(feature)
                if cat not in categorized:
                    categorized[cat] = []
                categorized[cat].append(feature)
            
            # Write categorized
            for category in sorted(categorized.keys()):
                f.write(f"\n# {category} ({len(categorized[category])} features)\n")
                for feature in sorted(categorized[category]):
                    f.write(f"{feature}\n")
            
            # Also write flat list for compatibility
            f.write("\n" + "#" * 50 + "\n")
            f.write("# Flat list for model training\n")
            f.write("#" * 50 + "\n")
            for feature in self.best_features:
                f.write(f"{feature}\n")
        
        print(f"✅ Optimized feature set saved to 'optimized_features.txt'")
        
        # Also save as CSV with importance if available
        try:
            importance_df = self.get_feature_importance_ranking()
            best_importance = importance_df[importance_df['feature'].isin(self.best_features)]
            best_importance.to_csv('optimized_features_with_importance.csv', index=False)
            print(f"📈 Feature importance saved to 'optimized_features_with_importance.csv'")
        except:
            pass

def main():
    """Run the automated feature optimization"""
    print("="*70)
    print("🤖 AUTOMATED FEATURE SELECTION OPTIMIZER")
    print("="*70)
    
    optimizer = FeatureOptimizer()
    
    print("\n1. Loading data...")
    optimizer.load_features()
    
    print("\n2. Running comprehensive optimization...")
    best_features = optimizer.run_comprehensive_optimization()
    
    if best_features:
        print("\n" + "="*70)
        print("✅ OPTIMIZATION COMPLETE!")
        print("="*70)
        print(f"\n🎯 Best feature set: {len(best_features)} features")
        print(f"📈 Expected F1 Score: {optimizer.best_score:.4f}")
        print(f"\n📄 Output files created:")
        print("  1. optimized_features.txt - Best feature set")
        print("  2. feature_optimization_results.json - All results")
        print("  3. optimized_features_with_importance.csv - With scores")
        print("\n🔧 Next steps:")
        print("  1. Use 'optimized_features.txt' in your model training")
        print("  2. Retrain model with optimized features")
        print("  3. Compare performance with original feature set")
    else:
        print("\n❌ Optimization failed!")

if __name__ == "__main__":
    main()