"""Tests for Toobit WebSocket Client - Phase 9."""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from apex.infrastructure.exchanges.toobit_ws import ToobitWebSocketClient
from apex.core.events import EventBus
from apex.core.types.enums import EventType

@pytest.fixture
def event_bus():
    return EventBus()

@pytest.fixture
def ws_client(event_bus):
    return ToobitWebSocketClient(event_bus, ["BTC-SWAP-USDT"])

@pytest.mark.asyncio
async def test_process_trade_message(ws_client, event_bus):
    received_events = []
    
    async def handler(event):
        received_events.append(event)
        
    event_bus.subscribe(EventType.NEW_TICK, handler)
    
    mock_msg = {
        "symbol": "BTC-SWAP-USDT",
        "topic": "trade",
        "data": [
            {
                "v": "1291465821801168896",
                "t": 1668690723096,
                "p": "399",
                "q": "1.5",
                "m": False  # False means Buy side
            }
        ]
    }
    
    await ws_client._process_message(mock_msg)
    
    assert len(received_events) == 1
    tick_data = received_events[0].payload["tick"]
    assert tick_data["symbol"] == "BTC-SWAP-USDT"
    assert tick_data["price"] == 399.0
    assert tick_data["volume"] == 1.5
    assert tick_data["side"] == "buy"

@pytest.mark.asyncio
async def test_process_kline_message(ws_client, event_bus):
    received_events = []
    
    async def handler(event):
        received_events.append(event)
        
    event_bus.subscribe(EventType.NEW_CANDLE, handler)
    
    mock_msg = {
        "symbol": "BTC-SWAP-USDT",
        "topic": "kline",
        "params": {"klineType": "1m"},
        "data": [
            {
                "t": 1668753840000,
                "s": "BTC-SWAP-USDT",
                "c": "445.5",
                "h": "446.0",
                "l": "444.0",
                "o": "444.2",
                "v": "10.5"
            }
        ]
    }
    
    await ws_client._process_message(mock_msg)
    
    assert len(received_events) == 1
    bar_data = received_events[0].payload["bar"]
    assert bar_data["symbol"] == "BTC-SWAP-USDT"
    assert bar_data["open"] == 444.2
    assert bar_data["high"] == 446.0
    assert bar_data["close"] == 445.5
    assert bar_data["volume"] == 10.5
    assert bar_data["timeframe"] == "1m"

@pytest.mark.asyncio
async def test_pong_message_ignored(ws_client, event_bus):
    received_events = []
    
    async def handler(event):
        received_events.append(event)
        
    event_bus.subscribe(EventType.NEW_TICK, handler)
    event_bus.subscribe(EventType.NEW_CANDLE, handler)
    
    mock_pong = {"pong": 1535975085052}
    await ws_client._process_message(mock_pong)
    
    assert len(received_events) == 0

@pytest.mark.asyncio
async def test_heartbeat_sends_ping(ws_client):
    ws_client._running = True  # <--- اصلاح این خط
    ws_client._ws = MagicMock()
    ws_client._ws.closed = False
    ws_client._ws.send = AsyncMock()
    
    task = asyncio.create_task(ws_client._heartbeat_loop())
    await asyncio.sleep(0.1)  # Allow it to execute
    task.cancel()
    
    ws_client._ws.send.assert_called_once()
    sent_msg = json.loads(ws_client._ws.send.call_args[0][0])
    assert "ping" in sent_msg
