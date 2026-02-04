"""
Survivor Engine Reporter
Handles logging of position events and protection changes
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import shutil
import random

class SurvivorReporter:
    """
    Lightweight reporter for Survivor Engine v5.0
    Saves to: Trading Bot/reports/
    """
    
    def __init__(self, base_path: str = None):
        """
        Initialize reporter WITHOUT creating files
        
        Args:
            base_path: Optional custom base path. If None, uses:
                      Trading Bot/reports/
        """
        # Get the directory where THIS FILE is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # current_dir = .../Trading Bot/trailing_sltp/
        
        # Go up one level to Trading Bot folder
        trading_bot_dir = os.path.dirname(current_dir)
        # trading_bot_dir = .../Trading Bot/
        
        # Set reports directory
        if base_path:
            self.reports_dir = base_path
        else:
            self.reports_dir = os.path.join(trading_bot_dir, "reports")
        
        # Create subdirectories
        self.archive_dir = os.path.join(self.reports_dir, "archive")
        self.exports_dir = os.path.join(self.reports_dir, "exports")
        
        # Create directories if they don't exist
        for directory in [self.reports_dir, self.archive_dir, self.exports_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Set file paths
        self.last_run_file = os.path.join(self.reports_dir, "survivor_last_run.json")
        self.history_file = os.path.join(self.reports_dir, "survivor_history.json")
        
        # DON'T create files here - do it lazily when needed
        # self._ensure_files_exist()  # REMOVED!
        
        print(f"📁 Reporter instance created (files will be created when needed)")

    def _ensure_files_exist(self):
        """Create empty JSON files if they don't exist - LAZY INITIALIZATION"""
        files_created = []
        
        # History file - empty array
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w') as f:
                json.dump([], f, indent=2)
            files_created.append("history")
        
        # Last run file - empty object
        if not os.path.exists(self.last_run_file):
            with open(self.last_run_file, 'w') as f:
                json.dump({}, f, indent=2)
            files_created.append("last_run")
        
        # Also ensure files have valid JSON if they exist but are empty
        for file_path, default_content in [
            (self.history_file, []),
            (self.last_run_file, {})
        ]:
            if os.path.exists(file_path) and os.path.getsize(file_path) == 0:
                with open(file_path, 'w') as f:
                    json.dump(default_content, f, indent=2)
        
        # Only print if we actually created files
        if files_created:
            print(f"📁 Created report files: {', '.join(files_created)}")


    # ================== EVENT LOGGING METHODS ==================
    
    def log_position_opened(self, position: Dict, market_context: Dict = None) -> str:
        """
        Log when a new position is opened
        """
        # Ensure files exist before writing
        self._ensure_files_exist()
        
        event_id = self._generate_event_id()
        
        event = {
            "event_id": event_id,
            "event_timestamp": datetime.now().isoformat(),
            "event_type": "POSITION_OPENED",
            "position_id": f"{position['symbol']}-{position['ticket']}",
            "symbol": position['symbol'],
            "ticket": position['ticket'],
            "position_type": "BUY" if position.get('type') == 0 else "SELL",
            
            "entry_data": {
                "entry_price": position.get('entry_price', 0.0),
                "lot_size": position.get('volume', 1.0),
                "initial_sl": position.get('sl', 0.0),
                "initial_tp": position.get('tp', 0.0),
                "commission": position.get('commission', 0.0),
                "swap": position.get('swap', 0.0)
            },
            
            "market_context": market_context or {},
            
            "engine_data": {
                "engine_version": "5.0.2",
                "strategy": "survivor_v5"
            }
        }
        
        self._append_to_history(event)
        return event_id
    
    def log_stage_change(self, position: Dict, old_stage: str, new_stage: str,
                        profit_pips: float, trigger: str, bb_data: Dict = None) -> str:
        """
        Log when position moves to a new protection stage
        """
        # Ensure files exist before writing
        self._ensure_files_exist()
        
        event_id = self._generate_event_id()
        
        # Extract stage number
        old_stage_num = old_stage.split('_')[-1] if '_' in old_stage else '0'
        new_stage_num = new_stage.split('_')[-1] if '_' in new_stage else '0'
        
        event = {
            "event_id": event_id,
            "event_timestamp": datetime.now().isoformat(),
            "event_type": "STAGE_CHANGE",
            "position_id": f"{position['symbol']}-{position['ticket']}",
            "symbol": position['symbol'],
            "ticket": position['ticket'],
            
            "stage_data": {
                "old_stage": old_stage,
                "old_stage_number": int(old_stage_num),
                "new_stage": new_stage,
                "new_stage_number": int(new_stage_num),
                "old_sl": position.get('sl', 0.0),
                "new_sl": position.get('new_sl', 0.0),
                "protection_percent": self._get_protection_percent(new_stage)
            },
            
            "profit_data": {
                "profit_pips": round(profit_pips, 1),
                "profit_ratio": bb_data.get('profit_ratio', 0.0) if bb_data else 0.0,
                "peak_profit_pips": bb_data.get('peak_profit', profit_pips) if bb_data else profit_pips
            },
            
            "trigger_data": {
                "trigger_type": trigger,
                "threshold_pips": bb_data.get('threshold_pips', 0) if bb_data else 0,
                "bb_width_pips": bb_data.get('bb_width_pips', 0.0) if bb_data else 0.0,
                "distance_to_upper": bb_data.get('distance_to_upper', 0.0) if bb_data else 0.0
            },
            
            "market_condition": {
                "bb_width_change": bb_data.get('bb_width_change', 0.0) if bb_data else 0.0,
                "trend_strength": bb_data.get('trend_strength', 'unknown') if bb_data else 'unknown'
            }
        }
        
        self._append_to_history(event)
        return event_id
    
    def log_engine_cycle(self, cycle_data: Dict) -> str:
        """
        Log start of engine processing cycle
        """
        # Ensure files exist before writing
        self._ensure_files_exist()
        
        event_id = self._generate_event_id()
        
        event = {
            "event_id": event_id,
            "event_timestamp": datetime.now().isoformat(),
            "event_type": "ENGINE_CYCLE",
            
            "cycle_data": {
                **cycle_data,
                "reports_dir": self.reports_dir,
                "history_file": self.history_file,
                "last_run_file": self.last_run_file
            }
        }
        
        self._append_to_history(event)
        return event_id
    
    # ================== LAST RUN REPORT ==================
    
    def save_last_run(self, cycle_results: Dict):
        """
        Save current cycle results to last_run file (overwrites)
        """
        # Ensure files exist before writing
        self._ensure_files_exist()
        
        last_run_data = {
            "metadata": {
                "cycle_timestamp": datetime.now().isoformat(),
                "engine_version": "5.0.2",
                "positions_processed": cycle_results.get('positions_processed', 0),
                "processing_duration_ms": cycle_results.get('processing_duration_ms', 0)
            },
            "summary": cycle_results.get('summary', {}),
            "detailed_changes": cycle_results.get('detailed_changes', []),
            "system_health": cycle_results.get('system_health', {}),
            "file_locations": {
                "reports_dir": self.reports_dir,
                "history_file": self.history_file,
                "last_run_file": self.last_run_file
            }
        }
        
        try:
            with open(self.last_run_file, 'w') as f:
                json.dump(last_run_data, f, indent=2)
            
            # Optional: Print summary to console
            summary = last_run_data['summary']
            if summary.get('positions_modified', 0) > 0:
                print(f"📝 Last run saved: {summary.get('positions_modified', 0)} positions modified")
                print(f"   Protection added: {summary.get('total_protection_added_pips', 0)} pips")
                
        except Exception as e:
            print(f"⚠️ Failed to save last run: {e}")
    
    # ================== UTILITY METHODS ==================
    
    def _append_to_history(self, event: Dict):
        """Safely append event to history file"""
        try:
            # Ensure files exist
            self._ensure_files_exist()
            
            # Read existing history - handle empty file case
            history = []
            try:
                with open(self.history_file, 'r') as f:
                    content = f.read().strip()
                    if content:  # Only load if file has content
                        history = json.loads(content)
            except (json.JSONDecodeError, FileNotFoundError):
                # If file is empty or corrupted, start with empty list
                history = []
            
            # Append new event
            history.append(event)
            
            # Write back
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
            
            # Check if we need to archive (every 1000 events)
            if len(history) % 1000 == 0:
                self._archive_if_needed()
                
        except Exception as e:
            print(f"⚠️ Failed to append to history: {e}")
            # Don't crash - just log error
    
    def _archive_if_needed(self, max_size_mb: int = 50):
        """Archive history file if it gets too large"""
        try:
            size_mb = os.path.getsize(self.history_file) / (1024 * 1024)
            
            if size_mb > max_size_mb:
                # Create archive filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_file = os.path.join(
                    self.archive_dir,
                    f"survivor_history_{timestamp}.json"
                )
                
                # Copy current file to archive
                shutil.copy2(self.history_file, archive_file)
                print(f"📦 Archived history file: {archive_file}")
                
                # Clear current history (keep last 100 events)
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
                
                # Keep last 100 events in current file
                if len(history) > 100:
                    history = history[-100:]
                    with open(self.history_file, 'w') as f:
                        json.dump(history, f, indent=2)
                    
        except Exception as e:
            print(f"⚠️ Failed to archive history: {e}")
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = f"{random.randint(1000, 9999)}"
        return f"{timestamp}_{random_suffix}"
    
    def _get_protection_percent(self, stage: str) -> int:
        """Get protection percentage for a stage"""
        # This should match SurvivorEngine.STAGE_DEFINITIONS
        stage_protections = {
            'STAGE_0': 0, 'STAGE_1': 10, 'STAGE_2': 15, 'STAGE_3': 20,
            'STAGE_4': 25, 'STAGE_5': 30, 'STAGE_6': 35, 'STAGE_7': 40,
            'STAGE_8': 45, 'STAGE_9': 50, 'STAGE_10': 55, 'STAGE_11': 60,
            'STAGE_12': 65, 'STAGE_13': 70, 'STAGE_14': 72, 'STAGE_15': 75,
            'STAGE_16': 78, 'STAGE_17': 80, 'STAGE_18': 82, 'STAGE_19': 84,
            'STAGE_20': 86, 'STAGE_21': 88, 'STAGE_22': 90
        }
        return stage_protections.get(stage, 0)
    
    # ================== QUERY METHODS ==================
    
    def get_position_history(self, position_id: str) -> List[Dict]:
        """Get all events for a specific position"""
        try:
            # Check if file exists
            if not os.path.exists(self.history_file):
                return []
            
            # Check if file is empty
            if os.path.getsize(self.history_file) == 0:
                return []
                
            with open(self.history_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    return []
                history = json.loads(content)
            
            return [event for event in history 
                if event.get('position_id') == position_id]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        """Get most recent events"""
        try:
            # Ensure files exist before reading
            if not os.path.exists(self.history_file):
                return []
                
            with open(self.history_file, 'r') as f:
                history = json.load(f)
            
            return history[-limit:] if len(history) > limit else history
        except:
            return []
    
    def get_last_run(self) -> Dict:
        """Get last run data"""
        try:
            # Ensure files exist before reading
            if not os.path.exists(self.last_run_file):
                return {}
                
            with open(self.last_run_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def get_file_locations(self) -> Dict:
        """Return all file locations"""
        return {
            "reports_dir": self.reports_dir,
            "history_file": self.history_file,
            "last_run_file": self.last_run_file,
            "archive_dir": self.archive_dir,
            "exports_dir": self.exports_dir
        }