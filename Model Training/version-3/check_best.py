"""
Check best configurations from checkpoint database.
Works with both old and new schema.
"""
import sqlite3
import json
import sys

def main():
    db_path = "checkpoints/fast.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check schema
    cursor.execute("PRAGMA table_info(completed)")
    columns = [row[1] for row in cursor.fetchall()]
    
    print("=" * 80)
    print("CHECKPOINT DATABASE ANALYSIS")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Columns: {columns}")
    print()
    
    # Get counts
    total = cursor.execute("SELECT COUNT(*) FROM completed").fetchone()[0]
    passed = cursor.execute("SELECT COUNT(*) FROM completed WHERE status = 'PASSED'").fetchone()[0]
    rejected = cursor.execute("SELECT COUNT(*) FROM completed WHERE status = 'REJECTED'").fetchone()[0]
    failed = cursor.execute("SELECT COUNT(*) FROM completed WHERE status = 'FAILED'").fetchone()[0]
    
    print(f"Total:    {total}")
    print(f"Passed:   {passed}")
    print(f"Rejected: {rejected}")
    print(f"Failed:   {failed}")
    print()
    
    # Check if new schema
    has_full_schema = 'bb_threshold' in columns
    
    if has_full_schema:
        print("=" * 80)
        print("TOP 10 PASSED CONFIGURATIONS (Full Details)")
        print("=" * 80)
        
        cursor.execute("""
            SELECT 
                config_id, bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars,
                ev_mean, precision_mean, total_trades, consensus_threshold, selected_features
            FROM completed 
            WHERE status = 'PASSED' AND ev_mean IS NOT NULL
            ORDER BY ev_mean DESC 
            LIMIT 10
        """)
        
        print(f"{'Config':<12} | {'BB':>5} | {'RSI':>3} | {'TP':>3} | {'SL':>3} | {'Hold':>4} | {'EV':>7} | {'Prec':>5} | {'Trades':>6} | {'Thresh':>6} | Features")
        print("-" * 120)
        
        for row in cursor.fetchall():
            features = json.loads(row[10]) if row[10] else []
            features_str = ", ".join(features[:3]) + ("..." if len(features) > 3 else "")
            print(f"{row[0]:<12} | {row[1]:>5.2f} | {row[2]:>3} | {row[3]:>3} | {row[4]:>3} | {row[5]:>4} | {row[6]:>7.2f} | {row[7]:>5.3f} | {row[8]:>6} | {row[9]:>6.3f} | {features_str}")
    else:
        print("=" * 80)
        print("TOP 10 PASSED CONFIGURATIONS (Limited - Old Schema)")
        print("=" * 80)
        print("WARNING: Old schema detected. Only config_id and ev_mean available.")
        print("         Re-run training with updated checkpoint_db.py for full details.")
        print()
        
        cursor.execute("""
            SELECT config_id, ev_mean 
            FROM completed 
            WHERE status = 'PASSED' AND ev_mean IS NOT NULL
            ORDER BY ev_mean DESC 
            LIMIT 10
        """)
        
        print(f"{'Config':<20} | {'EV':>10}")
        print("-" * 35)
        
        for row in cursor.fetchall():
            ev = row[1] if row[1] else 0
            print(f"{row[0]:<20} | {ev:>10.2f}")
    
    print()
    
    # Show rejection reasons if available
    if 'rejection_reasons' in columns:
        print("=" * 80)
        print("REJECTION REASON SUMMARY")
        print("=" * 80)
        
        cursor.execute("""
            SELECT rejection_reasons FROM completed 
            WHERE status = 'REJECTED' AND rejection_reasons IS NOT NULL
        """)
        
        summary = {}
        for row in cursor.fetchall():
            reasons = json.loads(row[0]) if row[0] else []
            for reason in reasons:
                clean = reason.split('(')[0].strip()
                summary[clean] = summary.get(clean, 0) + 1
        
        for reason, count in sorted(summary.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")
    
    conn.close()


if __name__ == "__main__":
    main()
