"""
Lightning fast checkpoint system using SQLite.
Only stores what's needed for resume + progress tracking.
"""

import sqlite3
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

class FastCheckpointManager:
    """
    Minimal, FAST checkpoint manager.
    
    Only stores:
    - config_id (to know what's done)
    - status (PASSED/REJECTED/FAILED)
    - ev_mean (for progress tracking)
    - timestamp (for ordering)
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self):
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=5.0,
                isolation_level=None  # Auto-commit
            )
            # Speed optimizations
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-16000")  # 16MB cache
        return self._local.conn
    
    def _init_db(self):
        """Create minimal table structure."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        # SUPER SIMPLE table - only what we need
        conn.execute("""
            CREATE TABLE IF NOT EXISTS completed (
                config_id TEXT PRIMARY KEY,
                status TEXT,
                ev_mean REAL,
                timestamp TEXT
            )
        """)
        
        # Single index for fast lookups
        conn.execute("CREATE INDEX IF NOT EXISTS idx_config ON completed(config_id)")
        
        conn.commit()
        conn.close()
    
    def mark_completed(self, config_id: str, status: str, ev_mean: float = None) -> None:
        """
        Mark a config as completed.
        
        This is the ONLY write operation. Super fast.
        """
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO completed (config_id, status, ev_mean, timestamp)
            VALUES (?, ?, ?, ?)
        """, (config_id, status, ev_mean, datetime.now().isoformat()))
    
    def is_completed(self, config_id: str) -> bool:
        """Check if config is done - SUPER FAST (indexed lookup)."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT 1 FROM completed WHERE config_id = ? LIMIT 1",
            (config_id,)
        )
        return cursor.fetchone() is not None
    
    def get_completed_ids(self) -> List[str]:
        """Get all completed config IDs."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT config_id FROM completed")
        return [row[0] for row in cursor.fetchall()]
    
    def get_pending_configs(self, all_configs: List) -> List:
        """Get configs that need processing."""
        if not all_configs:
            return []
        
        # Get completed IDs (single query)
        conn = self._get_conn()
        cursor = conn.execute("SELECT config_id FROM completed")
        completed = {row[0] for row in cursor.fetchall()}
        
        # Filter (set lookup is O(1))
        return [c for c in all_configs if c.config_id not in completed]
    
    def get_progress_stats(self) -> Dict[str, Any]:
        """Get quick progress stats."""
        conn = self._get_conn()
        
        total = conn.execute("SELECT COUNT(*) FROM completed").fetchone()[0]
        
        # Get best EV so far
        best = conn.execute("""
            SELECT config_id, ev_mean FROM completed 
            WHERE ev_mean IS NOT NULL 
            ORDER BY ev_mean DESC LIMIT 1
        """).fetchone()
        
        # Get status counts
        passed = conn.execute(
            "SELECT COUNT(*) FROM completed WHERE status = 'PASSED'"
        ).fetchone()[0]
        
        rejected = conn.execute(
            "SELECT COUNT(*) FROM completed WHERE status = 'REJECTED'"
        ).fetchone()[0]
        
        failed = conn.execute(
            "SELECT COUNT(*) FROM completed WHERE status = 'FAILED'"
        ).fetchone()[0]
        
        db_size = self.db_path.stat().st_size / (1024 * 1024)
        
        return {
            'total': total,
            'passed': passed,
            'rejected': rejected,
            'failed': failed,
            'best_config': best[0] if best else None,
            'best_ev': best[1] if best else None,
            'database_size_mb': db_size
        }