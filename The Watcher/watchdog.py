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
        
    USE_CONFIG = True
    
except ImportError as e:
    print(f"✗ Failed to import config: {e}")
    # Fallback to original hardcoded values
    MT5_FILES_DIR = Path(
        r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
        r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files"
    )
    WATCHED_FILE = "marketdata_PERIOD_H4.json"
    USE_CONFIG = False
# ========================

# ===== SCRIPT PATHS =====
TRADING_BOT_DIR = Path(
    r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Trading Bot"
)

SOLARA_SCRIPT = TRADING_BOT_DIR / "solara.py"
SLTP_SCRIPT = TRADING_BOT_DIR / "trailing_sltp" / "sltp.py"

# ===== WATCHER SETTINGS =====
CHECK_INTERVAL = 5
COOLDOWN = 10
# =========================

def run_script(script_path, script_name):
    """Run a Python script and return success status"""
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting {script_name}...")
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(script_path), "--mode", "once"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            env=env,
            cwd=script_path.parent
        )
        
        if result.returncode == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {script_name} completed successfully")
            
            # Show output if there is any
            if result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        print(f"  {line}")
            
            return True
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {script_name} failed with code: {result.returncode}")
            
            # Show error if any
            if result.stderr:
                error_lines = result.stderr.strip().split('\n')
                for line in error_lines[:5]:  # Show first 5 error lines
                    if line.strip():
                        print(f"  ERROR: {line}")
            
            return False
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error running {script_name}: {e}")
        return False

def main():
    print("\n" + "="*50)
    print("SOLARA FILE WATCHER with SLTP")
    print("="*50)
    
    # Construct the full file path to watch
    file_path = MT5_FILES_DIR / WATCHED_FILE
    
    print(f"Using config: {'YES' if USE_CONFIG else 'NO (fallback)'}")
    print(f"Watching: {file_path}")
    print(f"Solara script: {SOLARA_SCRIPT}")
    print(f"SLTP script: {SLTP_SCRIPT}")
    print(f"Check every: {CHECK_INTERVAL}s, Cooldown: {COOLDOWN}s")
    print("="*50)
    print("\nPress Ctrl+C to stop\n")
    
    # Verify scripts exist
    if not SOLARA_SCRIPT.exists():
        print(f"✗ ERROR: Solara script not found: {SOLARA_SCRIPT}")
        return
    
    if not SLTP_SCRIPT.exists():
        print(f"✗ ERROR: SLTP script not found: {SLTP_SCRIPT}")
        return
    
    last_hash = None
    last_run = 0
    check_count = 0
    change_count = 0
    solara_runs = 0
    sltp_runs = 0
    
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
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === FILE CHANGED ===")
                    last_hash = current_hash
                    change_count += 1
                    
                    # Check cooldown
                    now = time.time()
                    if now - last_run >= COOLDOWN:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Running scripts...")
                        last_run = now
                        
                        # Run Solara first
                        if run_script(SOLARA_SCRIPT, "SOLARA"):
                            solara_runs += 1
                            
                            # Wait 2 seconds before running SLTP
                            time.sleep(2)
                            
                            # Then run SLTP
                            if run_script(SLTP_SCRIPT, "SLTP"):
                                sltp_runs += 1
                            
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Script sequence completed")
                        print("-" * 50)
                        
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
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Status: "
                      f"Checks={check_count}, "
                      f"Changes={change_count}, "
                      f"Solara runs={solara_runs}, "
                      f"SLTP runs={sltp_runs}")
            
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print(f"\n\n[{datetime.now().strftime('%H:%M:%S')}] Stopped")
        print(f"Total checks: {check_count}")
        print(f"Total changes: {change_count}")
        print(f"Solara runs: {solara_runs}")
        print(f"SLTP runs: {sltp_runs}")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()