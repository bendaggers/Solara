#!/usr/bin/env python3
# sltp.py - Survivor's Edition v3.0 Main Runner

import os
import sys
import time
import argparse
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
    DATA_PATH = config.DATA_PATH  # This is your market data path
    LOG_PATH = getattr(config, 'LOG_PATH', 'logs')
    
    # Stage hysteresis configuration
    STAGE_HYSTERESIS = getattr(config, 'STAGE_HYSTERESIS', {
        'up_buffer': 0.02,
        'down_buffer': 0.05,
        'min_stage_time': 2
    })
    
    # Safe distance configuration
    SAFE_DISTANCE = getattr(config, 'SAFE_DISTANCE', {
        'min_pips': 10,
        'bb_percentage': 0.10
    })
    
    # Regression Defense Configuration
    REGRESSION_CONFIG = getattr(config, 'REGRESSION_CONFIG', {
        'min_stage_for_detection': 'STAGE_1',
        'giveback_threshold': 0.30,
        'stagnation_cycles': 4,
        'defense_level_1': 'STAGE_2C',
        'defense_level_2': 'STAGE_3A',
        'defense_level_3': 'STAGE_3B',
        'min_defense_cycles': 2,
        'max_defense_cycles': 8,
    })
    
except ImportError:
    print("❌ Config import failed")
    sys.exit(1)
# ===================================================

print(f"📁 Market data path: {DATA_PATH}")
print(f"📁 Current directory: {current_dir}")

from mt5_interface import MT5SimpleInterface
from survivor_engine import SurvivorEngineV3


class SurvivorRunner:
    """Main runner for Survivor's Edition"""
    
    def __init__(self):
        self.mt5 = MT5SimpleInterface(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER
        )
        self.engine = SurvivorEngineV3(
            market_data_file=DATA_PATH,  # Use the path from config
            hysteresis_config=STAGE_HYSTERESIS,
            safe_distance_config=SAFE_DISTANCE,
            regression_config=REGRESSION_CONFIG
        )
        self.cycle_count = 0
    
    def run_cycle(self):
        """Run one protection cycle"""
        self.cycle_count += 1
        print(f"\n{'='*60}")
        print(f"🛡️  CYCLE #{self.cycle_count} - SURVIVOR'S EDITION v3.0")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Connect to MT5
        if not self.mt5.connect():
            print("❌ MT5 connection failed")
            return False
        
        # Load market data from the external path
        if not self.engine.load_market_data():
            print("❌ Failed to load market data")
            return False
        
        # Get positions
        positions = self.mt5.get_positions()
        if not positions:
            print("📭 No positions")
            return True
        
        print(f"📊 Found {len(positions)} positions")
        
        # Process positions
        updates = self.engine.process_all_positions(positions)
        
        # Apply updates
        successful = 0
        defense_activated = 0
        for update in updates:
            if update['needs_update']:
                if self.mt5.modify_position(
                    ticket=update['ticket'],
                    sl=update['new_sl'],
                    tp=update['new_tp']
                ):
                    successful += 1
                    if update.get('defense_activated', False):
                        defense_activated += 1
        
        print(f"\n📊 Updated {successful}/{len(updates)} positions")
        
        if defense_activated > 0:
            print(f"🛡️  DEFENSE ACTIVATED for {defense_activated} positions")
        
        # Show stage distribution
        self._show_stage_distribution(updates)
        
        print(f"\n✅ Cycle completed")
        return True
    
    def _show_stage_distribution(self, updates: list):
        """Show stage distribution"""
        stage_counts = {}
        defense_counts = {}
        
        for update in updates:
            stage = update['stage']
            if update.get('defense_active', False):
                defense_counts[stage] = defense_counts.get(stage, 0) + 1
            else:
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        if stage_counts:
            print(f"\n📊 NORMAL STAGE DISTRIBUTION:")
            for stage, count in sorted(stage_counts.items()):
                protection = self.engine.get_protection_percent(stage)
                if protection > 0:
                    print(f"   {stage}: {count} positions ({int(protection*100)}% protection)")
                else:
                    print(f"   {stage}: {count} positions")
        
        if defense_counts:
            print(f"\n🛡️  DEFENSE MODE DISTRIBUTION:")
            for stage, count in sorted(defense_counts.items()):
                protection = self.engine.get_protection_percent(stage)
                print(f"   {stage}: {count} positions ({int(protection*100)}% protection)")
    
    def run_continuous(self, interval_minutes=240):
        """Run continuously"""
        print(f"\n⏰ Running continuously every {interval_minutes//60}h {interval_minutes%60}m")
        
        try:
            while True:
                self.run_cycle()
                
                if interval_minutes <= 0:
                    break
                
                print(f"\n💤 Waiting {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print(f"\n👋 Stopped after {self.cycle_count} cycles")


def main():
    parser = argparse.ArgumentParser(description='Survivor\'s Edition Position Protection')
    parser.add_argument('--mode', choices=['once', 'continuous'], default='once')
    parser.add_argument('--interval', type=int, default=240)
    parser.add_argument('--clean-history', action='store_true', help='Clean position history file')
    args = parser.parse_args()
    
    runner = SurvivorRunner()
    
    if args.clean_history:
        runner.engine.clean_position_history_file()
    
    if args.mode == 'continuous':
        runner.run_continuous(args.interval)
    else:
        runner.run_cycle()


if __name__ == "__main__":
    main()