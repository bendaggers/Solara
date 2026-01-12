# trailing_sltp/sltp.py
import os
import sys
import time
from datetime import datetime

# ================== CONFIG IMPORT ==================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    import config
    MT5_LOGIN = config.MT5_LOGIN
    MT5_PASSWORD = config.MT5_PASSWORD
    MT5_SERVER = config.MT5_SERVER
    DATA_PATH = config.DATA_PATH
except ImportError:
    print("❌ Could not import config.py")
    print("   Using hardcoded values - update sltp.py with your credentials")
    MT5_LOGIN = 000000
    MT5_PASSWORD = "your_password"
    MT5_SERVER = "your_server"
    DATA_PATH = r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files\marketdata_PERIOD_H4.json"
# ===================================================

from trailing_sltp.mt5_interface import MT5Interface
from trailing_sltp.sltp_engine import SLTPEngine


class SLTPRunner:
    """Main runner class for the trailing SL/TP system"""
    
    def __init__(self):
        self.mt5_interface = None
        self.sltp_engine = None
        
    def initialize(self) -> bool:
        try:
            self.mt5_interface = MT5Interface(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER
            )
            
            self.sltp_engine = SLTPEngine(
                market_data_file=DATA_PATH
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize system: {e}")
            return False
    
    def run_once(self) -> bool:
        try:
            print(f"\n🚀 Starting SL TP Adjustment Cycle - {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 50)
            
            # Connect to MT5
            if not self.mt5_interface.connect():
                return False
            
            # Load market data
            if not self.sltp_engine.load_market_data():
                print("❌ Failed to load market data")
                return False
            
            # Get open positions
            positions = self.mt5_interface.get_open_positions()
            if not positions:
                print("📭 No positions to process")
                return True
            
            # Process positions
            updates_needed = self.sltp_engine.process_positions(positions)
            
            # Track results
            successful_updates = 0
            no_change_errors = []
            invalid_stop_errors = []
            other_errors = []
            
            # Apply updates
            for update in updates_needed:
                ticket = update['ticket']
                new_sl = update['new_sl'] if update['new_sl'] is not None else update['current_sl']
                new_tp = update['new_tp'] if update['new_tp'] is not None else update['current_tp']
                
                success, message = self.mt5_interface.modify_position(
                    ticket=ticket,
                    sl=new_sl,
                    tp=new_tp
                )
                
                if success:
                    successful_updates += 1
                elif "10025" in message or "No changes" in message:
                    no_change_errors.append(ticket)
                elif "Invalid stops" in message or "Invalid stops" in message:
                    invalid_stop_errors.append(ticket)
                else:
                    other_errors.append((ticket, message))
            
            # Display summary
            print("\n" + "=" * 50)
            print("📊 SL TP ADJUSTMENT CYCLE SUMMARY:")
            print(f"   Positions checked: {len(positions)}")
            print(f"   Updates needed: {len(updates_needed)}")
            print(f"   Successful updates: {successful_updates}")
            print(f"   Failed updates: {len(updates_needed) - successful_updates}")
            
            if no_change_errors:
                print(f"\n   📋 No change errors (10025): {len(no_change_errors)} tickets")
                if len(no_change_errors) <= 10:
                    print(f"      Tickets: {', '.join(map(str, no_change_errors))}")
                else:
                    print(f"      First 10 tickets: {', '.join(map(str, no_change_errors[:10]))}...")
            
            if invalid_stop_errors:
                print(f"\n   ⚠️ Invalid stops errors: {len(invalid_stop_errors)} tickets")
                if len(invalid_stop_errors) <= 10:
                    print(f"      Tickets: {', '.join(map(str, invalid_stop_errors))}")
                else:
                    print(f"      First 10 tickets: {', '.join(map(str, invalid_stop_errors[:10]))}...")
            
            if other_errors:
                print(f"\n   ❌ Other errors: {len(other_errors)} tickets")
                for ticket, msg in other_errors[:5]:  # Show first 5 errors
                    print(f"      Ticket {ticket}: {msg}")
                if len(other_errors) > 5:
                    print(f"      ... and {len(other_errors) - 5} more")
            
            print("=" * 50)
            return True
            
        except Exception as e:
            print(f"❌ Error in adjustment cycle: {e}")
            return False
        
        finally:
            if self.mt5_interface:
                self.mt5_interface.disconnect()
    
    def run_continuous(self, interval_minutes: int = 60):
        print(f"⏰ Starting continuous mode - checking every {interval_minutes} minutes")
        print("Press Ctrl+C to stop\n")
        
        while True:
            try:
                self.run_once()
                print(f"\n💤 Sleeping for {interval_minutes} minutes...\n")
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                print("\n👋 Shutdown requested by user")
                break
            except Exception as e:
                print(f"❌ Error in continuous run: {e}")
                print(f"💤 Retrying in {interval_minutes} minutes...\n")
                time.sleep(interval_minutes * 60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Trailing SL/TP System')
    parser.add_argument('--mode', choices=['once', 'continuous'], default='once',
                       help='Run mode: once or continuous')
    parser.add_argument('--interval', type=int, default=60,
                       help='Interval in minutes for continuous mode')
    
    args = parser.parse_args()
    
    runner = SLTPRunner()
    
    if not runner.initialize():
        print("❌ Failed to initialize system. Exiting.")
        return
    
    if args.mode == 'once':
        runner.run_once()
    else:
        runner.run_continuous(args.interval)


if __name__ == "__main__":
    main()