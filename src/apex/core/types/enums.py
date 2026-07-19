
"""Enums - Full implementation per blueprints - Fixed"""
from __future__ import annotations
from enum import Enum

class EventType(str, Enum):
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    NEW_CANDLE = "new_candle"
    NEW_TICK = "new_tick"
    ORDERBOOK_UPDATE = "orderbook_update"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    ORDER_CANCELLED = "order_cancelled"
    KILL_SWITCH = "kill_switch"
    RISK_ALERT = "risk_alert"
    SIGNAL_GENERATED = "signal_generated"
    TRADE_CLOSED = "trade_closed"

class OrderStatus(str, Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"

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
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
