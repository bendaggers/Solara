"""
Solara AI Quant - Engine Module

Model execution engine with parallel processing.

Components:
- ModelRegistry: Load/manage model configurations
- ExecutionEngine: Parallel model execution
- ModelHealthTracker: Health tracking and auto-disable
"""

from .registry import (
    ModelRegistry,
    ModelConfig,
    ModelType,
    TimeframeEnum,
    model_registry
)

from .execution_engine import (
    ExecutionEngine,
    ModelResult,
    ModelResultSet,
    execution_engine
)

from .model_health import (
    ModelHealthTracker,
    HealthStatus,
    HealthReport,
    RunStatus,
    model_health_tracker
)

__all__ = [
    # Registry
    'ModelRegistry',
    'ModelConfig',
    'ModelType',
    'TimeframeEnum',
    'model_registry',
    
    # Execution
    'ExecutionEngine',
    'ModelResult',
    'ModelResultSet',
    'execution_engine',
    
    # Health
    'ModelHealthTracker',
    'HealthStatus',
    'HealthReport',
    'RunStatus',
    'model_health_tracker',
]
