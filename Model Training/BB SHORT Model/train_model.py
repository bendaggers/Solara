import pandas as pd
import numpy as np
import pickle
import json
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, precision_recall_curve
from sklearn.model_selection import cross_val_score, TimeSeriesSplit
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class BollingerBandsModelTrainer:
    """
    Train and evaluate the Bollinger Bands Reversal Short model
    """
    
    def __init__(self, features_file="processed_features.pkl"):
        self.features_file = features_file
        self.features = None
        self.model = None
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.feature_names = None
        
    def load_features(self):
        """Load processed features"""
        print("Loading features...")
        with open(self.features_file, 'rb') as f:
            self.features = pickle.load(f)
        
        print(f"Features shape: {self.features.shape}")
        print(f"Label distribution: 0={(self.features['label']==0).sum()}, 1={(self.features['label']==1).sum()}")
        print(f"Positive ratio: {self.features['label'].mean():.3f}")
        
        return self.features
    
    def prepare_data(self, test_size=0.2, random_state=42):
        """Prepare training and testing data"""
        if self.features is None:
            self.load_features()
        
        # Read feature columns from file
        with open('feature_columns.txt', 'r') as f:
            feature_names = [line.strip() for line in f]
        
        # Filter to existing columns
        self.feature_names = [col for col in feature_names if col in self.features.columns]
        
        print(f"\nUsing {len(self.feature_names)} features")
        
        # For time series, use chronological split
        split_idx = int(len(self.features) * (1 - test_size))
        
        # Prepare feature matrix and labels
        X = self.features[self.feature_names]
        y = self.features['label']
        
        # Split chronologically (no shuffling for time series)
        self.X_train = X.iloc[:split_idx]
        self.X_test = X.iloc[split_idx:]
        self.y_train = y.iloc[:split_idx]
        self.y_test = y.iloc[split_idx:]
        
        print(f"\nData Split:")
        print(f"  Train: {self.X_train.shape} ({self.y_train.sum()}/{len(self.y_train)} positive)")
        print(f"  Test:  {self.X_test.shape} ({self.y_test.sum()}/{len(self.y_test)} positive)")
        
        # Add timestamps if available
        if 'timestamp' in self.features.columns:
            self.train_timestamps = self.features['timestamp'].iloc[:split_idx]
            self.test_timestamps = self.features['timestamp'].iloc[split_idx:]
            print(f"  Train period: {self.train_timestamps.min()} to {self.train_timestamps.max()}")
            print(f"  Test period:  {self.test_timestamps.min()} to {self.test_timestamps.max()}")
        
        return self.X_train, self.X_test, self.y_train, self.y_test
    
    def train_random_forest(self, n_estimators=200, max_depth=15, 
                           class_weight='balanced_subsample', random_state=42):
        """Train Random Forest classifier"""
        print("\n" + "="*60)
        print("TRAINING RANDOM FOREST CLASSIFIER")
        print("="*60)
        
        # Initialize model
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features='sqrt',
            class_weight=class_weight,
            random_state=random_state,
            n_jobs=-1,
            bootstrap=True,
            oob_score=True
        )
        
        print(f"Model parameters:")
        print(f"  n_estimators: {n_estimators}")
        print(f"  max_depth: {max_depth}")
        print(f"  class_weight: {class_weight}")
        print(f"  max_features: sqrt")
        
        # Train the model
        print("\nTraining model...")
        self.model.fit(self.X_train, self.y_train)
        
        # Out-of-bag score
        print(f"\nOut-of-bag score: {self.model.oob_score_:.4f}")
        
        return self.model
    
    def evaluate_model(self, threshold=0.5):
        """Evaluate model performance"""
        if self.model is None:
            raise ValueError("Model not trained yet. Call train_random_forest() first.")
        
        print("\n" + "="*60)
        print("MODEL EVALUATION")
        print("="*60)
        
        # Predictions
        y_pred_proba = self.model.predict_proba(self.X_test)[:, 1]
        y_pred = (y_pred_proba >= threshold).astype(int)
        
        # Classification report
        print("\nClassification Report:")
        print(classification_report(self.y_test, y_pred, 
                                   target_names=['No Short', 'Short'],
                                   digits=4))
        
        # Confusion matrix
        print("\nConfusion Matrix:")
        cm = confusion_matrix(self.y_test, y_pred)
        print(f"                Predicted")
        print(f"                No Short  Short")
        print(f"Actual No Short  {cm[0,0]:7d}  {cm[0,1]:6d}")
        print(f"Actual Short     {cm[1,0]:7d}  {cm[1,1]:6d}")
        
        # Calculate metrics
        tn, fp, fn, tp = cm.ravel()
        accuracy = (tp + tn) / (tp + tn + fp + fn)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        
        print(f"\nDetailed Metrics:")
        print(f"  Accuracy:    {accuracy:.4f}")
        print(f"  Precision:   {precision:.4f}")
        print(f"  Recall:      {recall:.4f}")
        print(f"  F1-Score:    {f1:.4f}")
        print(f"  Specificity: {specificity:.4f}")
        print(f"  AUC-ROC:     {roc_auc_score(self.y_test, y_pred_proba):.4f}")
        
        # Save predictions for analysis
        predictions_df = pd.DataFrame({
            'timestamp': self.test_timestamps.values if hasattr(self, 'test_timestamps') else range(len(self.y_test)),
            'actual': self.y_test.values,
            'predicted': y_pred,
            'probability': y_pred_proba
        })
        
        predictions_df.to_csv('model_predictions.csv', index=False)
        print(f"\nPredictions saved to 'model_predictions.csv'")
        
        return y_pred_proba, y_pred
    
    def analyze_feature_importance(self, top_n=20):
        """Analyze and visualize feature importance"""
        if self.model is None:
            raise ValueError("Model not trained yet.")
        
        print("\n" + "="*60)
        print("FEATURE IMPORTANCE ANALYSIS")
        print("="*60)
        
        # Get feature importances
        importances = self.model.feature_importances_
        indices = np.argsort(importances)[::-1]
        
        print(f"\nTop {top_n} Most Important Features:")
        print("-" * 50)
        
        top_features = []
        for i in range(min(top_n, len(self.feature_names))):
            feat_idx = indices[i]
            feat_name = self.feature_names[feat_idx]
            importance = importances[feat_idx]
            top_features.append((feat_name, importance))
            print(f"{i+1:2}. {feat_name:30} : {importance:.4f}")
        
        # Create feature importance DataFrame
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)
        
        # Save to CSV
        importance_df.to_csv('feature_importance.csv', index=False)
        print(f"\nFull feature importance saved to 'feature_importance.csv'")
        
        # Group features by category
        print("\nFeature Importance by Category:")
        print("-" * 50)
        
        categories = {
            'BB Features': [f for f in importance_df['feature'] if 'bb_' in f],
            'RSI Features': [f for f in importance_df['feature'] if 'rsi_' in f],
            'Price Features': [f for f in importance_df['feature'] if any(x in f for x in ['close', 'open', 'high', 'low'])],
            'Volume Features': [f for f in importance_df['feature'] if 'volume' in f],
            'Candle Features': [f for f in importance_df['feature'] if any(x in f for x in ['wick', 'body', 'candle'])],
            'Trend Features': [f for f in importance_df['feature'] if any(x in f for x in ['trend', 'momentum', 'slope', 'ema'])],
            'Derived Features': [f for f in importance_df['feature'] if any(x in f for x in ['rejection', 'signal', 'score'])]
        }
        
        for category, features in categories.items():
            if features:
                cat_importance = importance_df[importance_df['feature'].isin(features)]['importance'].sum()
                print(f"  {category:20}: {cat_importance:.4f}")
        
        # Visualize top features
        self._plot_feature_importance(importance_df.head(top_n))
        
        return importance_df
    
    def _plot_feature_importance(self, importance_df):
        """Plot feature importance"""
        plt.figure(figsize=(12, 8))
        bars = plt.barh(range(len(importance_df)), importance_df['importance'][::-1])
        plt.yticks(range(len(importance_df)), importance_df['feature'][::-1])
        plt.xlabel('Feature Importance')
        plt.title('Top Feature Importances - Bollinger Bands Short Model')
        
        # Add value labels
        for i, (bar, importance) in enumerate(zip(bars, importance_df['importance'][::-1])):
            plt.text(bar.get_width() + 0.001, bar.get_y() + bar.get_height()/2,
                    f'{importance:.4f}', va='center')
        
        plt.tight_layout()
        plt.savefig('feature_importance_plot.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f"\nFeature importance plot saved to 'feature_importance_plot.png'")
    
    def optimize_threshold(self):
        """Find optimal probability threshold"""
        print("\n" + "="*60)
        print("THRESHOLD OPTIMIZATION")
        print("="*60)
        
        y_pred_proba = self.model.predict_proba(self.X_test)[:, 1]
        
        # Calculate precision-recall curve
        precision, recall, thresholds = precision_recall_curve(self.y_test, y_pred_proba)
        
        # Find threshold that maximizes F1-score
        f1_scores = 2 * precision * recall / (precision + recall)
        f1_scores = np.nan_to_num(f1_scores)  # Handle division by zero
        
        optimal_idx = np.argmax(f1_scores)
        optimal_threshold = thresholds[optimal_idx] if optimal_idx < len(thresholds) else 0.5
        
        print(f"\nOptimal threshold based on F1-score: {optimal_threshold:.4f}")
        print(f"Maximum F1-score: {f1_scores[optimal_idx]:.4f}")
        
        # Test different thresholds
        print("\nPerformance at different thresholds:")
        print("-" * 50)
        print("Threshold | Precision | Recall   | F1-Score")
        print("-" * 50)
        
        test_thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
        for thresh in test_thresholds:
            y_pred = (y_pred_proba >= thresh).astype(int)
            cm = confusion_matrix(self.y_test, y_pred)
            tn, fp, fn, tp = cm.ravel()
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            
            print(f"{thresh:9.2f} | {precision:9.4f} | {recall:8.4f} | {f1:8.4f}")
        
        return optimal_threshold
    

    def save_model(self, filename='BB_SHORT_REVERSAL_Model.pkl'):
        """Save the trained model (just the model, no dictionary wrapper)"""
        if self.model is None:
            raise ValueError("Model not trained yet.")
        
        # Save ONLY the model (not wrapped in dictionary)
        with open(filename, 'wb') as f:
            pickle.dump(self.model, f)  # <-- JUST the model object
        
        print(f"\nModel saved to '{filename}'")
        
        # Save feature names separately (for reference)
        feature_names_path = 'feature_columns.txt'
        with open(feature_names_path, 'w') as f:
            for feature in self.feature_names:
                f.write(f"{feature}\n")
        print(f"Feature names saved to '{feature_names_path}'")
        
        # Save model info as JSON (separate file)
        model_info = {
            'model_type': 'RandomForestClassifier',
            'training_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'n_features': len(self.feature_names),
            'train_samples': int(self.X_train.shape[0]),
            'test_samples': int(self.X_test.shape[0]),
            'train_positive': int(self.y_train.sum()),
            'test_positive': int(self.y_test.sum()),
            'optimal_threshold': self.optimal_threshold if hasattr(self, 'optimal_threshold') else 0.5,
            'save_format': 'model_only'  # Indicates no dictionary wrapper
        }
        
        with open('model_info.json', 'w') as f:
            json.dump(model_info, f, indent=2)
        
        print(f"Model info saved to 'model_info.json'")
        
        return filename





    def generate_trading_signals(self, threshold=0.5):
        """Generate trading signals from test predictions"""
        print("\n" + "="*60)
        print("TRADING SIGNAL GENERATION")
        print("="*60)
        
        y_pred_proba = self.model.predict_proba(self.X_test)[:, 1]
        y_pred = (y_pred_proba >= threshold).astype(int)
        
        # Create signals DataFrame
        signals_df = pd.DataFrame({
            'timestamp': self.test_timestamps.values if hasattr(self, 'test_timestamps') else [],
            'close': self.X_test['close_lag1'].values if 'close_lag1' in self.X_test.columns else np.zeros(len(y_pred)),
            'signal': y_pred,
            'probability': y_pred_proba,
            'actual': self.y_test.values
        })
        
        # Add signal strength categories
        signals_df['signal_strength'] = pd.cut(signals_df['probability'], 
                                               bins=[0, 0.3, 0.5, 0.7, 0.9, 1.0],
                                               labels=['Very Weak', 'Weak', 'Moderate', 'Strong', 'Very Strong'])
        
        # Calculate signal statistics
        total_signals = signals_df['signal'].sum()
        correct_signals = signals_df[(signals_df['signal'] == 1) & (signals_df['actual'] == 1)].shape[0]
        
        print(f"\nSignal Statistics:")
        print(f"  Total signals generated: {total_signals}")
        print(f"  Correct signals: {correct_signals}")
        print(f"  Signal accuracy: {correct_signals/max(1, total_signals):.2%}")
        
        # Save signals
        signals_df.to_csv('trading_signals.csv', index=False)
        print(f"\nTrading signals saved to 'trading_signals.csv'")
        
        # Analyze signal strength
        print(f"\nSignal Strength Distribution:")
        strength_counts = signals_df[signals_df['signal'] == 1]['signal_strength'].value_counts().sort_index()
        for strength, count in strength_counts.items():
            print(f"  {strength:12}: {count:3d} signals")
        
        return signals_df

def main():
    """Main execution function"""
    print("="*70)
    print("BOLLINGER BANDS REVERSAL SHORT - MODEL TRAINING")
    print("="*70)
    
    # Initialize trainer
    trainer = BollingerBandsModelTrainer()
    
    # Step 1: Load features
    trainer.load_features()
    
    # Step 2: Prepare data (80/20 split)
    trainer.prepare_data(test_size=0.2)
    
    # Step 3: Train Random Forest
    trainer.train_random_forest(
        n_estimators=200,
        max_depth=15,
        class_weight='balanced_subsample'
    )
    
    # Step 4: Evaluate model
    y_pred_proba, y_pred = trainer.evaluate_model(threshold=0.5)
    
    # Step 5: Analyze feature importance
    importance_df = trainer.analyze_feature_importance(top_n=20)
    
    # Step 6: Optimize threshold
    optimal_threshold = trainer.optimize_threshold()
    
    # Step 7: Save model
    trainer.save_model('BB_SHORT_REVERSAL_Model.pkl')
    
    # Step 8: Generate trading signals
    signals_df = trainer.generate_trading_signals(threshold=optimal_threshold)
    
    print("\n" + "="*70)
    print("MODEL TRAINING COMPLETE")
    print("="*70)
    print("\nGenerated Files:")
    print("  1. bb_rev_short_model.pkl    - Trained model")
    print("  2. model_info.json           - Model metadata")
    print("  3. feature_importance.csv    - Feature rankings")
    print("  4. feature_importance_plot.png - Feature importance visualization")
    print("  5. model_predictions.csv     - Test set predictions")
    print("  6. trading_signals.csv       - Trading signals")
    print("\nNext Steps:")
    print("  1. Review feature importance to understand what drives predictions")
    print("  2. Adjust threshold based on risk tolerance (current optimal: {:.3f})".format(optimal_threshold))
    print("  3. Test model on new data")
    print("  4. Integrate with trading system")

if __name__ == "__main__":
    main()