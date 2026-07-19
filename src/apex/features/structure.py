"""Institutional Market Structure, Order Blocks, FVG, and Liquidity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from ..domain.market import MarketBar
from .indicators import clamp

@dataclass(frozen=True)
class StructureState:
    last_ph: float = 0.0
    last_pl: float = 0.0
    prev_ph: float = 0.0
    prev_pl: float = 0.0
    trend_dir: int = 0
    bos_up: bool = False
    bos_dn: bool = False
    choch_up: bool = False
    choch_dn: bool = False
    sweep_high: bool = False
    sweep_low: bool = False
    equal_highs: bool = False
    equal_lows: bool = False

@dataclass(frozen=True)
class OrderBlock:
    top: float
    bot: float
    confidence: float
    quality: float
    born_index: int

@dataclass(frozen=True)
class FairValueGap:
    top: float
    bot: float
    confidence: float

def detect_pivots(highs: Sequence[float], lows: Sequence[float], left: int, right: int):
    if len(highs) < left + right + 1:
        return None, None
    idx = len(highs) - 1 - right
    if idx < left:
        return None, None
    pivot_high = highs[idx]
    pivot_low = lows[idx]
    is_ph = True
    is_pl = True
    for i in range(idx - left, idx + right + 1):
        if i == idx: continue
        if highs[i] >= pivot_high: is_ph = False
        if lows[i] <= pivot_low: is_pl = False
    return (pivot_high if is_ph else None), (pivot_low if is_pl else None)

def update_structure(state: StructureState, highs, lows, closes, atr, pivot_lb=8, eq_tol=0.10, disp_atr=1.20):
    ph, pl = detect_pivots(highs, lows, pivot_lb, pivot_lb)
    
    last_ph = state.last_ph
    last_pl = state.last_pl
    prev_ph = state.prev_ph
    prev_pl = state.prev_pl
    trend_dir = state.trend_dir
    bos_up, bos_dn = False, False
    choch_up, choch_dn = False, False
    
    if ph is not None:
        prev_ph = last_ph
        last_ph = ph
    if pl is not None:
        prev_pl = last_pl
        last_pl = pl
        
    # Equal Highs/Lows Detection
    equal_highs = False
    equal_lows = False
    if last_ph > 0 and prev_ph > 0 and atr > 0:
        if abs(last_ph - prev_ph) <= atr * eq_tol:
            equal_highs = True
    if last_pl > 0 and prev_pl > 0 and atr > 0:
        if abs(last_pl - prev_pl) <= atr * eq_tol:
            equal_lows = True
            
    # Liquidity Sweeps
    sweep_high = False
    sweep_low = False
    close = closes[-1]
    high = highs[-1]
    low = lows[-1]
    
    if last_ph > 0 and high > last_ph and close < last_ph:
        sweep_high = True
    if last_pl > 0 and low < last_pl and close > last_pl:
        sweep_low = True

    # BOS / CHOCH Logic
    prev_close = closes[-2] if len(closes) > 1 else close
    if ph is not None and ph > 0 and close > ph and prev_close <= ph:
        if trend_dir == -1:
            choch_up = True
        else:
            bos_up = True
        trend_dir = 1
        
    elif pl is not None and pl > 0 and close < pl and prev_close >= pl:
        if trend_dir == 1:
            choch_dn = True
        else:
            bos_dn = True
        trend_dir = -1
        
    return StructureState(
        last_ph=last_ph, last_pl=last_pl, prev_ph=prev_ph, prev_pl=prev_pl,
        trend_dir=trend_dir, bos_up=bos_up, bos_dn=bos_dn,
        choch_up=choch_up, choch_dn=choch_dn,
        sweep_high=sweep_high, sweep_low=sweep_low,
        equal_highs=equal_highs, equal_lows=equal_lows
    )

def detect_order_blocks(bars: Sequence[MarketBar], bos_up: bool, bos_dn: bool, max_lookback: int = 5):
    obs = []
    if bos_up:
        for i in range(1, min(len(bars), max_lookback)):
            if bars[i].close < bars[i].open:
                obs.append(OrderBlock(top=bars[i].high, bot=bars[i].low, confidence=0.8, quality=0.8, born_index=i))
                break
    if bos_dn:
        for i in range(1, min(len(bars), max_lookback)):
            if bars[i].close > bars[i].open:
                obs.append(OrderBlock(top=bars[i].high, bot=bars[i].low, confidence=0.8, quality=0.8, born_index=i))
                break
    return obs

def detect_fvgs(bars: Sequence[MarketBar]):
    if len(bars) < 3: return None, None
    bull_fvg = None
    bear_fvg = None
    if bars[-1].low > bars[-3].high:
        bull_fvg = FairValueGap(top=bars[-1].low, bot=bars[-3].high, confidence=0.8)
    if bars[-1].high < bars[-3].low:
        bear_fvg = FairValueGap(top=bars[-3].low, bot=bars[-1].high, confidence=0.8)
    return bull_fvg, bear_fvg
