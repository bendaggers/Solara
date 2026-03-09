"""
Pure ML Diagnostic Analyzer
============================

Comprehensive analysis of experiment results:
1. Why configs PASSED
2. Why configs FAILED/REJECTED
3. Find GOLD configs (exceptional performers)
4. Statistical analysis
5. Recommendations

Usage:
    python diagnose.py
    python diagnose.py --db artifacts/pure_ml.db
    python diagnose.py --top 10
"""

import sqlite3
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import statistics

# Try colorama for colored output (optional)
try:
    from colorama import init, Fore, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        GREEN = RED = YELLOW = CYAN = MAGENTA = WHITE = BLUE = ""
        RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ConfigResult:
    """Single config result from database."""
    tp_pips: int
    sl_pips: int
    max_holding_bars: int
    config_id: str
    status: str
    ev_mean: float
    ev_std: float
    precision_mean: float
    precision_std: float
    recall_mean: float
    f1_mean: float
    auc_pr_mean: float
    total_trades: int
    selected_features: List[str]
    consensus_threshold: float
    n_features: int
    rejection_reasons: List[str]
    execution_time: float
    
    @property
    def status_normalized(self) -> str:
        """Normalize status to uppercase."""
        return self.status.upper() if self.status else 'UNKNOWN'
    
    @property
    def is_passed(self) -> bool:
        """Check if config passed."""
        return self.status_normalized == 'PASSED'
    
    @property
    def is_rejected(self) -> bool:
        """Check if config was rejected."""
        return self.status_normalized in ('REJECTED', 'FAILED')
    
    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk/reward ratio (SL/TP)."""
        return self.sl_pips / self.tp_pips if self.tp_pips > 0 else 0
    
    @property
    def required_winrate(self) -> float:
        """Win rate needed to break even."""
        return self.sl_pips / (self.tp_pips + self.sl_pips) if (self.tp_pips + self.sl_pips) > 0 else 0
    
    @property
    def edge_above_breakeven(self) -> float:
        """How much precision exceeds breakeven requirement."""
        return (self.precision_mean - self.required_winrate) * 100 if self.precision_mean else 0
    
    @property
    def precision_cv(self) -> float:
        """Coefficient of variation for precision."""
        return self.precision_std / self.precision_mean if self.precision_mean > 0 else 0
    
    @property
    def ev_cv(self) -> float:
        """Coefficient of variation for EV."""
        return abs(self.ev_std / self.ev_mean) if self.ev_mean != 0 else 0
    
    @property
    def sharpe_like_ratio(self) -> float:
        """EV / StdDev - similar to Sharpe ratio concept."""
        return self.ev_mean / self.ev_std if self.ev_std > 0 else 0
    
    @property
    def is_gold(self) -> bool:
        """Check if this is a GOLD config."""
        return (
            self.is_passed and
            self.ev_mean > 3.0 and
            self.precision_mean > 0.58 and
            self.precision_cv < 0.15 and
            self.total_trades > 500
        )
    
    @property
    def is_silver(self) -> bool:
        """Check if this is a SILVER config."""
        return (
            self.is_passed and
            self.ev_mean > 1.5 and
            self.precision_mean > 0.55 and
            self.precision_cv < 0.20 and
            not self.is_gold
        )
    
    @property 
    def is_bronze(self) -> bool:
        """Check if this is a BRONZE config."""
        return (
            self.is_passed and
            self.ev_mean > 0 and
            not self.is_gold and
            not self.is_silver
        )
    
    def short_str(self) -> str:
        return f"TP={self.tp_pips} SL={self.sl_pips} H={self.max_holding_bars}"


# =============================================================================
# DATABASE LOADING
# =============================================================================

def load_results(db_path: str) -> List[ConfigResult]:
    """Load all results from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT 
            tp_pips, sl_pips, max_holding_bars, config_id, status,
            ev_mean, ev_std, precision_mean, precision_std, recall_mean,
            f1_mean, auc_pr_mean, total_trades, selected_features,
            consensus_threshold, n_features, rejection_reasons, execution_time
        FROM completed
        ORDER BY ev_mean DESC
    """)
    
    results = []
    for row in cursor.fetchall():
        features = json.loads(row[13]) if row[13] else []
        reasons = json.loads(row[16]) if row[16] else []
        
        results.append(ConfigResult(
            tp_pips=row[0],
            sl_pips=row[1],
            max_holding_bars=row[2],
            config_id=row[3] or f"TP{row[0]}_SL{row[1]}_H{row[2]}",
            status=row[4] or 'UNKNOWN',
            ev_mean=row[5] or 0.0,
            ev_std=row[6] or 0.0,
            precision_mean=row[7] or 0.0,
            precision_std=row[8] or 0.0,
            recall_mean=row[9] or 0.0,
            f1_mean=row[10] or 0.0,
            auc_pr_mean=row[11] or 0.0,
            total_trades=row[12] or 0,
            selected_features=features,
            consensus_threshold=row[14] or 0.5,
            n_features=row[15] or 0,
            rejection_reasons=reasons,
            execution_time=row[17] or 0.0
        ))
    
    conn.close()
    return results


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def print_header(title: str):
    """Print section header."""
    width = 80
    print(f"\n{Fore.CYAN}{'='*width}")
    print(f"  {title}")
    print(f"{'='*width}{Style.RESET_ALL}")


def print_subheader(title: str):
    """Print subsection header."""
    print(f"\n{Fore.YELLOW}--- {title} ---{Style.RESET_ALL}")


def analyze_overview(results: List[ConfigResult]):
    """Print overall statistics."""
    print_header("OVERVIEW")
    
    total = len(results)
    passed = [r for r in results if r.is_passed]
    rejected = [r for r in results if r.is_rejected]
    failed = [r for r in results if r.status_normalized == 'FAILED']
    
    gold = [r for r in results if r.is_gold]
    silver = [r for r in results if r.is_silver]
    bronze = [r for r in results if r.is_bronze]
    
    print(f"""
    Total Configurations Tested: {total}
    
    {Fore.GREEN}✓ PASSED:   {len(passed):4d} ({100*len(passed)/total:.1f}%){Style.RESET_ALL}
    {Fore.RED}✗ REJECTED: {len(rejected):4d} ({100*len(rejected)/total:.1f}%){Style.RESET_ALL}
    {Fore.RED}✗ FAILED:   {len(failed):4d} ({100*len(failed)/total:.1f}%){Style.RESET_ALL}
    
    {Fore.YELLOW}🥇 GOLD:   {len(gold):4d}{Style.RESET_ALL}  (EV>3, Precision>58%, CV<15%)
    {Fore.WHITE}🥈 SILVER: {len(silver):4d}{Style.RESET_ALL}  (EV>1.5, Precision>55%, CV<20%)
    {Fore.RED}🥉 BRONZE: {len(bronze):4d}{Style.RESET_ALL}  (EV>0, Passed)
    """)
    
    if passed:
        evs = [r.ev_mean for r in passed]
        precisions = [r.precision_mean for r in passed]
        trades = [r.total_trades for r in passed]
        
        print(f"""
    PASSED Configs Statistics:
    ─────────────────────────────────────────
    Expected Value (pips):
        Best:    {max(evs):+.2f}
        Worst:   {min(evs):+.2f}
        Mean:    {statistics.mean(evs):+.2f}
        Median:  {statistics.median(evs):+.2f}
    
    Precision:
        Best:    {max(precisions)*100:.1f}%
        Worst:   {min(precisions)*100:.1f}%
        Mean:    {statistics.mean(precisions)*100:.1f}%
    
    Total Trades:
        Max:     {max(trades):,}
        Min:     {min(trades):,}
        Mean:    {statistics.mean(trades):,.0f}
        """)


def analyze_gold_configs(results: List[ConfigResult]):
    """Detailed analysis of GOLD configurations."""
    print_header("🥇 GOLD CONFIGURATIONS")
    
    gold = [r for r in results if r.is_gold]
    
    if not gold:
        print(f"\n    {Fore.YELLOW}No GOLD configurations found.{Style.RESET_ALL}")
        print("""
    GOLD criteria:
    • EV > 3.0 pips
    • Precision > 58%
    • Precision CV < 15% (stable)
    • Total trades > 500
        """)
        return
    
    print(f"\n    Found {len(gold)} GOLD configuration(s):\n")
    
    for i, r in enumerate(sorted(gold, key=lambda x: x.ev_mean, reverse=True), 1):
        print(f"""
    {Fore.YELLOW}{'─'*70}{Style.RESET_ALL}
    #{i} {Fore.GREEN}{Style.BRIGHT}{r.short_str()}{Style.RESET_ALL}
    {Fore.YELLOW}{'─'*70}{Style.RESET_ALL}
    
    Trade Parameters:
        Take Profit:     {r.tp_pips} pips
        Stop Loss:       {r.sl_pips} pips
        Max Hold:        {r.max_holding_bars} bars
        Risk:Reward:     1:{r.tp_pips/r.sl_pips:.2f}
        Threshold:       {r.consensus_threshold:.2f}
    
    Performance Metrics:
        {Fore.GREEN}Expected Value:  {r.ev_mean:+.2f} pips/trade{Style.RESET_ALL}
        EV Std:          ±{r.ev_std:.2f}
        Sharpe-like:     {r.sharpe_like_ratio:.2f}
        
        {Fore.GREEN}Precision:       {r.precision_mean*100:.1f}%{Style.RESET_ALL}
        Precision Std:   ±{r.precision_std*100:.1f}%
        Precision CV:    {r.precision_cv*100:.1f}%
        
        Recall:          {r.recall_mean*100:.1f}%
        F1 Score:        {r.f1_mean*100:.1f}%
        AUC-PR:          {r.auc_pr_mean:.3f}
    
    Edge Analysis:
        Required Win%:   {r.required_winrate*100:.1f}% (to break even)
        Your Win%:       {r.precision_mean*100:.1f}%
        {Fore.GREEN}Edge:            +{r.edge_above_breakeven:.1f}% above breakeven{Style.RESET_ALL}
    
    Volume:
        Total Trades:    {r.total_trades:,}
        Features Used:   {r.n_features}
        
    Selected Features:
        {', '.join(r.selected_features[:10])}
        {'...' if len(r.selected_features) > 10 else ''}
        """)


def analyze_silver_configs(results: List[ConfigResult], top_n: int = 5):
    """Analysis of SILVER configurations."""
    print_header("🥈 SILVER CONFIGURATIONS")
    
    silver = [r for r in results if r.is_silver]
    
    if not silver:
        print(f"\n    {Fore.YELLOW}No SILVER configurations found.{Style.RESET_ALL}")
        return
    
    print(f"\n    Found {len(silver)} SILVER configuration(s). Top {min(top_n, len(silver))}:\n")
    
    print(f"    {'Config':<20} {'EV':>8} {'Prec':>8} {'CV':>8} {'Trades':>10} {'Threshold':>10}")
    print(f"    {'─'*70}")
    
    for r in sorted(silver, key=lambda x: x.ev_mean, reverse=True)[:top_n]:
        print(f"    {r.short_str():<20} {r.ev_mean:>+7.2f} {r.precision_mean*100:>7.1f}% {r.precision_cv*100:>7.1f}% {r.total_trades:>10,} {r.consensus_threshold:>10.2f}")


def analyze_passed_configs(results: List[ConfigResult], top_n: int = 10):
    """Detailed analysis of all PASSED configurations."""
    print_header("✓ ALL PASSED CONFIGURATIONS")
    
    passed = [r for r in results if r.is_passed]
    
    if not passed:
        print(f"\n    {Fore.RED}No configurations passed acceptance criteria!{Style.RESET_ALL}")
        return
    
    # Sort by EV
    passed_sorted = sorted(passed, key=lambda x: x.ev_mean, reverse=True)
    
    print(f"\n    Showing all {len(passed)} passed configs (sorted by EV):\n")
    
    print(f"    {'#':<3} {'Config':<22} {'EV':>8} {'Prec':>7} {'Recall':>7} {'F1':>7} {'Trades':>8} {'Thresh':>7} {'R:R':>6} {'Edge':>6}")
    print(f"    {'─'*95}")
    
    for i, r in enumerate(passed_sorted, 1):
        # Color coding based on tier
        if r.is_gold:
            color = Fore.YELLOW
            tier = "🥇"
        elif r.is_silver:
            color = Fore.WHITE
            tier = "🥈"
        else:
            color = Fore.RED
            tier = "🥉"
        
        rr = f"1:{r.tp_pips/r.sl_pips:.1f}"
        
        print(f"    {color}{i:<3} {r.short_str():<22} {r.ev_mean:>+7.2f} {r.precision_mean*100:>6.1f}% {r.recall_mean*100:>6.1f}% {r.f1_mean*100:>6.1f}% {r.total_trades:>8,} {r.consensus_threshold:>7.2f} {rr:>6} {r.edge_above_breakeven:>+5.1f}%{Style.RESET_ALL} {tier}")


def analyze_rejected_configs(results: List[ConfigResult]):
    """Analysis of why configs were rejected."""
    print_header("✗ REJECTION ANALYSIS")
    
    rejected = [r for r in results if r.is_rejected]
    
    if not rejected:
        print(f"\n    {Fore.GREEN}No rejected configurations!{Style.RESET_ALL}")
        return
    
    print(f"\n    Total Rejected: {len(rejected)}")
    
    # Count rejection reasons
    reason_counts: Dict[str, int] = {}
    for r in rejected:
        for reason in r.rejection_reasons:
            # Clean up reason string
            clean_reason = reason.split('(')[0].strip()
            reason_counts[clean_reason] = reason_counts.get(clean_reason, 0) + 1
    
    print_subheader("Rejection Reasons Summary")
    print(f"\n    {'Reason':<40} {'Count':>8} {'%':>8}")
    print(f"    {'─'*60}")
    
    for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        pct = 100 * count / len(rejected)
        print(f"    {reason:<40} {count:>8} {pct:>7.1f}%")
    
    # Show some examples
    print_subheader("Sample Rejected Configs (worst performers)")
    
    # Sort by EV (worst first)
    worst = sorted(rejected, key=lambda x: x.ev_mean)[:5]
    
    print(f"\n    {'Config':<22} {'EV':>8} {'Prec':>8} {'Trades':>10} {'Reason'}")
    print(f"    {'─'*80}")
    
    for r in worst:
        reason = r.rejection_reasons[0] if r.rejection_reasons else "Unknown"
        reason_short = reason[:30] + "..." if len(reason) > 30 else reason
        print(f"    {r.short_str():<22} {r.ev_mean:>+7.2f} {r.precision_mean*100:>7.1f}% {r.total_trades:>10,} {reason_short}")


def analyze_near_misses(results: List[ConfigResult]):
    """Find configs that almost passed - might work with slight tweaks."""
    print_header("⚠️ NEAR MISSES (Almost Passed)")
    
    rejected = [r for r in results if r.is_rejected]
    
    # Find configs that are close to passing
    near_misses = []
    for r in rejected:
        # Check if close to acceptance criteria
        precision_close = r.precision_mean > 0.52  # Within 3% of 0.55
        ev_close = r.ev_mean > -1.0  # Close to positive
        has_trades = r.total_trades > 100
        
        if precision_close and ev_close and has_trades:
            near_misses.append(r)
    
    if not near_misses:
        print(f"\n    No near-miss configurations found.")
        return
    
    print(f"\n    Found {len(near_misses)} configs that almost passed:\n")
    
    # Sort by how close to passing
    near_misses.sort(key=lambda x: (x.precision_mean, x.ev_mean), reverse=True)
    
    print(f"    {'Config':<22} {'EV':>8} {'Prec':>8} {'Trades':>10} {'Issue'}")
    print(f"    {'─'*70}")
    
    for r in near_misses[:10]:
        issues = []
        if r.precision_mean < 0.55:
            issues.append(f"Prec {r.precision_mean*100:.1f}% < 55%")
        if r.ev_mean <= 0:
            issues.append(f"EV {r.ev_mean:+.2f} <= 0")
        
        issue_str = " | ".join(issues) if issues else "CV too high?"
        print(f"    {r.short_str():<22} {r.ev_mean:>+7.2f} {r.precision_mean*100:>7.1f}% {r.total_trades:>10,} {issue_str}")


def analyze_parameter_patterns(results: List[ConfigResult]):
    """Analyze which parameter values tend to work better."""
    print_header("📊 PARAMETER PATTERN ANALYSIS")
    
    passed = [r for r in results if r.is_passed]
    rejected = [r for r in results if r.is_rejected]
    
    if not results:
        print("\n    No results to analyze.")
        return
    
    # Analyze TP values
    print_subheader("Take Profit Analysis")
    tp_values = sorted(set(r.tp_pips for r in results))
    
    print(f"\n    {'TP (pips)':<12} {'Passed':>8} {'Rejected':>10} {'Pass%':>8} {'Avg EV':>10}")
    print(f"    {'─'*55}")
    
    for tp in tp_values:
        tp_passed = [r for r in passed if r.tp_pips == tp]
        tp_rejected = [r for r in rejected if r.tp_pips == tp]
        total = len(tp_passed) + len(tp_rejected)
        pass_rate = 100 * len(tp_passed) / total if total > 0 else 0
        avg_ev = statistics.mean([r.ev_mean for r in tp_passed]) if tp_passed else 0
        
        color = Fore.GREEN if pass_rate > 50 else Fore.RED if pass_rate < 20 else Fore.YELLOW
        print(f"    {tp:<12} {len(tp_passed):>8} {len(tp_rejected):>10} {color}{pass_rate:>7.1f}%{Style.RESET_ALL} {avg_ev:>+9.2f}")
    
    # Analyze SL values
    print_subheader("Stop Loss Analysis")
    sl_values = sorted(set(r.sl_pips for r in results))
    
    print(f"\n    {'SL (pips)':<12} {'Passed':>8} {'Rejected':>10} {'Pass%':>8} {'Avg EV':>10}")
    print(f"    {'─'*55}")
    
    for sl in sl_values:
        sl_passed = [r for r in passed if r.sl_pips == sl]
        sl_rejected = [r for r in rejected if r.sl_pips == sl]
        total = len(sl_passed) + len(sl_rejected)
        pass_rate = 100 * len(sl_passed) / total if total > 0 else 0
        avg_ev = statistics.mean([r.ev_mean for r in sl_passed]) if sl_passed else 0
        
        color = Fore.GREEN if pass_rate > 50 else Fore.RED if pass_rate < 20 else Fore.YELLOW
        print(f"    {sl:<12} {len(sl_passed):>8} {len(sl_rejected):>10} {color}{pass_rate:>7.1f}%{Style.RESET_ALL} {avg_ev:>+9.2f}")
    
    # Analyze Hold values
    print_subheader("Max Holding Bars Analysis")
    hold_values = sorted(set(r.max_holding_bars for r in results))
    
    print(f"\n    {'Hold (bars)':<12} {'Passed':>8} {'Rejected':>10} {'Pass%':>8} {'Avg EV':>10}")
    print(f"    {'─'*55}")
    
    for hold in hold_values:
        h_passed = [r for r in passed if r.max_holding_bars == hold]
        h_rejected = [r for r in rejected if r.max_holding_bars == hold]
        total = len(h_passed) + len(h_rejected)
        pass_rate = 100 * len(h_passed) / total if total > 0 else 0
        avg_ev = statistics.mean([r.ev_mean for r in h_passed]) if h_passed else 0
        
        color = Fore.GREEN if pass_rate > 50 else Fore.RED if pass_rate < 20 else Fore.YELLOW
        print(f"    {hold:<12} {len(h_passed):>8} {len(h_rejected):>10} {color}{pass_rate:>7.1f}%{Style.RESET_ALL} {avg_ev:>+9.2f}")
    
    # Risk/Reward Analysis
    print_subheader("Risk/Reward Ratio Analysis")
    
    print(f"\n    {'R:R Ratio':<15} {'Passed':>8} {'Rejected':>10} {'Pass%':>8} {'Avg EV':>10}")
    print(f"    {'─'*58}")
    
    # Group by R:R buckets
    rr_buckets = {
        "Favorable (R:R<1)": lambda r: r.sl_pips < r.tp_pips,
        "Even (R:R=1)": lambda r: r.sl_pips == r.tp_pips,
        "Unfavorable (R:R>1)": lambda r: r.sl_pips > r.tp_pips
    }
    
    for bucket_name, condition in rr_buckets.items():
        b_passed = [r for r in passed if condition(r)]
        b_rejected = [r for r in rejected if condition(r)]
        total = len(b_passed) + len(b_rejected)
        
        if total == 0:
            continue
            
        pass_rate = 100 * len(b_passed) / total
        avg_ev = statistics.mean([r.ev_mean for r in b_passed]) if b_passed else 0
        
        color = Fore.GREEN if pass_rate > 50 else Fore.RED if pass_rate < 20 else Fore.YELLOW
        print(f"    {bucket_name:<15} {len(b_passed):>8} {len(b_rejected):>10} {color}{pass_rate:>7.1f}%{Style.RESET_ALL} {avg_ev:>+9.2f}")


def analyze_feature_importance(results: List[ConfigResult]):
    """Analyze which features appear most often in passed configs."""
    print_header("🔧 FEATURE ANALYSIS")
    
    passed = [r for r in results if r.is_passed and r.selected_features]
    
    if not passed:
        print("\n    No passed configs with feature data.")
        return
    
    # Count feature occurrences
    feature_counts: Dict[str, int] = {}
    for r in passed:
        for f in r.selected_features:
            feature_counts[f] = feature_counts.get(f, 0) + 1
    
    print(f"\n    Features used across {len(passed)} passed configs:\n")
    
    print(f"    {'Feature':<35} {'Count':>8} {'%':>8}")
    print(f"    {'─'*55}")
    
    for feature, count in sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
        pct = 100 * count / len(passed)
        bar = "█" * int(pct / 5)
        print(f"    {feature:<35} {count:>8} {pct:>7.1f}% {Fore.CYAN}{bar}{Style.RESET_ALL}")


def generate_recommendations(results: List[ConfigResult]):
    """Generate actionable recommendations."""
    print_header("💡 RECOMMENDATIONS")
    
    passed = [r for r in results if r.is_passed]
    rejected = [r for r in results if r.is_rejected]
    gold = [r for r in results if r.is_gold]
    
    recommendations = []
    
    # Check pass rate
    if len(results) > 0:
        pass_rate = len(passed) / len(results)
        
        if pass_rate == 0:
            recommendations.append({
                'priority': 'HIGH',
                'issue': 'No configurations passed',
                'action': 'Relax acceptance criteria OR expand config space',
                'detail': 'Try min_precision: 0.52 or test more TP/SL combinations'
            })
        elif pass_rate < 0.1:
            recommendations.append({
                'priority': 'MEDIUM',
                'issue': f'Low pass rate ({pass_rate*100:.1f}%)',
                'action': 'Review acceptance criteria',
                'detail': 'Current criteria may be too strict'
            })
    
    # Check for gold configs
    if passed and not gold:
        best = max(passed, key=lambda x: x.ev_mean)
        recommendations.append({
            'priority': 'MEDIUM',
            'issue': 'No GOLD configurations',
            'action': 'Optimize around best config',
            'detail': f'Best config: {best.short_str()} with EV={best.ev_mean:+.2f}'
        })
    
    # Check R:R ratios
    unfavorable = [r for r in passed if r.sl_pips > r.tp_pips]
    if len(unfavorable) == len(passed) and passed:
        recommendations.append({
            'priority': 'HIGH',
            'issue': 'All passed configs have unfavorable R:R',
            'action': 'Test configs where TP >= SL',
            'detail': 'Risking more than potential gain is dangerous'
        })
    
    # Check EV stability
    if passed:
        ev_negative_folds = [r for r in passed if r.ev_std > abs(r.ev_mean)]
        if len(ev_negative_folds) > len(passed) * 0.5:
            recommendations.append({
                'priority': 'HIGH',
                'issue': 'High EV variance in most configs',
                'action': 'Investigate fold-by-fold performance',
                'detail': 'Some folds may be negative (recent market regime change?)'
            })
    
    # Print recommendations
    if not recommendations:
        print(f"\n    {Fore.GREEN}✓ No critical issues found!{Style.RESET_ALL}")
        if gold:
            print(f"\n    You have {len(gold)} GOLD config(s). Consider paper trading the best one.")
    else:
        for i, rec in enumerate(recommendations, 1):
            priority_color = Fore.RED if rec['priority'] == 'HIGH' else Fore.YELLOW
            print(f"""
    {priority_color}[{rec['priority']}]{Style.RESET_ALL} {rec['issue']}
    
        Action:  {rec['action']}
        Detail:  {rec['detail']}
            """)
    
    # Final verdict
    print_subheader("FINAL VERDICT")
    
    if gold:
        best_gold = max(gold, key=lambda x: x.ev_mean)
        print(f"""
    {Fore.GREEN}✓ READY FOR PAPER TRADING{Style.RESET_ALL}
    
    Recommended Config: {best_gold.short_str()}
    Expected Value:     {best_gold.ev_mean:+.2f} pips/trade
    Win Rate:           {best_gold.precision_mean*100:.1f}%
    Threshold:          {best_gold.consensus_threshold:.2f}
        """)
    elif passed:
        best = max(passed, key=lambda x: x.ev_mean)
        print(f"""
    {Fore.YELLOW}⚠️ PROCEED WITH CAUTION{Style.RESET_ALL}
    
    Best Config:    {best.short_str()}
    Expected Value: {best.ev_mean:+.2f} pips/trade
    Win Rate:       {best.precision_mean*100:.1f}%
    
    Consider:
    - Paper trade before live
    - Use smaller position size
    - Monitor recent performance closely
        """)
    else:
        print(f"""
    {Fore.RED}✗ NOT READY FOR TRADING{Style.RESET_ALL}
    
    No profitable configurations found.
    
    Next Steps:
    1. Expand config space (more TP/SL combinations)
    2. Relax acceptance criteria temporarily to analyze patterns
    3. Consider combining with Signal Filter (v3) approach
    4. Review if Pure ML is viable for this market
        """)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Pure ML Diagnostic Analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--db', '-d',
        type=str,
        default='artifacts/pure_ml.db',
        help='Path to checkpoint database'
    )
    
    parser.add_argument(
        '--top', '-t',
        type=int,
        default=10,
        help='Number of top configs to show in detailed views'
    )
    
    args = parser.parse_args()
    
    # Check if database exists
    if not Path(args.db).exists():
        print(f"{Fore.RED}Error: Database not found: {args.db}{Style.RESET_ALL}")
        print(f"\nRun the pipeline first to generate results.")
        return
    
    # Load results
    print(f"\n{Fore.CYAN}Loading results from: {args.db}{Style.RESET_ALL}")
    results = load_results(args.db)
    
    if not results:
        print(f"{Fore.RED}No results found in database.{Style.RESET_ALL}")
        return
    
    print(f"Loaded {len(results)} configuration results.\n")
    
    # Run all analyses
    analyze_overview(results)
    analyze_gold_configs(results)
    analyze_silver_configs(results, top_n=args.top)
    analyze_passed_configs(results, top_n=args.top)
    analyze_rejected_configs(results)
    analyze_near_misses(results)
    analyze_parameter_patterns(results)
    analyze_feature_importance(results)
    generate_recommendations(results)
    
    print(f"\n{'='*80}")
    print(f"  Analysis Complete")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
