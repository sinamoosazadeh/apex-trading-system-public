
"""Institutional Order Flow Intelligence - CVD, Delta, Absorption per Book I 5.20"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import math

@dataclass(frozen=True)
class OrderFlowSignal:
    delta: float
    cum_delta: float
    absorption_score: float
    stacked_imbalance: float
    confidence: float

def calculate_cvd(volumes: List[float], closes: List[float], opens: List[float]) -> Tuple[float,float]:
    """Cumulative Volume Delta - simplified from Pine roll_delta, cum_delta_bias"""
    if len(volumes) < 2:
        return 0.0, 0.0
    deltas = []
    for i in range(1, len(volumes)):
        if closes[i] > opens[i]:
            deltas.append(volumes[i])
        elif closes[i] < opens[i]:
            deltas.append(-volumes[i])
        else:
            deltas.append(0.0)
    roll_delta = sum(deltas[-20:]) if len(deltas)>=20 else sum(deltas)
    cum_delta = sum(deltas)
    return roll_delta, cum_delta

def detect_absorption(bars_high: List[float], bars_low: List[float], bars_vol: List[float], delta: float) -> float:
    """Absorption: high volume but small price movement"""
    if len(bars_high) < 5:
        return 0.0
    range_last = bars_high[-1] - bars_low[-1]
    avg_range = sum(h-l for h,l in zip(bars_high[-10:], bars_low[-10:]))/10 if len(bars_high)>=10 else range_last+1e-9
    vol_last = bars_vol[-1]
    avg_vol = sum(bars_vol[-10:])/10 if len(bars_vol)>=10 else vol_last+1e-9
    if avg_range == 0 or avg_vol == 0:
        return 0.0
    # High vol + low range = absorption
    vol_ratio = vol_last / avg_vol
    range_ratio = range_last / avg_range
    if vol_ratio > 1.5 and range_ratio < 0.7:
        return min(1.0, (vol_ratio-1.5)*range_ratio)
    return 0.0

def order_flow_engine(
    highs: List[float], lows: List[float], closes: List[float], opens: List[float], volumes: List[float]
) -> OrderFlowSignal:
    roll_delta, cum_delta = calculate_cvd(volumes, closes, opens)
    absorption = detect_absorption(highs, lows, volumes, roll_delta)
    # Stacked imbalance: consecutive delta same direction
    _, cum = calculate_cvd(volumes, closes, opens)
    stacked = 1.0 if abs(roll_delta) > abs(cum)*0.3 else 0.0
    confidence = min(1.0, (abs(roll_delta)/(sum(volumes[-20:])+1e-9))*5)
    return OrderFlowSignal(delta=roll_delta, cum_delta=cum, absorption_score=absorption, stacked_imbalance=stacked, confidence=confidence)


# --- Compatibility layer for existing tests ---
class OrderFlowEngine:
    """Wrapper for backward compat with tests"""
    def __init__(self):
        pass
    
    def calculate_delta(self, volumes, closes, opens):
        roll, cum = calculate_cvd(volumes, closes, opens)
        return roll
    
    def calculate_cvd(self, volumes, closes, opens):
        return calculate_cvd(volumes, closes, opens)
    
    def detect_absorption(self, highs, lows, vols, delta):
        return detect_absorption(highs, lows, vols, delta)
    
    def analyze(self, highs, lows, closes, opens, volumes):
        return order_flow_engine(highs, lows, closes, opens, volumes)

# Also for test: book imbalance
def calculate_book_imbalance(bid_vol, ask_vol):
    total = bid_vol + ask_vol + 1e-9
    return (bid_vol - ask_vol) / total
