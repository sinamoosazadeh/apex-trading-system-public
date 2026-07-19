"""Tests for Risk Engine - Phase 6."""
import pytest
import math
from apex.engines.risk_engine import RiskEngine
from apex.domain.trading import PortfolioState, Decision
from apex.domain.contracts import ProbabilityReport

@pytest.fixture
def engine():
    return RiskEngine(risk_per_trade_pct=1.0, sl_mult=2.0, tp_mult=3.5)

@pytest.fixture
def portfolio():
    return PortfolioState(total_equity=10000.0, available_capital=10000.0)

@pytest.fixture
def long_decision():
    return Decision(decision_type="TRADE", direction="LONG", confidence=0.8, trace_id="test_long")

@pytest.fixture
def prob_report():
    return ProbabilityReport(probability_long=0.8, probability_short=0.1, probability_neutral=0.1)

def test_stop_loss_atr_only(engine):
    sl = engine.compute_stop_loss(100.0, 5.0, "LONG")
    assert math.isclose(sl, 90.0)
    
    sl = engine.compute_stop_loss(100.0, 5.0, "SHORT")
    assert math.isclose(sl, 110.0)

def test_stop_loss_structure_hybrid(engine):
    # OB Bot at 92, ATR 5. Struct SL = 92 - 0.75 = 91.25
    sl = engine.compute_stop_loss(100.0, 5.0, "LONG", ob_bot=92.0)
    assert math.isclose(sl, 91.25)
    
    # If OB Bot is too far, fallback to ATR
    sl = engine.compute_stop_loss(100.0, 5.0, "LONG", ob_bot=50.0)
    assert math.isclose(sl, 90.0)

def test_take_profit_liquidity_targets(engine):
    # Risk=10, Base RR=1.75. TP3 Cand = 126.25
    tp1, tp2, tp3, tp = engine.compute_take_profit(100.0, 90.0, "LONG")
    assert math.isclose(tp1, 108.75)
    assert math.isclose(tp2, 117.5)
    assert math.isclose(tp3, 126.25)
    
    # With HTF High at 120.0 -> TP3 should be 120.0
    tp1, tp2, tp3, tp = engine.compute_take_profit(100.0, 90.0, "LONG", htf_high=120.0)
    assert math.isclose(tp3, 120.0)

def test_position_sizing(engine, portfolio):
    # Risk 1% of 10000 = 100. Risk per unit = 10. Size = 10
    size, risk = engine.compute_position_size(10000.0, 100.0, 90.0)
    assert math.isclose(size, 10.0)
    assert math.isclose(risk, 100.0)

def test_create_blueprint_long(engine, portfolio, long_decision, prob_report):
    blueprint = engine.create_blueprint(
        decision=long_decision,
        portfolio=portfolio,
        probability_report=prob_report,
        current_price=100.0,
        atr=5.0,
        ob_bot=92.0,
        htf_high=120.0
    )
    
    assert blueprint is not None
    assert blueprint.direction == "LONG"
    assert blueprint.entry_price == 100.0
    assert math.isclose(blueprint.stop_loss, 91.25)
    assert math.isclose(blueprint.take_profit, 120.0)
    assert blueprint.position_size > 0
    assert 0.0 <= blueprint.trade_quality_index <= 1.0
