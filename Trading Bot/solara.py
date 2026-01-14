#!/usr/bin/env python3
"""
Solara Trading Bot - Clean Version
"""

import sys
import traceback
import os
from datetime import datetime

# Import modules
from data_loader import DataLoader
from preprocessors.bb_reversal_long_preprocessor import BBReversalLongPreprocessor
from predictors.bb_reversal_long_predictor import BBReversalLongPredictor
from execute import TradeExecutor
import config


def main():
    """Clean main execution"""
    print(f"🚀 Solara Trading Bot - {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 40)
    
    try:
        # 1. Load data
        print("Loading market data...")
        temp_file = os.environ.get('MARKET_DATA_TEMP')
        data_loader = DataLoader(config.get_data_path(temp_file))
        raw_data = data_loader.load_json()
        
        # 2. Preprocess
        print("Processing features...")
        preprocessor = BBReversalLongPreprocessor()
        processed_data = preprocessor.process(raw_data)
        
        # 3. Make predictions
        print("Analyzing setups...")
        predictor = BBReversalLongPredictor(config.MODELS_PATH)
        predictions = predictor.predict(processed_data)
        
        # 4. Execute trades
        if predictions:
            print("\n" + "-" * 40)
            print("Executing trades...")
            executor = TradeExecutor(
                login=config.MT5_LOGIN,
                password=config.MT5_PASSWORD,
                server=config.MT5_SERVER
            )
            executor.connect()
            executor.execute_trades(predictions)
            executor.disconnect()
            print(f"\n✅ {len(predictions)} trades completed")
        else:
            print("\n🔶 No trades to execute")
        
        print(f"\nCompleted at {datetime.now().strftime('%H:%M:%S')}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()