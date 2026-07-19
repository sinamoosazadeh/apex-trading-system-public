"""Institutional SMT (Smart Money Technique) Intelligence Engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import math

from .indicators import clamp
from .structure import detect_pivots

# SMT Type IDs
SMT_NONE = 0
SMT_CLASSIC = 1
SMT_HIDDEN = 2
SMT_REVERSE = 3
SMT_SIMPLE = 4
SMT_LIQUIDITY = 5
SMT_STOP_HUNT = 6
SMT_FVG = 7
SMT_ORDER_BLOCK = 8
SMT_CHOCH = 9
SMT_BOS = 10
SMT_INDUCEMENT = 11
SMT_PREMIUM = 12
SMT_DISCOUNT = 13
SMT_INTERNAL = 14
SMT_EXTERNAL = 15

@dataclass(frozen=True)
class SMTPivots:
    """Pivot data package for SMT evaluation."""
    lp: float
    pp: float
    lh: float
    phh: float
    pl_age: int
    ph_age: int

def extract_smt_pivots(highs: Sequence[float], lows: Sequence[float], pivot_lb: int = 5) -> SMTPivots:
    """Extract required pivots for SMT analysis."""
    ph, pl = detect_pivots(highs, lows, pivot_lb, pivot_lb)
    
    if not ph and not pl:
        return SMTPivots(0, 0, 0, 0, 999, 999)
        
    return SMTPivots(
        lp=lows[-1] if not pl else pl,
        pp=lows[-2] if len(lows) > 1 else 0,
        lh=highs[-1] if not ph else ph,
        phh=highs[-2] if len(highs) > 1 else 0,
        pl_age=1,
        ph_age=1
    )

def evaluate_smt(
    enabled: bool,
    corr_q: float,
    chart_pivots: SMTPivots,
    ref_pivots: SMTPivots,
    context_scores: dict[str, float],
    max_age: int = 10,
    decay_rate: float = 0.985,
    entry_window: int = 8,
    regime_mult: float = 1.0
) -> tuple[float, float, int, int]:
    """
    Evaluate SMT divergence and return (bull_score, bear_score, bull_type_id, bear_type_id).
    Implements Book II, 7.12 - 15 SMT Types.
    """
    if not enabled or corr_q <= 0:
        return 0.0, 0.0, SMT_NONE, SMT_NONE

    c_lp, c_pp, c_lh, c_phh, c_pl_age, c_ph_age = (
        chart_pivots.lp, chart_pivots.pp, chart_pivots.lh, chart_pivots.phh,
        chart_pivots.pl_age, chart_pivots.ph_age
    )
    
    r_lp, r_pp, r_lh, r_phh, r_pl_age, r_ph_age = (
        ref_pivots.lp, ref_pivots.pp, ref_pivots.lh, ref_pivots.phh,
        ref_pivots.pl_age, ref_pivots.ph_age
    )

    valid_bull = all(v > 0 for v in [c_lp, c_pp, r_lp, r_pp]) and c_pl_age <= max_age and r_pl_age <= max_age
    valid_bear = all(v > 0 for v in [c_lh, c_phh, r_lh, r_phh]) and c_ph_age <= max_age and r_ph_age <= max_age

    # Basic Divergence Detection
    c_down = c_lp < c_pp
    r_down = r_lp < r_pp
    classic_bull = valid_bull and ((c_down and not r_down) or (not c_down and r_down))

    c_up = c_lh > c_phh
    r_up = r_lh > r_phh
    classic_bear = valid_bear and ((c_up and not r_up) or (not c_up and r_up))

    simple_bull = classic_bull
    simple_bear = classic_bear

    if not simple_bull and not simple_bear:
        return 0.0, 0.0, SMT_NONE, SMT_NONE

    # Context Scores
    liq_l = context_scores.get("liq_l", 0.0)
    liq_s = context_scores.get("liq_s", 0.0)
    sweep_l = context_scores.get("sweep_l", 0.0)
    sweep_s = context_scores.get("sweep_s", 0.0)
    struct_l = context_scores.get("struct_l", 0.0)
    struct_s = context_scores.get("struct_s", 0.0)
    trend_l = context_scores.get("trend_l", 0.0)
    trend_s = context_scores.get("trend_s", 0.0)
    stop_l = context_scores.get("stop_l", 0.0)
    stop_s = context_scores.get("stop_s", 0.0)
    fvg_l = context_scores.get("fvg_l", 0.0)
    fvg_s = context_scores.get("fvg_s", 0.0)
    ob_l = context_scores.get("ob_l", 0.0)
    ob_s = context_scores.get("ob_s", 0.0)
    pd_l = context_scores.get("pd_l", 0.0)
    pd_s = context_scores.get("pd_s", 0.0)

    # Type Classification (15 Types)
    liq_bull = simple_bull and sweep_l > 0.35
    liq_bear = simple_bear and sweep_s > 0.35

    stop_bull = simple_bull and stop_l > 0.5
    stop_bear = simple_bear and stop_s > 0.5

    hidden_bull = valid_bull and not c_down and r_down and trend_l > 0.35
    hidden_bear = valid_bear and not c_up and r_up and trend_s > 0.35

    fvg_smt_bull = simple_bull and fvg_l > 0.35
    fvg_smt_bear = simple_bear and fvg_s > 0.35

    ob_smt_bull = simple_bull and ob_l > 0.35
    ob_smt_bear = simple_bear and ob_s > 0.35

    choch_bull = simple_bull and struct_l > 0.55
    choch_bear = simple_bear and struct_s > 0.55

    bos_bull = simple_bull and struct_l > 0.35
    bos_bear = simple_bear and struct_s > 0.35

    ind_bull = simple_bull and liq_l > 0.60 and struct_l > 0.25
    ind_bear = simple_bear and liq_s > 0.60 and struct_s > 0.25

    disc_bull = simple_bull and pd_l > 0.45
    prem_bear = simple_bear and pd_s > 0.45

    # Type Scoring
    bull_type_score = 0.0
    bull_type_score += classic_bull * 0.16
    bull_type_score += hidden_bull * 0.08
    bull_type_score += liq_bull * 0.11
    bull_type_score += stop_bull * 0.09
    bull_type_score += fvg_smt_bull * 0.08
    bull_type_score += ob_smt_bull * 0.08
    bull_type_score += choch_bull * 0.08
    bull_type_score += bos_bull * 0.05
    bull_type_score += ind_bull * 0.06
    bull_type_score += disc_bull * 0.05
    bull_type_score = clamp(bull_type_score, 0.0, 1.0)

    bear_type_score = 0.0
    bear_type_score += classic_bear * 0.16
    bear_type_score += hidden_bear * 0.08
    bear_type_score += liq_bear * 0.11
    bear_type_score += stop_bear * 0.09
    bear_type_score += fvg_smt_bear * 0.08
    bear_type_score += ob_smt_bear * 0.08
    bear_type_score += choch_bear * 0.08
    bear_type_score += bos_bear * 0.05
    bear_type_score += ind_bear * 0.06
    bear_type_score += prem_bear * 0.05
    bear_type_score = clamp(bear_type_score, 0.0, 1.0)

    # Probability Calculation
    prob_bull = (
        corr_q * 0.15 + liq_l * 0.20 + sweep_l * 0.15 + struct_l * 0.15 +
        fvg_l * 0.10 + ob_l * 0.10 + trend_l * 0.05 + 0.05
    )
    prob_bear = (
        corr_q * 0.15 + liq_s * 0.20 + sweep_s * 0.15 + struct_s * 0.15 +
        fvg_s * 0.10 + ob_s * 0.10 + trend_s * 0.05 + 0.05
    )

    age_bull = min(c_pl_age, r_pl_age)
    age_bear = min(c_ph_age, r_ph_age)
    dec_bull = decay_rate ** age_bull
    dec_bear = decay_rate ** age_bear
    win_bull = 1.08 if age_bull <= entry_window else 0.92
    win_bear = 1.08 if age_bear <= entry_window else 0.92

    candle_l = context_scores.get("candle_l", 0.0)
    candle_s = context_scores.get("candle_s", 0.0)

    bull_score = clamp(
        (prob_bull * 0.68 + bull_type_score * 0.32) *
        (0.70 + candle_l * 0.30) * dec_bull * win_bull * regime_mult,
        0.0, 1.0
    ) if simple_bull else 0.0

    bear_score = clamp(
        (prob_bear * 0.68 + bear_type_score * 0.32) *
        (0.70 + candle_s * 0.30) * dec_bear * win_bear * regime_mult,
        0.0, 1.0
    ) if simple_bear else 0.0

    # Type ID Determination
    bull_type_id = SMT_NONE
    if stop_bull: bull_type_id = SMT_STOP_HUNT
    elif liq_bull: bull_type_id = SMT_LIQUIDITY
    elif fvg_smt_bull: bull_type_id = SMT_FVG
    elif ob_smt_bull: bull_type_id = SMT_ORDER_BLOCK
    elif choch_bull: bull_type_id = SMT_CHOCH
    elif bos_bull: bull_type_id = SMT_BOS
    elif ind_bull: bull_type_id = SMT_INDUCEMENT
    elif disc_bull: bull_type_id = SMT_DISCOUNT
    elif hidden_bull: bull_type_id = SMT_HIDDEN
    elif classic_bull: bull_type_id = SMT_CLASSIC
    elif simple_bull: bull_type_id = SMT_SIMPLE

    bear_type_id = SMT_NONE
    if stop_bear: bear_type_id = SMT_STOP_HUNT
    elif liq_bear: bear_type_id = SMT_LIQUIDITY
    elif fvg_smt_bear: bear_type_id = SMT_FVG
    elif ob_smt_bear: bear_type_id = SMT_ORDER_BLOCK
    elif choch_bear: bear_type_id = SMT_CHOCH
    elif bos_bear: bear_type_id = SMT_BOS
    elif ind_bear: bear_type_id = SMT_INDUCEMENT
    elif prem_bear: bear_type_id = SMT_PREMIUM
    elif hidden_bear: bear_type_id = SMT_HIDDEN
    elif classic_bear: bear_type_id = SMT_CLASSIC
    elif simple_bear: bear_type_id = SMT_SIMPLE

    return bull_score, bear_score, bull_type_id, bear_type_id
