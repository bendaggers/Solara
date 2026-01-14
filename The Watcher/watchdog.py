#!/usr/bin/env python3
"""
SOLARA CLEAN WATCHDOG WITH TEMP FILE PROTECTION
Prevents feedback loops by using temporary file copies
"""

import os
import sys
import time
import hashlib
import shutil
import subprocess
import uuid
from pathlib import Path
from datetime import datetime, timedelta

# ===== IMPORT CONFIG =====
current_dir = Path(__file__).parent.absolute()
trading_bot_dir = current_dir.parent / "Trading Bot"
sys.path.insert(0, str(trading_bot_dir))

try:
    import config
    MT5_FILES_DIR = Path(config.TERMINAL_PATH) / "MQL5" / "Files"
    if hasattr(config, 'MARKET_DATA_FILE'):
        WATCHED_FILE = config.MARKET_DATA_FILE
    else:
        WATCHED_FILE = "marketdata_PERIOD_H4.json"
    USE_CONFIG = True
except ImportError:
    MT5_FILES_DIR = Path(
        r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
        r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files"
    )
    WATCHED_FILE = "marketdata_PERIOD_H4.json"
    USE_CONFIG = False

# ===== SCRIPT PATHS =====
TRADING_BOT_DIR = Path(
    r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Trading Bot"
)
SOLARA_SCRIPT = TRADING_BOT_DIR / "solara.py"
SLTP_SCRIPT = TRADING_BOT_DIR / "trailing_sltp" / "sltp.py"

# ===== WATCHER SETTINGS (YOUR ORIGINAL VALUES) =====
CHECK_INTERVAL = 5
COOLDOWN = 10
# =========================

class TempFileManager:
    """Manages temporary file creation and cleanup"""
    
    @staticmethod
    def create_temp_copy(original_path):
        """Create a unique temporary copy of the file"""
        # Generate unique filename
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        temp_filename = f"marketdata_{timestamp}_{unique_id}.json"
        
        # Create temp file in same directory
        temp_path = Path(original_path).parent / temp_filename
        
        try:
            # Copy the file
            shutil.copy2(original_path, temp_path)
            print(f"  [Temp] Created: {temp_filename}")
            return str(temp_path)
        except Exception as e:
            print(f"  [Temp] Error creating copy: {e}")
            return None
    
    @staticmethod
    def cleanup_temp_file(temp_path):
        """Clean up temporary file"""
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                print(f"  [Temp] Cleaned: {os.path.basename(temp_path)}")
            except Exception as e:
                print(f"  [Temp] Error cleaning up: {e}")

class CleanWatcher:
    def __init__(self):
        self.last_hash = None
        self.last_run = None
        self.total_runs = 0
        self.start_time = datetime.now()
        self.temp_manager = TempFileManager()
        
    def should_run(self):
        """Check if we should run trading"""
        now = datetime.now()
        
        # Check cooldown - USING YOUR 10 SECONDS
        if self.last_run:
            seconds_since = (now - self.last_run).total_seconds()
            if seconds_since < COOLDOWN:
                return False
        
        return True
    
    def run_trading(self):
        """Run trading sequence with temp file protection"""
        now = datetime.now()
        self.total_runs += 1
        
        # Show minimal header
        print(f"\n{'='*60}")
        print(f"[{now.strftime('%H:%M:%S')}] TRADING CYCLE #{self.total_runs}")
        print(f"[Using temp file protection")
        print(f"{'='*60}")
        
        # Get the original file path
        original_file = MT5_FILES_DIR / WATCHED_FILE
        
        # Create temp copy
        temp_file = self.temp_manager.create_temp_copy(original_file)
        
        if not temp_file:
            print("  ERROR: Could not create temp file, aborting cycle")
            return
        
        try:
            # Run SOLARA with temp file
            solara_success = self.run_script_with_temp(SOLARA_SCRIPT, "SOLARA", temp_file)
            
            if solara_success:
                # Brief pause between scripts
                time.sleep(2)
                
                # Run SLTP with SAME temp file
                print(f"\n{'-'*60}")
                self.run_script_with_temp(SLTP_SCRIPT, "SLTP", temp_file)
            
            # Show footer
            print(f"{'='*60}")
            print(f"[{now.strftime('%H:%M:%S')}] CYCLE COMPLETE")
            print(f"{'='*60}\n")
            
        finally:
            # ALWAYS clean up temp file
            self.temp_manager.cleanup_temp_file(temp_file)
        
        self.last_run = now
    
    def run_script_with_temp(self, script_path, script_name, temp_file_path):
        """Run a script with temp file environment variable"""
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting {script_name}...")
            
            # Create environment with temp file path
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['MARKET_DATA_TEMP'] = temp_file_path  # Pass temp file to script
            
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(script_path), "--mode", "once"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                cwd=script_path.parent,
                timeout=30
            )
            
            # SHOW THE SCRIPT'S OUTPUT
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():  # Only show non-empty lines
                        print(f"  {line}")
            
            if result.returncode != 0:
                # Show errors
                if result.stderr:
                    error_lines = result.stderr.strip().split('\n')
                    for line in error_lines[:5]:
                        if line.strip():
                            print(f"  ERROR: {line}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            print(f"  {script_name} timed out after 30 seconds")
            return False
        except Exception as e:
            print(f"  {script_name} error: {e}")
            return False

def main():
    # Set UTF-8 encoding for the entire script
    if sys.platform == "win32":
        os.system('chcp 65001 >nul')
    
    print("\n============================================================")
    print("SOLARA WATCHDOG WITH TEMP PROTECTION")
    print(f"Watching: {MT5_FILES_DIR / WATCHED_FILE}")
    print(f"Cooldown: {COOLDOWN} seconds")
    print("Temp files: marketdata_TIMESTAMP_RANDOM.json")
    print("============================================================")
    print("Monitoring... (Ctrl+C to stop)")
    print("------------------------------------------------------------")
    
    file_path = MT5_FILES_DIR / WATCHED_FILE
    watcher = CleanWatcher()
    
    check_count = 0
    
    try:
        while True:
            check_count += 1
            
            # Check file
            if file_path.exists():
                try:
                    with open(file_path, 'rb') as f:
                        current_hash = hashlib.md5(f.read()).hexdigest()
                except:
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                # Check for changes
                if watcher.last_hash is None:
                    watcher.last_hash = current_hash
                elif current_hash != watcher.last_hash:
                    watcher.last_hash = current_hash
                    
                    # Check if we should run (10-second cooldown)
                    if watcher.should_run():
                        watcher.run_trading()
                    else:
                        # Silent - no output for cooldown
                        pass
            
            # SILENT monitoring - no status spam
            # Just sleep and check again
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        now = datetime.now()
        hours_up = (now - watcher.start_time).total_seconds() / 3600
        print(f"\n{'='*60}")
        print(f"[{now.strftime('%H:%M:%S')}] WATCHDOG STOPPED")
        print(f"Uptime: {hours_up:.1f} hours")
        print(f"Total cycles: {watcher.total_runs}")
        print(f"{'='*60}")

if __name__ == "__main__":
    main()