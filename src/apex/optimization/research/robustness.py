
from __future__ import annotations
from typing import Dict, Any, List
import numpy as np

class RobustnessAnalyzer:
    """Stability, Sensitivity, Robustness Score per blueprint"""
    def analyze(self, param_history: List[Dict[str, Any]], metrics_history: List[float]) -> Dict[str, Any]:
        if not param_history or not metrics_history:
            return {"passed": False, "stability_score": 0.0}
        # Variance of metrics
        mean_m = float(np.mean(metrics_history)) if metrics_history else 0
        std_m = float(np.std(metrics_history)) if len(metrics_history) > 1 else 0
        stability_score = 1.0 / (1.0 + std_m / max(0.01, abs(mean_m))) if mean_m != 0 else 0
        # Parameter sensitivity - how much metrics change with param change
        # Simplified: compute variance per param vs metric correlation
        sensitivity = {}
        importance = {}
        # For each param, compute std
        if param_history and isinstance(param_history[0], dict):
            for key in param_history[0].keys():
                try:
                    vals = [p.get(key, 0) for p in param_history if isinstance(p, dict)]
                    if vals and all(isinstance(v, (int, float)) for v in vals):
                        v_std = float(np.std(vals))
                        v_mean = float(np.mean(vals))
                        cv = v_std / max(0.01, abs(v_mean))
                        sensitivity[key] = cv
                        # Importance = correlation with metric improvement (simplified)
                        importance[key] = min(1.0, cv * 2)
                except:
                    pass
        robustness_score = stability_score * 0.6 + (1.0 - min(1.0, std_m)) * 0.4
        passed = stability_score > 0.3 and robustness_score > 0.3
        return {
            "passed": passed,
            "stability_score": float(stability_score),
            "robustness_score": float(robustness_score),
            "mean_metric": mean_m,
            "std_metric": std_m,
            "sensitivity": sensitivity,
            "parameter_importance": importance,
            "variance": float(std_m**2)
        }

class StressTester:
    """Stress Test scenarios per blueprint"""
    SCENARIOS = [
        "extreme_volatility",
        "flash_crash",
        "flash_pump",
        "exchange_freeze",
        "api_delay",
        "network_failure",
        "gap",
        "liquidity_collapse",
        "massive_spread",
        "partial_fill"
    ]

    def test(self, evaluate_fn, base_params: Dict[str, Any]) -> Dict[str, Any]:
        results = {}
        all_passed = True
        for scenario in self.SCENARIOS:
            try:
                # Simulate stress by adjusting evaluation
                # In real system, evaluate_fn would receive scenario param
                score = evaluate_fn(base_params, stress=scenario)
                # Should still be >0 or not crash
                passed = score > -1.0  # Allow small loss but not catastrophic
                results[scenario] = {"passed": passed, "score": float(score)}
                if not passed:
                    all_passed = False
            except Exception as e:
                results[scenario] = {"passed": False, "score": 0.0, "error": str(e)}
                all_passed = False
        avg_score = float(np.mean([r["score"] for r in results.values()])) if results else 0
        return {
            "passed": all_passed,
            "score": avg_score,
            "scenarios": results,
            "total_scenarios": len(self.SCENARIOS)
        }
