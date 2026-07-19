
from __future__ import annotations
from typing import Dict, Any, List, Callable
from ..models.optimization_metrics import OptimizationMetrics

class SignalObjective:
    """Multi-objective per blueprint: Expectancy, PF, Sharpe, Sortino, Calmar, Recovery, WinRate, Stability, Robustness"""
    def __init__(self, evaluate_fn: Callable[[Dict[str, Any]], OptimizationMetrics]):
        self.evaluate_fn = evaluate_fn
        self.weights = {
            "expectancy": 0.2,
            "profit_factor": 0.15,
            "sharpe": 0.1,
            "sortino": 0.1,
            "calmar": 0.05,
            "win_rate": 0.05,
            "robustness": 0.15,
            "stability": 0.1,
            "trade_count": 0.05,
            "recovery": 0.05
        }

    def __call__(self, params: Dict[str, Any]) -> float:
        metrics = self.evaluate_fn(params)
        if metrics.trade_count < 20:
            return 0.0
        score = (
            max(0, metrics.expectancy) * self.weights["expectancy"] * 5 +
            min(metrics.profit_factor/3, 1) * self.weights["profit_factor"] +
            max(0, min(metrics.sharpe_ratio/3, 1)) * self.weights["sharpe"] +
            max(0, min(metrics.sortino_ratio/3, 1)) * self.weights["sortino"] +
            max(0, min(metrics.calmar_ratio/2, 1)) * self.weights["calmar"] +
            metrics.win_rate * self.weights["win_rate"] +
            metrics.robustness_score * self.weights["robustness"] +
            metrics.stability_score * self.weights["stability"] +
            min(metrics.trade_count/200, 1) * self.weights["trade_count"] +
            min(metrics.recovery_factor/5, 1) * self.weights["recovery"]
        )
        # Penalty for high DD
        score *= (1.0 / (1.0 + metrics.max_drawdown))
        # Penalty for overfitting
        score *= (1.0 - metrics.overfitting_score*0.5)
        return max(0.0, score)

    def evaluate_detailed(self, params: Dict[str, Any]) -> OptimizationMetrics:
        return self.evaluate_fn(params)
