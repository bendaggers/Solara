"""
Solara AI Quant - Database Extensions for Survivor Engine

Additional database methods for survivor engine operations.
These extend the base DatabaseManager functionality.
"""

import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


def extend_database_manager(DatabaseManager):
    """
    Add Survivor Engine methods to DatabaseManager class.
    
    Usage:
        from database import DatabaseManager
        from database_extensions import extend_database_manager
        extend_database_manager(DatabaseManager)
    """
    
    def get_position_transitions(
        self, 
        ticket: int, 
        limit: int = 100
    ) -> List:
        """Get all transitions for a position."""
        from models import StageTransitionLog
        
        with self.session_scope() as session:
            return (
                session.query(StageTransitionLog)
                .filter_by(ticket=ticket)
                .order_by(StageTransitionLog.transitioned_at.desc())
                .limit(limit)
                .all()
            )
    
    DatabaseManager.get_position_transitions = get_position_transitions
    
    def get_transitions(
        self,
        ticket: Optional[int] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List:
        """Get stage transitions with optional filters."""
        from models import StageTransitionLog
        
        with self.session_scope() as session:
            query = session.query(StageTransitionLog)
            
            if ticket is not None:
                query = query.filter_by(ticket=ticket)
            
            if since is not None:
                query = query.filter(StageTransitionLog.transitioned_at >= since)
            
            return (
                query
                .order_by(StageTransitionLog.transitioned_at.desc())
                .limit(limit)
                .all()
            )
    
    DatabaseManager.get_transitions = get_transitions
    
    def update_position_price_extremes(
        self,
        ticket: int,
        current_price: float,
        direction: str
    ):
        """Update highest/lowest price for position."""
        from models import PositionState
        
        with self.session_scope() as session:
            state = session.query(PositionState).filter_by(ticket=ticket).first()
            if state is None:
                return
            
            if direction == 'LONG':
                if state.highest_price is None or current_price > state.highest_price:
                    state.highest_price = current_price
            else:
                if state.lowest_price is None or current_price < state.lowest_price:
                    state.lowest_price = current_price
            
            session.commit()
    
    DatabaseManager.update_position_price_extremes = update_position_price_extremes
    
    def get_positions_by_magic(self, magic: int) -> List:
        """Get all positions for a specific magic number."""
        from models import PositionState
        
        with self.session_scope() as session:
            return session.query(PositionState).filter_by(magic=magic).all()
    
    DatabaseManager.get_positions_by_magic = get_positions_by_magic
    
    def cleanup_closed_positions(self, open_tickets: List[int]):
        """Remove position states for positions that are no longer open."""
        from models import PositionState
        
        with self.session_scope() as session:
            # Get all tracked positions
            all_states = session.query(PositionState).all()
            
            removed = 0
            for state in all_states:
                if state.ticket not in open_tickets:
                    session.delete(state)
                    removed += 1
            
            session.commit()
            
            if removed > 0:
                logger.info(f"Cleaned up {removed} closed position states")
            
            return removed
    
    DatabaseManager.cleanup_closed_positions = cleanup_closed_positions
    
    logger.debug("DatabaseManager extended with Survivor Engine methods")
