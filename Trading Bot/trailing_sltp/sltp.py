import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List

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
    LOG_PATH = getattr(config, 'LOG_PATH', 'logs')
except ImportError:
    print("❌ Could not import config.py")
    print("   Using hardcoded values - update sltp.py with your credentials")
    MT5_LOGIN = 000000
    MT5_PASSWORD = "your_password"
    MT5_SERVER = "your_server"
    DATA_PATH = r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files\marketdata_PERIOD_H4.json"
    LOG_PATH = "logs"
# ===================================================

from trailing_sltp.mt5_interface import MT5Interface
from trailing_sltp.sltp_engine import SLTPEngine


class SLTPRunner:
    """Main runner class for the trailing SL/TP system"""
    
    def __init__(self):
        self.mt5_interface = None
        self.sltp_engine = None
        self.cycle_count = 0
        self.stage_stats = {}
        
        # Create logs directory if it doesn't exist
        if not os.path.exists(LOG_PATH):
            os.makedirs(LOG_PATH)
    
    def initialize(self) -> bool:
        try:
            print("=" * 70)
            print("🚀 DYNAMIC TRAILING STOP & PROFIT TARGET SYSTEM")
            print("   Volatility-Normalized Progressive Protection")
            print("=" * 70)
            
            self.mt5_interface = MT5Interface(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER
            )
            
            self.sltp_engine = SLTPEngine(
                market_data_file=DATA_PATH
            )
            
            print(f"✅ System initialized")
            print(f"   Account: {MT5_LOGIN}")
            print(f"   Market Data: {DATA_PATH}")
            print(f"   Log Path: {LOG_PATH}")
            print("=" * 70)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize system: {e}")
            return False
    
    def save_cycle_log(self, cycle_data: Dict):
        """Save cycle log to JSON file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(LOG_PATH, f"cycle_{timestamp}.json")
            
            with open(log_file, 'w') as f:
                json.dump(cycle_data, f, indent=2, default=str)
            
            print(f"📝 Cycle log saved: {log_file}")
        except Exception as e:
            print(f"❌ Failed to save log: {e}")
    
    def run_once(self) -> bool:
        try:
            self.cycle_count += 1
            cycle_start = datetime.now()
            
            print(f"\n🔄 CYCLE #{self.cycle_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 70)
            
            # Connect to MT5
            if not self.mt5_interface.connect():
                return False
            
            # Load market data
            print("📊 Loading market data...")
            if not self.sltp_engine.load_market_data():
                print("❌ Failed to load market data - data may be stale")
                return False
            
            # Get open positions
            print("🔍 Fetching open positions...")
            positions = self.mt5_interface.get_open_positions()
            if not positions:
                print("📭 No positions to process")
                return True
            
            print(f"📈 Found {len(positions)} open positions")
            
            # Check for positions with missing SL/TP
            missing_sl = sum(1 for p in positions if abs(p['sl']) < 0.00001)
            missing_tp = sum(1 for p in positions if abs(p['tp']) < 0.00001)
            
            if missing_sl > 0 or missing_tp > 0:
                print(f"⚠️  Found {missing_sl} positions without SL, {missing_tp} positions without TP")
                print("   Initializing missing SL/TP based on current stage...")
            
            # Process positions
            print("⚙️ Calculating adjustments...")
            updates_needed = self.sltp_engine.process_positions(positions)
            
            # Initialize tracking
            stage_distribution = {}
            successful_updates = 0
            no_change_errors = []
            invalid_stop_errors = []
            other_errors = []
            update_details = []
            
            # Apply updates
            print("🔄 Applying adjustments...")
            for update in updates_needed:
                ticket = update['ticket']
                symbol = update['symbol']
                stage = update['stage']
                
                # Track stage distribution
                stage_distribution[stage] = stage_distribution.get(stage, 0) + 1
                
                # Get current SL/TP values
                current_sl = update['current_sl']
                current_tp = update['current_tp']
                new_sl = update['new_sl']
                new_tp = update['new_tp']
                
                # Apply the update
                success, message = self.mt5_interface.modify_position(
                    ticket=ticket,
                    sl=new_sl,
                    tp=new_tp
                )
                
                # Store update details
                detail = {
                    'ticket': ticket,
                    'symbol': symbol,
                    'stage': stage,
                    'success': success,
                    'message': message,
                    'current_sl': current_sl,
                    'current_tp': current_tp,
                    'new_sl': new_sl,
                    'new_tp': new_tp,
                    'debug_info': update.get('debug_info', {})
                }
                update_details.append(detail)
                
                if success:
                    successful_updates += 1
                    # REMOVED: Detailed success messages - cycle summary shows this
                    
                elif "10025" in message or "No changes" in message:
                    no_change_errors.append(ticket)
                elif "Invalid stops" in message:
                    invalid_stop_errors.append(ticket)
                    print(f"   ⚠️ {symbol} (Ticket {ticket}): Invalid stops - {message}")
                else:
                    other_errors.append((ticket, message))
                    print(f"   ❌ {symbol} (Ticket {ticket}): {message}")
            
            # Display summary
            cycle_end = datetime.now()
            duration = (cycle_end - cycle_start).total_seconds()
            
            print("\n" + "=" * 70)
            print("📊 CYCLE SUMMARY")
            print("=" * 70)
            print(f"   Cycle: #{self.cycle_count}")
            print(f"   Duration: {duration:.2f} seconds")
            print(f"   Positions checked: {len(positions)}")
            print(f"   Updates needed: {len(updates_needed)}")
            print(f"   Successful updates: {successful_updates}")
            
            # Stage distribution
            if stage_distribution:
                print(f"\n   📈 STAGE DISTRIBUTION:")
                for stage, count in sorted(stage_distribution.items()):
                    percentage = (count / len(positions)) * 100
                    print(f"      {stage}: {count} positions ({percentage:.1f}%)")
            
            # Error details
            total_errors = len(no_change_errors) + len(invalid_stop_errors) + len(other_errors)
            if total_errors > 0:
                print(f"\n   ⚠️ ERRORS:")
                if no_change_errors:
                    print(f"      No change: {len(no_change_errors)} positions")
                if invalid_stop_errors:
                    print(f"      Invalid stops: {len(invalid_stop_errors)} positions")
                if other_errors:
                    print(f"      Other: {len(other_errors)} positions")
            
            print("=" * 70)
            
            # Save cycle log
            cycle_data = {
                'cycle_number': self.cycle_count,
                'start_time': cycle_start,
                'end_time': cycle_end,
                'duration_seconds': duration,
                'positions_checked': len(positions),
                'missing_sl_count': missing_sl,
                'missing_tp_count': missing_tp,
                'updates_needed': len(updates_needed),
                'successful_updates': successful_updates,
                'stage_distribution': stage_distribution,
                'errors': {
                    'no_change': len(no_change_errors),
                    'invalid_stops': len(invalid_stop_errors),
                    'other': len(other_errors)
                },
                'update_details': update_details
            }
            
            self.save_cycle_log(cycle_data)
            
            return True
            
        except Exception as e:
            print(f"❌ Error in adjustment cycle: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            if self.mt5_interface:
                self.mt5_interface.disconnect()
    
    def run_continuous(self, interval_minutes: int = 240):  # 4 hours as per spec
        print(f"⏰ Starting continuous mode - checking every {interval_minutes} minutes (4 hours)")
        print("   Aligned with H4 Bollinger Band updates")
        print("   Press Ctrl+C to stop\n")
        
        while True:
            try:
                print(f"\n{'='*70}")
                print(f"🔄 STARTING NEW CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print('='*70)
                
                self.run_once()
                
                print(f"\n💤 Sleeping for {interval_minutes} minutes ({interval_minutes/60:.1f} hours)...")
                print("⏰ Next check at:", 
                      (datetime.now() + timedelta(minutes=interval_minutes)).strftime('%Y-%m-%d %H:%M:%S'))
                
                # Sleep with progress indicator
                sleep_seconds = interval_minutes * 60
                for i in range(sleep_seconds):
                    if i % 300 == 0:  # Every 5 minutes
                        remaining = sleep_seconds - i
                        hours = remaining // 3600
                        minutes = (remaining % 3600) // 60
                        print(f"   ⏳ Next check in: {hours}h {minutes}m", end='\r')
                    time.sleep(1)
                
                print("\n" + "="*70)
                
            except KeyboardInterrupt:
                print("\n\n👋 Shutdown requested by user")
                break
            except Exception as e:
                print(f"\n❌ Error in continuous run: {e}")
                print(f"💤 Retrying in 5 minutes...")
                time.sleep(300)  # 5 minutes before retry


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Dynamic Trailing Stop & Profit Target System\nVolatility-Normalized Progressive Protection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Run once
  %(prog)s --mode continuous    # Run continuously every 4 hours
  %(prog)s --mode continuous --interval 60  # Run every hour (testing)
        """
    )
    
    parser.add_argument('--mode', choices=['once', 'continuous'], default='once',
                       help='Run mode: once or continuous (default: once)')
    parser.add_argument('--interval', type=int, default=240,
                       help='Interval in minutes for continuous mode (default: 240 = 4 hours)')
    
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