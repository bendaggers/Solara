#!/usr/bin/env python3
"""
Fast checkpoint viewer - shows just what you need.
"""

import argparse
from src.checkpoint_db import FastCheckpointManager

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    
    args = parser.parse_args()
    
    mgr = FastCheckpointManager(args.db)
    stats = mgr.get_progress_stats()
    
    print("\n📊 CHECKPOINT STATUS")
    print("=" * 40)
    print(f"Completed:  {stats['total']} configs")
    print(f"  PASSED:   {stats['passed']}")
    print(f"  REJECTED: {stats['rejected']}")
    print(f"  FAILED:   {stats['failed']}")
    print(f"DB Size:    {stats['database_size_mb']:.2f} MB")
    
    if stats['best_config']:
        print(f"\n🏆 Best EV: {stats['best_ev']:.2f} ({stats['best_config']})")

if __name__ == '__main__':
    main()