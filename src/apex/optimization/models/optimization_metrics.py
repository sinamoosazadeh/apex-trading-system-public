
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any
import math

@dataclass
class OptimizationMetrics:
    net_profit: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    recovery_factor: float = 0.0
    win_rate: float = 0.0
    avg_r: float = 0.0
    avg_holding_time: float = 0.0
    trade_count: int = 0
    exposure_efficiency: float = 0.0
    risk_efficiency: float = 0.0
    robustness_score: float = 0.0
    stability_score: float = 0.0
    sqn: float = 0.0
    # Signal quality
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    roc_auc: float = 0.0
    calibration_error: float = 0.0
    # Risk
    avg_rr: float = 0.0
    effective_rr: float = 0.0
    stop_efficiency: float = 0.0
    trailing_efficiency: float = 0.0
    capital_utilization: float = 0.0
    # Validation
    walk_forward_score: float = 0.0
    monte_carlo_score: float = 0.0
    out_of_sample_score: float = 0.0
    in_sample_score: float = 0.0
    overfitting_score: float = 0.0  # lower is better, 0 = no overfit
    extra: Dict[str, Any] = field(default_factory=dict)

    def compute_composite_score(self) -> float:
        # Multi-objective per blueprint - Maximize Robustness
        if self.trade_count < 30:
            return 0.0
        profit_component = max(0, self.expectancy) * math.sqrt(max(1, self.trade_count)) / 10
        risk_component = 1.0 / (1.0 + self.max_drawdown * 5)
        pf_component = min(self.profit_factor / 2.0, 1.0) if self.profit_factor > 0 else 0
        robustness_component = self.robustness_score
        stability_component = self.stability_score
        wf_component = self.walk_forward_score
        # Penalty for overfitting
        overfit_penalty = max(0, 1.0 - self.overfitting_score)
        composite = (profit_component*0.25 + risk_component*0.15 + pf_component*0.15 + 
                     robustness_component*0.15 + stability_component*0.1 + wf_component*0.1 + overfit_penalty*0.1)
        return max(0.0, min(1.0, composite))

    def is_better_than(self, other: "OptimizationMetrics", threshold: float = 0.05) -> bool:
        # Statistical significant improvement
        return self.compute_composite_score() > other.compute_composite_score() * (1 + threshold)
