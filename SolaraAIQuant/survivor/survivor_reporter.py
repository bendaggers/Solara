"""
Solara AI Quant - Survivor Reporter

Generates reports and provides visibility into Survivor Engine operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PositionSummary:
    """Summary of a position's survivor state."""
    ticket: int
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    profit_pips: float
    max_profit_pips: float
    current_stage: int
    current_sl: Optional[float]
    protection_pct: float
    locked_pips: float
    opened_at: datetime
    time_in_trade: timedelta
    total_transitions: int


class SurvivorReporter:
    """
    Generates reports on Survivor Engine activity.
    
    Provides:
    - Position summaries with survivor state
    - Stage transition history
    - Performance statistics
    - Real-time dashboard data
    """
    
    def __init__(self, db_manager, survivor_engine):
        """
        Initialize reporter.
        
        Args:
            db_manager: Database manager for querying state
            survivor_engine: SurvivorEngine for stage definitions
        """
        self.db_manager = db_manager
        self.survivor_engine = survivor_engine
    
    def get_position_summary(self, ticket: int) -> Optional[PositionSummary]:
        """
        Get summary for a single position.
        
        Args:
            ticket: Position ticket number
            
        Returns:
            PositionSummary or None if not found
        """
        state = self.db_manager.get_position_state(ticket)
        
        if state is None:
            return None
        
        # Get stage info
        stage_def = self.survivor_engine.get_stage_info(state.current_stage)
        protection_pct = stage_def.protection_pct if stage_def else 0
        
        # Calculate locked pips
        locked_pips = state.max_profit_pips * protection_pct if state.max_profit_pips else 0
        
        # Calculate profit pips
        pip_value = 0.01 if 'JPY' in state.symbol else 0.0001
        if state.direction == 'LONG':
            profit_pips = (state.highest_price - state.entry_price) / pip_value if state.highest_price else 0
        else:
            profit_pips = (state.entry_price - state.lowest_price) / pip_value if state.lowest_price else 0
        
        # Get transition count
        transitions = self.db_manager.get_position_transitions(ticket)
        
        return PositionSummary(
            ticket=state.ticket,
            symbol=state.symbol,
            direction=state.direction,
            entry_price=state.entry_price,
            current_price=0,  # Would need MT5 for current
            profit_pips=profit_pips,
            max_profit_pips=state.max_profit_pips or 0,
            current_stage=state.current_stage,
            current_sl=state.current_sl,
            protection_pct=protection_pct,
            locked_pips=locked_pips,
            opened_at=state.opened_at,
            time_in_trade=datetime.utcnow() - state.opened_at,
            total_transitions=len(transitions) if transitions else 0
        )
    
    def get_all_position_summaries(self) -> List[PositionSummary]:
        """Get summaries for all tracked positions."""
        positions = self.db_manager.get_all_position_states()
        
        summaries = []
        for state in positions:
            summary = self.get_position_summary(state.ticket)
            if summary:
                summaries.append(summary)
        
        return summaries
    
    def get_transition_history(
        self,
        ticket: Optional[int] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get stage transition history.
        
        Args:
            ticket: Filter by ticket (optional)
            since: Filter by time (optional)
            limit: Maximum records to return
            
        Returns:
            List of transition records
        """
        transitions = self.db_manager.get_transitions(
            ticket=ticket,
            since=since,
            limit=limit
        )
        
        results = []
        for t in transitions:
            results.append({
                'ticket': t.ticket,
                'from_stage': t.from_stage,
                'to_stage': t.to_stage,
                'trigger_pips': t.trigger_pips,
                'new_sl': t.new_sl,
                'protection_pct': t.protection_pct,
                'transitioned_at': t.transitioned_at
            })
        
        return results
    
    def get_daily_statistics(self, date: Optional[str] = None) -> Dict:
        """
        Get daily survivor statistics.
        
        Args:
            date: Date in YYYY-MM-DD format (default: today)
            
        Returns:
            Statistics dictionary
        """
        if date is None:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        
        since = datetime.strptime(date, '%Y-%m-%d')
        until = since + timedelta(days=1)
        
        transitions = self.db_manager.get_transitions(since=since)
        
        # Count statistics
        stage_counts = {}
        for t in transitions:
            key = f"{t.from_stage}->{t.to_stage}"
            stage_counts[key] = stage_counts.get(key, 0) + 1
        
        # Get unique positions that had transitions
        unique_tickets = set(t.ticket for t in transitions)
        
        # Calculate protection stats
        total_protection = sum(
            t.trigger_pips * (t.protection_pct or 0)
            for t in transitions
        )
        
        return {
            'date': date,
            'total_transitions': len(transitions),
            'unique_positions': len(unique_tickets),
            'stage_transition_counts': stage_counts,
            'total_pips_protected': total_protection,
            'avg_protection_pct': (
                sum(t.protection_pct or 0 for t in transitions) / len(transitions)
                if transitions else 0
            )
        }
    
    def print_position_report(self, ticket: int):
        """Print detailed report for a position."""
        summary = self.get_position_summary(ticket)
        
        if summary is None:
            print(f"Position {ticket} not found")
            return
        
        transitions = self.get_transition_history(ticket=ticket)
        
        print("\n" + "=" * 60)
        print(f"  POSITION REPORT: {summary.ticket}")
        print("=" * 60)
        
        print(f"""
  Symbol:        {summary.symbol}
  Direction:     {summary.direction}
  Entry Price:   {summary.entry_price:.5f}
  Opened:        {summary.opened_at}
  Time in Trade: {summary.time_in_trade}
  
  SURVIVOR STATE:
  ─────────────────────────────────────
  Current Stage:    {summary.current_stage}
  Max Profit:       {summary.max_profit_pips:.1f} pips
  Protection:       {summary.protection_pct*100:.0f}%
  Locked Pips:      {summary.locked_pips:.1f} pips
  Current SL:       {summary.current_sl:.5f if summary.current_sl else 'None'}
  
  TRANSITION HISTORY ({summary.total_transitions} transitions):
  ─────────────────────────────────────""")
        
        for t in transitions:
            print(
                f"  Stage {t['from_stage']} → {t['to_stage']} | "
                f"Trigger: {t['trigger_pips']:.1f} pips | "
                f"SL: {t['new_sl']:.5f if t['new_sl'] else 'N/A'} | "
                f"{t['transitioned_at']}"
            )
        
        print("=" * 60 + "\n")
    
    def print_all_positions_report(self):
        """Print summary of all tracked positions."""
        summaries = self.get_all_position_summaries()
        
        print("\n" + "=" * 80)
        print("  SURVIVOR ENGINE - ALL POSITIONS")
        print("=" * 80)
        
        if not summaries:
            print("  No positions currently tracked")
            print("=" * 80 + "\n")
            return
        
        print(f"\n  {'Ticket':<12} {'Symbol':<10} {'Dir':<6} {'Stage':<6} "
              f"{'Max Pips':<10} {'Protected':<10} {'Locked':<10}")
        print("  " + "-" * 74)
        
        for s in summaries:
            print(
                f"  {s.ticket:<12} {s.symbol:<10} {s.direction:<6} "
                f"{s.current_stage:<6} {s.max_profit_pips:<10.1f} "
                f"{s.protection_pct*100:<10.0f}% {s.locked_pips:<10.1f}"
            )
        
        # Summary stats
        total_locked = sum(s.locked_pips for s in summaries)
        avg_stage = sum(s.current_stage for s in summaries) / len(summaries)
        
        print("-" * 80)
        print(f"  TOTAL: {len(summaries)} positions | "
              f"Avg Stage: {avg_stage:.1f} | "
              f"Total Locked: {total_locked:.1f} pips")
        print("=" * 80 + "\n")
    
    def print_daily_report(self, date: Optional[str] = None):
        """Print daily statistics report."""
        stats = self.get_daily_statistics(date)
        
        print("\n" + "=" * 60)
        print(f"  SURVIVOR ENGINE - DAILY REPORT ({stats['date']})")
        print("=" * 60)
        
        print(f"""
  Total Transitions:    {stats['total_transitions']}
  Unique Positions:     {stats['unique_positions']}
  Total Pips Protected: {stats['total_pips_protected']:.1f}
  Avg Protection:       {stats['avg_protection_pct']*100:.1f}%
  
  STAGE TRANSITIONS:
  ─────────────────────────────────────""")
        
        for transition, count in sorted(stats['stage_transition_counts'].items()):
            print(f"  {transition}: {count} times")
        
        print("=" * 60 + "\n")
    
    def get_dashboard_data(self) -> Dict:
        """
        Get data for real-time dashboard.
        
        Returns:
            Dictionary with dashboard metrics
        """
        summaries = self.get_all_position_summaries()
        today_stats = self.get_daily_statistics()
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'active_positions': len(summaries),
            'total_locked_pips': sum(s.locked_pips for s in summaries),
            'avg_stage': (
                sum(s.current_stage for s in summaries) / len(summaries)
                if summaries else 0
            ),
            'max_stage': max((s.current_stage for s in summaries), default=0),
            'positions_by_stage': {
                stage: len([s for s in summaries if s.current_stage == stage])
                for stage in range(23)
                if any(s.current_stage == stage for s in summaries)
            },
            'today': {
                'transitions': today_stats['total_transitions'],
                'pips_protected': today_stats['total_pips_protected']
            }
        }
