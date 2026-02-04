#!/usr/bin/env python3
# sltp.py - Survivor's Edition v5.0 (Modified for Solara Integration)
# Now accepts positions dict directly - no MT5 login needed

import sys
from datetime import datetime
from .survivor_engine import SurvivorEngineV5

class SurvivorRunner:
    """Clean runner that accepts positions dict directly - no MT5 connection"""
    
    def __init__(self, initial_sl_pips=30):
        """
        Initialize SurvivorRunner
        
        Args:
            initial_sl_pips: Default stop loss pips if not specified
        """
        self.engine = SurvivorEngineV5(initial_sl_pips=initial_sl_pips)
        self.cycle_count = 0
    
    def run_cycle(self, positions_dict):
        """
        Run one protection cycle with provided positions dict
        
        Args:
            positions_dict: List of dictionaries with position data
                Each dict should have:
                - ticket: position ticket number (int)
                - symbol: symbol name (str)
                - type: 'BUY' or 'SELL' (str)
                - magic: magic number (int)
                - volume: position volume (float)
                - entry_price: entry price (float)
                - sl: current stop loss (float)
                - tp: current take profit (float)
                - current_price: current market price (float)
                - profit: current profit (float)
                - comment: position comment (str)
        
        Returns:
            list: Updates needed for each position
        """
        self.cycle_count += 1
        
        print(f"\n🔄 Survivor Protection Cycle #{self.cycle_count}")
        print(f"   Processing {len(positions_dict)} positions")
        
        # Convert positions dict to format expected by SurvivorEngineV5
        formatted_positions = []
        for pos in positions_dict:
            formatted_pos = {
                'ticket': pos['ticket'],
                'symbol': pos['symbol'],
                'type': 0 if pos['type'] == 'BUY' else 1,  # Convert to 0=BUY, 1=SELL
                'entry_price': pos['entry_price'],
                'current_price': pos['current_price'],
                'sl': pos['sl'],
                'tp': pos['tp'],
                'volume': pos['volume'],
                'profit': pos['profit'],
                'magic': pos['magic'],
                'comment': pos.get('comment', '')
            }
            formatted_positions.append(formatted_pos)
        
        # Process positions with SurvivorEngine
        updates = self.engine.process_all_positions(formatted_positions)
        
        # Print summary
        self._print_summary(updates)
        
        return updates
    
    def _print_summary(self, updates):
        """Print clean summary of updates"""
        needs_update = sum(1 for u in updates if u['needs_update'])
        
        if needs_update > 0:
            print(f"\n📋 UPDATES NEEDED ({needs_update} positions):")
            for update in updates:
                if update['needs_update']:
                    print(f"   • {update['symbol']} (#{update['ticket']}):")
                    
                    # Show SL update if needed
                    if update['update_sl']:
                        print(f"     SL: {update['current_sl']:.5f} → {update['new_sl']:.5f}")
                    
                    # Show TP update if needed
                    if update['update_tp']:
                        print(f"     TP: {update['current_tp']:.5f} → {update['new_tp']:.5f}")
                    
                    # Show stage info
                    print(f"     Stage: {update['stage_name']} ({update['protection_percent']}% protection)")
                    print(f"     Profit: {update['profit_pips']} pips ({update['profit_ratio']:.1%} of BB width)")
        else:
            print("\n✅ No updates needed - all positions protected")
        
        print(f"\n📊 SUMMARY:")
        print(f"   • Total positions processed: {len(updates)}")
        print(f"   • Positions needing update: {needs_update}")
        print(f"   • Positions unchanged: {len(updates) - needs_update}")


def apply_updates_to_mt5(mt5_manager, updates):
    """
    Apply Survivor updates to MT5 positions
    
    Args:
        mt5_manager: Connected MT5Manager instance
        updates: List of update dicts from SurvivorRunner
    
    Returns:
        dict: Results of applying updates
    """
    # Check if mt5_manager is valid and connected
    if not mt5_manager:
        print("❌ MT5 manager is None - cannot apply updates")
        return {'applied': 0, 'failed': len(updates), 'total': len(updates)}
    
    if not hasattr(mt5_manager, 'connected'):
        print("❌ Invalid MT5 manager object - missing 'connected' attribute")
        return {'applied': 0, 'failed': len(updates), 'total': len(updates)}
    
    if not mt5_manager.connected:
        print("❌ MT5 not connected - cannot apply updates")
        return {'applied': 0, 'failed': len(updates), 'total': len(updates)}
    
    applied = 0
    failed = 0
    
    print(f"\n💾 Applying {len(updates)} updates to MT5...")
    
    for update in updates:
        if update['needs_update']:
            try:
                # Check what needs to be updated
                sl_to_update = update['new_sl'] if update['update_sl'] else None
                tp_to_update = update['new_tp'] if update['update_tp'] else None
                
                # Modify position in MT5
                success = mt5_manager.modify_position(
                    ticket=update['ticket'],
                    sl=sl_to_update,
                    tp=tp_to_update
                )
                
                if success:
                    print(f"   ✅ Updated #{update['ticket']} ({update['symbol']})")
                    applied += 1
                else:
                    print(f"   ❌ Failed to update #{update['ticket']}")
                    failed += 1
                    
            except Exception as e:
                print(f"   ❌ Error updating #{update['ticket']}: {str(e)}")
                failed += 1
    
    return {
        'applied': applied,
        'failed': failed,
        'total': applied + failed
    }


def run_survivor_protection(mt5_manager, initial_sl_pips=30):
    """
    Complete Survivor protection cycle integrated with Solara
    
    Args:
        mt5_manager: Connected MT5Manager instance from Solara
        initial_sl_pips: Initial stop loss pips
    
    Returns:
        dict: Protection results
    """
   
    # Validate mt5_manager
    if not mt5_manager:
        print("❌ MT5 manager is None - cannot run protection")
        return {'status': 'error', 'message': 'MT5 manager is None'}
    
    # Check connection
    if not mt5_manager.connected:
        print("❌ MT5 not connected - attempting to reconnect...")
        try:
            mt5_manager.connect()
            if not mt5_manager.connected:
                print("❌ Failed to reconnect to MT5")
                return {'status': 'error', 'message': 'MT5 connection failed'}
        except Exception as e:
            print(f"❌ Reconnection failed: {str(e)}")
            return {'status': 'error', 'message': f'Reconnection failed: {str(e)}'}
    
    # Get current positions from MT5Manager
    positions = mt5_manager.get_open_positions()
    
    if not positions:
        print("📭 No open positions to protect")
        return {'status': 'no_positions', 'positions': 0}
    
    # print(f"🔍 Found {len(positions)} open positions")
    
    # Run Survivor protection
    try:
        runner = SurvivorRunner(initial_sl_pips=initial_sl_pips)
        updates = runner.run_cycle(positions)
        
        # Apply updates to MT5
        results = apply_updates_to_mt5(mt5_manager, updates)
        
        # Final summary
        print(f"\n✅ Survivor protection completed")
        print(f"   • Positions analyzed: {len(positions)}")
        print(f"   • Updates applied: {results['applied']}")
        print(f"   • Updates failed: {results['failed']}")
        
        return {
            'status': 'completed',
            'positions_analyzed': len(positions),
            'updates_applied': results['applied'],
            'updates_failed': results['failed'],
            'total_updates': len(updates),
            'updates': updates
        }
        
    except Exception as e:
        print(f"❌ Error in survivor protection: {str(e)}")
        return {
            'status': 'error',
            'message': str(e),
            'positions_analyzed': len(positions) if 'positions' in locals() else 0
        }