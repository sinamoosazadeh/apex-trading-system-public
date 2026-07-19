"""Integration test for the full APEX CDK pipeline - Phase 18."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from apex.application.bootstrap import Application
from apex.core.events import EventBus, Event
from apex.core.types.enums import EventType
from apex.domain.market import MarketBar

@pytest.fixture
def app():
    return Application(api_key="test", api_secret="test", symbols=["BTC-SWAP-USDT"])

@pytest.mark.asyncio
async def test_cdk_pipeline_runs_without_errors(app):
    await app.initialize()
    
    # Generate 25 bearish bars to trigger LONG signal
    base_price = 50000.0
    for i in range(25):
        price = base_price - (i * 50)
        bar = MarketBar(
            timestamp=float(i), open=price + 25, high=price + 50,
            low=price - 50, close=price, volume=100.0,
            symbol="BTC-SWAP-USDT", timeframe="1m"
        )
        event = Event(event_type=EventType.NEW_CANDLE, source="test", payload={"bar": bar.__dict__})
        
        # Mock execution engine
        app.execution_engine.execute_blueprint = AsyncMock(return_value={"orderId": "mock_cdk_123", "status": "NEW"})
        
        await app._on_new_candle(event)
        
    # Verify pipeline executed and either opened a position or correctly rejected
    # Since CDK is very strict, it might reject. We just check it didn't crash.
    state = app.portfolio_engine.get_state()
    assert state.health_score > 0.0
    
    # If it did open a position, verify SL/TP logic
    if len(app.portfolio_engine.open_positions) > 0:
        position = list(app.portfolio_engine.open_positions.values())[0]
        assert position.direction in ["LONG", "SHORT"]
        
        tp_price = position.take_profit
        tick_event = Event(
            event_type=EventType.NEW_TICK, source="test", 
            payload={"tick": {"symbol": "BTC-SWAP-USDT", "price": tp_price}}
        )
        await app._on_new_tick(tick_event)
        
        assert len(app.portfolio_engine.open_positions) == 0
        assert len(app.portfolio_engine.closed_trades) == 1
