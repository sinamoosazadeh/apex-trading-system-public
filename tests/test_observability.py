"""Tests for Observability Platform - Phase 11."""
import pytest
import json
import time
from apex.monitoring.structured_logger import StructuredLogger
from apex.monitoring.metrics_engine import MetricsEngine
from apex.monitoring.health_monitor import HealthMonitor
from apex.monitoring.contracts import Metric, HealthReport

def test_structured_logger_outputs_json(capsys):
    logger = StructuredLogger("TestModule")
    logger.info("Trade executed", trade_id="123", pnl=50.5)
    
    captured = capsys.readouterr()
    log_dict = json.loads(captured.out.strip())
    
    assert log_dict["module"] == "TestModule"
    assert log_dict["level"] == "INFO"
    assert log_dict["message"] == "Trade executed"
    assert log_dict["trade_id"] == "123"
    assert log_dict["pnl"] == 50.5

def test_metrics_engine_record_and_retrieve():
    engine = MetricsEngine()
    engine.record("cpu_usage", 45.5, "%", node="main")
    engine.record("cpu_usage", 55.0, "%", node="main")
    
    latest = engine.get_latest("cpu_usage")
    assert latest is not None
    assert latest.value == 55.0
    assert latest.tags["node"] == "main"
    
    history = engine.get_history("cpu_usage")
    assert len(history) == 2

def test_metrics_engine_nan_rejection():
    engine = MetricsEngine()
    with pytest.raises(ValueError):
        engine.record("invalid_metric", float('nan'))

def test_health_monitor_heartbeat_and_timeout():
    monitor = HealthMonitor(heartbeat_timeout=0.1)  # 100ms timeout
    monitor.register_module("ExecutionEngine")
    monitor.heartbeat("ExecutionEngine")
    
    statuses = monitor.get_all_statuses()
    assert statuses["ExecutionEngine"].status == "HEALTHY"
    
    time.sleep(0.2)
    statuses = monitor.get_all_statuses()
    assert statuses["ExecutionEngine"].status == "OFFLINE"
    assert statuses["ExecutionEngine"].score == 0.0

def test_health_monitor_manual_score_update():
    monitor = HealthMonitor()
    monitor.register_module("ProbabilityEngine")
    # 0.6 is between 0.5 and 0.8, so it should be WARNING
    monitor.update_status("ProbabilityEngine", 0.6, {"reason": "High uncertainty"})
    
    statuses = monitor.get_all_statuses()
    assert statuses["ProbabilityEngine"].status == "WARNING"
    assert statuses["ProbabilityEngine"].score == 0.6
