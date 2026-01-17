# sltp.py - Survivor's Edition

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
    
    # SAFE DISTANCE CONFIGURATION - SURVIVOR'S EDITION
    # This handles both old and new config files gracefully
    DEFAULT_SAFE_DISTANCE = {
        'min_pips': 12,                      # Increased from 10
        'bb_percentage': 0.10,               # Increased from 0.08
        'spread_multiplier': 3.0,            # Increased from 2.0
        'max_profit_giveback': 0.07,         # 7% max giveback (tighter than 10%)
        'trailing_max_giveback': 0.05,       # 5% for trailing stages
        'stage_specific_mins': {             # Increased buffers
            'STAGE_0': 35,    # Increased from 30
            'STAGE_1': 30,    # Increased from 25
            'STAGE_1A': 25,   # Increased from 20
            'STAGE_2A': 20,   # Increased from 15
            'STAGE_2B': 15,   # Increased from 12
            'STAGE_2C': 12,   # Increased from 10
            'STAGE_3A': 10,   # Increased from 8
            'STAGE_3B': 8,    # Increased from 6
            'STAGE_4': 6,     # Increased from 5
            'STAGE_5': 6      # Increased from 5
        }
    }
    
    # Get safe distance config from file or use defaults
    if hasattr(config, 'SAFE_DISTANCE'):
        SAFE_DISTANCE = config.SAFE_DISTANCE.copy()  # Start with config values
        
        # Ensure all survivor keys exist (backward compatibility)
        for key, value in DEFAULT_SAFE_DISTANCE.items():
            if key not in SAFE_DISTANCE:
                SAFE_DISTANCE[key] = value
                print(f"⚠️  Added missing config key: {key} = {value}")
    else:
        SAFE_DISTANCE = DEFAULT_SAFE_DISTANCE
        print("⚠️  Using Survivor's Edition default configuration")
    
except ImportError:
    print("❌ Config import failed - using Survivor's Edition defaults")
    MT5_LOGIN = 000000
    MT5_PASSWORD = "your_password"
    MT5_SERVER = "your_server"
    DATA_PATH = "market_data.json"
    LOG_PATH = "logs"
    
    # Default configurations - SURVIVOR'S EDITION
    STAGE_HYSTERESIS = {
        'up_buffer': 0.02,
        'down_buffer': 0.03,
        'min_stage_time': 2
    }
    
    SAFE_DISTANCE = {
        'min_pips': 12,
        'bb_percentage': 0.10,
        'spread_multiplier': 3.0,
        'max_profit_giveback': 0.07,
        'trailing_max_giveback': 0.05,
        'stage_specific_mins': {
            'STAGE_0': 35, 'STAGE_1': 30, 'STAGE_1A': 25, 'STAGE_2A': 20, 'STAGE_2B': 15,
            'STAGE_2C': 12, 'STAGE_3A': 10, 'STAGE_3B': 8, 'STAGE_4': 6, 'STAGE_5': 6
        }
    }
# ===================================================

from trailing_sltp.mt5_interface import MT5Interface
from trailing_sltp.sltp_engine import SLTPEngine


class SLTPRunner:
    """Main runner class for the trailing SL/TP system - Survivor's Edition"""
    
    def __init__(self):
        self.mt5_interface = None
        self.sltp_engine = None
        self.cycle_count = 0
        self.total_protected_profit = 0.0
        self.safety_rejections = 0
        self.survivor_stats = {
            'cycles_completed': 0,
            'positions_protected': 0,
            'profit_locked': 0.0,
            'safety_rejections': 0,
            'emergency_fixes': 0
        }
        
        # Create directories
        if not os.path.exists(LOG_PATH):
            os.makedirs(LOG_PATH)
        
        STATE_PATH = "state"
        if not os.path.exists(STATE_PATH):
            os.makedirs(STATE_PATH)
            
        # Survivor statistics file
        self.survivor_stats_file = os.path.join(STATE_PATH, "survivor_stats.json")
    
    def initialize(self) -> bool:
        try:
            print("🚀 Initializing Survivor's Edition SL/TP System...")
            print(f"   Protection Levels: 25% → 40% → 50% → 60% → 70% → 75%")
            print(f"   Safe Distance: {SAFE_DISTANCE['min_pips']} pips min, {SAFE_DISTANCE['bb_percentage']*100}% BB width")
            
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
            
            # Load survivor statistics
            self._load_survivor_stats()
            
            print("✅ Survivor's Edition initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ Init failed: {e}")
            return False
    
    def _load_survivor_stats(self):
        """Load survivor statistics from file"""
        try:
            if os.path.exists(self.survivor_stats_file):
                with open(self.survivor_stats_file, 'r') as f:
                    self.survivor_stats = json.load(f)
        except:
            pass  # Use defaults if can't load
    
    def _save_survivor_stats(self):
        """Save survivor statistics to file"""
        try:
            with open(self.survivor_stats_file, 'w') as f:
                json.dump(self.survivor_stats, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save survivor stats: {e}")
    
    def save_cycle_log(self, cycle_data: Dict) -> str:
        """Save cycle log to JSON file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(LOG_PATH, f"cycle_{timestamp}_survivor.json")  # Added survivor tag
            
            # Add stage definitions to cycle data
            if self.sltp_engine:
                cycle_data['stage_definitions'] = self.sltp_engine.get_stage_definitions()
                
                # Add stage statistics
                positions = self.mt5_interface.get_open_positions() if hasattr(self, 'mt5_interface') and self.mt5_interface else []
                if positions:
                    cycle_data['stage_statistics'] = self.sltp_engine.get_stage_statistics(positions)
            
            # Add survivor configuration
            cycle_data['survivor_config'] = {
                'safe_distance': SAFE_DISTANCE,
                'stage_hysteresis': STAGE_HYSTERESIS,
                'protection_levels': '25-75% progressive'
            }
            
            # Add survivor statistics
            cycle_data['survivor_statistics'] = self.survivor_stats
            
            with open(log_file, 'w') as f:
                json.dump(cycle_data, f, indent=2, default=str)
            
            return log_file
        except Exception as e:
            print(f"⚠️  Failed to save cycle log: {e}")
            return ""
    
    def run_once(self) -> bool:
        try:
            self.cycle_count += 1
            self.survivor_stats['cycles_completed'] += 1
            cycle_start = datetime.now()
            
            # SURVIVOR'S EDITION HEADER
            print(f"\n{'='*60}")
            print(f"🛡️  CYCLE #{self.cycle_count} - SURVIVOR'S EDITION")
            print(f"   Time: {cycle_start.strftime('%H:%M:%S')}")
            print(f"{'='*60}")
            
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
                print("📭 No positions to protect")
                # Still save a cycle log
                self._save_empty_cycle_log(cycle_start)
                return True
            
            print(f"📈 Found {len(positions)} positions to protect")
            
            # Process positions
            print("⚙️  Calculating Survivor's protection (25-75%)...")
            updates_needed = self.sltp_engine.process_positions(positions)
            
            # Initialize tracking
            stage_distribution = {}
            protection_summary = {}
            successful_updates = 0
            update_details = []
            cycle_protected_profit = 0.0
            cycle_safety_rejections = 0
            worse_sl_skips = 0
            
            # SURVIVOR: Track protection levels
            protection_levels = {
                'STAGE_1': '25%', 'STAGE_1A': '40%', 'STAGE_2A': '50%',
                'STAGE_2B': '60%', 'STAGE_2C': '70%', 'STAGE_3A': '75%'
            }
            
            # Apply updates
            print("🛡️  Applying Survivor's protection...")
            for update in updates_needed:
                ticket = update['ticket']
                log_entry = update['log_entry']
                stage = update['stage']
                
                # Track stage distribution
                stage_distribution[stage] = stage_distribution.get(stage, 0) + 1
                
                # Track protection summary
                if stage in protection_levels:
                    protection_summary[protection_levels[stage]] = protection_summary.get(protection_levels[stage], 0) + 1
                
                # Apply the update
                if update['needs_update']:
                    success, message = self.mt5_interface.safe_modify_position(
                        ticket=ticket,
                        sl=update['new_sl'],
                        tp=update['new_tp']
                    )
                else:
                    # No changes needed, mark as success with no action
                    success = True
                    message = "Already optimal - no modification"
                
                # Update log entry with execution result
                log_entry['execution'] = {
                    'success': success,
                    'message': message
                }
                
                # Track safety rejections
                if 'safety_adjustment' in log_entry and log_entry['safety_adjustment']['decision'] == 'keep_current_sl':
                    cycle_safety_rejections += 1
                    self.safety_rejections += 1
                    self.survivor_stats['safety_rejections'] += 1
                
                # Track emergency fixes
                if 'Emergency fix' in message:
                    self.survivor_stats['emergency_fixes'] += 1
                
                update_details.append(log_entry)
                
                if success:
                    successful_updates += 1
                    self.survivor_stats['positions_protected'] += 1
                    
                    # Estimate protected profit (simplified)
                    if update['new_sl'] is not None and update['current_sl'] != 0.0:
                        profit_locked = abs(update['new_sl'] - update['current_sl'])
                        cycle_protected_profit += profit_locked
                        self.total_protected_profit += profit_locked
                        self.survivor_stats['profit_locked'] += profit_locked
            
            # Display clean summary - SURVIVOR'S EDITION STYLE
            cycle_end = datetime.now()
            duration = (cycle_end - cycle_start).total_seconds()

            if worse_sl_skips > 0:
                print(f"\n   ⚠️  PROTECTION PRESERVATION:")
                print(f"      Skipped {worse_sl_skips} updates (new SL would worsen protection)")
            
            print(f"\n{'='*60}")
            print(f"📊 SURVIVOR'S SUMMARY")
            print(f"{'='*60}")
            print(f"   Cycle: #{self.cycle_count}")
            print(f"   Time: {duration:.1f}s")
            print(f"   Positions: {len(positions)}")
            print(f"   Protected: {successful_updates}/{len(updates_needed)}")
            print(f"   Safety Rejections: {cycle_safety_rejections}")
            
            # Stage distribution with protection percentages
            if stage_distribution:
                print(f"\n   🛡️  PROTECTION LEVELS:")
                # Show profit-locking stages with percentages
                for stage in ['STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B', 'STAGE_2C', 'STAGE_3A']:
                    if stage in stage_distribution:
                        count = stage_distribution[stage]
                        percentage = (count / len(positions)) * 100
                        protection = protection_levels.get(stage, '')
                        print(f"      {stage}: {count} positions ({percentage:.0f}%) [{protection} protection]")
                
                # Show trailing stages
                for stage in ['STAGE_0', 'STAGE_3B', 'STAGE_4', 'STAGE_5']:
                    if stage in stage_distribution:
                        count = stage_distribution[stage]
                        percentage = (count / len(positions)) * 100
                        phase = 'Entry' if stage == 'STAGE_0' else 'Trailing'
                        print(f"      {stage}: {count} positions ({percentage:.0f}%) [{phase}]")
            
            # Protection summary
            if protection_summary:
                print(f"\n   📈 PROTECTION DISTRIBUTION:")
                for level, count in sorted(protection_summary.items()):
                    print(f"      {level} protection: {count} positions")
            
            # Profit protection summary
            if cycle_protected_profit > 0:
                print(f"\n   💰 PROFIT PROTECTED THIS CYCLE:")
                print(f"      Estimated: ${cycle_protected_profit:.2f}")
                print(f"      Total Protected: ${self.total_protected_profit:.2f}")
            
            # Save cycle log
            cycle_data = {
                'cycle_number': self.cycle_count,
                'timestamp': cycle_start.strftime('%Y-%m-%d %H:%M:%S'),
                'duration_seconds': round(duration, 2),
                'positions_checked': len(positions),
                'updates_needed': len(updates_needed),
                'successful_updates': successful_updates,
                'stage_distribution': stage_distribution,
                'protection_summary': protection_summary,
                'cycle_protected_profit': round(cycle_protected_profit, 2),
                'safety_rejections': cycle_safety_rejections,
                'position_updates': update_details,
                'edition': 'Survivor v2.4',
                'protection_philosophy': 'Progressive 25-75% with capital preservation focus'
            }
            
            log_file = self.save_cycle_log(cycle_data)
            if log_file:
                print(f"\n📝 Survivor's log saved: {os.path.basename(log_file)}")
            
            # Save confirmed stages
            self.sltp_engine.save_confirmed_stages()
            
            # Save survivor statistics
            self._save_survivor_stats()
            
            print(f"\n✅ Survivor's protection cycle completed")
            print(f"{'='*60}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ SURVIVOR ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            if self.mt5_interface:
                self.mt5_interface.disconnect()
    
    def _save_empty_cycle_log(self, cycle_start):
        """Save an empty cycle log when no positions"""
        cycle_data = {
            'cycle_number': self.cycle_count,
            'timestamp': cycle_start.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_seconds': 0,
            'positions_checked': 0,
            'updates_needed': 0,
            'successful_updates': 0,
            'stage_distribution': {},
            'protection_summary': {},
            'cycle_protected_profit': 0,
            'safety_rejections': 0,
            'position_updates': [],
            'edition': 'Survivor v2.4',
            'protection_philosophy': 'Progressive 25-75% with capital preservation focus',
            'note': 'No positions to protect'
        }
        
        log_file = self.save_cycle_log(cycle_data)
        if log_file:
            print(f"📝 Empty survivor log saved: {os.path.basename(log_file)}")
    
    def run_continuous(self, interval_minutes: int = 240):
        """Run continuously with survivor output"""
        print(f"\n{'='*60}")
        print(f"⏰ SURVIVOR'S EDITION - Starting continuous protection")
        print(f"   Checking every {interval_minutes//60} hours")
        print(f"   Protection: Progressive 25-75%")
        print(f"   Safe Distance: {SAFE_DISTANCE['min_pips']} pips min")
        print(f"{'='*60}")
        print("   Press Ctrl+C to stop survivor protection\n")
        
        while True:
            try:
                self.run_once()
                
                # Calculate next run time
                next_time = datetime.now() + timedelta(minutes=interval_minutes)
                print(f"\n💤 Survivor resting until: {next_time.strftime('%H:%M')}")
                print(f"   Next protection cycle in {interval_minutes//60}h {interval_minutes%60}m")
                
                # Sleep with survivor-themed progress
                sleep_seconds = interval_minutes * 60
                for i in range(sleep_seconds):
                    if i % 300 == 0:  # Every 5 minutes
                        remaining = sleep_seconds - i
                        minutes = remaining // 60
                        hours = minutes // 60
                        mins = minutes % 60
                        if hours > 0:
                            print(f"   ⏳ Survivor resting: {hours}h {mins}m remaining", end='\r')
                        else:
                            print(f"   ⏳ Survivor resting: {mins}m remaining", end='\r')
                    time.sleep(1)
                
                print()  # New line after progress
                
            except KeyboardInterrupt:
                print(f"\n{'='*60}")
                print("👋 Survivor protection stopped")
                print(f"   Total cycles: {self.cycle_count}")
                print(f"   Total safety rejections: {self.safety_rejections}")
                print(f"   Estimated profit protected: ${self.total_protected_profit:.2f}")
                print(f"{'='*60}")
                break
            except Exception as e:
                print(f"\n❌ Survivor error: {e}")
                print("💤 Survivor will retry in 5 minutes...")
                time.sleep(300)  # 5 minutes


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='SURVIVOR\'S EDITION: Dynamic Trailing Stop & Profit Target System\nProgressive Protection with Capital Preservation Focus',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SURVIVOR'S EDITION FEATURES:
  • Progressive protection: 25% → 75% profit locking
  • Enhanced safe distances: 12 pips min, 10% BB width
  • Capital preservation focus
  • Safety-first adjustments
  • Detailed survivor statistics

Examples:
  %(prog)s                      # Run once (default)
  %(prog)s --mode continuous    # Run continuously every 4 hours
  %(prog)s --mode continuous --interval 60  # Run every hour
  %(prog)s --min-pips 15        # Override min safe distance
  %(prog)s --bb-percentage 0.12 # Override BB percentage
        """
    )
    
    parser.add_argument('--mode', choices=['once', 'continuous'], default='once',
                       help='Run mode: once or continuous (default: once)')
    parser.add_argument('--interval', type=int, default=240,
                       help='Interval in minutes for continuous mode (default: 240 = 4 hours)')
    parser.add_argument('--min-pips', type=int, default=None,
                       help='Override minimum safe distance in pips (Survivor default: 12)')
    parser.add_argument('--bb-percentage', type=float, default=None,
                       help='Override safe distance as percentage of BB width (Survivor default: 0.10)')
    
    args = parser.parse_args()
    
    # Override config values if provided - with survivor awareness
    if args.min_pips is not None:
        SAFE_DISTANCE['min_pips'] = args.min_pips
        print(f"⚠️  Overriding min safe distance: {args.min_pips} pips")
    
    if args.bb_percentage is not None:
        SAFE_DISTANCE['bb_percentage'] = args.bb_percentage
        print(f"⚠️  Overriding BB percentage: {args.bb_percentage*100}%")
    
    runner = SLTPRunner()
    
    if not runner.initialize():
        return
    
    if args.mode == 'continuous':
        runner.run_continuous(args.interval)
    else:
        runner.run_once()


if __name__ == "__main__":
    main()