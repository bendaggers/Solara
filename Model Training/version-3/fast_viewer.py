#!/usr/bin/env python3
"""
Fast checkpoint viewer - shows progress and best configs with ALL metrics.
"""

import argparse
import sqlite3
import json

def main():
    parser = argparse.ArgumentParser(description="View checkpoint database status")
    parser.add_argument('--db', required=True, help="Path to checkpoint database")
    parser.add_argument('--top', type=int, default=10, help="Number of top configs to show")
    parser.add_argument('--export', type=str, help="Export passed configs to CSV file")
    parser.add_argument('--sort', type=str, default='ev', 
                        choices=['ev', 'precision', 'f1', 'auc_pr', 'recall', 'trades'],
                        help="Sort by metric (default: ev)")
    
    args = parser.parse_args()
    
    conn = sqlite3.connect(args.db)
    cursor = conn.cursor()
    
    # Check schema
    cursor.execute("PRAGMA table_info(completed)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Basic stats
    total = cursor.execute("SELECT COUNT(*) FROM completed").fetchone()[0]
    passed = cursor.execute("SELECT COUNT(*) FROM completed WHERE status = 'PASSED'").fetchone()[0]
    rejected = cursor.execute("SELECT COUNT(*) FROM completed WHERE status = 'REJECTED'").fetchone()[0]
    failed = cursor.execute("SELECT COUNT(*) FROM completed WHERE status = 'FAILED'").fetchone()[0]
    
    # Best EV
    best = cursor.execute("""
        SELECT config_id, ev_mean FROM completed 
        WHERE ev_mean IS NOT NULL 
        ORDER BY ev_mean DESC LIMIT 1
    """).fetchone()
    
    print("\n" + "=" * 100)
    print("CHECKPOINT STATUS")
    print("=" * 100)
    print(f"Completed:  {total} configs")
    print(f"  PASSED:   {passed}")
    print(f"  REJECTED: {rejected}")
    print(f"  FAILED:   {failed}")
    
    if best:
        print(f"\nBest EV: {best[1]:.2f} ({best[0]})")
    
    # Show top configs with ALL metrics
    if passed > 0:
        print("\n" + "=" * 100)
        print(f"TOP {args.top} PASSED CONFIGURATIONS (sorted by {args.sort})")
        print("=" * 100)
        
        # Sort column mapping
        sort_map = {
            'ev': 'ev_mean',
            'precision': 'precision_mean',
            'f1': 'f1_mean',
            'auc_pr': 'auc_pr_mean',
            'recall': 'recall_mean',
            'trades': 'total_trades'
        }
        sort_col = sort_map[args.sort]
        
        has_full_schema = 'f1_mean' in columns
        
        if has_full_schema:
            cursor.execute(f"""
                SELECT 
                    config_id, bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars,
                    ev_mean, precision_mean, recall_mean, f1_mean, auc_pr_mean,
                    total_trades, consensus_threshold, n_features, selected_features
                FROM completed 
                WHERE status = 'PASSED' AND ev_mean IS NOT NULL
                ORDER BY {sort_col} DESC 
                LIMIT ?
            """, (args.top,))
            
            # Header
            print(f"{'#':<3} | {'BB':>5} | {'RSI':>3} | {'TP':>3} | {'SL':>3} | {'Hold':>4} | "
                  f"{'EV':>7} | {'Prec':>5} | {'Rec':>5} | {'F1':>5} | {'AUC':>5} | "
                  f"{'Trades':>6} | {'Thr':>5} | {'#Feat':>5}")
            print("-" * 100)
            
            for i, row in enumerate(cursor.fetchall(), 1):
                config_id = row[0]
                bb = row[1] or 0
                rsi = row[2] or 0
                tp = row[3] or 0
                sl = row[4] or 0
                hold = row[5] or 0
                ev = row[6] or 0
                prec = row[7] or 0
                rec = row[8] or 0
                f1 = row[9] or 0
                auc = row[10] or 0
                trades = row[11] or 0
                thresh = row[12] or 0
                n_feat = row[13] or 0
                
                print(f"{i:<3} | {bb:>5.2f} | {rsi:>3} | {tp:>3} | {sl:>3} | {hold:>4} | "
                      f"{ev:>7.2f} | {prec:>5.3f} | {rec:>5.3f} | {f1:>5.3f} | {auc:>5.3f} | "
                      f"{trades:>6} | {thresh:>5.2f} | {n_feat:>5}")
            
            # Show features for best config
            print("\n" + "-" * 100)
            print("SELECTED FEATURES (Best Config):")
            cursor.execute("""
                SELECT selected_features FROM completed 
                WHERE status = 'PASSED' AND ev_mean IS NOT NULL
                ORDER BY ev_mean DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row and row[0]:
                features = json.loads(row[0])
                for j, feat in enumerate(features, 1):
                    print(f"  {j}. {feat}")
        else:
            print("WARNING: Old schema - missing metrics columns.")
            print("Delete checkpoint and restart training with updated code.")
    
    # Rejection summary
    if 'rejection_reasons' in columns and rejected > 0:
        print("\n" + "=" * 100)
        print("REJECTION REASONS")
        print("=" * 100)
        
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
            pct = 100 * count / rejected if rejected > 0 else 0
            print(f"  {reason}: {count} ({pct:.1f}%)")
    
    # Export if requested
    if args.export and passed > 0:
        import csv
        cursor.execute("""
            SELECT 
                config_id, bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars,
                ev_mean, ev_std, precision_mean, precision_std, recall_mean, f1_mean, auc_pr_mean,
                total_trades, consensus_threshold, n_features, selected_features
            FROM completed 
            WHERE status = 'PASSED'
            ORDER BY ev_mean DESC
        """)
        
        with open(args.export, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'config_id', 'bb_threshold', 'rsi_threshold', 'tp_pips', 'sl_pips', 'max_holding_bars',
                'ev_mean', 'ev_std', 'precision_mean', 'precision_std', 'recall_mean', 'f1_mean', 'auc_pr_mean',
                'total_trades', 'consensus_threshold', 'n_features', 'selected_features'
            ])
            for row in cursor.fetchall():
                writer.writerow(row)
        
        print(f"\nExported to: {args.export}")
    
    conn.close()
    print()


if __name__ == '__main__':
    main()