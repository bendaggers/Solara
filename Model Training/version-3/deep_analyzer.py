#!/usr/bin/env python3
"""
Deep Analyzer - Find hidden gems in rejected configs.
Analyzes ALL configs (passed + rejected) to find potentially good ones.
"""

import sqlite3
import json
import argparse
import pandas as pd
from pathlib import Path


def load_all_configs(db_path: str) -> pd.DataFrame:
    """Load all configs into DataFrame."""
    conn = sqlite3.connect(db_path)
    
    df = pd.read_sql_query("""
        SELECT 
            config_id, status, bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars,
            ev_mean, ev_std, precision_mean, precision_std, recall_mean, f1_mean, auc_pr_mean,
            total_trades, consensus_threshold, n_features, selected_features, rejection_reasons
        FROM completed
    """, conn)
    
    conn.close()
    
    # Calculate derived metrics
    if len(df) > 0 and 'tp_pips' in df.columns and 'sl_pips' in df.columns:
        df['trades_per_fold'] = df['total_trades'] / 5  # Assuming 5 folds
        df['breakeven_precision'] = df['sl_pips'] / (df['sl_pips'] + df['tp_pips'])
        df['edge_over_breakeven'] = df['precision_mean'] - df['breakeven_precision']
        df['risk_reward'] = df['tp_pips'] / df['sl_pips']
    
    return df


def analyze_high_ev_rejected(df: pd.DataFrame, min_ev: float = 5.0) -> pd.DataFrame:
    """Find rejected configs with high EV."""
    rejected = df[df['status'] == 'REJECTED'].copy()
    high_ev = rejected[rejected['ev_mean'] >= min_ev].sort_values('ev_mean', ascending=False)
    return high_ev


def analyze_high_precision_rejected(df: pd.DataFrame, min_precision: float = 0.55) -> pd.DataFrame:
    """Find rejected configs with high precision."""
    rejected = df[df['status'] == 'REJECTED'].copy()
    high_prec = rejected[rejected['precision_mean'] >= min_precision].sort_values('precision_mean', ascending=False)
    return high_prec


def analyze_good_but_low_trades(df: pd.DataFrame, min_ev: float = 3.0, min_precision: float = 0.50) -> pd.DataFrame:
    """Find configs that are good but rejected only for low trades."""
    rejected = df[df['status'] == 'REJECTED'].copy()
    
    good_metrics = rejected[
        (rejected['ev_mean'] >= min_ev) & 
        (rejected['precision_mean'] >= min_precision)
    ].copy()
    
    # Check if only rejected for trades
    def only_trades_rejection(reasons_json):
        if pd.isna(reasons_json):
            return False
        try:
            reasons = json.loads(reasons_json)
            # Filter out warnings
            hard_rejections = [r for r in reasons if not r.startswith('warning')]
            # Check if only trades-related
            return all('trades' in r.lower() for r in hard_rejections)
        except:
            return False
    
    good_metrics['only_trades_issue'] = good_metrics['rejection_reasons'].apply(only_trades_rejection)
    
    return good_metrics.sort_values('ev_mean', ascending=False)


def analyze_near_miss(df: pd.DataFrame) -> pd.DataFrame:
    """Find configs that almost passed (1 rejection reason only)."""
    rejected = df[df['status'] == 'REJECTED'].copy()
    
    def count_hard_rejections(reasons_json):
        if pd.isna(reasons_json):
            return 0
        try:
            reasons = json.loads(reasons_json)
            return len([r for r in reasons if not r.startswith('warning')])
        except:
            return 0
    
    rejected['n_rejections'] = rejected['rejection_reasons'].apply(count_hard_rejections)
    near_miss = rejected[rejected['n_rejections'] == 1].sort_values('ev_mean', ascending=False)
    
    return near_miss


def analyze_parameter_patterns(df: pd.DataFrame) -> dict:
    """Analyze which parameter ranges perform best."""
    passed = df[df['status'] == 'PASSED']
    rejected = df[df['status'] == 'REJECTED']
    
    patterns = {}
    
    # BB analysis
    if len(passed) > 0:
        patterns['passed_bb_range'] = {
            'min': passed['bb_threshold'].min(),
            'max': passed['bb_threshold'].max(),
            'mean': passed['bb_threshold'].mean()
        }
    
    if len(rejected) > 0:
        high_ev_rejected = rejected[rejected['ev_mean'] > rejected['ev_mean'].median()]
        patterns['high_ev_rejected_bb_range'] = {
            'min': high_ev_rejected['bb_threshold'].min(),
            'max': high_ev_rejected['bb_threshold'].max(),
            'mean': high_ev_rejected['bb_threshold'].mean()
        }
    
    # RSI analysis
    if len(passed) > 0:
        patterns['passed_rsi_range'] = {
            'min': passed['rsi_threshold'].min(),
            'max': passed['rsi_threshold'].max(),
            'mean': passed['rsi_threshold'].mean()
        }
    
    # TP analysis
    if len(passed) > 0:
        patterns['passed_tp_range'] = {
            'min': passed['tp_pips'].min(),
            'max': passed['tp_pips'].max(),
            'mean': passed['tp_pips'].mean()
        }
    
    return patterns


def find_golden_rejects(df: pd.DataFrame) -> pd.DataFrame:
    """
    Find the GOLDEN configs - rejected but potentially better than passed ones.
    
    Criteria:
    - EV > best passed EV OR
    - Precision > best passed precision
    - With reasonable trades (> 20 total)
    """
    passed = df[df['status'] == 'PASSED']
    rejected = df[df['status'] == 'REJECTED']
    
    if len(passed) == 0:
        # No passed configs - find best rejected
        return rejected.sort_values('ev_mean', ascending=False).head(20)
    
    best_passed_ev = passed['ev_mean'].max()
    best_passed_precision = passed['precision_mean'].max()
    
    golden = rejected[
        ((rejected['ev_mean'] > best_passed_ev) | 
         (rejected['precision_mean'] > best_passed_precision)) &
        (rejected['total_trades'] >= 20)
    ].sort_values('ev_mean', ascending=False)
    
    return golden


def print_config_table(df: pd.DataFrame, title: str, max_rows: int = 15):
    """Print formatted config table."""
    if len(df) == 0:
        print(f"\n{title}")
        print("="*100)
        print("No configs found.")
        return
    
    print(f"\n{title}")
    print("="*100)
    print(f"{'#':<3} | {'BB':>5} | {'RSI':>3} | {'TP':>3} | {'SL':>3} | {'EV':>7} | {'Prec':>5} | {'Trades':>6} | {'Status':<8} | Rejection Reasons")
    print("-"*100)
    
    for i, (_, row) in enumerate(df.head(max_rows).iterrows(), 1):
        status = row.get('status', 'N/A')
        reasons = row.get('rejection_reasons', '')
        if pd.notna(reasons) and reasons:
            try:
                reasons_list = json.loads(reasons)
                # Shorten reasons
                short_reasons = [r.split('(')[0].strip()[:20] for r in reasons_list if not r.startswith('warning')]
                reasons_str = ', '.join(short_reasons[:2])
                if len(short_reasons) > 2:
                    reasons_str += '...'
            except:
                reasons_str = str(reasons)[:40]
        else:
            reasons_str = '-'
        
        bb = row.get('bb_threshold', 0) or 0
        rsi = row.get('rsi_threshold', 0) or 0
        tp = row.get('tp_pips', 0) or 0
        sl = row.get('sl_pips', 0) or 0
        ev = row.get('ev_mean', 0) or 0
        prec = row.get('precision_mean', 0) or 0
        trades = row.get('total_trades', 0) or 0
        
        print(f"{i:<3} | {bb:>5.2f} | {rsi:>3.0f} | {tp:>3.0f} | {sl:>3.0f} | {ev:>+7.2f} | {prec:>5.3f} | {trades:>6.0f} | {status:<8} | {reasons_str}")


def print_summary(df: pd.DataFrame):
    """Print overall summary."""
    total = len(df)
    passed = len(df[df['status'] == 'PASSED'])
    rejected = len(df[df['status'] == 'REJECTED'])
    failed = len(df[df['status'] == 'FAILED'])
    
    print("\n" + "="*100)
    print("OVERALL SUMMARY")
    print("="*100)
    print(f"Total configs:  {total}")
    print(f"Passed:         {passed} ({100*passed/total:.1f}%)")
    print(f"Rejected:       {rejected} ({100*rejected/total:.1f}%)")
    print(f"Failed:         {failed} ({100*failed/total:.1f}%)")
    
    if passed > 0:
        best_passed = df[df['status'] == 'PASSED'].sort_values('ev_mean', ascending=False).iloc[0]
        print(f"\nBest PASSED:    EV={best_passed['ev_mean']:.2f}, Precision={best_passed['precision_mean']:.3f}")
    
    if rejected > 0:
        best_rejected = df[df['status'] == 'REJECTED'].sort_values('ev_mean', ascending=False).iloc[0]
        print(f"Best REJECTED:  EV={best_rejected['ev_mean']:.2f}, Precision={best_rejected['precision_mean']:.3f}")


def main():
    parser = argparse.ArgumentParser(description="Deep analysis of checkpoint database")
    parser.add_argument('--db', required=True, help="Path to checkpoint database")
    parser.add_argument('--export', type=str, help="Export all data to CSV")
    parser.add_argument('--min-ev', type=float, default=5.0, help="Minimum EV for high-EV analysis")
    parser.add_argument('--min-precision', type=float, default=0.50, help="Minimum precision for analysis")
    
    args = parser.parse_args()
    
    # Load data
    print(f"Loading data from {args.db}...")
    df = load_all_configs(args.db)
    print(f"Loaded {len(df)} configs.")
    
    # Print summary
    print_summary(df)
    
    # Analysis 1: All passed configs
    passed = df[df['status'] == 'PASSED'].sort_values('ev_mean', ascending=False)
    print_config_table(passed, "ALL PASSED CONFIGS")
    
    # Analysis 2: Golden rejects (better than passed!)
    golden = find_golden_rejects(df)
    print_config_table(golden, "🏆 GOLDEN REJECTS (Better than passed configs!)")
    
    # Analysis 3: High EV rejected
    high_ev = analyze_high_ev_rejected(df, min_ev=args.min_ev)
    print_config_table(high_ev, f"HIGH EV REJECTED (EV >= {args.min_ev})")
    
    # Analysis 4: Near misses (only 1 rejection reason)
    near_miss = analyze_near_miss(df)
    print_config_table(near_miss, "NEAR MISSES (Only 1 rejection reason)")
    
    # Analysis 5: Good but low trades
    good_low_trades = analyze_good_but_low_trades(df, min_ev=3.0, min_precision=0.50)
    if 'only_trades_issue' in good_low_trades.columns:
        only_trades = good_low_trades[good_low_trades['only_trades_issue'] == True]
        print_config_table(only_trades, "GOOD CONFIGS REJECTED ONLY FOR LOW TRADES")
    
    # Parameter patterns
    print("\n" + "="*100)
    print("PARAMETER PATTERNS")
    print("="*100)
    patterns = analyze_parameter_patterns(df)
    for key, value in patterns.items():
        print(f"{key}: {value}")
    
    # Recommendations
    print("\n" + "="*100)
    print("RECOMMENDATIONS")
    print("="*100)
    
    if len(golden) > 0:
        print("⚠️  You have GOLDEN REJECTS - configs better than your passed ones!")
        print("    Consider relaxing acceptance criteria:")
        
        # Check what's causing rejections
        all_reasons = []
        for reasons_json in golden['rejection_reasons'].dropna():
            try:
                reasons = json.loads(reasons_json)
                all_reasons.extend([r.split('(')[0].strip() for r in reasons if not r.startswith('warning')])
            except:
                pass
        
        from collections import Counter
        reason_counts = Counter(all_reasons)
        print(f"\n    Top rejection reasons in golden configs:")
        for reason, count in reason_counts.most_common(5):
            print(f"      - {reason}: {count}")
    
    # Export if requested
    if args.export:
        df.to_csv(args.export, index=False)
        print(f"\nExported all data to: {args.export}")
    
    print()


if __name__ == '__main__':
    main()
