#!/usr/bin/env python3
"""
DEEP ANALYZER v2.0 - Comprehensive Quant Analysis Tool

This tool performs institutional-grade analysis on ML model training results.
Designed for senior quants and ML engineers to make production deployment decisions.

Features:
- Statistical significance testing
- Regime analysis
- Risk metrics (Sharpe proxy, max drawdown estimates)
- Parameter sensitivity analysis
- Actionable recommendations with specific thresholds
- Production readiness scoring

Author: Senior Quant Trading Desk
"""

import sqlite3
import json
import argparse
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')


# =============================================================================
# CONSTANTS & THRESHOLDS
# =============================================================================

PRODUCTION_THRESHOLDS = {
    'min_precision': 0.55,
    'min_ev': 5.0,
    'min_trades': 50,
    'min_trades_per_fold': 10,
    'max_precision_cv': 0.30,
    'max_ev_cv': 0.50,
    'min_sharpe_proxy': 0.5,
    'min_profit_factor': 1.3,
}

RISK_PARAMS = {
    'max_consecutive_losses': 8,
    'max_drawdown_pct': 20,
    'confidence_level': 0.95,
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ConfigResult:
    bb: float
    rsi: int
    tp: int
    sl: int
    hold: int
    ev: float
    ev_std: float
    precision: float
    precision_std: float
    recall: float
    f1: float
    auc_pr: float
    trades: int
    threshold: float
    n_features: int
    features: List[str]
    status: str
    rejection_reasons: List[str]
    execution_time: float
    
    @property
    def precision_cv(self) -> float:
        if self.precision and self.precision > 0 and self.precision_std:
            return self.precision_std / self.precision
        return 0
    
    @property
    def ev_cv(self) -> float:
        if self.ev and self.ev > 0 and self.ev_std:
            return self.ev_std / self.ev
        return 0
    
    @property
    def profit_factor(self) -> float:
        if self.precision and self.tp and self.sl:
            wins = self.precision * self.tp
            losses = (1 - self.precision) * self.sl
            return wins / losses if losses > 0 else 0
        return 0
    
    @property
    def sharpe_proxy(self) -> float:
        if self.ev and self.ev_std and self.ev_std > 0:
            return self.ev / self.ev_std
        return 0
    
    @property
    def expected_max_drawdown(self) -> float:
        if self.precision and self.sl and self.precision > 0:
            loss_prob = 1 - self.precision
            if loss_prob >= 1:
                return 10 * self.sl
            max_streak = min(int(np.log(0.05) / np.log(loss_prob)) if loss_prob > 0 else 10, 15)
            return max_streak * self.sl
        return 0
    
    @property 
    def production_score(self) -> float:
        score = 0
        if self.precision >= 0.60: score += 25
        elif self.precision >= 0.55: score += 20
        elif self.precision >= 0.50: score += 10
        
        if self.ev >= 15: score += 25
        elif self.ev >= 10: score += 20
        elif self.ev >= 5: score += 15
        elif self.ev > 0: score += 5
        
        if self.precision_cv <= 0.15: score += 25
        elif self.precision_cv <= 0.25: score += 20
        elif self.precision_cv <= 0.35: score += 10
        
        if self.trades >= 100: score += 25
        elif self.trades >= 50: score += 20
        elif self.trades >= 30: score += 10
        
        return score


# =============================================================================
# DATA LOADING
# =============================================================================

def load_results(db_path: str) -> List[ConfigResult]:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT 
            bb_threshold, rsi_threshold, tp_pips, sl_pips, max_holding_bars,
            ev_mean, ev_std, precision_mean, precision_std, recall_mean, f1_mean, auc_pr_mean,
            total_trades, consensus_threshold, n_features, selected_features,
            status, rejection_reasons, execution_time
        FROM completed WHERE bb_threshold IS NOT NULL ORDER BY ev_mean DESC
    """)
    
    results = []
    for row in cursor.fetchall():
        features = json.loads(row[15]) if row[15] else []
        reasons = json.loads(row[17]) if row[17] else []
        results.append(ConfigResult(
            bb=row[0], rsi=row[1], tp=row[2], sl=row[3], hold=row[4],
            ev=row[5] or 0, ev_std=row[6] or 0, precision=row[7] or 0,
            precision_std=row[8] or 0, recall=row[9] or 0, f1=row[10] or 0,
            auc_pr=row[11] or 0, trades=row[12] or 0, threshold=row[13] or 0.5,
            n_features=row[14] or 0, features=features, status=row[16] or 'UNKNOWN',
            rejection_reasons=reasons, execution_time=row[18] or 0
        ))
    conn.close()
    return results


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def analyze_parameter_sensitivity(results: List[ConfigResult]) -> Dict:
    analysis = {'bb': defaultdict(list), 'rsi': defaultdict(list), 'tp': defaultdict(list)}
    
    for r in results:
        if r.ev is not None and r.ev > -100:
            analysis['bb'][r.bb].append(r)
            analysis['rsi'][r.rsi].append(r)
            analysis['tp'][r.tp].append(r)
    
    sensitivity = {}
    for param in ['bb', 'rsi', 'tp']:
        param_data = []
        for value, configs in sorted(analysis[param].items()):
            evs = [c.ev for c in configs if c.ev is not None]
            precisions = [c.precision for c in configs if c.precision is not None]
            passed = sum(1 for c in configs if c.status == 'PASSED')
            if evs:
                param_data.append({
                    'value': value, 'count': len(configs), 'passed': passed,
                    'pass_rate': passed / len(configs) * 100,
                    'ev_mean': np.mean(evs), 'ev_std': np.std(evs), 'ev_max': max(evs),
                    'precision_mean': np.mean(precisions) if precisions else 0,
                    'precision_max': max(precisions) if precisions else 0,
                })
        sensitivity[param] = param_data
    return sensitivity


def analyze_rejection_reasons(results: List[ConfigResult]) -> Dict:
    reasons_count = defaultdict(int)
    reasons_by_ev = defaultdict(list)
    reasons_combinations = defaultdict(int)
    
    rejected = [r for r in results if r.status == 'REJECTED']
    for r in rejected:
        for reason in r.rejection_reasons:
            clean_reason = reason.split('(')[0].strip()
            reasons_count[clean_reason] += 1
            reasons_by_ev[clean_reason].append(r.ev)
        combo = tuple(sorted([rr.split('(')[0].strip() for rr in r.rejection_reasons]))
        reasons_combinations[combo] += 1
    
    reason_stats = {}
    for reason, evs in reasons_by_ev.items():
        reason_stats[reason] = {
            'count': reasons_count[reason],
            'pct': reasons_count[reason] / len(rejected) * 100 if rejected else 0,
            'avg_ev_lost': np.mean(evs) if evs else 0,
            'max_ev_lost': max(evs) if evs else 0,
        }
    
    return {'by_reason': reason_stats, 'combinations': dict(reasons_combinations), 'total_rejected': len(rejected)}


def analyze_feature_importance(results: List[ConfigResult]) -> Dict:
    passed = [r for r in results if r.status == 'PASSED']
    high_ev = [r for r in results if r.ev and r.ev > 5]
    
    feature_counts_passed = defaultdict(int)
    feature_counts_high_ev = defaultdict(int)
    
    for r in passed:
        for f in r.features:
            feature_counts_passed[f] += 1
    for r in high_ev:
        for f in r.features:
            feature_counts_high_ev[f] += 1
    
    return {
        'passed_configs': dict(sorted(feature_counts_passed.items(), key=lambda x: -x[1])[:20]),
        'high_ev_configs': dict(sorted(feature_counts_high_ev.items(), key=lambda x: -x[1])[:20]),
        'n_passed': len(passed), 'n_high_ev': len(high_ev)
    }


def calculate_statistical_significance(results: List[ConfigResult]) -> Dict:
    passed = [r for r in results if r.status == 'PASSED']
    if not passed:
        return {'significant': False, 'reason': 'No passed configs'}
    
    significant_configs = []
    for r in passed:
        if r.ev and r.ev_std and r.trades:
            se = r.ev_std / np.sqrt(r.trades) if r.trades > 0 else r.ev_std
            t_stat = r.ev / se if se > 0 else 0
            t_critical = 1.96
            is_significant = t_stat > t_critical
            p_value_approx = 2 * (1 - min(0.9999, 0.5 + 0.5 * np.tanh(t_stat / 2)))
            significant_configs.append({
                'config': r, 't_stat': t_stat, 'p_value': p_value_approx,
                'significant': is_significant, 'confidence': min(99, max(50, 50 + t_stat * 10))
            })
    
    return {
        'configs': significant_configs,
        'n_significant': sum(1 for c in significant_configs if c['significant']),
        'n_total': len(significant_configs)
    }


def get_rejection_fix(reason: str) -> str:
    fixes = {
        'precision < 0.45': 'KEEP STRICT - This is a safety threshold. Consider: different features, tighter filters.',
        'precision_cv > 0.3': 'CONSIDER RELAXING to 0.35. Means precision varies across regimes. Add regime filtering.',
        'trades_per_fold < 10': 'CONSIDER RELAXING to 8. Or widen BB/RSI range for more signals.',
        'EV <= 1.0': 'EV too low. Optimize TP/SL ratio or improve feature selection.',
        'insufficient_data_after_filter': 'Filter too strict. Widen BB/RSI range.',
        'no_valid_folds': 'All folds failed. Check data quality or relax requirements.',
    }
    return fixes.get(reason, 'Review this criterion.')


def generate_recommendations(results, sensitivity, rejection_analysis, significance) -> List[Dict]:
    recommendations = []
    passed = [r for r in results if r.status == 'PASSED']
    rejected = [r for r in results if r.status == 'REJECTED']
    
    # 1. Production Readiness
    if passed:
        best = max(passed, key=lambda x: x.production_score)
        if best.production_score >= 80:
            recommendations.append({
                'priority': 'HIGH', 'category': 'DEPLOYMENT',
                'title': '🚀 PRODUCTION READY CONFIG FOUND!',
                'description': f'BB={best.bb}, RSI={best.rsi}, TP={best.tp} scores {best.production_score}/100',
                'action': 'Paper trade 2 weeks → Deploy with conservative sizing',
                'config': best
            })
        elif best.production_score >= 60:
            gap_analysis = []
            if best.precision < 0.55: gap_analysis.append(f"Precision {best.precision:.1%} < 55%")
            if best.precision_cv > 0.30: gap_analysis.append(f"Precision CV {best.precision_cv:.2f} > 0.30")
            if best.trades < 50: gap_analysis.append(f"Trades {best.trades} < 50")
            recommendations.append({
                'priority': 'MEDIUM', 'category': 'DEPLOYMENT',
                'title': '⚠️ NEAR PRODUCTION READY',
                'description': f'Score {best.production_score}/100. Gaps: {", ".join(gap_analysis)}',
                'action': 'Fix gaps before deployment'
            })
        else:
            recommendations.append({
                'priority': 'LOW', 'category': 'DEPLOYMENT',
                'title': '❌ NOT PRODUCTION READY',
                'description': f'Best score only {best.production_score}/100',
                'action': 'Continue parameter exploration'
            })
    
    # 2. Golden Rejects
    best_passed_ev = max(p.ev for p in passed) if passed else 0
    golden = [r for r in rejected if r.ev and r.ev > best_passed_ev and r.precision and r.precision > 0.40]
    if golden:
        best_golden = max(golden, key=lambda x: x.ev)
        reason_counts = defaultdict(int)
        for g in golden:
            for r in g.rejection_reasons:
                reason_counts[r.split('(')[0].strip()] += 1
        top_reason = max(reason_counts.items(), key=lambda x: x[1])
        
        recommendations.append({
            'priority': 'HIGH', 'category': 'CRITERIA',
            'title': f'💎 {len(golden)} GOLDEN REJECTS FOUND!',
            'description': f'Best: BB={best_golden.bb}, RSI={best_golden.rsi}, TP={best_golden.tp}, EV={best_golden.ev:.2f}',
            'detail': f'Top rejection: {top_reason[0]} ({top_reason[1]} configs)',
            'action': get_rejection_fix(top_reason[0])
        })
    
    # 3. Parameter Focus
    for param in ['bb', 'rsi']:
        data = sensitivity.get(param, [])
        if data:
            best_param = max(data, key=lambda x: x['pass_rate'])
            if best_param['pass_rate'] > 0:
                recommendations.append({
                    'priority': 'MEDIUM', 'category': 'PARAMETERS',
                    'title': f'🎯 OPTIMAL {param.upper()} = {best_param["value"]}',
                    'description': f'Pass rate {best_param["pass_rate"]:.1f}%, Avg EV {best_param["ev_mean"]:.2f}',
                    'action': f'Focus exploration around {param.upper()}={best_param["value"]} ± {"0.02" if param == "bb" else "3"}'
                })
    
    # 4. Rejection Analysis
    if rejection_analysis.get('by_reason'):
        top_reasons = sorted(rejection_analysis['by_reason'].items(), key=lambda x: -x[1]['count'])[:3]
        for reason, stats in top_reasons:
            if stats['max_ev_lost'] > 5:
                recommendations.append({
                    'priority': 'MEDIUM', 'category': 'CRITERIA',
                    'title': f'📊 {reason}',
                    'description': f'{stats["count"]} configs rejected, max EV lost: {stats["max_ev_lost"]:.2f}',
                    'action': get_rejection_fix(reason)
                })
    
    # 5. Statistical Significance
    n_sig = significance.get('n_significant', 0)
    n_total = significance.get('n_total', 0)
    if n_sig > 0:
        recommendations.append({
            'priority': 'HIGH', 'category': 'VALIDATION',
            'title': f'📈 {n_sig}/{n_total} STATISTICALLY SIGNIFICANT',
            'description': 'These configs have validated edge at 95% confidence',
            'action': 'Prioritize these for deployment'
        })
    elif n_total > 0:
        recommendations.append({
            'priority': 'MEDIUM', 'category': 'VALIDATION',
            'title': '⚠️ NO STATISTICAL SIGNIFICANCE',
            'description': 'Need more trades or higher precision for significance',
            'action': 'Increase trade volume or improve precision'
        })
    
    return recommendations


# =============================================================================
# REPORT GENERATION
# =============================================================================

def print_header(text: str, char: str = "=", width: int = 100):
    print(f"\n{char * width}")
    print(f" {text}")
    print(f"{char * width}")


def print_config_table(configs: List[ConfigResult], limit: int = 15):
    print(f"\n{'#':<3} | {'BB':>6} | {'RSI':>3} | {'TP':>3} | {'EV':>8} | {'Prec':>6} | {'CV':>5} | {'PF':>5} | {'Trades':>6} | {'Score':>5} | Reasons")
    print("-" * 100)
    for i, r in enumerate(configs[:limit], 1):
        ev_str = f"+{r.ev:.2f}" if r.ev > 0 else f"{r.ev:.2f}"
        reasons_str = ', '.join(r.rejection_reasons[:2]) if r.rejection_reasons else '-'
        if len(reasons_str) > 30: reasons_str = reasons_str[:27] + '...'
        print(f"{i:<3} | {r.bb:>6.2f} | {r.rsi:>3} | {r.tp:>3} | {ev_str:>8} | {r.precision:>5.1%} | {r.precision_cv:>5.2f} | {r.profit_factor:>5.2f} | {r.trades:>6} | {r.production_score:>5.0f} | {reasons_str}")


def print_risk_analysis(config: ConfigResult):
    print(f"\n  {'Metric':<25} {'Value':>15} {'Assessment':>15}")
    print("  " + "-" * 60)
    
    # Precision
    prec_assess = "✅ Good" if config.precision >= 0.55 else "⚠️ Marginal" if config.precision >= 0.50 else "❌ Low"
    print(f"  {'Precision':<25} {config.precision:>14.1%} {prec_assess:>15}")
    
    # EV
    ev_assess = "✅ Good" if config.ev >= 10 else "⚠️ OK" if config.ev >= 5 else "❌ Low"
    print(f"  {'Expected Value':<25} {config.ev:>+14.2f} {ev_assess:>15}")
    
    # Profit Factor
    pf_assess = "✅ Good" if config.profit_factor >= 1.5 else "⚠️ OK" if config.profit_factor >= 1.2 else "❌ Low"
    print(f"  {'Profit Factor':<25} {config.profit_factor:>14.2f} {pf_assess:>15}")
    
    # Precision CV
    cv_assess = "✅ Stable" if config.precision_cv <= 0.20 else "⚠️ Variable" if config.precision_cv <= 0.35 else "❌ Unstable"
    print(f"  {'Precision CV':<25} {config.precision_cv:>14.2f} {cv_assess:>15}")
    
    # Trades
    trades_assess = "✅ Good" if config.trades >= 100 else "⚠️ OK" if config.trades >= 50 else "❌ Low"
    print(f"  {'Total Trades':<25} {config.trades:>14} {trades_assess:>15}")
    
    # Max Drawdown
    dd_assess = "✅ OK" if config.expected_max_drawdown <= 150 else "⚠️ Watch" if config.expected_max_drawdown <= 250 else "❌ High"
    print(f"  {'Est. Max Drawdown':<25} {config.expected_max_drawdown:>12.0f}p {dd_assess:>15}")
    
    # Production Score
    score_assess = "✅ Ready" if config.production_score >= 80 else "⚠️ Close" if config.production_score >= 60 else "❌ Not Ready"
    print(f"  {'Production Score':<25} {config.production_score:>13.0f}% {score_assess:>15}")
    
    # Simulation
    print(f"\n  TRADE SIMULATION (per 100 trades):")
    wins = int(config.precision * 100)
    losses = 100 - wins
    gross_profit = wins * config.tp
    gross_loss = losses * config.sl
    net = gross_profit - gross_loss
    print(f"    Wins:   {wins} × {config.tp}p = +{gross_profit}p")
    print(f"    Losses: {losses} × {config.sl}p = -{gross_loss}p")
    print(f"    Net:    {'+' if net > 0 else ''}{net}p (EV = {net/100:.2f}p/trade)")


def print_recommendations(recommendations: List[Dict]):
    priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'LOW'), 3))
    
    for rec in recommendations:
        priority = rec.get('priority', 'MEDIUM')
        emoji = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(priority, '⚪')
        print(f"\n{emoji} [{priority}] {rec.get('title', '')}")
        print(f"   {rec.get('description', '')}")
        if 'detail' in rec:
            print(f"   Detail: {rec['detail']}")
        if 'action' in rec:
            print(f"   ➡️  {rec['action']}")


def generate_report(db_path: str):
    print_header("DEEP QUANTITATIVE ANALYSIS REPORT v2.0", "=", 100)
    print(f" Database: {db_path}")
    print(f" Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = load_results(db_path)
    if not results:
        print("\n❌ No results found!")
        return
    
    passed = [r for r in results if r.status == 'PASSED']
    rejected = [r for r in results if r.status == 'REJECTED']
    
    # EXECUTIVE SUMMARY
    print_header("1. EXECUTIVE SUMMARY")
    print(f"\n  📊 Total Configs:  {len(results):,}")
    print(f"  ✅ Passed:         {len(passed):,} ({len(passed)/len(results)*100:.1f}%)")
    print(f"  ❌ Rejected:       {len(rejected):,} ({len(rejected)/len(results)*100:.1f}%)")
    
    if passed:
        best = max(passed, key=lambda x: x.production_score)
        verdict = "✅ PRODUCTION READY" if best.production_score >= 80 else "⚠️ NEEDS WORK" if best.production_score >= 60 else "❌ NOT READY"
        print(f"\n  🏆 BEST CONFIG: BB={best.bb}, RSI={best.rsi}, TP={best.tp}")
        print(f"     EV={best.ev:.2f}, Precision={best.precision:.1%}, Score={best.production_score}/100")
        print(f"\n  📋 VERDICT: {verdict}")
    
    # PASSED CONFIGS
    print_header("2. PASSED CONFIGURATIONS")
    if passed:
        passed_sorted = sorted(passed, key=lambda x: -x.production_score)
        print_config_table(passed_sorted, limit=len(passed_sorted))
    else:
        print("\n  No passed configurations.")
    
    # GOLDEN REJECTS
    print_header("3. GOLDEN REJECTS (Better EV than Passed!)")
    best_passed_ev = max(p.ev for p in passed) if passed else 0
    golden = sorted([r for r in rejected if r.ev and r.ev > best_passed_ev and r.precision and r.precision > 0.40], key=lambda x: -x.ev)[:10]
    if golden:
        print(f"\n  ⚠️ {len(golden)} configs have HIGHER EV than passed!")
        print_config_table(golden)
    else:
        print("\n  ✅ No golden rejects.")
    
    # PARAMETER SENSITIVITY
    print_header("4. PARAMETER SENSITIVITY")
    sensitivity = analyze_parameter_sensitivity(results)
    for param, label in [('bb', 'BB Threshold'), ('rsi', 'RSI Threshold'), ('tp', 'Take Profit')]:
        data = sensitivity.get(param, [])
        if data:
            print(f"\n  {label}:")
            print(f"  {'Value':<8} | {'Count':>6} | {'Passed':>6} | {'PassRate':>8} | {'AvgEV':>8} | {'MaxEV':>8}")
            print("  " + "-" * 60)
            for d in sorted(data, key=lambda x: -x['pass_rate'])[:8]:
                print(f"  {d['value']:<8} | {d['count']:>6} | {d['passed']:>6} | {d['pass_rate']:>7.1f}% | {d['ev_mean']:>+8.2f} | {d['ev_max']:>+8.2f}")
    
    # REJECTION ANALYSIS
    print_header("5. REJECTION REASON ANALYSIS")
    rejection_analysis = analyze_rejection_reasons(results)
    print(f"\n  {'Reason':<35} | {'Count':>6} | {'%':>6} | {'Avg EV Lost':>12}")
    print("  " + "-" * 70)
    for reason, stats in sorted(rejection_analysis['by_reason'].items(), key=lambda x: -x[1]['count']):
        print(f"  {reason:<35} | {stats['count']:>6} | {stats['pct']:>5.1f}% | {stats['avg_ev_lost']:>+12.2f}")
    
    # FEATURE IMPORTANCE
    print_header("6. FEATURE IMPORTANCE")
    feature_analysis = analyze_feature_importance(results)
    print(f"\n  Top features in PASSED configs ({feature_analysis['n_passed']}):")
    for i, (f, c) in enumerate(list(feature_analysis['passed_configs'].items())[:8], 1):
        print(f"    {i}. {f}: {c}")
    print(f"\n  Top features in HIGH-EV configs ({feature_analysis['n_high_ev']}):")
    for i, (f, c) in enumerate(list(feature_analysis['high_ev_configs'].items())[:8], 1):
        print(f"    {i}. {f}: {c}")
    
    # STATISTICAL SIGNIFICANCE
    print_header("7. STATISTICAL SIGNIFICANCE")
    significance = calculate_statistical_significance(results)
    if significance.get('configs'):
        print(f"\n  {'Config':<25} | {'t-stat':>8} | {'p-value':>8} | {'Conf':>6} | {'Sig?'}")
        print("  " + "-" * 65)
        for c in sorted(significance['configs'], key=lambda x: -x['t_stat'])[:10]:
            cfg = c['config']
            sig_str = "✅" if c['significant'] else "❌"
            print(f"  BB={cfg.bb:.2f} RSI={cfg.rsi} TP={cfg.tp:<3} | {c['t_stat']:>8.2f} | {c['p_value']:>8.4f} | {c['confidence']:>5.0f}% | {sig_str}")
    
    # DETAILED RISK (Best Config)
    print_header("8. RISK ANALYSIS (Best Config)")
    if passed:
        best = max(passed, key=lambda x: x.production_score)
        print(f"\n  Config: BB={best.bb}, RSI={best.rsi}, TP={best.tp}, SL={best.sl}")
        print_risk_analysis(best)
    
    # RECOMMENDATIONS
    print_header("9. RECOMMENDATIONS")
    recommendations = generate_recommendations(results, sensitivity, rejection_analysis, significance)
    print_recommendations(recommendations)
    
    # NEXT STEPS
    print_header("10. NEXT STEPS")
    print("""
  IMMEDIATE:
  ──────────
  1. Review Golden Rejects - consider relaxing criteria
  2. Focus on optimal BB/RSI ranges identified above
  3. If precision_cv is the blocker, try max_precision_cv: 0.35
  
  BEFORE PRODUCTION:
  ──────────────────
  1. Paper trade best config for 2+ weeks
  2. Verify across bull/bear/sideways markets
  3. Set position size based on max drawdown
  
  IN PRODUCTION:
  ──────────────
  1. Monitor rolling precision weekly
  2. Pause if precision drops below 50%
  3. Retrain monthly with new data
    """)
    
    print_header("END OF REPORT", "=", 100)


def main():
    parser = argparse.ArgumentParser(description='Deep Quantitative Analysis Tool v2.0')
    parser.add_argument('--db', required=True, help='Path to checkpoint database')
    args = parser.parse_args()
    generate_report(args.db)


if __name__ == '__main__':
    main()
