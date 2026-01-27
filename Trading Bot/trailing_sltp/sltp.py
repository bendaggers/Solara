#!/usr/bin/env python3
# sltp.py - Survivor's Edition v5.0 (Clean Version)

import os
import sys
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
except ImportError:
    print("❌ Config import failed")
    sys.exit(1)
# ===================================================

from mt5_interface import MT5SimpleInterface
from survivor_engine import SurvivorEngineV5


class SurvivorRunner:
    """Clean runner with minimal output"""
    
    def __init__(self):
        self.mt5 = MT5SimpleInterface(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER
        )
        self.engine = SurvivorEngineV5(initial_sl_pips=30)
        self.cycle_count = 0
    
    def run_cycle(self):
        """Run one protection cycle - clean output"""
        self.cycle_count += 1
        
        # Connect to MT5
        if not self.mt5.connect():
            return False
        
        # Get positions
        positions = self.mt5.get_positions()
        if not positions:
            return True
        
        # Process positions
        updates = self.engine.process_all_positions(positions)
        
        # Apply updates
        successful = 0
        total_updates = 0
        
        for update in updates:
            if update['needs_update']:
                total_updates += 1
                if self.mt5.modify_position(
                    ticket=update['ticket'],
                    sl=update['new_sl'],
                    tp=update['new_tp']
                ):
                    successful += 1
        
        # Summary
        if successful > 0:
            print(f"Updated {successful}/{total_updates} positions")
        
        return True


def main():
    """Main function"""
    runner = SurvivorRunner()
    runner.run_cycle()


if __name__ == "__main__":
    main()