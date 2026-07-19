"""Knowledge and Research domain objects."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import time
import math

@dataclass(frozen=True)
class Experience:
    """Record of a completed trade and its context for learning."""
    trade_id: str
    symbol: str
    setup_name: str
    direction: str
    win: bool
    r_multiple: float
    probability_at_entry: float
    uncertainty_at_entry: float
    regime: str
    feature_vector: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        for val in [self.r_multiple, self.probability_at_entry, self.uncertainty_at_entry]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"Experience contains NaN or Inf: {val}")
        if not (0.0 <= self.probability_at_entry <= 1.0):
            raise ValueError("Probability must be in [0, 1]")

@dataclass(frozen=True)
class Knowledge:
    """Extracted pattern or rule from experiences."""
    knowledge_id: str
    category: str  # 'setup_performance', 'regime_edge', 'feature_drift'
    description: str
    confidence: float
    sample_size: int
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Knowledge confidence out of bounds: {self.confidence}")
