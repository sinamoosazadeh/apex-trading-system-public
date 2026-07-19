"""Tests for Decision Engine - Phase 5."""
import pytest
from apex.domain.contracts import ProbabilityReport
from apex.domain.trading import PortfolioState, Decision
from apex.engines.decision_engine import DecisionEngine
from apex.engines.governance import GovernanceEngine, GovernancePolicy

@pytest.fixture
def engine():
    policy = GovernancePolicy(
        max_concurrent_trades=5, min_probability_threshold=0.62, min_prob_edge=0.03,
        min_contributors=3, min_expected_r=0.10, max_uncertainty=0.45, min_decision_readiness=0.40
    )
    return DecisionEngine(GovernanceEngine(policy))

def test_decision_kill_switch(engine):
    prob = ProbabilityReport(probability_long=0.9, probability_short=0.05, probability_neutral=0.05)
    portfolio = PortfolioState(health_score=0.1)  # Critical health
    
    decision = engine.evaluate(prob, portfolio, contributors_long=5)
    
    assert decision.decision_type == "NO_TRADE"
    assert "Kill switch active" in decision.reasoning

def test_decision_portfolio_limits(engine):
    prob = ProbabilityReport(probability_long=0.9, probability_short=0.05, probability_neutral=0.05)
    portfolio = PortfolioState(open_positions_count=5)  # Max reached
    
    decision = engine.evaluate(prob, portfolio, contributors_long=5)
    
    assert decision.decision_type == "NO_TRADE"
    assert "Max concurrent trades reached" in decision.reasoning[0]

def test_decision_low_dri(engine):
    prob = ProbabilityReport(
        probability_long=0.9, probability_short=0.05, probability_neutral=0.05,
        uncertainty=0.2, decision_readiness_index=0.20  # Low DRI
    )
    portfolio = PortfolioState()
    
    decision = engine.evaluate(prob, portfolio, contributors_long=5)
    
    assert decision.decision_type == "WAIT"
    assert "DRI too low" in decision.reasoning[0]

def test_decision_trade_approved(engine):
    prob = ProbabilityReport(
        probability_long=0.85, probability_short=0.10, probability_neutral=0.05,
        confidence=0.7, uncertainty=0.2, expected_r=0.5,
        decision_readiness_index=0.8
    )
    portfolio = PortfolioState()
    
    decision = engine.evaluate(prob, portfolio, contributors_long=5, contributors_short=2)
    
    assert decision.decision_type == "TRADE"
    assert decision.direction == "LONG"
    assert decision.confidence > 0.0
    assert "All gates passed" in decision.reasoning[0]

def test_decision_rejected_low_contributors(engine):
    prob = ProbabilityReport(
        probability_long=0.85, probability_short=0.10, probability_neutral=0.05,
        uncertainty=0.2, expected_r=0.5, decision_readiness_index=0.8
    )
    portfolio = PortfolioState()
    
    decision = engine.evaluate(prob, portfolio, contributors_long=2)  # < 3
    
    assert decision.decision_type == "NO_TRADE"
    assert "Insufficient long contributors" in decision.reasoning[-1]
