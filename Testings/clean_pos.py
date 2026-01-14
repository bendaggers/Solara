#!/usr/bin/env python3
"""
MT5 POSITION CLEANUP - AUTOMATIC VERSION
No prompts, clean output
"""

import sys
import time

# ===== CREDENTIALS =====
MT5_LOGIN = 61457079  # SOLARA DEV
MT5_PASSWORD = "o!83Ot8U6c2N"
MT5_SERVER = "Pepperstone-Demo"
# =======================

print("="*50)
print("MT5 POSITION CLEANUP - AUTOMATIC")
print("="*50)


class AutoPositionManager:
    """Automatic position manager - no prompts"""
    
    def __init__(self):
        self.connected = False
        
    def connect(self):
        """Connect to MT5"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"[{attempt+1}/{max_retries}] Connecting...")
                
                import MetaTrader5 as mt5
                
                if not mt5.initialize():
                    error = mt5.last_error()
                    print(f"  ❌ Init failed: {error[1]}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return False
                
                authorized = mt5.login(
                    login=MT5_LOGIN,
                    password=MT5_PASSWORD,
                    server=MT5_SERVER
                )
                
                if not authorized:
                    error = mt5.last_error()
                    print(f"  ❌ Login failed: {error[1]}")
                    mt5.shutdown()
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return False
                
                self.connected = True
                self.mt5 = mt5
                account = mt5.account_info()
                print(f"✅ Connected: #{account.login}, ${account.balance:.2f}")
                return True
                
            except Exception as e:
                print(f"  ❌ Attempt {attempt+1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            self.mt5.shutdown()
            self.connected = False
    
    def get_positions(self):
        """Get all positions (silent)"""
        if not self.connected:
            return []
        
        positions = self.mt5.positions_get()
        return positions if positions else []
    
    def remove_all_sl_tp(self):
        """Remove ALL SL/TP automatically - no prompts"""
        positions = self.get_positions()
        
        if not positions:
            print("❌ No positions found")
            return 0
        
        print(f"\n🔄 Removing SL/TP from {len(positions)} positions")
        print("-" * 40)
        
        modified = 0
        failed = 0
        
        for pos in positions:
            request = {
                "action": self.mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "sl": 0.0,
                "tp": 0.0,
                "deviation": 10,
            }
            
            result = self.mt5.order_send(request)
            
            if result.retcode == self.mt5.TRADE_RETCODE_DONE:
                print(f"{pos.ticket} - {pos.symbol} ✅ SL/TP removed")
                modified += 1
            else:
                print(f"{pos.ticket} - {pos.symbol} ❌ Failed: {result.comment}")
                failed += 1
            
            time.sleep(0.05)
        
        print("-" * 40)
        print(f"📊 Results: {modified} successful, {failed} failed")
        return modified
    
    def close_all_positions(self):
        """Close ALL positions automatically - no prompts"""
        positions = self.get_positions()
        
        if not positions:
            print("❌ No positions to close")
            return 0
        
        print(f"\n⚠️  Closing {len(positions)} positions")
        print("-" * 40)
        
        closed = 0
        failed = 0
        
        for pos in positions:
            symbol_info = self.mt5.symbol_info(pos.symbol)
            if not symbol_info:
                print(f"{pos.ticket} - {pos.symbol} ❌ No symbol info")
                failed += 1
                continue
            
            order_type = self.mt5.ORDER_TYPE_SELL if pos.type == 0 else self.mt5.ORDER_TYPE_BUY
            price = symbol_info.ask if order_type == self.mt5.ORDER_TYPE_SELL else symbol_info.bid
            
            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": order_type,
                "price": price,
                "deviation": 10,
                "magic": 0,
                "comment": "Cleanup",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }
            
            result = self.mt5.order_send(request)
            
            if result.retcode == self.mt5.TRADE_RETCODE_DONE:
                profit_str = f"${result.profit:+.2f}"
                print(f"{pos.ticket} - {pos.symbol} ✅ Closed ({profit_str})")
                closed += 1
            else:
                print(f"{pos.ticket} - {pos.symbol} ❌ Failed: {result.comment}")
                failed += 1
            
            time.sleep(0.1)
        
        print("-" * 40)
        print(f"📊 Results: {closed} closed, {failed} failed")
        return closed
    
    def show_positions_summary(self):
        """Show brief position summary"""
        positions = self.get_positions()
        
        if not positions:
            print("📭 No open positions")
            return
        
        print(f"\n📊 {len(positions)} Open Positions")
        print("-" * 40)
        
        total_profit = 0
        for pos in positions:
            total_profit += pos.profit
            profit_str = f"${pos.profit:+.2f}"
            sl_tp = f"SL:{pos.sl:.5f}" if pos.sl > 0 else "SL:None"
            sl_tp += f" TP:{pos.tp:.5f}" if pos.tp > 0 else " TP:None"
            print(f"{pos.ticket} - {pos.symbol} {pos.volume} lots - {profit_str} - {sl_tp}")
        
        print("-" * 40)
        print(f"💰 Total Profit: ${total_profit:+.2f}")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("\nUsage: python auto_cleanup.py [COMMAND]")
        print("\nCommands:")
        print("  1 - Show positions (brief)")
        print("  2 - Remove ALL SL/TP (AUTOMATIC)")
        print("  3 - Close ALL positions (AUTOMATIC)")
        print("\nExamples:")
        print("  python auto_cleanup.py 1")
        print("  python auto_cleanup.py 2  # Removes SL/TP from ALL positions")
        print("  python auto_cleanup.py 3  # Closes ALL positions")
        return
    
    command = sys.argv[1]
    
    manager = AutoPositionManager()
    
    # Connect
    if not manager.connect():
        print("\n❌ Connection failed")
        return
    
    try:
        if command == "1":
            manager.show_positions_summary()
        
        elif command == "2":
            print("\n⚠️  AUTOMATIC: Removing ALL SL/TP")
            manager.remove_all_sl_tp()
        
        elif command == "3":
            print("\n⚠️  AUTOMATIC: Closing ALL positions")
            manager.close_all_positions()
        
        else:
            print(f"❌ Unknown command: {command}")
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        manager.disconnect()


if __name__ == "__main__":
    main()