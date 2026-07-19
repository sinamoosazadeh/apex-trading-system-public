"""Enumerations for type-safe business logic."""
from __future__ import annotations

from enum import Enum

class Direction(Enum):
    LONG = 1
    SHORT = -1
    FLAT = 0

class OrderStatus(Enum):
    CREATED = "created"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class EventType(Enum):
    NEW_CANDLE = "new_candle"
    NEW_TICK = "new_tick"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
