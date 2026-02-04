#!/usr/bin/env python3
"""
Predictor Reporter - Exports prediction results to CSV format
"""

import pandas as pd
from datetime import datetime
import os
from typing import Dict, Optional

class PredictorReporter:
    """
    Handles reporting and exporting of prediction results to CSV format.
    Simply extracts data from the combined predictions dict.
    """
    
    def __init__(self, output_dir: str = "/home/user/trading_bot/predictions/reports"):
        """
        Initialize the PredictorReporter.
        """
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    
    def extract_to_dataframe(self, combined_predictions: Dict) -> pd.DataFrame:
        """
        Extract data from combined predictions dict to DataFrame.
        
        Args:
            combined_predictions: Output from PredictorManager.combine_predictions()
            
        Returns:
            pd.DataFrame: Clean DataFrame with prediction data
        """
        if not combined_predictions:
            return pd.DataFrame()
        
        data_rows = []
        
        for unique_key, pred_data in combined_predictions.items():
            # Extract what's already in the dict
            row = {
                'timestamp': pred_data.get('timestamp', ''),
                'symbol': pred_data.get('symbol', ''),
                'prediction': pred_data.get('prediction', 0),
                'probability': pred_data.get('probability', 0.0),
                'confidence': pred_data.get('confidence', 0.0),
                'signal_strength': pred_data.get('signal_strength', ''),
                'predictor': pred_data.get('source_predictor', pred_data.get('predictor', '')),
                'predictor_type': pred_data.get('predictor_type', ''),
            }
            
            data_rows.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(data_rows)
        
        if df.empty:
            return df
        
        # Format timestamp if it exists
        if 'timestamp' in df.columns and not df['timestamp'].empty:
            # Try to convert to datetime
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
                df['time'] = df['timestamp'].dt.strftime('%H:%M:%S')
            except:
                df['date'] = ''
                df['time'] = ''
        
        return df
       
    def export_to_csv(self, combined_predictions: Dict, 
                     filename: Optional[str] = None) -> str:
        """
        Export combined predictions to CSV file.
        
        Args:
            combined_predictions: Output from PredictorManager.combine_predictions()
            filename: Custom filename (optional)
            
        Returns:
            str: Full path to the created CSV file
        """
        # Extract data to DataFrame
        df = self.extract_to_dataframe(combined_predictions)
        
        if df.empty:
            print("No predictions to export")
            return ""
        
        # Generate filename
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"predictions_{timestamp}.csv"
        
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Save to CSV
        df.to_csv(filepath, index=False)
        
        # Simple success message
        print(f"✓ Predictions exported: {filename}")
        
        return filepath