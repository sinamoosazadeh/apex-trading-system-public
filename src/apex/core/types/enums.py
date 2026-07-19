
"""Enums - Full implementation per blueprints"""
from __future__ import annotations
from enum import Enum

class EventType(str, Enum):
    NEW_CANDLE = "new_candle"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    KILL_SWITCH = "kill_switch"
    RISK_ALERT = "risk_alert"

class OrderStatus(str, Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

class DecisionType(str, Enum):
    TRADE = "TRADE"
    NO_TRADE = "NO_TRADE"
    WAIT = "WAIT"

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"

class RegimeType(str, Enum):
    STRONG_BULL = "STRONG_BULL"
    STRONG_BEAR = "STRONG_BEAR"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    TRENDING = "TRENDING"
