
"""Institutional SMT Intelligence Layer - Rewrite of Pine f_smt_* per Book II 2.27"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import math

@dataclass(frozen=True)
class SMTSignal:
    symbol: str
    paired_symbol: str
    direction: int  # 1 bullish divergence, -1 bearish
    strength: float  # 0-1
    correlation: float
    age_bars: int
    confidence: float
    timestamp: float

@dataclass
class SMTState:
    pivot_highs: Dict[str, List[float]] = field(default_factory=dict)
    pivot_lows: Dict[str, List[float]] = field(default_factory=dict)
    active_signals: List[SMTSignal] = field(default_factory=list)
    correlation_cache: Dict[Tuple[str,str], float] = field(default_factory=dict)

def _rolling_correlation(a: List[float], b: List[float], length: int) -> float:
    if len(a) < length or len(b) < length:
        return 0.0
    a_slice = a[-length:]
    b_slice = b[-length:]
    mean_a = sum(a_slice)/length
    mean_b = sum(b_slice)/length
    num = sum((x-mean_a)*(y-mean_b) for x,y in zip(a_slice, b_slice))
    den_a = math.sqrt(sum((x-mean_a)**2 for x in a_slice))
    den_b = math.sqrt(sum((y-mean_b)**2 for y in b_slice))
    if den_a == 0 or den_b == 0:
        return 0.0
    return max(-1.0, min(1.0, num/(den_a*den_b)))

def detect_smt_divergence(
    symbol: str,
    highs: List[float],
    lows: List[float],
    paired_symbol: str,
    paired_highs: List[float],
    paired_lows: List[float],
    state: SMTState,
    corr_len: int = 120,
    corr_min: float = 0.60,
    min_score: float = 0.35,
    piv_lb: int = 5,
    max_age: int = 10,
    decay_rate: float = 0.985,
    inverse: bool = False
) -> Tuple[List[SMTSignal], SMTState]:
    """
    Implements Pine SMT logic:
    - Detect pivot highs/lows with piv_lb
    - Check if main makes higher high but paired makes lower high (bearish SMT) etc.
    - Correlation filter
    - Decay and lifecycle
    """
    if len(highs) < piv_lb*2+5 or len(paired_highs) < piv_lb*2+5:
        return [], state
    
    corr = _rolling_correlation(highs, paired_highs, corr_len)
    if inverse:
        corr = -corr
    
    # Absolute correlation check per Pine smt_corr_min
    if abs(corr) < corr_min:
        return [], state
    
    # Pivot detection simplified: last pivot vs previous
    # High pivot detection
    def get_last_two_pivots(arr: List[float], lb: int) -> Tuple[float,float,int,int]:
        # Find last two local highs
        pivots = []
        for i in range(len(arr)-lb-1, lb, -1):
            if i-lb <0 or i+lb >= len(arr): continue
            window = arr[i-lb:i+lb+1]
            if arr[i] == max(window):
                pivots.append((arr[i], i))
                if len(pivots)>=2:
                    break
        if len(pivots)>=2:
            return pivots[0][0], pivots[1][0], pivots[0][1], pivots[1][1]
        return 0,0,0,0
    
    h1,h2,_,_ = get_last_two_pivots(highs, piv_lb)
    ph1,ph2,_,_ = get_last_two_pivots(paired_highs, piv_lb)
    
    l1,l2,_,_ = get_last_two_pivots([-x for x in lows], piv_lb)
    l1=-l1; l2=-l2
    pl1,pl2,_,_ = get_last_two_pivots([-x for x in paired_lows], piv_lb)
    pl1=-pl1; pl2=-pl2
    
    signals = []
    now_ts = 0 # will be set by caller
    
    # Bullish SMT: main makes lower low, paired makes higher low
    if l1 < l2 and pl1 > pl2 and l1>0 and l2>0:
        strength = min(1.0, abs(l1-l2)/ (abs(l2)*0.01 + 1e-9) )  # simplified strength
        if strength >= min_score:
            signals.append(SMTSignal(
                symbol=symbol, paired_symbol=paired_symbol, direction=1,
                strength=strength, correlation=corr, age_bars=0, confidence=abs(corr), timestamp=now_ts
            ))
    
    # Bearish SMT: main makes higher high, paired makes lower high
    if h1 > h2 and ph1 < ph2 and h1>0:
        strength = min(1.0, abs(h1-h2)/ (abs(h2)*0.01 + 1e-9))
        if strength >= min_score:
            signals.append(SMTSignal(
                symbol=symbol, paired_symbol=paired_symbol, direction=-1,
                strength=strength, correlation=corr, age_bars=0, confidence=abs(corr), timestamp=now_ts
            ))
    
    # Apply decay to old signals
    new_active = []
    for s in state.active_signals:
        if s.age_bars < 80: # smt_event_max_age
            decayed_strength = s.strength * (decay_rate ** s.age_bars)
            if decayed_strength >= min_score*0.5:
                new_active.append(s)
    
    new_active.extend(signals)
    state.active_signals = new_active
    state.correlation_cache[(symbol, paired_symbol)] = corr
    
    return signals, state

