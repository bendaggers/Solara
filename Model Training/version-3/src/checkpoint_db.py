"""
Checkpoint system using SQLite - COMPLETE VERSION.
Stores all important config details for later analysis.

FIXED: Now checks by PARAMETERS (bb, rsi, tp, sl, hold) not config_id
       This allows widening config space without duplicating work!
"""

import sqlite3
import threading
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime


class FastCheckpointManager:
    """
    Complete checkpoint manager that stores ALL important details.
    
    IMPORTANT: Uses PARAMETERS to check completion, not config_id!
    This allows config space changes without re-running tested configs.
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._completed_params_cache = None  # Cache for fast lookup
        self._init_db()
    
    def _get_conn(self):
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=5.0,
                isolation_level=None  # Auto-commit
            )
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-16000")
        return self._local.conn
    
    def _init_db(self):
        """Create complete table structure."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Check if table exists
        cursor = conn.execute("PRAGMA table_info(completed)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if columns and 'bb_threshold' not in columns:
            # Old schema exists - need to migrate
            print("Migrating checkpoint database to new schema...")
            self._migrate_schema(conn)
        elif not columns:
            # New database - create full schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS completed (
                    config_id TEXT PRIMARY KEY,
                    status TEXT,
                    
                    -- Config parameters
                    bb_threshold REAL,
                    rsi_threshold INTEGER,
                    tp_pips INTEGER,
                    sl_pips INTEGER,
                    max_holding_bars INTEGER,
                    
                    -- Metrics
                    ev_mean REAL,
                    ev_std REAL,
                    precision_mean REAL,
                    precision_std REAL,
                    recall_mean REAL,
                    f1_mean REAL,
                    auc_pr_mean REAL,
                    total_trades INTEGER,
                    
                    -- Model details
                    selected_features TEXT,
                    consensus_threshold REAL,
                    n_features INTEGER,
                    
                    -- Metadata
                    rejection_reasons TEXT,
                    execution_time REAL,
                    timestamp TEXT
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_config ON completed(config_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON completed(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ev ON completed(ev_mean)")
        
        # Create index on parameters for fast lookup (if not exists)
        try:
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_params 
                ON completed(bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars)
            """)
        except:
            pass
        
        conn.commit()
        conn.close()
    
    def _migrate_schema(self, conn):
        """Migrate old schema to new schema."""
        conn.execute("ALTER TABLE completed RENAME TO completed_old")
        
        conn.execute("""
            CREATE TABLE completed (
                config_id TEXT PRIMARY KEY,
                status TEXT,
                bb_threshold REAL,
                rsi_threshold INTEGER,
                tp_pips INTEGER,
                sl_pips INTEGER,
                max_holding_bars INTEGER,
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
                timestamp TEXT
            )
        """)
        
        conn.execute("""
            INSERT INTO completed (config_id, status, ev_mean, timestamp)
            SELECT config_id, status, ev_mean, timestamp FROM completed_old
        """)
        
        conn.execute("DROP TABLE completed_old")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_config ON completed(config_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON completed(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ev ON completed(ev_mean)")
        
        conn.commit()
        print("Migration complete.")
    
    def _get_completed_params(self) -> Set[Tuple]:
        """Get all completed parameter combinations as a set for fast lookup."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars 
            FROM completed
            WHERE bb_threshold IS NOT NULL
        """)
        
        # Return as set of tuples for O(1) lookup
        return {(row[0], row[1], row[2], row[3], row[4]) for row in cursor.fetchall()}
    
    def _refresh_cache(self):
        """Refresh the completed params cache."""
        self._completed_params_cache = self._get_completed_params()
    
    def is_params_completed(self, bb: float, rsi: int, tp: int, sl: int, hold: int) -> bool:
        """Check if this parameter combination was already tested."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT 1 FROM completed 
            WHERE bb_threshold = ? AND rsi_threshold = ? AND tp_pips = ? AND sl_pips = ? AND max_holding_bars = ?
            LIMIT 1
        """, (bb, rsi, tp, sl, hold))
        return cursor.fetchone() is not None
    
    def get_pending_configs(self, all_configs: List) -> List:
        """
        Get configs that need processing.
        
        FIXED: Now checks by PARAMETERS, not config_id!
        This allows widening config space without duplicates.
        """
        if not all_configs:
            return []
        
        # Get all completed parameter combinations
        completed_params = self._get_completed_params()
        
        # Filter configs by checking parameters
        pending = []
        for config in all_configs:
            param_tuple = (
                config.bb_threshold,
                config.rsi_threshold,
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
        ev_mean: float = None,
        bb_threshold: float = None,
        rsi_threshold: int = None,
        tp_pips: int = None,
        sl_pips: int = None,
        max_holding_bars: int = None,
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
    ) -> None:
        """Mark a config as completed with ALL details."""
        conn = self._get_conn()
        
        features_json = json.dumps(selected_features) if selected_features else None
        reasons_json = json.dumps(rejection_reasons) if rejection_reasons else None
        n_features = len(selected_features) if selected_features else None
        
        conn.execute("""
            INSERT OR REPLACE INTO completed (
                config_id, status,
                bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars,
                ev_mean, ev_std, precision_mean, precision_std, recall_mean, f1_mean, auc_pr_mean, total_trades,
                selected_features, consensus_threshold, n_features,
                rejection_reasons, execution_time, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            config_id, status,
            bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars,
            ev_mean, ev_std, precision_mean, precision_std, recall_mean, f1_mean, auc_pr_mean, total_trades,
            features_json, consensus_threshold, n_features,
            reasons_json, execution_time, datetime.now().isoformat()
        ))
        
        # Invalidate cache
        self._completed_params_cache = None
    
    def is_completed(self, config_id: str) -> bool:
        """Check if config is done (by config_id - legacy support)."""
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
    
    def get_progress_stats(self) -> Dict[str, Any]:
        """Get quick progress stats."""
        conn = self._get_conn()
        
        total = conn.execute("SELECT COUNT(*) FROM completed").fetchone()[0]
        
        best = conn.execute("""
            SELECT config_id, ev_mean FROM completed 
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
    
    def get_best_configs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top N configs by EV."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT 
                config_id, status,
                bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars,
                ev_mean, precision_mean, total_trades,
                selected_features, consensus_threshold
            FROM completed 
            WHERE status = 'PASSED' AND ev_mean IS NOT NULL
            ORDER BY ev_mean DESC 
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            features = json.loads(row[10]) if row[10] else []
            results.append({
                'config_id': row[0],
                'status': row[1],
                'bb_threshold': row[2],
                'rsi_threshold': row[3],
                'tp_pips': row[4],
                'sl_pips': row[5],
                'max_holding_bars': row[6],
                'ev_mean': row[7],
                'precision_mean': row[8],
                'total_trades': row[9],
                'selected_features': features,
                'consensus_threshold': row[11]
            })
        
        return results
    
    def get_rejection_summary(self) -> Dict[str, int]:
        """Get summary of rejection reasons."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT rejection_reasons FROM completed 
            WHERE status = 'REJECTED' AND rejection_reasons IS NOT NULL
        """)
        
        summary = {}
        for row in cursor.fetchall():
            reasons = json.loads(row[0]) if row[0] else []
            for reason in reasons:
                clean = reason.split('(')[0].strip()
                summary[clean] = summary.get(clean, 0) + 1
        
        return summary
    
    def export_passed_to_csv(self, filepath: str) -> None:
        """Export all passed configs to CSV."""
        import csv
        
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT 
                config_id, bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars,
                ev_mean, ev_std, precision_mean, precision_std, total_trades,
                consensus_threshold, n_features, selected_features
            FROM completed 
            WHERE status = 'PASSED'
            ORDER BY ev_mean DESC
        """)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'config_id', 'bb_threshold', 'rsi_threshold', 'tp_pips', 'sl_pips', 'max_holding_bars',
                'ev_mean', 'ev_std', 'precision_mean', 'precision_std', 'total_trades',
                'consensus_threshold', 'n_features', 'selected_features'
            ])
            for row in cursor.fetchall():
                writer.writerow(row)
        
        print(f"Exported to {filepath}")
    
    def get_tested_parameter_ranges(self) -> Dict[str, Dict[str, float]]:
        """Get the ranges of parameters that have been tested."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT 
                MIN(bb_threshold), MAX(bb_threshold),
                MIN(rsi_threshold), MAX(rsi_threshold),
                MIN(tp_pips), MAX(tp_pips),
                MIN(sl_pips), MAX(sl_pips),
                MIN(max_holding_bars), MAX(max_holding_bars)
            FROM completed
            WHERE bb_threshold IS NOT NULL
        """)
        row = cursor.fetchone()
        
        if row and row[0] is not None:
            return {
                'bb_threshold': {'min': row[0], 'max': row[1]},
                'rsi_threshold': {'min': row[2], 'max': row[3]},
                'tp_pips': {'min': row[4], 'max': row[5]},
                'sl_pips': {'min': row[6], 'max': row[7]},
                'max_holding_bars': {'min': row[8], 'max': row[9]}
            }
        return {}
    
    def count_pending(self, all_configs: List) -> Tuple[int, int, int]:
        """
        Count how many configs are pending vs already completed.
        Returns: (total, completed, pending)
        """
        completed_params = self._get_completed_params()
        
        completed_count = 0
        pending_count = 0
        
        for config in all_configs:
            param_tuple = (
                config.bb_threshold,
                config.rsi_threshold,
                config.tp_pips,
                config.sl_pips,
                config.max_holding_bars
            )
            if param_tuple in completed_params:
                completed_count += 1
            else:
                pending_count += 1
        
        return len(all_configs), completed_count, pending_count
