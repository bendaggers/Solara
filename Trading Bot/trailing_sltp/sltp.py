import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

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
    
    # Stage hysteresis configuration
    STAGE_HYSTERESIS = getattr(config, 'STAGE_HYSTERESIS', {
        'up_buffer': 0.02,
        'down_buffer': 0.03,
        'min_stage_time': 2
    })
    
    # Safe distance configuration
    SAFE_DISTANCE = getattr(config, 'SAFE_DISTANCE', {
        'min_pips': 10,
        'bb_percentage': 0.08,
        'spread_multiplier': 2.0
    })
    
except ImportError:
    print("❌ Config import failed")
    MT5_LOGIN = 000000
    MT5_PASSWORD = "your_password"
    MT5_SERVER = "your_server"
    DATA_PATH = "market_data.json"
    LOG_PATH = "logs"
    
    # Default configurations
    STAGE_HYSTERESIS = {
        'up_buffer': 0.02,
        'down_buffer': 0.03,
        'min_stage_time': 2
    }
    
    SAFE_DISTANCE = {
        'min_pips': 10,
        'bb_percentage': 0.08,
        'spread_multiplier': 2.0
    }
# ===================================================

from trailing_sltp.mt5_interface import MT5Interface
from trailing_sltp.sltp_engine import SLTPEngine


class SLTPRunner:
    """Main runner class for the trailing SL/TP system"""
    
    def __init__(self):
        self.mt5_interface = None
        self.sltp_engine = None
        self.cycle_count = 0
        
        # Create directories
        if not os.path.exists(LOG_PATH):
            os.makedirs(LOG_PATH)
        
        STATE_PATH = "state"
        if not os.path.exists(STATE_PATH):
            os.makedirs(STATE_PATH)
    
    def initialize(self) -> bool:
        try:
            # Clean minimal initialization
            self.mt5_interface = MT5Interface(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER
            )
            
            self.sltp_engine = SLTPEngine(
                market_data_file=DATA_PATH,
                stage_hysteresis=STAGE_HYSTERESIS,
                safe_distance_config=SAFE_DISTANCE
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Init failed: {e}")
            return False
    
    def save_cycle_log(self, cycle_data: Dict) -> str:
        """Save cycle log to JSON file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(LOG_PATH, f"cycle_{timestamp}.json")
            
            # Add stage definitions to cycle data
            if self.sltp_engine:
                cycle_data['stage_definitions'] = self.sltp_engine.get_stage_definitions()
            
            with open(log_file, 'w') as f:
                json.dump(cycle_data, f, indent=2, default=str)
            
            return log_file
        except Exception as e:
            return ""
    
    def run_once(self) -> bool:
        try:
            self.cycle_count += 1
            cycle_start = datetime.now()
            
            # Clean header - no equals signs
            print(f"\n🔄 Cycle #{self.cycle_count} - {cycle_start.strftime('%H:%M:%S')}")
            
            # Connect to MT5
            if not self.mt5_interface.connect():
                return False
            
            # Load market data
            print("📊 Loading market data...")
            if not self.sltp_engine.load_market_data():
                print("❌ Market data failed")
                return False
            
            # Get open positions
            print("🔍 Fetching positions...")
            positions = self.mt5_interface.get_open_positions()
            if not positions:
                print("📭 No positions")
                return True
            
            print(f"📈 Found {len(positions)} positions")
            
            # Process positions
            print("⚙️ Calculating...")
            updates_needed = self.sltp_engine.process_positions(positions)
            
            # Initialize tracking
            stage_distribution = {}
            successful_updates = 0
            update_details = []
            
            # Apply updates
            print("🔄 Applying...")
            for update in updates_needed:
                ticket = update['ticket']
                log_entry = update['log_entry']
                stage = update['stage']
                
                # Track stage distribution
                stage_distribution[stage] = stage_distribution.get(stage, 0) + 1
                
                # Apply the update
                success, message = self.mt5_interface.modify_position(
                    ticket=ticket,
                    sl=update['new_sl'],
                    tp=update['new_tp']
                )
                
                # Update log entry with execution result
                log_entry['execution'] = {
                    'success': success,
                    'message': message
                }
                
                update_details.append(log_entry)
                
                if success:
                    successful_updates += 1
            
            # Display clean summary - no equals signs
            cycle_end = datetime.now()
            duration = (cycle_end - cycle_start).total_seconds()
            
            print(f"\n📊 Summary:")
            print(f"   Cycle: #{self.cycle_count}")
            print(f"   Time: {duration:.1f}s")
            print(f"   Positions: {len(positions)}")
            print(f"   Updates: {len(updates_needed)}/{successful_updates}")
            
            # Stage distribution - clean format
            if stage_distribution:
                print(f"\n   📈 Stages:")
                for stage, count in sorted(stage_distribution.items()):
                    percentage = (count / len(positions)) * 100
                    # Clean display - just stage and count
                    print(f"      {stage}: {count} ({percentage:.0f}%)")
            
            # Save cycle log
            cycle_data = {
                'cycle_number': self.cycle_count,
                'timestamp': cycle_start.strftime('%Y-%m-%d %H:%M:%S'),
                'duration_seconds': round(duration, 2),
                'positions_checked': len(positions),
                'updates_needed': len(updates_needed),
                'successful_updates': successful_updates,
                'stage_distribution': stage_distribution,
                'position_updates': update_details,
            }
            
            log_file = self.save_cycle_log(cycle_data)
            if log_file:
                # Clean log message
                print(f"\n📝 Log: {os.path.basename(log_file)}")
            
            # Save confirmed stages
            self.sltp_engine.save_confirmed_stages()
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            if self.mt5_interface:
                self.mt5_interface.disconnect()
    
    def run_continuous(self, interval_minutes: int = 240):
        """Run continuously with clean output"""
        print(f"⏰ Starting - checking every {interval_minutes//60}h")
        print("   Press Ctrl+C to stop\n")
        
        while True:
            try:
                # Minimal separator
                print(f"\n――――――――――――――――――――――")
                
                self.run_once()
                
                # Clean sleep message
                next_time = datetime.now() + timedelta(minutes=interval_minutes)
                print(f"\n💤 Next: {next_time.strftime('%H:%M')}")
                
                # Sleep with minimal progress
                sleep_seconds = interval_minutes * 60
                for i in range(sleep_seconds):
                    if i % 300 == 0:  # Every 5 minutes
                        remaining = sleep_seconds - i
                        minutes = remaining // 60
                        print(f"   ⏳ {minutes}m", end='\r')
                    time.sleep(1)
                
                print()  # New line after progress
                
            except KeyboardInterrupt:
                print("\n👋 Stopping")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("💤 Retry in 5m...")
                time.sleep(300)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Dynamic Trailing SL/TP System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage:
  python sltp.py                    # Run once
  python sltp.py -c                # Run continuous (4h)
  python sltp.py -c -i 60          # Run every hour
        """
    )
    
    parser.add_argument('-c', '--continuous', action='store_true',
                       help='Run continuously')
    parser.add_argument('-i', '--interval', type=int, default=240,
                       help='Interval in minutes (default: 240 = 4h)')
    parser.add_argument('--min-pips', type=int, default=None,
                       help='Min safe distance in pips')
    parser.add_argument('--bb-percentage', type=float, default=None,
                       help='Safe distance as % of BB width')
    
    args = parser.parse_args()
    
    # Override config values if provided
    if args.min_pips is not None:
        SAFE_DISTANCE['min_pips'] = args.min_pips
    if args.bb_percentage is not None:
        SAFE_DISTANCE['bb_percentage'] = args.bb_percentage
    
    runner = SLTPRunner()
    
    if not runner.initialize():
        return
    
    if args.continuous:
        runner.run_continuous(args.interval)
    else:
        runner.run_once()


if __name__ == "__main__":
    main()