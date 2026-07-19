"""Meta Intelligence domain objects and contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math

@dataclass(frozen=True)
class MetaDecisionScore:
    """Evaluation of a past decision after the trade is closed."""
    decision_id: str
    expected_probability: float
    actual_outcome: bool  # True=Win, False=Loss
    calibration_error: float  # |expected_prob - actual_outcome|
    attribution_accuracy: float  # Did the expected features actually drive the outcome?
    timestamp: float = 0.0

@dataclass(frozen=True)
class ImprovementRecommendation:
    """System-generated recommendation for optimization."""
    recommendation_id: str
    category: str  # 'retrain_model', 'disable_feature', 'adjust_risk', 'check_data'
    severity: str  # 'INFO', 'WARNING', 'CRITICAL'
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

@dataclass(frozen=True)
class SystemHealthGraph:
    """Aggregated health snapshot of all system modules."""
    overall_score: float
    module_scores: dict[str, float]
    critical_modules: list[str] = field(default_factory=list)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.overall_score <= 1.0):
            raise ValueError("Overall score must be in [0, 1]")
