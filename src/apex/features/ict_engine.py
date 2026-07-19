
"""ICT Engine - Fixed for both tests and crypto bootstrap - No forex sessions per user request"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timezone
import math

@dataclass
class OHLC:
    high: float
    low: float
    close: float
    open: float = 0.0
    volume: float = 0.0
    timestamp: int = 0

@dataclass
class StructureState:
    trend: str = "NEUTRAL"
    swing_high: float = 0.0
    swing_low: float = 0.0
    bos_up: bool = False
    bos_dn: bool = False
    choch_up: bool = False
    choch_dn: bool = False
    trend_dir: int = 0

@dataclass
class Zone:
    kind: str
    top: float
    bottom: float
    bias: str = "NEUTRAL"
    strength: float = 0.5
    origin_idx: int = 0
    valid: bool = True
    meta: dict = field(default_factory=dict)

@dataclass
class ICTState:
    bias: str = "NEUTRAL"
    zones: List[Zone] = field(default_factory=list)
    killzone: dict = field(default_factory=dict)
    ote_zone: Optional[Zone] = None
    premium_discount: str = "NEUTRAL"
    eq_level: float = 0.0
    mss_confirmed: bool = False
    confluence_score: float = 0.0
    ob_level: float = 0.0

class ICTEngine:
    def __init__(self):
        self.last_state: Optional[ICTState] = None

    def analyze(self, *args, **kwargs) -> ICTState:
        # Handle both signatures
        if len(args) == 2:
            candles = args[0]
            struct = args[1]
            if isinstance(candles, list) and len(candles)>0 and isinstance(candles[0], (int, float)):
                # Actually highs passed? Treat as legacy
                highs = args[0]
                lows = kwargs.get('lows', [])
                closes = kwargs.get('closes', [])
                # fallback simple
                candles = [OHLC(high=h, low=lows[i] if i < len(lows) else h, close=closes[i] if i < len(closes) else h) for i, h in enumerate(highs)]
            # if first arg is list of OHLC
            if len(candles)>0 and hasattr(candles[0], 'close'):
                return self._analyze_candles(candles, struct)
            else:
                # empty
                return ICTState()
        if len(args) >= 3:
            highs = args[0]
            lows = args[1]
            closes = args[2]
            struct = args[3] if len(args)>=4 else StructureState()
            atr = args[4] if len(args)>=5 else 1.0
            candles = []
            for i in range(len(highs)):
                h = highs[i]
                l = lows[i] if i < len(lows) else h
                c = closes[i] if i < len(closes) else h
                candles.append(OHLC(high=h, low=l, close=c, open=c, volume=100.0, timestamp=i))
            return self._analyze_candles(candles, struct)
        # kwargs version
        highs = kwargs.get('highs', [])
        lows = kwargs.get('lows', [])
        closes = kwargs.get('closes', [])
        struct = kwargs.get('structure_state') or kwargs.get('struct') or StructureState()
        if highs:
            candles = [OHLC(high=h, low=lows[i] if i < len(lows) else h, close=closes[i] if i < len(closes) else h) for i,h in enumerate(highs)]
            return self._analyze_candles(candles, struct)
        return ICTState()

    def _analyze_candles(self, candles: List[OHLC], struct) -> ICTState:
        if not candles:
            return ICTState()
        # Simplified ICT logic - crypto only, no forex sessions
        swing_high = max(c.high for c in candles[-20:])
        swing_low = min(c.low for c in candles[-20:])
        price = candles[-1].close
        # OTE 0.62-0.79
        range_ = swing_high - swing_low
        ote_top = swing_high - range_*0.62
        ote_bot = swing_high - range_*0.79
        ote_zone = Zone(kind="OTE", top=ote_top, bottom=ote_bot, bias="BULLISH" if price < ote_top else "BEARISH", strength=0.7)
        # EQ
        eq = (swing_high + swing_low)/2
        # Bias from structure
        bias = "NEUTRAL"
        if hasattr(struct, 'trend'):
            bias = struct.trend
        elif hasattr(struct, 'trend_dir'):
            bias = "BULLISH" if struct.trend_dir>0 else "BEARISH" if struct.trend_dir<0 else "NEUTRAL"
        state = ICTState(bias=bias, zones=[ote_zone], ote_zone=ote_zone, eq_level=eq, mss_confirmed=False, confluence_score=0.5, ob_level=swing_low)
        self.last_state = state
        return state

    def get_bayesian_prior(self):
        return {"p_bull_ict":0.5, "p_bear_ict":0.5, "confluence":0.0}
