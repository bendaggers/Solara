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

# ===== CONFIGURATION =====
MT5_FILES_DIR = Path(
    r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files"
)

SOLARA_SCRIPT = Path(
    r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Trading Bot\solara.py"
)

WATCHED_FILE = "marketdata_PERIOD_M5.json"
CHECK_INTERVAL = 5
COOLDOWN = 10
# =========================

def main():
    print("\n" + "="*50)
    print("SOLARA FILE WATCHER")
    print("="*50)
    
    # Setup paths
    file_path = MT5_FILES_DIR / WATCHED_FILE
    solara_dir = SOLARA_SCRIPT.parent
    
    print(f"Watching: {file_path}")
    print(f"Solara: {SOLARA_SCRIPT}")
    print(f"Check every: {CHECK_INTERVAL}s, Cooldown: {COOLDOWN}s")
    print("="*50)
    print("\nPress Ctrl+C to stop\n")
    
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
                                    print("Output:", result.stdout[:200])
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