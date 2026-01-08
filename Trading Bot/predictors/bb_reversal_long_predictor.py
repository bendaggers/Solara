"""
BB Reversal Long Predictor - The AI Advisor

This is your trading system's AI consultant, the module that actually looks 
at market data and says "I think this is a buying opportunity" or "let's 
stay away from this one." It loads your trained machine learning model 
(which learned from thousands of historical examples) and asks it to analyze 
the current market situation. The predictor doesn't just give a simple yes/no 
answer - it provides a confidence score, telling you how sure the model is 
about its recommendation. It's like having an experienced trader who's studied 
patterns for years, but available instantly and without emotion, evaluating 
whether current market conditions match the profitable setups it learned 
during training.
"""

import pickle
import numpy as np
import os
import config


class BBReversalLongPredictor:
    """Handles loading and prediction with the BB reversal long model"""
    
    def __init__(self, models_path=None):
        self.models_path = models_path or config.MODELS_PATH
        self.model = None
        self.model_loaded = False
    
    def load_model(self):
        """Load the trained BB reversal long model"""
        # Use the exact model filename from your structure
        model_path = os.path.join(self.models_path, config.BB_REVERSAL_LONG_MODEL)
        
        try:
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            self.model_loaded = True
            print(f"✅ BB reversal long model loaded from {model_path}")
        except FileNotFoundError:
            raise Exception(f"BB reversal long model not found at: {model_path}")
        except Exception as e:
            raise Exception(f"Error loading model: {str(e)}")
    
    def predict(self, processed_data):
        """
        Make predictions for all symbols
        Args:
            processed_data: dict from BBReversalLongPreprocessor
        Returns: dict with predictions for each symbol
        """
        if not self.model_loaded:
            self.load_model()
        
        predictions = {}
        
        for symbol, symbol_data in processed_data.items():
            features = symbol_data['features']
            
            # Reshape for single prediction (model expects 2D array)
            features_2d = features.reshape(1, -1)
            
            # Make prediction
            try:
                prediction = self.model.predict(features_2d)[0]
                probability = self.model.predict_proba(features_2d)[0]
                
                # Store prediction
                predictions[symbol] = {
                    'prediction': int(prediction),
                    'probability': float(max(probability)),
                    'confidence': self.calculate_confidence(probability),
                    'timestamp': symbol_data['timestamp'],
                    'price': symbol_data['price'],
                    'features_used': symbol_data['feature_names']
                }
                
            except Exception as e:
                print(f"⚠️ Prediction failed for {symbol}: {str(e)}")
                predictions[symbol] = {
                    'prediction': 0,
                    'probability': 0.0,
                    'confidence': 0.0,
                    'timestamp': symbol_data['timestamp'],
                    'price': symbol_data['price'],
                    'error': str(e)
                }
        
        # Filter predictions by confidence threshold
        qualified_predictions = self.filter_by_confidence(predictions)
        
        return qualified_predictions
    
    def calculate_confidence(self, probabilities):
        """Calculate confidence score from probabilities"""
        if len(probabilities) == 2:
            # Binary classification - use difference from 0.5
            confidence = abs(probabilities[1] - 0.5) * 2
        else:
            # Multi-class - use max probability
            confidence = max(probabilities)
        
        return float(confidence)
    
    def filter_by_confidence(self, predictions):
        """Filter predictions by minimum confidence threshold"""
        qualified = {}
        
        for symbol, pred_data in predictions.items():
            if pred_data['confidence'] >= config.BB_REVERSAL_LONG_THRESHOLD:
                qualified[symbol] = pred_data
        
        print(f"📊 Predictions: {len(predictions)} total, {len(qualified)} qualified")
        return qualified