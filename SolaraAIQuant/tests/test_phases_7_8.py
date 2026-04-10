"""
Solara AI Quant - Phase 7 & 8 Tests

Tests for:
- Phase 7: Survivor Engine (22-stage trailing stop)
- Phase 8: Integration & End-to-End Testing
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Mock Classes for Testing
# =============================================================================

class MockMT5Manager:
    """Mock MT5 manager for testing without real MT5 connection."""
    
    def __init__(self):
        self.positions: List = []
        self.modifications: List[Dict] = []
        self.connected = False
    
    def connect(self) -> bool:
        self.connected = True
        return True
    
    def disconnect(self):
        self.connected = False
    
    def get_positions(self):
        """Return mock positions."""
        return self.positions
    
    def get_symbol_tick(self, symbol: str):
        """Return mock tick data."""
        @dataclass
        class MockTick:
            bid: float
            ask: float
        
        if 'JPY' in symbol:
            return MockTick(bid=150.500, ask=150.502)
        return MockTick(bid=1.08500, ask=1.08502)
    
    def modify_position(self, ticket: int, sl: float = None, tp: float = None) -> bool:
        """Record modification and return success."""
        self.modifications.append({
            'ticket': ticket,
            'sl': sl,
            'tp': tp,
            'timestamp': datetime.utcnow()
        })
        return True
    
    def add_mock_position(
        self,
        ticket: int,
        symbol: str,
        type_: int,
        price_open: float,
        volume: float = 0.1,
        sl: float = None,
        tp: float = None,
        magic: int = 123456,
        profit: float = 0
    ):
        """Add a mock position for testing."""
        @dataclass
        class MockPosition:
            ticket: int
            symbol: str
            type: int
            price_open: float
            volume: float
            sl: Optional[float]
            tp: Optional[float]
            magic: int
            profit: float
        
        self.positions.append(MockPosition(
            ticket=ticket,
            symbol=symbol,
            type=type_,
            price_open=price_open,
            volume=volume,
            sl=sl,
            tp=tp,
            magic=magic,
            profit=profit
        ))


class MockDatabaseManager:
    """Mock database manager for testing without real database."""
    
    def __init__(self):
        self.position_states: Dict[int, Dict] = {}
        self.transitions: List[Dict] = []
    
    def get_position_state(self, ticket: int) -> Optional[Dict]:
        state = self.position_states.get(ticket)
        if state:
            @dataclass
            class MockState:
                ticket: int
                current_stage: int
                max_profit_pips: float
                highest_price: Optional[float]
                lowest_price: Optional[float]
            return MockState(**{k: state.get(k) for k in ['ticket', 'current_stage', 'max_profit_pips', 'highest_price', 'lowest_price']})
        return None
    
    def upsert_position_state(self, ticket: int, **kwargs):
        if ticket not in self.position_states:
            self.position_states[ticket] = {
                'ticket': ticket,
                'current_stage': 0,
                'max_profit_pips': 0,
                'highest_price': kwargs.get('entry_price'),
                'lowest_price': kwargs.get('entry_price'),
                **kwargs
            }
        else:
            self.position_states[ticket].update(kwargs)
    
    def update_position_stage(
        self,
        ticket: int,
        new_stage: int,
        new_sl: float,
        new_tp: float,
        trigger_pips: float,
        protection_pct: float
    ):
        if ticket in self.position_states:
            old_stage = self.position_states[ticket].get('current_stage', 0)
            self.position_states[ticket]['current_stage'] = new_stage
            self.position_states[ticket]['current_sl'] = new_sl
            self.position_states[ticket]['max_profit_pips'] = max(
                self.position_states[ticket].get('max_profit_pips', 0),
                trigger_pips
            )
            
            self.transitions.append({
                'ticket': ticket,
                'from_stage': old_stage,
                'to_stage': new_stage,
                'trigger_pips': trigger_pips,
                'new_sl': new_sl,
                'protection_pct': protection_pct,
                'transitioned_at': datetime.utcnow()
            })
    
    def get_all_position_states(self):
        return list(self.position_states.values())
    
    def get_transitions(self, ticket=None, since=None, limit=100):
        result = self.transitions
        if ticket:
            result = [t for t in result if t['ticket'] == ticket]
        if since:
            result = [t for t in result if t['transitioned_at'] >= since]
        return result[:limit]


# =============================================================================
# Phase 7 Tests: Survivor Engine
# =============================================================================

def test_stage_definitions_loading():
    """Test loading of stage definitions."""
    print("\n  TEST: Stage definitions loading")
    
    from survivor_engine import SurvivorEngine
    
    engine = SurvivorEngine()
    
    assert len(engine.stages) == 23, f"Expected 23 stages, got {len(engine.stages)}"
    assert engine.stages[0].stage == 0, "First stage should be 0"
    assert engine.stages[-1].stage == 22, "Last stage should be 22"
    assert engine.stages[0].protection_pct == 0, "Stage 0 should have 0% protection"
    assert engine.stages[-1].protection_pct >= 0.85, "Stage 22 should have ~88% protection"
    
    print("    ✓ Stage definitions loaded correctly")
    print(f"    ✓ {len(engine.stages)} stages defined")
    print(f"    ✓ Protection range: 0% to {engine.stages[-1].protection_pct*100:.0f}%")
    
    return True


def test_stage_determination():
    """Test stage determination based on profit."""
    print("\n  TEST: Stage determination")
    
    from survivor_engine import SurvivorEngine
    
    engine = SurvivorEngine()
    
    test_cases = [
        (0, 0, 0),
        (5, 0, 0),
        (10, 0, 1),
        (30, 0, 5),
        (50, 0, 9),
        (100, 0, 17),
        (200, 0, 22),
        (250, 0, 22),
    ]
    
    for profit_pips, current_stage, expected_stage in test_cases:
        result = engine.get_stage_for_profit(profit_pips, current_stage)
        assert result.stage == expected_stage, \
            f"Profit {profit_pips} pips: expected stage {expected_stage}, got {result.stage}"
    
    print("    ✓ Stage determination correct for various profit levels")
    
    result = engine.get_stage_for_profit(20, 10)
    assert result.stage == 10, "Stage should not go backward"
    
    print("    ✓ Stages only move forward (never backward)")
    
    return True


def test_sl_calculation():
    """Test stop-loss calculation."""
    print("\n  TEST: Stop-loss calculation")
    
    from survivor_engine import SurvivorEngine, StageDefinition
    
    engine = SurvivorEngine()
    
    entry_price = 1.08000
    profit_pips = 50
    stage = StageDefinition(stage=9, trigger_pips=50, protection_pct=0.55)
    
    new_sl = engine.calculate_new_sl(
        entry_price=entry_price,
        direction='LONG',
        profit_pips=profit_pips,
        stage=stage,
        pip_value=0.0001
    )
    
    expected_sl = entry_price + (profit_pips * stage.protection_pct - engine.settings.pip_buffer) * 0.0001
    
    assert abs(new_sl - expected_sl) < 0.00001, \
        f"LONG SL mismatch: expected {expected_sl:.5f}, got {new_sl:.5f}"
    
    print(f"    ✓ LONG position: Entry {entry_price:.5f} + 50 pips profit -> SL {new_sl:.5f}")
    
    entry_price = 1.08500
    
    new_sl = engine.calculate_new_sl(
        entry_price=entry_price,
        direction='SHORT',
        profit_pips=profit_pips,
        stage=stage,
        pip_value=0.0001
    )
    
    expected_sl = entry_price - (profit_pips * stage.protection_pct - engine.settings.pip_buffer) * 0.0001
    
    assert abs(new_sl - expected_sl) < 0.00001, \
        f"SHORT SL mismatch: expected {expected_sl:.5f}, got {new_sl:.5f}"
    
    print(f"    ✓ SHORT position: Entry {entry_price:.5f} + 50 pips profit -> SL {new_sl:.5f}")
    
    return True


def test_position_processing():
    """Test single position processing."""
    print("\n  TEST: Position processing")
    
    from survivor_engine import SurvivorEngine
    
    engine = SurvivorEngine()
    
    update = engine.process_position(
        ticket=12345,
        symbol='EURUSD',
        direction='LONG',
        entry_price=1.08000,
        current_price=1.08350,
        current_sl=None,
        current_stage=0,
        max_profit_pips=0,
        pip_value=0.0001
    )
    
    assert update.ticket == 12345
    assert update.profit_pips == 35, f"Expected 35 pips profit, got {update.profit_pips}"
    assert update.new_stage == 6, f"35 pips should trigger stage 6, got {update.new_stage}"
    assert update.stage_changed == True
    assert update.sl_modified == True
    assert update.new_sl is not None
    
    print(f"    ✓ Position processed: 35 pips profit -> stage {update.new_stage}")
    print(f"    ✓ New SL: {update.new_sl:.5f}")
    
    update2 = engine.process_position(
        ticket=12345,
        symbol='EURUSD',
        direction='LONG',
        entry_price=1.08000,
        current_price=1.08250,
        current_sl=update.new_sl,
        current_stage=6,
        max_profit_pips=35,
        pip_value=0.0001
    )
    
    assert update2.new_stage == 6, "Stage should not decrease"
    assert update2.stage_changed == False, "Stage should not change on pullback"
    
    print(f"    ✓ Pullback handled: max profit {update2.max_profit_pips:.1f} pips, stage maintained at {update2.new_stage}")
    
    return True


def test_survivor_runner():
    """Test Survivor Runner."""
    print("\n  TEST: Survivor Runner")
    
    from survivor_engine import SurvivorEngine
    from survivor_runner import SurvivorRunner
    
    mock_mt5 = MockMT5Manager()
    mock_db = MockDatabaseManager()
    
    mock_mt5.add_mock_position(
        ticket=12345,
        symbol='EURUSD',
        type_=0,
        price_open=1.08000,
        volume=0.1
    )
    
    mock_db.upsert_position_state(
        ticket=12345,
        symbol='EURUSD',
        direction='LONG',
        entry_price=1.08000
    )
    
    engine = SurvivorEngine(mt5_manager=mock_mt5, db_manager=mock_db)
    runner = SurvivorRunner(
        survivor_engine=engine,
        mt5_manager=mock_mt5,
        db_manager=mock_db,
        check_interval=1
    )
    
    runner.run_once()
    
    stats = runner.get_stats()
    print(f"    ✓ Runner cycle executed")
    print(f"    ✓ Stats available: {list(stats.keys())}")
    
    return True


def test_stage_transitions_logging():
    """Test that stage transitions are properly logged."""
    print("\n  TEST: Stage transition logging")
    
    mock_db = MockDatabaseManager()
    
    mock_db.upsert_position_state(
        ticket=12345,
        symbol='EURUSD',
        direction='LONG',
        entry_price=1.08000
    )
    
    mock_db.update_position_stage(
        ticket=12345,
        new_stage=1,
        new_sl=1.08010,
        new_tp=None,
        trigger_pips=10,
        protection_pct=0.20
    )
    
    mock_db.update_position_stage(
        ticket=12345,
        new_stage=5,
        new_sl=1.08050,
        new_tp=None,
        trigger_pips=30,
        protection_pct=0.40
    )
    
    transitions = mock_db.get_transitions(ticket=12345)
    assert len(transitions) == 2, f"Expected 2 transitions, got {len(transitions)}"
    
    assert transitions[0]['from_stage'] == 0
    assert transitions[0]['to_stage'] == 1
    assert transitions[1]['from_stage'] == 1
    assert transitions[1]['to_stage'] == 5
    
    print(f"    ✓ {len(transitions)} transitions logged")
    for t in transitions:
        print(f"      Stage {t['from_stage']} → {t['to_stage']} at {t['trigger_pips']} pips")
    
    return True


# =============================================================================
# Phase 8 Tests: Integration
# =============================================================================

def test_configuration():
    """Test configuration loading."""
    print("\n  TEST: Configuration loading")
    
    from config import (
        PROJECT_ROOT, MODELS_DIR, LOGS_DIR, STATE_DIR,
        MQL5_FILES_DIR, mt5_config, risk_config, execution_config
    )
    
    assert PROJECT_ROOT.exists(), "PROJECT_ROOT should exist"
    print(f"    ✓ PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"    ✓ MODELS_DIR: {MODELS_DIR}")
    print(f"    ✓ MT5 Magic: {mt5_config.magic}")
    print(f"    ✓ Max Drawdown: {risk_config.max_drawdown_pct}%")
    
    return True


def test_database_tables():
    """Test database table creation."""
    print("\n  TEST: Database tables")
    
    from database import db_manager
    from sqlalchemy import inspect
    
    inspector = inspect(db_manager.engine)
    tables = inspector.get_table_names()
    
    required_tables = [
        'position_state',
        'stage_transition_log',
        'model_run',
        'signal_log',
        'trade_log',
        'model_health',
        'daily_stats'
    ]
    
    for table in required_tables:
        assert table in tables, f"Table {table} not found"
        print(f"    ✓ Table: {table}")
    
    return True


def test_model_registry():
    """Test model registry loading."""
    print("\n  TEST: Model registry")
    
    from registry import model_registry
    
    models = model_registry.get_all_models()
    print(f"    ✓ Loaded {len(models)} models")
    
    for model in models:
        status = "enabled" if model.enabled else "disabled"
        print(f"      - {model.name} ({model.timeframe}) [{status}]")
    
    return True


def test_signal_aggregation():
    """Test signal aggregation."""
    print("\n  TEST: Signal aggregation")
    
    from signal_models import RawSignal, SignalDirection
    from aggregator import SignalAggregator
    
    aggregator = SignalAggregator()
    
    signals = [
        RawSignal(
            model_name="model_1",
            symbol="EURUSD",
            direction=SignalDirection.LONG,
            confidence=0.75,
            weight=1.0,
            timestamp=datetime.utcnow()
        ),
        RawSignal(
            model_name="model_2",
            symbol="EURUSD",
            direction=SignalDirection.LONG,
            confidence=0.65,
            weight=1.0,
            timestamp=datetime.utcnow()
        ),
    ]
    
    aggregated = aggregator.aggregate(signals)
    
    assert len(aggregated) == 1
    assert aggregated[0].symbol == "EURUSD"
    assert aggregated[0].direction == SignalDirection.LONG
    
    print(f"    ✓ Aggregated {len(signals)} signals into {len(aggregated)}")
    print(f"    ✓ Final confidence: {aggregated[0].confidence:.2f}")
    
    return True


def test_conflict_checker():
    """Test conflict detection."""
    print("\n  TEST: Conflict checker")
    
    from signal_models import AggregatedSignal, SignalDirection
    from conflict_checker import ConflictChecker
    
    checker = ConflictChecker()
    
    signals = [
        AggregatedSignal(
            symbol="EURUSD",
            direction=SignalDirection.LONG,
            confidence=0.70,
            model_count=2,
            timestamp=datetime.utcnow()
        ),
        AggregatedSignal(
            symbol="EURUSD",
            direction=SignalDirection.SHORT,
            confidence=0.65,
            model_count=1,
            timestamp=datetime.utcnow()
        ),
    ]
    
    conflicts = checker.detect_conflicts(signals)
    
    assert len(conflicts) > 0, "Should detect conflict"
    print(f"    ✓ Detected {len(conflicts)} conflict(s)")
    
    return True


def test_full_application_lifecycle():
    """Test full application initialization and shutdown."""
    print("\n  TEST: Full application lifecycle")
    
    from main import SolaraAIQuant
    
    app = SolaraAIQuant(production=False, dry_run=True)
    
    # Check initial state
    assert app._is_initialized == False
    assert app.cycles_completed == 0
    
    print("    ✓ Application created")
    
    # We can't fully test without real components, but check structure
    status = app.get_status()
    assert 'is_initialized' in status
    assert 'is_running' in status
    assert 'cycles_completed' in status
    
    print("    ✓ Status reporting works")
    print(f"    ✓ Status keys: {list(status.keys())}")
    
    return True


# =============================================================================
# Test Runner
# =============================================================================

def run_all_tests():
    """Run all Phase 7 & 8 tests."""
    print("\n" + "=" * 60)
    print("  PHASE 7 & 8 TESTS")
    print("=" * 60)
    
    phase_7_tests = [
        ("Stage Definitions", test_stage_definitions_loading),
        ("Stage Determination", test_stage_determination),
        ("SL Calculation", test_sl_calculation),
        ("Position Processing", test_position_processing),
        ("Survivor Runner", test_survivor_runner),
        ("Transition Logging", test_stage_transitions_logging),
    ]
    
    phase_8_tests = [
        ("Configuration", test_configuration),
        ("Database Tables", test_database_tables),
        ("Model Registry", test_model_registry),
        ("Signal Aggregation", test_signal_aggregation),
        ("Conflict Checker", test_conflict_checker),
        ("Application Lifecycle", test_full_application_lifecycle),
    ]
    
    all_tests = [
        ("Phase 7: Survivor Engine", phase_7_tests),
        ("Phase 8: Integration", phase_8_tests),
    ]
    
    total_passed = 0
    total_failed = 0
    failures = []
    
    for phase_name, tests in all_tests:
        print(f"\n  {phase_name}")
        print("  " + "-" * 40)
        
        for test_name, test_func in tests:
            try:
                test_func()
                total_passed += 1
            except Exception as e:
                total_failed += 1
                failures.append((test_name, str(e)))
                print(f"\n    ✗ {test_name} FAILED: {e}")
    
    print("\n" + "=" * 60)
    print(f"  RESULTS: {total_passed} passed, {total_failed} failed")
    print("=" * 60)
    
    if failures:
        print("\n  FAILURES:")
        for name, error in failures:
            print(f"    - {name}: {error}")
    
    return total_failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
