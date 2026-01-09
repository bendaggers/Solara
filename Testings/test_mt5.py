"""
model_checker.py - Comprehensive Model Diagnostics

This is your model's health checkup doctor - it examines every aspect of your 
trained ML model to ensure it's ready for trading. It checks feature names, 
validates the prediction pipeline, examines thresholds, and provides detailed 
diagnostics. Think of it as a pre-flight checklist before your AI trading 
system takes off, ensuring all systems are go and nothing is overlooked.
"""

import pickle
import numpy as np
import pandas as pd
import json
import os
import warnings
from datetime import datetime
from sklearn.metrics import roc_curve, precision_recall_curve, f1_score
import config

warnings.filterwarnings('ignore')  # Suppress sklearn warnings for clean output


class ModelChecker:
    """Comprehensive diagnostics for trading models"""
    
    def __init__(self, model_path=None, config_module=None):
        self.model_path = model_path or os.path.join(config.MODELS_PATH, config.BB_REVERSAL_LONG_MODEL)
        self.config = config_module or config
        self.model = None
        self.metadata = {}
        self.feature_names = []
        self.threshold = getattr(config, 'BB_REVERSAL_LONG_THRESHOLD', 0.7)
        
    def run_full_diagnostics(self):
        """Run complete model diagnostics"""
        print("🔍" * 50)
        print("🤖 COMPREHENSIVE MODEL DIAGNOSTICS")
        print("🔍" * 50)
        
        results = {}
        
        # 1. Check file existence and load model
        results['file_check'] = self.check_model_file()
        
        # 2. Load and inspect model
        results['model_load'] = self.load_and_inspect_model()
        
        # 3. Check feature names and counts
        results['feature_check'] = self.check_features()
        
        # 4. Validate threshold
        results['threshold_check'] = self.check_threshold()
        
        # 5. Test prediction pipeline
        results['prediction_test'] = self.test_prediction_pipeline()
        
        # 6. Check for metadata
        results['metadata_check'] = self.check_metadata()
        
        # 7. Performance simulation
        results['performance_sim'] = self.simulate_performance()
        
        # 8. Export diagnostics report
        self.export_report(results)
        
        print("\n✅ Diagnostics complete!")
        return results
    
    def check_model_file(self):
        """Check if model file exists and is accessible"""
        print("\n📁 1. MODEL FILE CHECK")
        print("-" * 40)
        
        result = {'exists': False, 'size': 0, 'path': self.model_path}
        
        try:
            if os.path.exists(self.model_path):
                result['exists'] = True
                result['size'] = os.path.getsize(self.model_path)
                result['readable'] = True
                print(f"✅ Model file found: {self.model_path}")
                print(f"   Size: {result['size']:,} bytes ({result['size']/1024:.1f} KB)")
                
                # Check file permissions
                if os.access(self.model_path, os.R_OK):
                    print(f"✅ File is readable")
                else:
                    print(f"❌ File is not readable - check permissions")
                    result['readable'] = False
            else:
                print(f"❌ Model file NOT found: {self.model_path}")
                
        except Exception as e:
            print(f"❌ Error checking file: {str(e)}")
            result['error'] = str(e)
            
        return result
    
    def load_and_inspect_model(self):
        """Load model and inspect its properties"""
        print("\n🤖 2. MODEL INSPECTION")
        print("-" * 40)
        
        result = {'loaded': False, 'type': None, 'features_in': 0}
        
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            
            result['loaded'] = True
            result['type'] = str(type(self.model)).split("'")[1]
            
            print(f"✅ Model loaded successfully")
            print(f"   Type: {result['type']}")
            
            # Get basic model info
            if hasattr(self.model, 'n_features_in_'):
                result['features_in'] = self.model.n_features_in_
                print(f"   Expected features: {result['features_in']}")
                
            if hasattr(self.model, 'n_classes_'):
                print(f"   Number of classes: {self.model.n_classes_}")
                
            if hasattr(self.model, 'estimators_'):
                print(f"   Number of trees: {len(self.model.estimators_)}")
                
            # Check for model-specific attributes
            model_attrs = [attr for attr in dir(self.model) 
                          if not attr.startswith('_') and not callable(getattr(self.model, attr))]
            
            print(f"\n📋 Model attributes ({len(model_attrs)}):")
            for attr in sorted(model_attrs):
                value = getattr(self.model, attr)
                if isinstance(value, (int, float, str, bool, list, tuple)):
                    print(f"   • {attr}: {value}")
                elif hasattr(value, 'shape'):
                    print(f"   • {attr}: shape {value.shape}")
                    
        except Exception as e:
            print(f"❌ Failed to load model: {str(e)}")
            result['error'] = str(e)
            
        return result
    
    def check_features(self):
        """Check feature names and validation"""
        print("\n📊 3. FEATURE VALIDATION")
        print("-" * 40)
        
        result = {'has_feature_names': False, 'expected_features': [], 
                 'count_match': False, 'names_match': False}
        
        if self.model is None:
            print("❌ Model not loaded")
            return result
        
        # Check if model has feature names
        if hasattr(self.model, 'feature_names_in_'):
            result['has_feature_names'] = True
            self.feature_names = list(self.model.feature_names_in_)
            result['expected_features'] = self.feature_names.copy()
            
            print(f"✅ Model has feature names")
            print(f"📋 Expected features ({len(self.feature_names)}):")
            for i, name in enumerate(self.feature_names):
                print(f"   {i+1:2d}. {name}")
                
            # Check against what preprocessor should provide
            from preprocessors.bb_reversal_long_preprocessor import BBReversalLongPreprocessor
            preprocessor = BBReversalLongPreprocessor()
            preprocessor_features = preprocessor.feature_names
            
            result['preprocessor_features'] = preprocessor_features
            
            if len(self.feature_names) == len(preprocessor_features):
                result['count_match'] = True
                print(f"✅ Feature count matches: {len(self.feature_names)}")
                
                # Check if names match
                names_match = all(a == b for a, b in zip(self.feature_names, preprocessor_features))
                result['names_match'] = names_match
                
                if names_match:
                    print(f"✅ Feature names match exactly!")
                else:
                    print(f"⚠️ Feature names don't match!")
                    print(f"   Model expects: {self.feature_names}")
                    print(f"   Preprocessor provides: {preprocessor_features}")
            else:
                print(f"❌ Feature count mismatch!")
                print(f"   Model expects: {len(self.feature_names)}")
                print(f"   Preprocessor provides: {len(preprocessor_features)}")
        else:
            print(f"⚠️ Model doesn't have feature_names_in_ attribute")
            
        return result
    
    def check_threshold(self):
        """Validate and suggest thresholds"""
        print("\n🎯 4. THRESHOLD ANALYSIS")
        print("-" * 40)
        
        result = {'current_threshold': self.threshold, 'recommended': None}
        
        print(f"Current threshold in config: {self.threshold}")
        
        # Check if model has saved threshold
        model_threshold = None
        if self.model is not None:
            threshold_attrs = [attr for attr in dir(self.model) 
                             if 'threshold' in attr.lower() and not attr.startswith('_')]
            
            if threshold_attrs:
                for attr in threshold_attrs:
                    value = getattr(self.model, attr)
                    if isinstance(value, (int, float)):
                        model_threshold = value
                        print(f"✅ Model has saved threshold: {attr} = {value}")
                        break
        
        # Threshold recommendations
        print(f"\n📈 Threshold guidance:")
        print(f"   • < 0.60: Very aggressive (many trades, lower quality)")
        print(f"   • 0.60-0.70: Aggressive")
        print(f"   • 0.70-0.75: Balanced (recommended starting point)")
        print(f"   • 0.75-0.80: Conservative")
        print(f"   • > 0.80: Very conservative (few but high quality trades)")
        
        if model_threshold and abs(model_threshold - self.threshold) > 0.05:
            print(f"\n⚠️ Warning: Config threshold ({self.threshold}) differs from model's ({model_threshold})")
            result['recommended'] = model_threshold
            
        return result
    
    def test_prediction_pipeline(self):
        """Test the complete prediction pipeline"""
        print("\n🧪 5. PREDICTION PIPELINE TEST")
        print("-" * 40)
        
        result = {'samples_tested': 0, 'predictions_work': False}
        
        if self.model is None or not self.feature_names:
            print("❌ Cannot test - model or features not loaded")
            return result
        
        # Create test samples
        test_samples = [
            {
                'name': 'Strong BUY Signal',
                'features': [1.0001, 0.05, 0.30, 1.0, 0.8, -0.02, -0.05, 1.5, -0.03, 0.1]
            },
            {
                'name': 'Strong NO-BUY Signal',
                'features': [1.2, 0.7, 0.7, 0.0, 0.1, 0.1, 0.1, 0.8, 0.02, 0.8]
            },
            {
                'name': 'Marginal Signal',
                'features': [1.0005, 0.2, 0.45, 0.0, 0.3, 0.0, 0.0, 1.1, -0.01, 0.3]
            }
        ]
        
        print("Testing 3 sample scenarios:")
        print("=" * 60)
        
        for sample in test_samples:
            print(f"\n📊 {sample['name']}:")
            
            # Create DataFrame with proper feature names
            df = pd.DataFrame([sample['features']], columns=self.feature_names)
            
            try:
                # Get predictions
                prediction = self.model.predict(df)[0]
                probabilities = self.model.predict_proba(df)[0]
                confidence = abs(probabilities[1] - 0.5) * 2
                
                print(f"   Prediction: {prediction} (0=NO BUY, 1=BUY)")
                print(f"   Probabilities: [NO_BUY={probabilities[0]:.3f}, BUY={probabilities[1]:.3f}]")
                print(f"   Confidence: {confidence:.3f}")
                print(f"   Meets threshold ({self.threshold})? {confidence >= self.threshold}")
                
                # Show feature values
                print(f"   Feature values:")
                for i, (name, value) in enumerate(zip(self.feature_names, sample['features'])):
                    print(f"     {i+1:2d}. {name:25s}: {value:.4f}")
                    
                result['samples_tested'] += 1
                
            except Exception as e:
                print(f"   ❌ Prediction failed: {str(e)}")
                
        if result['samples_tested'] > 0:
            result['predictions_work'] = True
            print(f"\n✅ Prediction pipeline working!")
            
        return result
    
    def check_metadata(self):
        """Check for and load model metadata"""
        print("\n📄 6. METADATA CHECK")
        print("-" * 40)
        
        result = {'found': False, 'files': []}
        
        model_dir = os.path.dirname(self.model_path)
        
        # Look for metadata files
        metadata_patterns = ['*metadata*', '*threshold*', '*report*', '*train*', '*val*']
        
        for pattern in metadata_patterns:
            import glob
            files = glob.glob(os.path.join(model_dir, pattern))
            for file in files:
                if file != self.model_path:  # Don't include the model itself
                    result['files'].append(file)
        
        if result['files']:
            result['found'] = True
            print(f"✅ Found metadata files:")
            for file in result['files']:
                print(f"   • {os.path.basename(file)}")
                
            # Try to read metadata
            for file in result['files']:
                try:
                    if file.endswith('.json'):
                        with open(file, 'r') as f:
                            data = json.load(f)
                            print(f"\n📖 Contents of {os.path.basename(file)}:")
                            print(json.dumps(data, indent=2)[:500] + "..." if len(json.dumps(data)) > 500 else json.dumps(data, indent=2))
                    elif file.endswith('.txt') or file.endswith('.csv'):
                        with open(file, 'r') as f:
                            content = f.read()
                            print(f"\n📖 Contents of {os.path.basename(file)} (first 500 chars):")
                            print(content[:500] + "..." if len(content) > 500 else content)
                except Exception as e:
                    print(f"   Could not read {file}: {str(e)}")
        else:
            print(f"ℹ️ No metadata files found")
            
        return result
    
    def simulate_performance(self):
        """Simulate model performance with different thresholds"""
        print("\n📈 7. PERFORMANCE SIMULATION")
        print("-" * 40)
        
        result = {'simulation_run': False}
        
        if not self.feature_names:
            print("❌ Cannot simulate - no feature names")
            return result
        
        # Generate random test data
        np.random.seed(42)
        n_samples = 1000
        
        print(f"Simulating {n_samples} random trades with different thresholds...")
        
        # Create random features
        X_sim = np.random.randn(n_samples, len(self.feature_names))
        
        # Adjust to make some samples look like good trades
        for i in range(n_samples):
            if i % 4 == 0:  # 25% good trades
                X_sim[i, 0] = 1.0001 + np.random.randn() * 0.0005  # bb_touch_strength
                X_sim[i, 1] = np.random.uniform(0, 0.2)  # bb_position low
                X_sim[i, 2] = np.random.uniform(0.2, 0.4)  # rsi_value low
                X_sim[i, 3] = 1  # rsi_divergence
        
        # Get predictions
        df_sim = pd.DataFrame(X_sim, columns=self.feature_names)
        probabilities = self.model.predict_proba(df_sim)[:, 1]  # Probability of class 1 (BUY)
        
        # Test different thresholds
        thresholds = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
        
        print("\nThreshold | Trades Taken | Avg Confidence")
        print("-" * 40)
        
        for thresh in thresholds:
            # Calculate confidence scores
            confidences = np.abs(probabilities - 0.5) * 2
            
            # Count trades that would be taken
            trades_taken = np.sum(confidences >= thresh)
            avg_confidence = np.mean(confidences[confidences >= thresh]) if trades_taken > 0 else 0
            
            marker = " ← current" if abs(thresh - self.threshold) < 0.01 else ""
            print(f"   {thresh:.2f}   |     {trades_taken:4d}      |     {avg_confidence:.3f}{marker}")
        
        result['simulation_run'] = True
        
        return result
    
    def export_report(self, results):
        """Export diagnostic report"""
        print("\n💾 8. EXPORTING DIAGNOSTICS REPORT")
        print("-" * 40)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'model_path': self.model_path,
            'threshold': self.threshold,
            'results': results,
            'recommendations': self.generate_recommendations(results)
        }
        
        # Create reports directory
        reports_dir = os.path.join(os.path.dirname(self.model_path), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        # Save report
        report_file = os.path.join(reports_dir, f"diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"✅ Report saved to: {report_file}")
        
        # Also print summary
        self.print_summary(results)
    
    def generate_recommendations(self, results):
        """Generate actionable recommendations"""
        recs = []
        
        if not results['file_check'].get('exists', False):
            recs.append("❌ MODEL FILE MISSING - Check model path in config.py")
        
        if not results['model_load'].get('loaded', False):
            recs.append("❌ CANNOT LOAD MODEL - File may be corrupted or wrong format")
        
        if results['feature_check'].get('has_feature_names', False):
            if not results['feature_check'].get('count_match', False):
                recs.append("⚠️ FEATURE COUNT MISMATCH - Update preprocessor to match model")
            if not results['feature_check'].get('names_match', False):
                recs.append("⚠️ FEATURE NAMES MISMATCH - Ensure preprocessor uses exact feature names")
        else:
            recs.append("ℹ️ MODEL LACKS FEATURE NAMES - Consider retraining with feature names")
        
        if results['threshold_check'].get('recommended'):
            recs.append(f"💡 THRESHOLD UPDATE - Model suggests {results['threshold_check']['recommended']}")
        
        if not results['prediction_test'].get('predictions_work', False):
            recs.append("❌ PREDICTIONS FAILING - Check feature values and model compatibility")
        
        if not results['metadata_check'].get('found', False):
            recs.append("ℹ️ NO METADATA FOUND - Save training metrics for future reference")
        
        return recs
    
    def print_summary(self, results):
        """Print summary of diagnostics"""
        print("\n" + "⭐" * 50)
        print("📋 DIAGNOSTICS SUMMARY")
        print("⭐" * 50)
        
        checks = [
            ("Model File", results['file_check'].get('exists', False)),
            ("Model Loaded", results['model_load'].get('loaded', False)),
            ("Feature Names", results['feature_check'].get('has_feature_names', False)),
            ("Feature Count Match", results['feature_check'].get('count_match', False)),
            ("Feature Names Match", results['feature_check'].get('names_match', False)),
            ("Predictions Work", results['prediction_test'].get('predictions_work', False)),
        ]
        
        for check_name, status in checks:
            symbol = "✅" if status else "❌"
            print(f"{symbol} {check_name}")
        
        print("\n🚀 RECOMMENDED ACTIONS:")
        recs = self.generate_recommendations(results)
        if recs:
            for rec in recs:
                print(f"   {rec}")
        else:
            print("   🎉 All systems go! Your model is ready for trading.")
        
        print(f"\n🔧 Current threshold: {self.threshold}")
        print("💡 Next steps: Run backtests with different thresholds to optimize performance")


def quick_check():
    """Quick one-command model check"""
    checker = ModelChecker()
    print("\n⚡ QUICK MODEL CHECK")
    print("=" * 50)
    
    # Just run essential checks
    checker.check_model_file()
    checker.load_and_inspect_model()
    checker.check_features()
    checker.check_threshold()
    
    print("\n✅ Quick check complete!")


if __name__ == "__main__":
    # Run full diagnostics
    checker = ModelChecker()
    checker.run_full_diagnostics()
    
    # Or run quick check only
    # quick_check()