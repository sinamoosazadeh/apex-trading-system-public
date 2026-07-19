"""Tests for Research Engine - Phase 10."""
import pytest
from apex.research.knowledge_base import KnowledgeBase
from apex.research.research_engine import ResearchEngine
from apex.engines.probability_engine import ProbabilityEngine
from apex.domain.trading import Trade
from apex.domain.knowledge import Experience

@pytest.fixture
def setup():
    kb = KnowledgeBase()
    pe = ProbabilityEngine()
    engine = ResearchEngine(kb, pe)
    return kb, pe, engine

def test_knowledge_base_record_and_stats(setup):
    kb, _, _ = setup
    
    exp1 = Experience("t1", "BTC", "Turtle Soup", "LONG", True, 2.0, 0.8, 0.2, "neutral")
    exp2 = Experience("t2", "BTC", "Turtle Soup", "LONG", False, -1.0, 0.7, 0.3, "neutral")
    
    kb.record_experience(exp1)
    kb.record_experience(exp2)
    
    stats = kb.get_setup_stats("Turtle Soup")
    assert stats["sample_size"] == 2
    assert stats["win_rate"] == 0.5
    assert stats["expectancy"] == 0.5

def test_research_engine_feedback_loop(setup):
    kb, pe, engine = setup
    
    # ثبت زمینه با position_id (مطابق کد واقعی bootstrap.py)
    context = Experience("t100", "ETH", "FVG Continuation", "LONG", False, 0.0, 0.85, 0.2, "neutral")
    engine.record_trade_context("p100", context)
    
    assert pe.calibration_bins[8].trades == 0.0
    
    closed_trade = Trade(
        trade_id="t100", position_id="p100", symbol="ETH", direction="LONG",
        entry_price=100, exit_price=110, quantity=1, pnl=10, r_multiple=1.5, win=True
    )
    
    engine.process_closed_trade(closed_trade)
    
    assert pe.calibration_bins[8].trades == 1.0
    assert pe.calibration_bins[8].wins == 1.0
    
    stats = kb.get_setup_stats("FVG Continuation")
    assert stats["sample_size"] == 1

def test_knowledge_extraction_positive_edge(setup):
    kb, pe, engine = setup
    
    for i in range(35):
        exp = Experience(f"t{i}", "BTC", "Super Setup", "LONG", True, 2.0, 0.8, 0.2, "neutral")
        # ثبت زمینه با position_id (مطابق کد واقعی bootstrap.py)
        engine.record_trade_context(f"p{i}", exp)
        trade = Trade(
            trade_id=f"t{i}", position_id=f"p{i}", symbol="BTC", direction="LONG",
            entry_price=100, exit_price=120, quantity=1, pnl=20, r_multiple=2.0, win=True
        )
        engine.process_closed_trade(trade)
        
    knowledge_list = kb.get_all_knowledge()
    assert len(knowledge_list) > 0
    
    edge_knowledge = knowledge_list[0]
    assert edge_knowledge.category == "setup_performance"
    assert "Super Setup" in edge_knowledge.description
    assert edge_knowledge.confidence > 0.0
