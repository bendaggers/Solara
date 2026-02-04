#!/usr/bin/env python3
"""
Solara Trading Bot - Clean Version with Universal Preprocessor
Main execution file - now clean and focused
"""

import sys
import traceback
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== FIX FOR WINDOWS EMOJI SUPPORT =====
if sys.platform == "win32":
    # Force UTF-8 encoding for Windows console
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
    # Try to set console code page to UTF-8
    try:
        os.system('chcp 65001 >nul')
    except:
        pass

# Import modules
from data_loader import DataLoader
from preprocessors.universal_preprocessor import UniversalPreprocessor
from predictors.predictor_manager import PredictorManager
from mt5.mt5_manager import MT5Manager
import config


def load_data_task(data_path):
    """Task function for data loading"""
    print("📂 Loading market data in background...")
    loader = DataLoader(data_path=data_path)
    return loader.load()


def login_task(login, password, server):
    """Task function for MT5 login"""
    print("🔐 Logging into MT5 in background...")
    executor = MT5Manager(
        login=login,
        password=password,
        server=server
    )
    return executor.connect()


def main():
    """Clean main execution - now delegates to PredictorManager"""
    print(f"⚡ Solara Trading Bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    mt5_manager = None
    
    try:
        # 1. Load data AND login to MT5 simultaneously
        print("\n📂 Starting parallel tasks...")
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both tasks
            future_data = executor.submit(load_data_task, config.DATA_PATH)
            future_login = executor.submit(
                login_task, 
                config.MT5_LOGIN, 
                config.MT5_PASSWORD, 
                config.MT5_SERVER
            )
            
            # Wait for both to complete
            print("⏳ Waiting for parallel tasks to complete...")
            futures = [future_data, future_login]
            
            df_raw = None
            trade_executor = None
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    
                    # Check which task completed
                    if future == future_data:
                        df_raw = result
                        print("✅ Market data loaded successfully")
                    elif future == future_login:
                        trade_executor = result
                        print("✅ MT5 login successful")
                        
                except Exception as e:
                    print(f"❌ Task failed: {str(e)}")
                    # If data loading fails, we can't continue
                    if future == future_data:
                        print("❌ Critical: Market data loading failed")
                        sys.exit(1)
                    # If login fails, we might still want to continue for testing
                    elif future == future_login:
                        print("⚠️ MT5 login failed - continuing in simulation mode")
                        trade_executor = None
        
        # Check if we have data
        if df_raw is None or df_raw.empty:
            print("❌ No data loaded")
            sys.exit(1)
        
        # 2. Preprocess raw data
        print("\n⚙️\u00A0 Processing features...")
        preprocessor = UniversalPreprocessor()
        processed_data = preprocessor.process(df_raw)
        
        if processed_data.empty:
            print("❌ No data after preprocessing")
            sys.exit(1)
            
        # 3. Initialize Predictor Manager
        print(f"\n🎯 Initializing predictor system...")
        predictor_manager = PredictorManager(config)
        
        # 4. Load predictors
        if not predictor_manager.load_predictors():
            print("\n❌ No predictors loaded successfully")
            sys.exit(1)
        
        # 5. Run all predictors concurrently
        predictor_manager.run_all_predictors(processed_data, max_workers=4)
        
        # 6. Combine predictions
        final_predictions = predictor_manager.combine_predictions()

        # 7. Display results
        predictor_manager.print_results(final_predictions)
        
        # 8. Execute trades (when ready)
        if final_predictions and trade_executor is not None:
            print("\n💸 Executing trades...")
            # Note: trade_executor is already the connected TradeExecutor instance
            trade_executor.execute_trades(final_predictions)
            print(f"\n✅ {len(final_predictions)} trades completed")
            
        elif final_predictions and trade_executor is None:
            print("\n⚠️ Trading disabled (MT5 not connected)")
            print(f"📊 Would execute {len(final_predictions)} trades in live mode")
        else:
            print("\n📊 No trades to execute")

        # 9. Execute SLTP
        print("\n" + "=" * 50)
        print("🛡️  SURVIVOR PROTECTION")
        print("=" * 50)
        
        # Get positions
        positions = trade_executor.get_open_positions()
        
        if positions:
            # Import survivor function
            from trailing_sltp.sltp import run_survivor_protection
            
            # Run complete protection cycle
            result = run_survivor_protection(
                trade_executor, 
                initial_sl_pips=config.STOP_LOSS_PIPS
            )
            
            print(f"📊 Survivor result: {result['status']}")
            
            if result['status'] == 'completed':
                print(f"✅ Applied {result['updates_applied']} updates")
            elif result['status'] == 'error':
                print(f"❌ Error: {result.get('message', 'Unknown error')}")
        else:
            print("📭 No positions to protect")

        # Disconnect
        if trade_executor and hasattr(trade_executor, 'disconnect'):
            trade_executor.disconnect()


        print(f"\n🏁 Bot execution completed at {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ Critical Error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()