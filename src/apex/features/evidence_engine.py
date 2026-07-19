
"""Evidence Engine - 13 Evidences + compute_all for crypto bootstrap + compatibility"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
import math

@dataclass
class EvidenceResult:
    long_score: float = 0.5
    short_score: float = 0.5
    confidence: float = 0.5
    name: str = ""

class EvidenceEngine:
    def __init__(self):
        self.weights = {
            "structure": 0.12, "liquidity": 0.10, "order_block": 0.10,
            "fvg": 0.08, "zone": 0.08, "smt": 0.07, "order_flow": 0.07,
            "trend": 0.08, "momentum": 0.07, "volatility": 0.05,
            "volume_profile": 0.05, "dna": 0.05, "kinematic": 0.08
        }
    
    def get_default_weights(self):
        return self.weights
    
    def compute_all(self, highs, lows, closes, opens, volumes, atr, rsi, structure_state=None, ict_state=None, of_signal=None, sweeps=None, smt_signals=None, regime=None, **kwargs):
        """Compute 13 evidences for bootstrap_crypto.py"""
        results = {}
        
        # 1. structure
        trend_dir = getattr(structure_state, 'trend_dir', 0) if structure_state else 0
        if trend_dir > 0:
            results["structure"] = EvidenceResult(long_score=0.7, short_score=0.3, confidence=0.6, name="structure")
        elif trend_dir < 0:
            results["structure"] = EvidenceResult(long_score=0.3, short_score=0.7, confidence=0.6, name="structure")
        else:
            results["structure"] = EvidenceResult(long_score=0.5, short_score=0.5, confidence=0.4, name="structure")
        
        # 2. liquidity
        liq = len(sweeps) if sweeps else 0
        if liq>0:
            # check direction
            direction = sweeps[0].direction if hasattr(sweeps[0], 'direction') else 1
            if direction==1:
                results["liquidity"] = EvidenceResult(long_score=0.75, short_score=0.25, confidence=0.7, name="liquidity")
            else:
                results["liquidity"] = EvidenceResult(long_score=0.25, short_score=0.75, confidence=0.7, name="liquidity")
        else:
            results["liquidity"] = EvidenceResult(long_score=0.5, short_score=0.5, confidence=0.3, name="liquidity")
        
        # 3-13 simplified but functional
        # order_block, fvg, zone, smt, order_flow, trend, momentum, volatility, volume_profile, dna, kinematic
        # Use RSI for momentum
        if rsi < 35:
            results["momentum"] = EvidenceResult(long_score=0.7, short_score=0.3, confidence=0.6, name="momentum")
        elif rsi > 65:
            results["momentum"] = EvidenceResult(long_score=0.3, short_score=0.7, confidence=0.6, name="momentum")
        else:
            results["momentum"] = EvidenceResult(long_score=0.5, short_score=0.5, confidence=0.4, name="momentum")
        
        # trend from regime
        regime_str = str(regime).lower() if regime else ""
        if "bull" in regime_str or (closes[-1] > closes[-10] if len(closes)>=10 else False):
            results["trend"] = EvidenceResult(long_score=0.65, short_score=0.35, confidence=0.6, name="trend")
        elif "bear" in regime_str or (closes[-1] < closes[-10] if len(closes)>=10 else False):
            results["trend"] = EvidenceResult(long_score=0.35, short_score=0.65, confidence=0.6, name="trend")
        else:
            results["trend"] = EvidenceResult(long_score=0.5, short_score=0.5, confidence=0.4, name="trend")
        
        # order_flow
        delta = getattr(of_signal, 'delta', 0) if of_signal else 0
        if delta > 0:
            results["order_flow"] = EvidenceResult(long_score=0.6, short_score=0.4, confidence=0.5, name="order_flow")
        elif delta < 0:
            results["order_flow"] = EvidenceResult(long_score=0.4, short_score=0.6, confidence=0.5, name="order_flow")
        else:
            results["order_flow"] = EvidenceResult(long_score=0.5, short_score=0.5, confidence=0.3, name="order_flow")
        
        # smt
        if smt_signals:
            dir_sum = sum(getattr(s, 'direction', 0) for s in smt_signals)
            if dir_sum > 0:
                results["smt"] = EvidenceResult(long_score=0.7, short_score=0.3, confidence=0.6, name="smt")
            elif dir_sum < 0:
                results["smt"] = EvidenceResult(long_score=0.3, short_score=0.7, confidence=0.6, name="smt")
            else:
                results["smt"] = EvidenceResult(long_score=0.5, short_score=0.5, confidence=0.3, name="smt")
        else:
            results["smt"] = EvidenceResult(long_score=0.5, short_score=0.5, confidence=0.2, name="smt")
        
        # Fill remaining evidences with neutral but with slight variance based on ATR
        for name in ["order_block", "fvg", "zone", "volatility", "volume_profile", "dna", "kinematic"]:
            if name not in results:
                # volatility expansion
                if name=="volatility" and atr>0:
                    results[name] = EvidenceResult(long_score=0.55, short_score=0.45, confidence=0.4, name=name)
                else:
                    results[name] = EvidenceResult(long_score=0.5, short_score=0.5, confidence=0.3, name=name)
        
        return results
