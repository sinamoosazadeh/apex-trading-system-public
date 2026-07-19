"""Standardized contracts and DTOs for engine communication."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math

@dataclass(frozen=True)
class ProbabilityReport:
    """Output contract from Probability Engine. Immutable and validated."""
    probability_long: float = 0.0
    probability_short: float = 0.0
    probability_neutral: float = 0.0
    confidence: float = 0.0
    uncertainty: float = 0.0
    entropy: float = 0.0
    consensus: float = 0.0
    calibration_score: float = 0.0
    expected_value: float = 0.0
    expected_r: float = 0.0
    expected_rr: float = 0.0
    expected_drawdown: float = 0.0
    expected_adverse_excursion: float = 0.0
    expected_favorable_excursion: float = 0.0
    trade_survival_probability: float = 0.0
    expected_holding_time: int = 0
    scenario_distribution: dict[str, float] = field(default_factory=dict)
    feature_attribution: dict[str, float] = field(default_factory=dict)
    evidence_summary: dict[str, float] = field(default_factory=dict)
    regime: str = "neutral"
    decision_readiness_index: float = 0.0
    model_version: str = "2.0.0"
    health_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for val in [self.probability_long, self.probability_short, self.probability_neutral, 
                    self.confidence, self.uncertainty, self.entropy, self.consensus]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"ProbabilityReport contains NaN or Inf: {val}")
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"Probability metric out of bounds [0, 1]: {val}")
        
        total_prob = self.probability_long + self.probability_short + self.probability_neutral
        if not math.isclose(total_prob, 1.0, abs_tol=1e-6):
            raise ValueError(f"Probabilities must sum to 1.0, got {total_prob}")
