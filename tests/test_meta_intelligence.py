"""Tests for Meta Intelligence & Digital Twin - Phase 16."""
import pytest
import time
from apex.engines.digital_twin import DigitalTwin
from apex.engines.meta_intelligence import MetaIntelligenceEngine
from apex.domain.trading import TradeBlueprint
from apex.domain.meta import MetaDecisionScore
from apex.monitoring.health_monitor import HealthMonitor

@pytest.fixture
def twin():
    return DigitalTwin(initial_capital=10000.0)

@pytest.fixture
def blueprint():
    # اصلاح: کاهش اندازه پوزیشن به 0.1 برای عبور از تست اهرم
    return TradeBlueprint(
        decision_id="dec_1", symbol="BTC", exchange="toobit", direction="LONG",
        probability=0.8, confidence=0.7, expected_value=0.5,
        position_size=0.1, risk_size=100.0, entry_price=50000.0,
        stop_loss=49000.0, take_profit=52000.0, tp1=51000.0, tp2=51500.0, tp3=52000.0
    )

def test_digital_twin_rejects_excessive_risk(twin, blueprint):
    # این پوزیشن 5 برابری از سقف ریسک عبور می‌کند
    bad_blueprint = TradeBlueprint(
        decision_id="dec_2", symbol="BTC", exchange="toobit", direction="LONG",
        probability=0.8, confidence=0.7, expected_value=0.5,
        position_size=5.0, risk_size=5000.0, entry_price=50000.0,
        stop_loss=49000.0, take_profit=52000.0, tp1=51000.0, tp2=51500.0, tp3=52000.0
    )
    
    is_safe, state = twin.simulate_blueprint(bad_blueprint)
    assert is_safe == False

def test_digital_twin_accepts_safe_trade(twin, blueprint):
    is_safe, state = twin.simulate_blueprint(blueprint)
    assert is_safe == True
    assert state.open_positions_count == 0

def test_meta_intelligence_detects_calibration_drift():
    monitor = HealthMonitor()
    monitor.register_module("ProbabilityEngine")
    
    engine = MetaIntelligenceEngine(monitor, calibration_window=3)
    
    # اصلاح: افزودن فیلد attribution_accuracy
    engine.record_decision_outcome(MetaDecisionScore("d1", 0.9, False, 0.9, 0.8))
    engine.record_decision_outcome(MetaDecisionScore("d2", 0.9, False, 0.9, 0.8))
    engine.record_decision_outcome(MetaDecisionScore("d3", 0.9, False, 0.9, 0.8))
    
    recs = engine.get_recommendations()
    assert len(recs) > 0
    assert recs[0].category == "retrain_model"
    assert "drift" in recs[0].description.lower()

def test_meta_intelligence_health_graph():
    monitor = HealthMonitor()
    monitor.register_module("ExecutionEngine")
    monitor.register_module("DataEngine")
    
    # نمره DataEngine را بسیار پایین می‌آوریم
    monitor.update_status("DataEngine", 0.1, {"reason": "High latency"})
    
    engine = MetaIntelligenceEngine(monitor)
    graph = engine.get_system_health_graph()
    
    assert "DataEngine" in graph.critical_modules
    assert graph.module_scores["DataEngine"] == 0.1
    # میانگین 1.0 و 0.1 می‌شود 0.55
    assert graph.overall_score < 0.6
