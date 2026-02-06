#!/usr/bin/env python3
"""
SOLARA DEBUG WATCHDOG - Fixed hash detection
"""

import os
import sys
import time
import hashlib
import shutil
import subprocess
import uuid
from pathlib import Path
from datetime import datetime
import importlib.util


# Load Watched File and Market Data path
current_folder = Path(__file__).resolve().parent
trading_bot_folder = current_folder.parent / "Trading Bot"
config_path = trading_bot_folder / "config.py"

if not config_path.exists():
    raise FileNotFoundError(f"Cannot find config.py at {config_path}")

spec = importlib.util.spec_from_file_location("config", str(config_path))
config = importlib.util.module_from_spec(spec)
sys.modules["config"] = config
spec.loader.exec_module(config)

MT5_FILES_DIR = Path(config.TERMINAL_PATH) / "MQL5" / "Files"
WATCHED_FILE = config.MARKET_DATA_FILE


TRADING_BOT_DIR = Path(
    r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Trading Bot"
)
SOLARA_SCRIPT = TRADING_BOT_DIR / "solara.py"

# ===== WATCHER SETTINGS =====
CHECK_INTERVAL = 2
COOLDOWN = 10

class DebugWatcher:
    def __init__(self):
        self.last_hash = None
        self.last_run = None
        self.total_runs = 0
        self.start_time = datetime.now()
        self.file_path = MT5_FILES_DIR / WATCHED_FILE
        self.last_size = 0
        self.last_mtime = 0
        self.file_initialized = False
        
    def show(self, msg):
        """Show message with timestamp"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    def check_file(self):
        """Check for file changes - BETTER DETECTION"""
        if not self.file_path.exists():
            if self.file_initialized or self.last_hash is not None:
                self.show("❌ File not found")
            return False
        
        try:
            # Get file stats first
            stat = self.file_path.stat()
            current_size = stat.st_size
            current_mtime = stat.st_mtime
            
            # Calculate FULL hash (not just first 8 chars)
            with open(self.file_path, 'rb') as f:
                current_hash = hashlib.md5(f.read()).hexdigest()  # FULL 32-char hash
            
            # For display, show first 8 chars
            hash_display = current_hash[:8]
            
            if self.last_hash is None:
                self.last_hash = current_hash
                self.last_size = current_size
                self.last_mtime = current_mtime
                self.file_initialized = True
                mod_time = datetime.fromtimestamp(current_mtime).strftime('%H:%M:%S')
                self.show(f"📂 Initial file: {self.file_path.name} (hash: {hash_display}..., size: {current_size}, modified: {mod_time})")
                return False
            
            # Check if ANYTHING changed
            if (current_hash != self.last_hash or 
                current_size != self.last_size or 
                current_mtime != self.last_mtime):
                
                mod_time = datetime.fromtimestamp(current_mtime).strftime('%H:%M:%S')
                self.show(f"🔄 File changed!")
                self.show(f"   Hash: {self.last_hash[:8]}... → {hash_display}...")
                self.show(f"   Size: {self.last_size} → {current_size} bytes")
                self.show(f"   Modified: {mod_time}")
                self.last_hash = current_hash
                self.last_size = current_size
                self.last_mtime = current_mtime
                return True
            
            return False
            
        except Exception as e:
            self.show(f"❌ Error checking file: {e}")
            return False
    
    def run_test(self):
        """Run solara.py"""
        self.total_runs += 1
        self.show(f"🚀 RUN #{self.total_runs}")
        print()
        
        # Create temp file
        temp_file = self.create_temp()
        if not temp_file:
            return
        
        try:
            # Run solara.py
            self.run_solara(temp_file)
        finally:
            self.cleanup_temp(temp_file)
        
        self.last_run = datetime.now()
        print()
        self.show(f"✅ Run #{self.total_runs} complete")
        print("-" * 50)
    
    def create_temp(self):
        """Create temp file"""
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        temp_name = f"temp_{timestamp}_{unique_id}.csv"
        temp_path = self.file_path.parent / temp_name
        
        try:
            shutil.copy2(self.file_path, temp_path)
            self.show(f"📄 Created: {temp_name}")
            return str(temp_path)
        except Exception as e:
            self.show(f"❌ Failed to create temp: {e}")
            return None
    
    def cleanup_temp(self, temp_path):
        """Clean up temp file"""
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                self.show(f"🧹 Cleaned: {os.path.basename(temp_path)}")
            except:
                pass
    
    def run_solara(self, temp_file):
        """Run solara.py"""
        if not SOLARA_SCRIPT.exists():
            self.show(f"❌ Script not found: {SOLARA_SCRIPT}")
            return
        
        # Set environment with UTF-8
        env = os.environ.copy()
        env['MARKET_DATA_TEMP'] = temp_file
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        self.show(f"💻 Starting solara.py...")
        print()
        
        try:
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(SOLARA_SCRIPT)],
                env=env,
                cwd=SOLARA_SCRIPT.parent,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )
            
            # Show output
            if result.stdout:
                print(result.stdout)
            
            if result.stderr:
                print("\n=== ERRORS ===")
                print(result.stderr)
            
            if result.returncode != 0:
                print(f"\n📊 Return code: {result.returncode}")
            
        except subprocess.TimeoutExpired:
            self.show("⏰ Timeout")
        except Exception as e:
            self.show(f"❌ Run error: {e}")
    
    def should_run(self):
        """Check cooldown"""
        if self.last_run is None:
            return True
        
        now = datetime.now()
        seconds_since = (now - self.last_run).total_seconds()
        
        if seconds_since < COOLDOWN:
            remaining = int(COOLDOWN - seconds_since)
            self.show(f"⏳ Cooldown: {remaining}s")
            return False
        
        return True

def main():
    print("\n" + "="*60)
    print("SOLARA WATCHDOG")
    print("="*60)
    print(f"Watching: {MT5_FILES_DIR / WATCHED_FILE}")
    print(f"Check: every {CHECK_INTERVAL}s")
    print(f"Cooldown: {COOLDOWN}s")
    print("="*60 + "\n")
    
    watcher = DebugWatcher()
    
    try:
        while True:
            if watcher.check_file() and watcher.should_run():
                watcher.run_test()
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("👋 Stopped")
        print(f"Runs: {watcher.total_runs}")
        print("="*60)

if __name__ == "__main__":
    if sys.platform == "win32":
        os.system('chcp 65001 >nul')
    main()