#!/usr/bin/env python3
"""
Solara Trading Bot - The Conductor

Imagine Solara as the conductor of an orchestra, bringing together all the 
instruments to create a symphony of automated trading. This main file doesn't 
do the hard work itself but coordinates everything: it calls the data loaders 
to gather market information, asks the preprocessors to clean and prepare the 
data, consults the AI models for predictions, and finally instructs the trade 
executor to place orders. Running this file is like pressing 'play' on your 
entire automated trading system - it starts the chain reaction that leads 
from market data to executed trades in just seconds.
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
    """Main execution flow"""
    print(f"🚀 Solara Trading Bot starting at {datetime.now()}")
    
    try:
        # 1. Load data
        print("📊 Loading market data...")
        data_loader = DataLoader(config.DATA_PATH)
        raw_data = data_loader.load_json()
        
        # 2. Preprocess for BB reversal long model
        print("🔄 Preprocessing data for BB reversal long model...")
        preprocessor = BBReversalLongPreprocessor()
        processed_data = preprocessor.process(raw_data)
        
        # 3. Make predictions
        print("🤖 Making predictions with BB reversal long model...")
        predictor = BBReversalLongPredictor(config.MODELS_PATH)
        predictions = predictor.predict(processed_data)
        
        # 4. Execute trades
        print("💸 Executing trades...")
        executor = TradeExecutor(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER
        )
        executor.connect()
        executor.execute_trades(predictions)
        executor.disconnect()
        
        print(f"✅ Execution completed at {datetime.now()}")
        
    except Exception as e:
        print(f"❌ Error in main execution: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()