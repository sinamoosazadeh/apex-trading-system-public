
"""SMT Engine - Compatible with Phase 13 tests + Production crypto pairs"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple

# Constants expected by tests
SMT_CLASSIC = "CLASSIC"
SMT_LIQUIDITY = "LIQUIDITY"
SMT_NONE = "NONE"

@dataclass(frozen=True)
class SMTPivots:
    lp: float  # last pivot low
    pp: float  # previous pivot low (for lows) OR logic for highs
    lh: float  # last high
    phh: float  # previous high
    pl_age: int = 0
    ph_age: int = 0

@dataclass(frozen=True)
class SMTSignal:
    symbol: str = ""
    paired_symbol: str = ""
    direction: int = 0
    strength: float = 0.0
    correlation: float = 0.0
    age_bars: int = 0
    confidence: float = 0.0
    timestamp: float = 0.0

@dataclass
class SMTState:
    pivot_highs: dict = None
    pivot_lows: dict = None
    active_signals: list = None
    correlation_cache: dict = None
    def __post_init__(self):
        if self.pivot_highs is None:
            self.pivot_highs = {}
        if self.pivot_lows is None:
            self.pivot_lows = {}
        if self.active_signals is None:
            self.active_signals = []
        if self.correlation_cache is None:
            self.correlation_cache = {}

def evaluate_smt(
    enabled: bool,
    corr_q: float,
    chart_pivots: SMTPivots,
    ref_pivots: SMTPivots,
    context_scores: Dict[str, float]
) -> Tuple[float, float, str, str]:
    """
    Evaluate SMT divergence.
    Returns: (bull_score, bear_score, bull_type, bear_type)
    Test expects:
    - Chart makes lower low (lp < pp) while Ref makes higher low (lp > pp) => bullish divergence
    - Bull type = CLASSIC or LIQUIDITY if sweep present
    """
    if not enabled:
        return 0.0, 0.0, SMT_NONE, SMT_NONE
    
    bull_score = 0.0
    bear_score = 0.0
    bull_type = SMT_NONE
    bear_type = SMT_NONE
    
    # Bullish divergence: chart LL, ref HL
    # chart_pivots.lp = 99, pp=100 => LL
    # ref_pivots.lp=102, pp=101 => HL
    if chart_pivots.lp < chart_pivots.pp and ref_pivots.lp > ref_pivots.pp:
        # Check correlation quality
        if corr_q >= 0.5:
            bull_score = corr_q * 0.8 + context_scores.get("liq_l", 0)*0.2
            # If sweep present, classify as LIQUIDITY else CLASSIC
            if context_scores.get("sweep_l", 0) > 0.35:
                bull_type = SMT_LIQUIDITY
            else:
                bull_type = SMT_CLASSIC
    
    # Bearish divergence: chart HH, ref LH
    # chart makes higher high, ref makes lower high
    if chart_pivots.lh > chart_pivots.phh and ref_pivots.lh < ref_pivots.phh:
        if corr_q >= 0.5:
            bear_score = corr_q * 0.8 + context_scores.get("liq_s", 0)*0.2
            if context_scores.get("sweep_s", 0) > 0.35:
                bear_type = SMT_LIQUIDITY
            else:
                bear_type = SMT_CLASSIC
    
    return bull_score, bear_score, bull_type, bear_type

def detect_smt_divergence(symbol, highs, lows, paired_symbol, paired_highs, paired_lows, state, corr_len=120, corr_min=0.60, min_score=0.35, piv_lb=5, max_age=10, decay_rate=0.985, inverse=False):
    """Production version for crypto pairs BTC vs alts"""
    import math
    if len(highs) < piv_lb*2+5 or len(paired_highs) < piv_lb*2+5:
        return [], state
    # Simplified correlation
    def corr(a,b,n):
        if len(a)<n or len(b)<n:
            return 0.0
        a_slice=a[-n:]
        b_slice=b[-n:]
        ma=sum(a_slice)/n
        mb=sum(b_slice)/n
        num=sum((x-ma)*(y-mb) for x,y in zip(a_slice,b_slice))
        den_a=math.sqrt(sum((x-ma)**2 for x in a_slice))
        den_b=math.sqrt(sum((y-mb)**2 for y in b_slice))
        if den_a==0 or den_b==0:
            return 0.0
        return max(-1.0, min(1.0, num/(den_a*den_b+1e-9)))
    c = corr(highs, paired_highs, min(corr_len, len(highs)))
    if abs(c) < corr_min:
        return [], state
    # Very simplified divergence for production
    signals=[]
    if len(highs)>=20 and len(lows)>=20:
        # bullish: main lower low, paired higher low
        if lows[-1] < min(lows[-20:-1]) and paired_lows[-1] > min(paired_lows[-20:-1]):
            signals.append(SMTSignal(symbol=symbol, paired_symbol=paired_symbol, direction=1, strength=0.6, correlation=c, confidence=abs(c)))
        if highs[-1] > max(highs[-20:-1]) and paired_highs[-1] < max(paired_highs[-20:-1]):
            signals.append(SMTSignal(symbol=symbol, paired_symbol=paired_symbol, direction=-1, strength=0.6, correlation=c, confidence=abs(c)))
    return signals, state
