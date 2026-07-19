"""Toobit WebSocket Client for real-time market data streams."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from ...domain.market import MarketBar, Tick
from ...core.events import Event, EventBus
from ...core.types.enums import EventType

log = logging.getLogger(__name__)

class ToobitWebSocketClient:
    """Manages WebSocket connection to Toobit."""

    BASE_URL = "wss://stream.toobit.com/quote/ws/v1"

    def __init__(self, event_bus: EventBus, symbols: list[str]) -> None:
        self.event_bus = event_bus
        self.symbols = symbols
        self._ws: Any = None
        self._running: bool = False
        self._reconnect_delay: float = 1.0

    async def connect(self) -> None:
        """Establish connection and start listening loop."""
        self._running = True
        
        # Wait until there is at least one symbol to subscribe to
        while self._running and not self.symbols:
            await asyncio.sleep(2.0)
            
        while self._running:
            try:
                log.info(f"Connecting to Toobit WebSocket: {self.BASE_URL}")
                async with websockets.connect(self.BASE_URL, ping_interval=None) as ws:
                    self._ws = ws
                    self._reconnect_delay = 1.0
                    
                    await self._subscribe_streams()
                    
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                    listen_task = asyncio.create_task(self._listen_loop())
                    
                    await listen_task
                    
                    heartbeat_task.cancel()
                    
            except (ConnectionClosed, ConnectionError, asyncio.TimeoutError) as e:
                if self._running:
                    log.warning(f"Toobit WS disconnected: {e}. Reconnecting in {self._reconnect_delay}s")
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, 60.0)
            except Exception as e:
                if self._running:
                    log.error(f"Unexpected WS error: {e}", exc_info=True)
                    await asyncio.sleep(5.0)
                
            finally:
                self._ws = None
                # Wait if symbols list became empty dynamically
                while self._running and not self.symbols:
                    await asyncio.sleep(2.0)

    async def disconnect(self) -> None:
        """Gracefully disconnect from WebSocket."""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

    async def _subscribe_streams(self) -> None:
        """Subscribe to required market data streams."""
        sym_str = ",".join(self.symbols)
        if not sym_str:
            return
            
        trade_msg = {
            "symbol": sym_str,
            "topic": "trade",
            "event": "sub",
            "params": {"binary": "false"}
        }
        await self._ws.send(json.dumps(trade_msg))
        
        kline_msg = {
            "symbol": sym_str,
            "topic": "kline_1m",
            "event": "sub",
            "params": {"binary": "false"}
        }
        await self._ws.send(json.dumps(kline_msg))
        log.info(f"Subscribed to trades and 1m klines for {self.symbols}")

    async def _heartbeat_loop(self) -> None:
        """Send periodic ping to keep connection alive."""
        while self._running:
            try:
                await asyncio.sleep(30.0)
                if self._ws:
                    ping_msg = {"ping": int(time.time() * 1000)}
                    await self._ws.send(json.dumps(ping_msg))
            except Exception:
                break

    async def _listen_loop(self) -> None:
        """Listen for incoming WebSocket messages."""
        async for raw_message in self._ws:
            try:
                data = json.loads(raw_message)
                await self._process_message(data)
            except json.JSONDecodeError:
                log.warning(f"Failed to decode WS message: {raw_message}")
            except Exception as e:
                log.error(f"Error processing WS message: {e}", exc_info=True)

    async def _process_message(self, data: dict[str, Any]) -> None:
        """Parse Toobit WS payload and publish domain events."""
        topic = data.get("topic")
        
        if "pong" in data or data.get("event") == "sub":
            return
            
        if not topic or "data" not in data:
            return

        symbol = data.get("symbol", "")
        payload_list = data.get("data", [])
        
        if topic == "trade":
            for item in payload_list:
                tick = Tick(
                    timestamp=int(item.get("t", 0)),
                    price=float(item.get("p", 0.0)),
                    volume=float(item.get("q", 0.0)),
                    side="sell" if item.get("m", False) else "buy",
                    symbol=symbol,
                    exchange="toobit"
                )
                await self.event_bus.publish(Event(
                    event_type=EventType.NEW_TICK,
                    source="toobit_ws",
                    payload={"tick": tick.__dict__}
                ))
                
        elif topic == "kline":
            for item in payload_list:
                open_time = int(item.get("t", 0))
                bar = MarketBar(
                    timestamp=open_time,
                    open=float(item.get("o", 0.0)),
                    high=float(item.get("h", 0.0)),
                    low=float(item.get("l", 0.0)),
                    close=float(item.get("c", 0.0)),
                    volume=float(item.get("v", 0.0)),
                    symbol=symbol,
                    exchange="toobit",
                    timeframe="1m"
                )
                await self.event_bus.publish(Event(
                    event_type=EventType.NEW_CANDLE,
                    source="toobit_ws",
                    payload={"bar": bar.__dict__}
                ))
