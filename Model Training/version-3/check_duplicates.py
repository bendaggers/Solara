#!/usr/bin/env python3
"""
CHECK FOR DUPLICATE CONFIGS

This script verifies:
1. No duplicate parameter combinations in the database
2. The pending configs logic is working correctly
3. Shows exactly how configs are filtered
"""

import sqlite3
import sys
from collections import defaultdict

def check_duplicates(db_path: str):
    print("=" * 70)
    print("DUPLICATE CONFIG CHECKER")
    print("=" * 70)
    
    conn = sqlite3.connect(db_path)
    
    # 1. Check total count
    total = conn.execute("SELECT COUNT(*) FROM completed").fetchone()[0]
    print(f"\n[1] Total rows in database: {total}")
    
    # 2. Check for duplicate parameter combinations
    print("\n[2] Checking for duplicate parameter combinations...")
    
    duplicates = conn.execute("""
        SELECT bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars, COUNT(*) as cnt
        FROM completed
        WHERE bb_threshold IS NOT NULL
        GROUP BY bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars
        HAVING cnt > 1
        ORDER BY cnt DESC
        LIMIT 20
    """).fetchall()
    
    if duplicates:
        print(f"\n   ⚠️  FOUND {len(duplicates)} DUPLICATE PARAMETER COMBINATIONS!")
        print(f"\n   {'BB':>6} | {'RSI':>3} | {'TP':>3} | {'SL':>3} | {'Hold':>4} | {'Count':>5}")
        print("   " + "-" * 45)
        for row in duplicates[:10]:
            print(f"   {row[0]:>6.2f} | {row[1]:>3} | {row[2]:>3} | {row[3]:>3} | {row[4]:>4} | {row[5]:>5}")
    else:
        print("   ✅ No duplicate parameter combinations found!")
    
    # 3. Check unique parameter count vs total rows
    unique_count = conn.execute("""
        SELECT COUNT(DISTINCT bb_threshold || '-' || rsi_threshold || '-' || tp_pips || '-' || sl_pips || '-' || max_holding_bars)
        FROM completed
        WHERE bb_threshold IS NOT NULL
    """).fetchone()[0]
    
    print(f"\n[3] Unique parameter combinations: {unique_count}")
    print(f"    Total rows: {total}")
    
    if unique_count == total:
        print("    ✅ All rows are unique!")
    else:
        print(f"    ⚠️  {total - unique_count} duplicate rows exist!")
    
    # 4. Check what the pending logic would return
    print("\n[4] Checking parameter tuple format...")
    
    sample = conn.execute("""
        SELECT bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars
        FROM completed
        WHERE bb_threshold IS NOT NULL
        LIMIT 5
    """).fetchall()
    
    print("    Sample parameter tuples from DB:")
    for row in sample:
        print(f"      {row}")
    
    # 5. Check data types
    print("\n[5] Checking data types...")
    
    type_check = conn.execute("""
        SELECT 
            typeof(bb_threshold) as bb_type,
            typeof(rsi_threshold) as rsi_type,
            typeof(tp_pips) as tp_type,
            typeof(sl_pips) as sl_type,
            typeof(max_holding_bars) as hold_type
        FROM completed
        WHERE bb_threshold IS NOT NULL
        LIMIT 1
    """).fetchone()
    
    if type_check:
        print(f"    bb_threshold:    {type_check[0]}")
        print(f"    rsi_threshold:   {type_check[1]}")
        print(f"    tp_pips:         {type_check[2]}")
        print(f"    sl_pips:         {type_check[3]}")
        print(f"    max_holding_bars: {type_check[4]}")
    
    # 6. Check for floating point precision issues with BB
    print("\n[6] Checking BB values for floating point issues...")
    
    bb_values = conn.execute("""
        SELECT DISTINCT bb_threshold
        FROM completed
        WHERE bb_threshold IS NOT NULL
        ORDER BY bb_threshold
    """).fetchall()
    
    print(f"    Unique BB values: {len(bb_values)}")
    for bb in bb_values[:15]:
        print(f"      {bb[0]}")
    
    # Check if there are very close but not equal BB values
    bb_list = [b[0] for b in bb_values]
    for i, bb1 in enumerate(bb_list):
        for bb2 in bb_list[i+1:]:
            diff = abs(bb1 - bb2)
            if diff < 0.01 and diff > 0:
                print(f"    ⚠️  Close BB values: {bb1} vs {bb2} (diff={diff})")
    
    # 7. Summary of configs by BB
    print("\n[7] Config count by BB threshold:")
    
    bb_counts = conn.execute("""
        SELECT bb_threshold, COUNT(*) as cnt
        FROM completed
        WHERE bb_threshold IS NOT NULL
        GROUP BY bb_threshold
        ORDER BY bb_threshold
    """).fetchall()
    
    total_sum = 0
    for bb, cnt in bb_counts:
        print(f"    BB={bb}: {cnt} configs")
        total_sum += cnt
    
    print(f"\n    Sum: {total_sum} (should equal {total})")
    
    # 8. Show recent entries to verify saving is working
    print("\n[8] Most recent 10 entries (by timestamp):")
    
    recent = conn.execute("""
        SELECT bb_threshold, rsi_threshold, tp_pips, status, timestamp
        FROM completed
        WHERE bb_threshold IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 10
    """).fetchall()
    
    print(f"    {'BB':>6} | {'RSI':>3} | {'TP':>3} | {'Status':<10} | Timestamp")
    print("    " + "-" * 60)
    for row in recent:
        print(f"    {row[0]:>6.2f} | {row[1]:>3} | {row[2]:>3} | {row[3]:<10} | {row[4]}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("CHECK COMPLETE")
    print("=" * 70)


def simulate_pending_check(db_path: str):
    """Simulate what get_pending_configs does."""
    print("\n" + "=" * 70)
    print("SIMULATING PENDING CHECK")
    print("=" * 70)
    
    conn = sqlite3.connect(db_path)
    
    # Get completed params (exactly like the code does)
    cursor = conn.execute("""
        SELECT bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars 
        FROM completed
        WHERE bb_threshold IS NOT NULL
    """)
    
    completed_params = {(row[0], row[1], row[2], row[3], row[4]) for row in cursor.fetchall()}
    
    print(f"\n  Completed parameter tuples: {len(completed_params)}")
    
    # Show a few examples
    print("\n  Sample completed tuples:")
    for i, t in enumerate(list(completed_params)[:5]):
        print(f"    {t}")
    
    # Test a specific config
    test_configs = [
        (0.80, 71, 40, 30, 18),
        (0.81, 72, 40, 30, 18),
        (0.85, 75, 50, 30, 18),
        (0.99, 99, 99, 99, 99),  # Should NOT exist
    ]
    
    print("\n  Testing specific configs:")
    for cfg in test_configs:
        exists = cfg in completed_params
        status = "✅ EXISTS (will skip)" if exists else "❌ NOT FOUND (will run)"
        print(f"    {cfg}: {status}")
    
    conn.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='checkpoints/fast.db', help='Database path')
    args = parser.parse_args()
    
    check_duplicates(args.db)
    simulate_pending_check(args.db)
