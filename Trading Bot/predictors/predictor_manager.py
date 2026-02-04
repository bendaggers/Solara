#!/usr/bin/env python3
"""
Predictor Manager - Handles concurrent execution of multiple predictors
CLEAN PRODUCTION VERSION
"""

import concurrent.futures
import time
import os
import sys
from typing import Dict, List, Any, Optional

# Clean import for PredictorReporter
try:
    from .predictor_reporter import PredictorReporter
except ImportError:
    # Create a simple fallback if import fails
    class PredictorReporter:
        def export_to_csv(self, combined_predictions, filename=None):
            print("⚠️ CSV export not available (PredictorReporter import failed)")
            return ""


class PredictorManager:
    """
    Manages concurrent execution of multiple trading predictors.
    Handles loading, running, and combining predictions from multiple strategies.
    """
    
    def __init__(self, config_module):
        """
        Initialize the PredictorManager.
        
        Args:
            config_module: The config module containing PREDICTOR_CONFIGS
        """
        self.config = config_module
        self.predictor_tasks = []
        self.results = []
        self.reporter = PredictorReporter()

    def export_predictions_csv(self, combined_predictions: Dict, 
                              filename: Optional[str] = None) -> str:
        """
        Export combined predictions to CSV.
        
        Args:
            combined_predictions: Output from combine_predictions()
            filename: Custom filename (optional)
            
        Returns:
            str: Path to exported CSV file
        """
        return self.reporter.export_to_csv(
            combined_predictions=combined_predictions,
            filename=filename
        )
        
    def load_predictors(self) -> bool:
        """
        Load all enabled predictors from configuration.
        
        Returns:
            bool: True if at least one predictor loaded successfully
        """
        print(f"🔧 Loading {len(self.config.ENABLED_PREDICTORS)} predictors...")
        
        for predictor_config in self.config.ENABLED_PREDICTORS:
            try:
                predictor_class = self.config.get_predictor_class(predictor_config['class_path'])
                self.predictor_tasks.append({
                    'class': predictor_class,
                    'config': predictor_config
                })
                print(f"   ✅ Loaded: {predictor_config['name']}")
                print(f"      ├─ Type: {predictor_config['model_type']}")
                print(f"      ├─ Model: {predictor_config['model_file']}")
                print(f"      ├─ Min Confidence: {predictor_config['min_confidence']}")
                print(f"      └─ Description: {predictor_config['comment']}")
            except Exception as e:
                print(f"   ❌ Failed to load {predictor_config['name']}: {str(e)}")
        
        return len(self.predictor_tasks) > 0
    
    def _run_single_predictor(self, predictor_class, predictor_config, processed_data) -> Dict:
        """
        Run a single predictor and return its predictions.
        This is the worker function for concurrent execution.
        
        Args:
            predictor_class: The predictor class to instantiate
            predictor_config: Configuration dictionary for this predictor
            processed_data: Preprocessed market data
            
        Returns:
            Dict: Predictions from this predictor
        """
        start_time = time.time()
        predictor_name = predictor_config['name']
        
        try:
            print(f"    🚀 Starting: {predictor_name}")
            
            # Initialize predictor
            predictor = predictor_class(
                models_path=self.config.MODELS_PATH,
                predictor_config=predictor_config
            )
            
            # Make predictions
            predictions = predictor.predict(processed_data)
            
            # Add metadata to predictions
            enriched_predictions = {}
            for symbol, prediction_data in predictions.items():
                if isinstance(prediction_data, dict):
                    prediction_data.update({
                        'predictor': predictor_name,
                        'predictor_type': predictor_config['model_type'],
                        'predictor_weight': predictor_config['weight'],
                        'predictor_confidence': predictor_config['min_confidence'],
                        'model_file': predictor_config['model_file']
                    })
                    enriched_predictions[symbol] = prediction_data
                else:
                    enriched_predictions[symbol] = {
                        'signal': prediction_data,
                        'predictor': predictor_name,
                        'predictor_type': predictor_config['model_type'],
                        'predictor_weight': predictor_config['weight'],
                        'predictor_confidence': predictor_config['min_confidence'],
                        'model_file': predictor_config['model_file']
                    }
            
            elapsed = time.time() - start_time
            return {
                'success': True,
                'predictor_name': predictor_name,
                'predictions': enriched_predictions,
                'elapsed_time': elapsed,
                'signal_count': len(enriched_predictions)
            }
            
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                'success': False,
                'predictor_name': predictor_name,
                'error': str(e),
                'elapsed_time': elapsed,
                'predictions': {}
            }
    
    def run_all_predictors(self, processed_data, max_workers: int = 4) -> List[Dict]:
        """
        Run all loaded predictors concurrently.
        
        Args:
            processed_data: Preprocessed market data
            max_workers: Maximum number of concurrent workers
            
        Returns:
            List[Dict]: Results from all predictors
        """
        print(f"\n🚀 Running {len(self.predictor_tasks)} predictors concurrently...")
        start_time = time.time()
        results = []
        
        # Submit all prediction tasks
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create futures for all predictors
            future_to_task = {}
            for task in self.predictor_tasks:
                future = executor.submit(
                    self._run_single_predictor,
                    task['class'],
                    task['config'],
                    processed_data.copy()  # Pass copy to avoid thread issues
                )
                future_to_task[future] = task['config']['name']
            
            # Collect results
            print("\n⏳ Waiting for predictions...")
            completed = 0
            total = len(future_to_task)
            
            for future in concurrent.futures.as_completed(future_to_task):
                completed += 1
                predictor_name = future_to_task[future]
                timeout = next((p['timeout'] for p in self.config.ENABLED_PREDICTORS 
                              if p['name'] == predictor_name), 30)
                
                try:
                    result = future.result(timeout=timeout)
                    results.append(result)
                    
                    if result['success']:
                        print(f"    ✅ {predictor_name}: {result['signal_count']} signals ({result['elapsed_time']:.1f}s)")
                    else:
                        print(f"    ❌ {predictor_name}: Failed - {result['error']} ({result['elapsed_time']:.1f}s)")
                        
                except concurrent.futures.TimeoutError:
                    results.append({
                        'success': False,
                        'predictor_name': predictor_name,
                        'error': f'Timed out after {timeout}s',
                        'elapsed_time': timeout,
                        'predictions': {}
                    })
                    print(f"    ⏰ {predictor_name}: Timed out after {timeout}s")
                except Exception as e:
                    results.append({
                        'success': False,
                        'predictor_name': predictor_name,
                        'error': str(e),
                        'elapsed_time': 0,
                        'predictions': {}
                    })
                    print(f"    ❌ {predictor_name}: Unexpected error - {str(e)}")
        
        total_time = time.time() - start_time
        print(f"\n✅ All predictors completed in {total_time:.1f}s")
        
        self.results = results
        return results
    
    def combine_predictions(self) -> Dict:
        """
        Combine predictions from all successful predictors.
        KEEPS ALL PREDICTIONS even if duplicates exist
        """
        # Get only successful predictions
        successful_results = [r for r in self.results if r['success'] and r['predictions']]
        
        if not successful_results:
            return {}
        
        # Combine ALL predictions (allow duplicates)
        combined = {}
        
        for result in successful_results:
            predictions = result['predictions']
            predictor_name = result['predictor_name']
            
            for symbol, prediction_data in predictions.items():
                # Create unique key: symbol + predictor (or just symbol if you want duplicates)
                unique_key = f"{symbol}_{predictor_name}"
                
                # Add predictor name to the data
                prediction_data['source_predictor'] = predictor_name
                prediction_data['original_symbol'] = symbol
                
                # Store with unique key or overwrite same symbol
                combined[unique_key] = prediction_data
        
        return combined

    
    def get_summary(self, final_predictions: Dict) -> Dict:
        """
        Generate a summary of the predictions.
        
        Args:
            final_predictions: Combined predictions
            
        Returns:
            Dict: Summary statistics
        """
        summary = {
            'total_signals': len(final_predictions),
            'long_signals': 0,
            'short_signals': 0,
            'predictor_success': 0,
            'predictor_failures': 0,
            'total_execution_time': 0
        }
        
        # Count by type
        for symbol, data in final_predictions.items():
            if data.get('predictor_type') == 'LONG':
                summary['long_signals'] += 1
            elif data.get('predictor_type') == 'SHORT':
                summary['short_signals'] += 1
        
        # Count predictor results
        for result in self.results:
            summary['total_execution_time'] += result.get('elapsed_time', 0)
            if result['success']:
                summary['predictor_success'] += 1
            else:
                summary['predictor_failures'] += 1
        
        return summary
    
    def print_results(self, final_predictions: Dict):
        """
        Print formatted results to console.
        
        Args:
            final_predictions: Combined predictions
        """
        if not final_predictions:
            print("\n🔶 No trading signals generated - skipping trade execution")
            return
        
        print("\n" + "=" * 50)
        print("📊 PREDICTION RESULTS")
        print("=" * 50)
        
        # Group by predictor type
        long_signals = {k:v for k,v in final_predictions.items() 
                       if v.get('predictor_type') == 'LONG'}
        short_signals = {k:v for k,v in final_predictions.items() 
                        if v.get('predictor_type') == 'SHORT'}
        
        if long_signals:
            print(f"\n📈 LONG Signals ({len(long_signals)}):")
            for key, data in long_signals.items():
                symbol = data.get('symbol', 'Unknown')
                confidence = data.get('predictor_confidence', 0)
                if data.get('consensus_count', 1) > 1:
                    print(f"   ✅ {symbol} - (Conf: {confidence:.1%}, Consensus: {data['consensus_count']})")
                else:
                    print(f"   ✅ {symbol} - (Conf: {confidence:.1%})")

        if short_signals:
            print(f"\n📉 SHORT Signals ({len(short_signals)}):")
            for key, data in short_signals.items():
                symbol = data.get('symbol', 'Unknown')
                confidence = data.get('predictor_confidence', 0)
                if data.get('consensus_count', 1) > 1:
                    print(f"   ✅ {symbol} - (Conf: {confidence:.1%}, Consensus: {data['consensus_count']})")
                else:
                    print(f"   ✅ {symbol} - (Conf: {confidence:.1%})")
        
        # Get summary
        summary = self.get_summary(final_predictions)
        
        print("\n📋 SUMMARY:")
        print(f"   • Total unique symbols: {summary['total_signals']}")
        print(f"   • LONG signals: {summary['long_signals']}")
        print(f"   • SHORT signals: {summary['short_signals']}")
        print(f"   • Successful predictors: {summary['predictor_success']}/{len(self.results)}")
        if summary['predictor_failures'] > 0:
            print(f"   • Failed predictors: {summary['predictor_failures']}")
        
        print("=" * 50)