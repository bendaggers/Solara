#!/usr/bin/env python3
# sltp.py - Survivor's Edition v2.6 SIMPLIFIED

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse

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
        'down_buffer': 0.05,
        'min_stage_time': 2
    })
    
    # Safe distance configuration
    SAFE_DISTANCE = getattr(config, 'SAFE_DISTANCE', {
        'min_pips': 10,
        'bb_percentage': 0.10
    })
    
except ImportError:
    print("❌ Config import failed")
    sys.exit(1)
# ===================================================

# Import engine modules
from mt5_interface import MT5SimpleInterface
from survivor_engine import SurvivorEngine


class SurvivorRunner:
    """Main runner for Survivor's Edition v2.6"""
    
    def __init__(self):
        self.mt5 = MT5SimpleInterface(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER
        )
        self.engine = SurvivorEngine(
            market_data_file=DATA_PATH,
            hysteresis_config=STAGE_HYSTERESIS,
            safe_distance_config=SAFE_DISTANCE
        )
        self.cycle_count = 0
    
    def run_cycle(self):
        """Run one protection cycle"""
        self.cycle_count += 1
        print(f"\n{'='*60}")
        print(f"🛡️  CYCLE #{self.cycle_count} - SURVIVOR'S EDITION")
        print(f"{'='*60}")
        
        # Connect to MT5
        if not self.mt5.connect():
            print("❌ MT5 connection failed")
            return False
        
        # Load market data
        if not self.engine.load_market_data():
            print("❌ Failed to load market data")
            return False
        
        # Get positions
        positions = self.mt5.get_positions()
        if not positions:
            print("📭 No positions")
            return True
        
        print(f"📈 Found {len(positions)} positions")
        
        # Process positions
        updates = self.engine.process_all_positions(positions)
        
        # Apply updates
        successful = 0
        for update in updates:
            if update['needs_update']:
                if self.mt5.modify_position(
                    ticket=update['ticket'],
                    sl=update['new_sl'],
                    tp=update['new_tp']
                ):
                    successful += 1
        
        print(f"\n📊 Updated {successful}/{len(updates)} positions")
        
        # Show stage distribution
        stage_counts = {}
        for update in updates:
            stage = update['stage']
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        if stage_counts:
            print(f"\n🛡️  STAGE DISTRIBUTION:")
            for stage, count in stage_counts.items():
                protection = self.engine.get_protection_percent(stage)
                if protection > 0:
                    print(f"   {stage}: {count} positions ({int(protection*100)}% protection)")
                else:
                    print(f"   {stage}: {count} positions")
        
        print(f"\n✅ Cycle completed")
        return True
    
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
    args = parser.parse_args()
    
    runner = SurvivorRunner()
    
    if args.mode == 'continuous':
        runner.run_continuous(args.interval)
    else:
        runner.run_cycle()


if __name__ == "__main__":
    main()