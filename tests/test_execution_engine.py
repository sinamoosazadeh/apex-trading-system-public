"""Tests for Execution Engine - Phase 8."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from apex.engines.execution_engine import ExecutionEngine
from apex.infrastructure.exchanges.toobit_adapter import ToobitAdapter
from apex.domain.trading import TradeBlueprint

@pytest.fixture
def blueprint():
    return TradeBlueprint(
        decision_id="test_123", symbol="BTC-SWAP-USDT", exchange="toobit", direction="LONG",
        probability=0.8, confidence=0.7, expected_value=0.5, position_size=10.0, risk_size=100.0,
        entry_price=50000.0, stop_loss=49000.0, take_profit=52000.0, tp1=51000.0, tp2=51500.0, tp3=52000.0
    )

@pytest.mark.asyncio
async def test_toobit_adapter_direction_mapping(blueprint):
    adapter = ToobitAdapter("key", "secret")
    assert adapter._map_direction_to_side("LONG") == "BUY_OPEN"
    assert adapter._map_direction_to_side("SHORT") == "SELL_OPEN"
    
    with pytest.raises(ValueError):
        adapter._map_direction_to_side("FLAT")

@pytest.mark.asyncio
async def test_execution_engine_success(blueprint):
    # Mock the adapter
    mock_adapter = MagicMock()
    mock_response = {"orderId": "toobit_123", "status": "NEW"}
    mock_adapter.place_order = AsyncMock(return_value=mock_response)
    
    engine = ExecutionEngine(mock_adapter)
    response = await engine.execute_blueprint(blueprint)
    
    assert response["status"] == "NEW"
    assert response["orderId"] == "toobit_123"
    mock_adapter.place_order.assert_called_once()

@pytest.mark.asyncio
async def test_execution_engine_retry_on_rate_limit(blueprint):
    mock_adapter = MagicMock()
    
    rejected_response = {"code": -1015, "msg": "Too many orders", "status": "REJECTED"}
    accepted_response = {"orderId": "toobit_456", "status": "NEW"}
    
    # First call rejects, second accepts
    mock_adapter.place_order = AsyncMock(side_effect=[rejected_response, accepted_response])
    
    engine = ExecutionEngine(mock_adapter, max_retries=3)
    response = await engine.execute_blueprint(blueprint)
    
    assert response["status"] == "NEW"
    assert mock_adapter.place_order.call_count == 2

@pytest.mark.asyncio
async def test_execution_engine_permanent_rejection(blueprint):
    mock_adapter = MagicMock()
    
    rejected_response = {"code": -1131, "msg": "Balance insufficient", "status": "REJECTED"}
    mock_adapter.place_order = AsyncMock(return_value=rejected_response)
    
    engine = ExecutionEngine(mock_adapter, max_retries=3)
    response = await engine.execute_blueprint(blueprint)
    
    assert response["status"] == "REJECTED"
    # Should not retry on -1131
    mock_adapter.place_order.assert_called_once()
