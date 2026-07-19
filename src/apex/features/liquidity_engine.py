
"""Liquidity Intelligence Engine - Sweep, Pool, Harvest per Book I"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

@dataclass(frozen=True)
class LiquiditySweep:
    direction: int  # 1 bullish sweep (sell side), -1 bearish sweep (buy side)
    swept_level: float
    strength: float
    confidence: float

def detect_liquidity_sweep(highs: List[float], lows: List[float], closes: List[float], atr: float, lookback: int = 50) -> List[LiquiditySweep]:
    """Detect liquidity sweep: price takes out recent high/low then reverses"""
    if len(highs) < lookback+5:
        return []
    sweeps = []
    recent_high = max(highs[-lookback:-1])
    recent_low = min(lows[-lookback:-1])
    curr_high = highs[-1]
    curr_low = lows[-1]
    curr_close = closes[-1]
    
    # Buy side sweep (bearish): takes out high then closes below
    if curr_high > recent_high and curr_close < recent_high:
        strength = min(1.0, (curr_high - recent_high)/(atr+1e-9))
        if strength > 0.2:
            sweeps.append(LiquiditySweep(direction=-1, swept_level=recent_high, strength=strength, confidence=strength*0.8))
    
    # Sell side sweep (bullish): takes out low then closes above
    if curr_low < recent_low and curr_close > recent_low:
        strength = min(1.0, (recent_low - curr_low)/(atr+1e-9))
        if strength > 0.2:
            sweeps.append(LiquiditySweep(direction=1, swept_level=recent_low, strength=strength, confidence=strength*0.8))
    
    return sweeps

def liquidity_score(sweeps: List[LiquiditySweep], order_flow_absorption: float) -> float:
    if not sweeps:
        return 0.0
    return min(1.0, sum(s.strength for s in sweeps)/len(sweeps) + order_flow_absorption*0.3)

