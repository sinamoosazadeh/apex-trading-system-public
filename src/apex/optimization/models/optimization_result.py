
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from .parameter_package import ParameterPackage
from .optimization_metrics import OptimizationMetrics
from .optimization_job import OptimizationJob

@dataclass
class OptimizationResult:
    job: OptimizationJob
    package: ParameterPackage
    metrics: OptimizationMetrics
    validation_passed: bool
    validation_details: Dict[str, Any] = field(default_factory=dict)
    benchmark_comparison: Dict[str, Any] = field(default_factory=dict)
    sensitivity_report: Dict[str, Any] = field(default_factory=dict)
    parameter_importance: Dict[str, float] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    logs: str = ""
    error: Optional[str] = None

    def is_acceptable(self) -> bool:
        # Per blueprint: must pass all validations and improve over baseline
        if not self.validation_passed:
            return False
        if self.metrics.trade_count < 30:
            return False
        if self.metrics.max_drawdown > 0.5:
            return False
        if self.metrics.overfitting_score > 0.5:
            return False
        if self.metrics.walk_forward_score < 0.3:
            return False
        return True
