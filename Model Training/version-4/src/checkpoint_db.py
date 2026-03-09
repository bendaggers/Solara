"""
Checkpoint system using SQLite for Pure ML Pipeline.
Stores progress to allow resuming interrupted runs.

PRIMARY KEY: (tp_pips, sl_pips, max_holding_bars)
Database: pure_ml.db (separate from v3's fast.db)
"""

import sqlite3
import threading
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime


class PureMLCheckpointManager:
    """
    Checkpoint manager for Pure ML pipeline.
    
    PRIMARY KEY: (tp_pips, sl_pips, max_holding_bars)
    
    Features:
    - Saves completed configs to SQLite
    - Allows resuming interrupted runs
    - Thread-safe for parallel workers
    """
    
    def __init__(self, db_path: str = "pure_ml.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._completed_params_cache: Optional[Set[Tuple]] = None
        self._cache_lock = threading.Lock()
        self._init_db()
    
    def _get_conn(self):
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                isolation_level=None
            )
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-16000")
        return self._local.conn
    
    def _init_db(self):
        """Create table with parameters as primary key."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS completed (
                tp_pips INTEGER NOT NULL,
                sl_pips INTEGER NOT NULL,
                max_holding_bars INTEGER NOT NULL,
                config_id TEXT,
                status TEXT,
                ev_mean REAL,
                ev_std REAL,
                precision_mean REAL,
                precision_std REAL,
                recall_mean REAL,
                f1_mean REAL,
                auc_pr_mean REAL,
                total_trades INTEGER,
                selected_features TEXT,
                consensus_threshold REAL,
                n_features INTEGER,
                rejection_reasons TEXT,
                execution_time REAL,
                timestamp TEXT,
                PRIMARY KEY (tp_pips, sl_pips, max_holding_bars)
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON completed(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ev ON completed(ev_mean)")
        
        conn.commit()
        conn.close()
    
    def _get_completed_params(self) -> Set[Tuple]:
        """Get all completed parameter combinations as a set for fast lookup."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT tp_pips, sl_pips, max_holding_bars 
            FROM completed
        """)
        return {(row[0], row[1], row[2]) for row in cursor.fetchall()}
    
    def is_params_completed(self, tp: int, sl: int, hold: int) -> bool:
        """Check if this parameter combination was already tested."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT 1 FROM completed 
            WHERE tp_pips = ? AND sl_pips = ? AND max_holding_bars = ?
            LIMIT 1
        """, (tp, sl, hold))
        return cursor.fetchone() is not None
    
    def get_pending_configs(self, all_configs: List) -> List:
        """
        Get configs that need processing.
        Checks by PARAMETERS (tp, sl, hold).
        """
        if not all_configs:
            return []
        
        with self._cache_lock:
            if self._completed_params_cache is None:
                self._completed_params_cache = self._get_completed_params()
            completed_params = self._completed_params_cache
        
        pending = []
        for config in all_configs:
            param_tuple = (
                config.tp_pips,
                config.sl_pips,
                config.max_holding_bars
            )
            if param_tuple not in completed_params:
                pending.append(config)
        
        return pending
    
    def mark_completed(
        self,
        config_id: str,
        status: str,
        tp_pips: int,
        sl_pips: int,
        max_holding_bars: int,
        ev_mean: float = None,
        ev_std: float = None,
        precision_mean: float = None,
        precision_std: float = None,
        recall_mean: float = None,
        f1_mean: float = None,
        auc_pr_mean: float = None,
        total_trades: int = None,
        selected_features: List[str] = None,
        consensus_threshold: float = None,
        rejection_reasons: List[str] = None,
        execution_time: float = None
    ):
        """
        Mark a config as completed with all metrics.
        Uses INSERT OR REPLACE to handle duplicates.
        """
        conn = self._get_conn()
        
        features_json = json.dumps(selected_features) if selected_features else None
        reasons_json = json.dumps(rejection_reasons) if rejection_reasons else None
        n_features = len(selected_features) if selected_features else 0
        
        conn.execute("""
            INSERT OR REPLACE INTO completed (
                tp_pips, sl_pips, max_holding_bars,
                config_id, status,
                ev_mean, ev_std, precision_mean, precision_std, 
                recall_mean, f1_mean, auc_pr_mean, total_trades,
                selected_features, consensus_threshold, n_features,
                rejection_reasons, execution_time, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tp_pips, sl_pips, max_holding_bars,
            config_id, status,
            ev_mean, ev_std, precision_mean, precision_std,
            recall_mean, f1_mean, auc_pr_mean, total_trades,
            features_json, consensus_threshold, n_features,
            reasons_json, execution_time, datetime.now().isoformat()
        ))
        
        # Invalidate cache
        with self._cache_lock:
            self._completed_params_cache = None
    
    def get_progress_stats(self) -> Dict[str, Any]:
        """Get quick progress stats."""
        conn = self._get_conn()
        
        total = conn.execute("SELECT COUNT(*) FROM completed").fetchone()[0]
        
        best = conn.execute("""
            SELECT config_id, ev_mean, tp_pips, sl_pips, max_holding_bars 
            FROM completed 
            WHERE ev_mean IS NOT NULL 
            ORDER BY ev_mean DESC LIMIT 1
        """).fetchone()
        
        passed = conn.execute(
            "SELECT COUNT(*) FROM completed WHERE status = 'PASSED'"
        ).fetchone()[0]
        
        rejected = conn.execute(
            "SELECT COUNT(*) FROM completed WHERE status = 'REJECTED'"
        ).fetchone()[0]
        
        failed = conn.execute(
            "SELECT COUNT(*) FROM completed WHERE status = 'FAILED'"
        ).fetchone()[0]
        
        db_size = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0
        
        return {
            'total': total,
            'passed': passed,
            'rejected': rejected,
            'failed': failed,
            'best_config': best[0] if best else None,
            'best_ev': best[1] if best else None,
            'best_params': f"TP={best[2]} SL={best[3]} H={best[4]}" if best else None,
            'database_size_mb': db_size
        }
    
    def get_passed_count(self) -> int:
        """Get count of passed configs."""
        conn = self._get_conn()
        return conn.execute(
            "SELECT COUNT(*) FROM completed WHERE status = 'PASSED'"
        ).fetchone()[0]
    
    def get_best_configs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top N configs by EV."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT 
                config_id, status,
                tp_pips, sl_pips, max_holding_bars,
                ev_mean, precision_mean, total_trades,
                selected_features, consensus_threshold
            FROM completed 
            WHERE status = 'PASSED' AND ev_mean IS NOT NULL
            ORDER BY ev_mean DESC 
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            features = json.loads(row[8]) if row[8] else []
            results.append({
                'config_id': row[0],
                'status': row[1],
                'tp_pips': row[2],
                'sl_pips': row[3],
                'max_holding_bars': row[4],
                'ev_mean': row[5],
                'precision_mean': row[6],
                'total_trades': row[7],
                'selected_features': features,
                'consensus_threshold': row[9]
            })
        
        return results
    
    def count_pending(self, all_configs: List) -> Tuple[int, int, int]:
        """
        Count how many configs are pending vs already completed.
        Returns: (total, completed, pending)
        """
        with self._cache_lock:
            if self._completed_params_cache is None:
                self._completed_params_cache = self._get_completed_params()
            completed_params = self._completed_params_cache
        
        completed_count = 0
        pending_count = 0
        
        for config in all_configs:
            param_tuple = (
                config.tp_pips,
                config.sl_pips,
                config.max_holding_bars
            )
            if param_tuple in completed_params:
                completed_count += 1
            else:
                pending_count += 1
        
        return len(all_configs), completed_count, pending_count
    
    def clear_all(self):
        """Clear all checkpoint data (use with caution!)."""
        conn = self._get_conn()
        conn.execute("DELETE FROM completed")
        with self._cache_lock:
            self._completed_params_cache = None
        print(f"Cleared all checkpoints from {self.db_path}")
    
    def export_to_csv(self, filepath: str) -> None:
        """Export all results to CSV."""
        import csv
        
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT 
                config_id, tp_pips, sl_pips, max_holding_bars,
                status, ev_mean, ev_std, precision_mean, precision_std, 
                total_trades, consensus_threshold, n_features, selected_features
            FROM completed 
            ORDER BY ev_mean DESC
        """)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'config_id', 'tp_pips', 'sl_pips', 'max_holding_bars',
                'status', 'ev_mean', 'ev_std', 'precision_mean', 'precision_std',
                'total_trades', 'consensus_threshold', 'n_features', 'selected_features'
            ])
            for row in cursor.fetchall():
                writer.writerow(row)
        
        print(f"Exported to {filepath}")
