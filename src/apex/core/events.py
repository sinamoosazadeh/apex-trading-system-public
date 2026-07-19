"""Event system - immutable, versioned, traceable."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from collections import defaultdict
import asyncio
import uuid
from datetime import datetime, timezone
from .types.enums import EventType

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def generate_id() -> str:
    return str(uuid.uuid4())

@dataclass(frozen=True)
class Event:
    """Immutable event object."""
    id: str = field(default_factory=generate_id)
    event_type: EventType = EventType.SYSTEM_STARTUP
    timestamp: str = field(default_factory=lambda: utc_now().isoformat())
    source: str = ""
    destination: str = ""
    priority: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    correlation_id: str = ""
    version: str = "1.0.0"

EventHandler = Callable[[Event], Awaitable[None]]

class EventBus:
    """In-memory async event bus with priority queues."""
    
    def __init__(self, max_history: int = 10000) -> None:
        self._handlers: dict[EventType, list[tuple[int, EventHandler]]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history: int = max_history

    def subscribe(self, event_type: EventType, handler: EventHandler, priority: int = 0) -> None:
        self._handlers[event_type].append((priority, handler))
        self._handlers[event_type].sort(key=lambda x: -x[0])

    async def publish(self, event: Event) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return

        tasks = [handler(event) for _, handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
