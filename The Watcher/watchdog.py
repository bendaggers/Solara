#!/usr/bin/env python3
"""
SOLARA WATCHER - ASCII Version
No Unicode, no emojis - just works
"""

import os
import sys
import time
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

# ===== IMPORT CONFIG =====
# Get absolute path to Trading Bot directory
current_dir = Path(__file__).parent.absolute()
trading_bot_dir = current_dir.parent / "Trading Bot"

# Add to Python path
sys.path.insert(0, str(trading_bot_dir))

try:
    import config
    print(f"✓ Imported config from: {trading_bot_dir}")
    
    # Use config values directly
    # Build MT5_FILES_DIR from TERMINAL_PATH
    MT5_FILES_DIR = Path(config.TERMINAL_PATH) / "MQL5" / "Files"
    
    # Get the filename - check in order of preference
    if hasattr(config, 'MARKET_DATA_FILE'):
        WATCHED_FILE = config.MARKET_DATA_FILE
        print(f"  Using MARKET_DATA_FILE: {WATCHED_FILE}")
    elif hasattr(config, 'DATA_PATH'):
        WATCHED_FILE = Path(config.DATA_PATH).name
        print(f"  Using filename from DATA_PATH: {WATCHED_FILE}")
    else:
        WATCHED_FILE = "marketdata_PERIOD_H4.json"
        print(f"  Using default: {WATCHED_FILE}")
        
    USE_CONFIG = True  # ADD THIS LINE!
    
except ImportError as e:
    print(f"✗ Failed to import config: {e}")
    # Fallback to original hardcoded values
    MT5_FILES_DIR = Path(
        r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
        r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files"
    )
    WATCHED_FILE = "marketdata_PERIOD_H4.json"
    USE_CONFIG = False  # ADD THIS LINE!
# ========================

# ===== WATCHER SETTINGS =====
SOLARA_SCRIPT = Path(
    r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Trading Bot\solara.py"
)

CHECK_INTERVAL = 5
COOLDOWN = 10
# =========================

# REMOVE THIS DUPLICATE SECTION! Delete everything from here...
# # Use config values for these two only
# if USE_CONFIG:
#     # Extract MT5_FILES_DIR from config.TERMINAL_PATH
#     MT5_FILES_DIR = Path(config.TERMINAL_PATH) / "MQL5" / "Files"
#     
#     # Extract WATCHED_FILE from config.DATA_PATH
#     if hasattr(config, 'DATA_PATH'):
#         # Get just the filename from the full DATA_PATH
#         WATCHED_FILE = Path(config.DATA_PATH).name
#     else:
#         WATCHED_FILE = "marketdata_PERIOD_H4.json"
# else:
#     # Fallback to original hardcoded values
#     MT5_FILES_DIR = Path(
#         r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
#         r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files"
#     )
#     WATCHED_FILE = "marketdata_PERIOD_H4.json"
# # =========================
# ...to here!

def main():
    print("\n" + "="*50)
    print("SOLARA FILE WATCHER")
    print("="*50)
    
    # Construct the full file path to watch
    file_path = MT5_FILES_DIR / WATCHED_FILE
    
    # Get solara directory for running the script
    solara_dir = SOLARA_SCRIPT.parent
    
    print(f"Using config: {'YES' if USE_CONFIG else 'NO (fallback)'}")
    print(f"Watching: {file_path}")
    print(f"Solara script: {SOLARA_SCRIPT}")
    print(f"Solara directory: {solara_dir}")
    print(f"Check every: {CHECK_INTERVAL}s, Cooldown: {COOLDOWN}s")
    print("="*50)
    print("\nPress Ctrl+C to stop\n")
    
    # Rest of your main() function remains exactly the same...
    last_hash = None
    last_run = 0
    check_count = 0
    change_count = 0
    
    try:
        while True:
            check_count += 1
            
            # Check file
            if file_path.exists():
                try:
                    with open(file_path, 'rb') as f:
                        current_hash = hashlib.md5(f.read()).hexdigest()
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Error reading file: {e}")
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                # Check if hash changed
                if last_hash is None:
                    # First time seeing file
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] File found")
                    last_hash = current_hash
                elif current_hash != last_hash:
                    # File changed!
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] FILE CHANGED")
                    last_hash = current_hash
                    change_count += 1
                    
                    # Check cooldown
                    now = time.time()
                    if now - last_run >= COOLDOWN:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Running Solara...")
                        last_run = now
                        
                        try:
                            # Run solara.py with UTF-8 fix
                            env = os.environ.copy()
                            env['PYTHONIOENCODING'] = 'utf-8'
                            
                            result = subprocess.run(
                                [sys.executable, "-X", "utf8", str(SOLARA_SCRIPT)],
                                capture_output=True,
                                text=True,
                                encoding='utf-8',
                                errors='ignore',
                                env=env,
                                cwd=solara_dir
                            )
                            
                            if result.returncode == 0:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Solara completed")
                                if result.stdout.strip():
                                    print("\n" + "="*60)
                                    print("SOLARA FULL OUTPUT:")
                                    print("="*60)
                                    print(result.stdout)
                                    print("="*60 + "\n")
                            else:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Solara failed: {result.returncode}")
                                if result.stderr:
                                    print("Error:", result.stderr[:500])
                                    
                        except Exception as e:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
                    else:
                        wait = COOLDOWN - (now - last_run)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting {wait:.0f}s (cooldown)")
            else:
                # File doesn't exist
                if last_hash is not None:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] File deleted")
                    last_hash = None
            
            # Status update
            if check_count % 20 == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Status: checked {check_count} times, {change_count} changes")
            
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print(f"\n\n[{datetime.now().strftime('%H:%M:%S')}] Stopped")
        print(f"Total checks: {check_count}")
        print(f"Total changes: {change_count}")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()