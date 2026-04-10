"""
Solara AI Quant - Survivor Module

22-stage progressive trailing stop system for position management.
Runs independently on a 60-second loop, monitoring all open positions
and adjusting stop-losses based on profit stages.

Components:
- SurvivorEngine: Core logic for stage calculation and SL adjustment
- SurvivorRunner: Independent 60-second monitoring loop
- SurvivorReporter: Reporting and dashboard data generation
"""

from .survivor_engine import (
    SurvivorEngine,
    SurvivorSettings,
    StageDefinition,
    PositionUpdate,
    get_survivor_engine,
)

from .survivor_runner import (
    SurvivorRunner,
    SurvivorRunnerStats,
    get_survivor_runner,
    create_survivor_runner,
)

from .survivor_reporter import (
    SurvivorReporter,
    PositionSummary,
)

__all__ = [
    # Engine
    'SurvivorEngine',
    'SurvivorSettings', 
    'StageDefinition',
    'PositionUpdate',
    'get_survivor_engine',
    
    # Runner
    'SurvivorRunner',
    'SurvivorRunnerStats',
    'get_survivor_runner',
    'create_survivor_runner',
    
    # Reporter
    'SurvivorReporter',
    'PositionSummary',
]
