"""Regime domain objects and contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math

@dataclass(frozen=True)
class RegimeState:
    """Multi-dimensional market regime snapshot (Book I, 8.33)."""
    trend_class: str         # STRONG_BULL, BULL, WEAK_BULL, NEUTRAL, WEAK_BEAR, BEAR, STRONG_BEAR
    volatility_class: str    # ULTRA_LOW, LOW, NORMAL, HIGH, EXTREME
    liquidity_class: str     # DEEP, HEALTHY, NORMAL, THIN, CRITICAL (Estimated)
    behavioral_class: str    # FEAR, PANIC, RECOVERY, GREED, EUPHORIA, ACCUMULATION, DISTRIBUTION
    
    trend_confidence: float  # 0.0 to 1.0
    volatility_confidence: float
    regime_entropy: float    # 0.0 (Clear) to 1.0 (Ambiguous)
    
    expected_duration: int   # Expected remaining bars for this regime
    transition_prob: dict[str, float] = field(default_factory=dict)
    
    is_trending: bool = False
    is_ranging: bool = False
    is_transition: bool = False
    is_compression: bool = False
    is_expansion: bool = False
    
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for val in [self.trend_confidence, self.volatility_confidence, self.regime_entropy]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"RegimeState contains NaN or Inf: {val}")
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"Regime metric out of bounds [0, 1]: {val}")
