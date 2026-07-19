"""Tests for Portfolio Engine - Phase 7."""
import pytest
import math
from apex.engines.portfolio_engine import PortfolioEngine
from apex.domain.trading import Position

@pytest.fixture
def engine():
    return PortfolioEngine(initial_capital=10000.0, max_drawdown=0.10)

@pytest.fixture
def long_position():
    return Position(
        position_id="pos_1", blueprint_id="bp_1", symbol="BTCUSDT", exchange="toobit",
        direction="LONG", entry_price=100.0, quantity=10.0, stop_loss=90.0, take_profit=120.0
    )

def test_portfolio_initial_state(engine):
    state = engine.get_state()
    assert state.total_equity == 10000.0
    assert state.drawdown == 0.0
    assert state.health_score == 1.0
    assert state.open_positions_count == 0

def test_portfolio_add_position_and_pnl(engine, long_position):
    engine.add_position(long_position)
    assert engine.get_state().open_positions_count == 1
    engine.update_positions({"BTCUSDT": 110.0})
    state = engine.get_state()
    assert math.isclose(state.total_equity, 10100.0)
    assert state.drawdown == 0.0
    engine.update_positions({"BTCUSDT": 95.0})
    state = engine.get_state()
    assert math.isclose(state.total_equity, 9950.0)
    assert state.drawdown > 0.0

def test_portfolio_close_position(engine, long_position):
    engine.add_position(long_position)
    engine.update_positions({"BTCUSDT": 110.0})
    trade = engine.close_position("pos_1", 110.0)
    assert trade is not None
    assert trade.win
    assert math.isclose(trade.pnl, 100.0)
    assert math.isclose(trade.r_multiple, 1.0)
    state = engine.get_state()
    assert state.open_positions_count == 0
    assert math.isclose(state.total_equity, 10100.0)

def test_portfolio_kill_switch(engine, long_position):
    large_pos = Position(
        position_id="pos_2", blueprint_id="bp_2", symbol="BTCUSDT", exchange="toobit",
        direction="LONG", entry_price=100.0, quantity=100.0, stop_loss=80.0, take_profit=150.0
    )
    engine.add_position(large_pos)
    engine.update_positions({"BTCUSDT": 99.0})
    assert not engine.kill_switch_active
    engine.update_positions({"BTCUSDT": 89.0})
    assert engine.kill_switch_active
    assert engine.get_state().health_score < 0.1
    assert not engine.add_position(long_position)
