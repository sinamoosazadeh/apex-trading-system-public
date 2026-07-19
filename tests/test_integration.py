"""Integration test for the full APEX pipeline - Phase 12."""
import pytest
import asyncio
from apex.application.bootstrap import Application
from apex.core.events import EventBus, Event
from apex.core.types.enums import EventType
from apex.domain.market import MarketBar

@pytest.fixture
def app():
    return Application(api_key="test", api_secret="test", symbols=["BTC-SWAP-USDT"], initial_capital=200000.0)

@pytest.mark.asyncio
async def test_pipeline_processes_bars_without_crashing(app):
    await app.initialize()
    
    # Generate 25 bearish bars
    base_price = 50000.0
    for i in range(25):
        price = base_price - (i * 50)
        bar = MarketBar(
            timestamp=float(i), open=price + 25, high=price + 50,
            low=price - 50, close=price, volume=100.0,
            symbol="BTC-SWAP-USDT", timeframe="1m"
        )
        event = Event(event_type=EventType.NEW_CANDLE, source="test", payload={"bar": bar.__dict__})
        await app._on_new_candle(event)
        
    # The system should process all bars without throwing exceptions.
    # It may or may not open a position depending on complex institutional logic.
    # We just verify the pipeline didn't crash and health is nominal.
    state = app.portfolio_engine.get_state()
    assert state.health_score > 0.0
