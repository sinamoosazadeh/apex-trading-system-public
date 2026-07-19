
from __future__ import annotations
import random
from typing import List, Dict, Any, Callable
import numpy as np

class MonteCarloValidator:
    """Monte Carlo Validation per blueprint: Random Order, Bootstrap, Slippage, etc."""
    def __init__(self, n_simulations=1000, random_seed=42):
        self.n_simulations = n_simulations
        self.random_seed = random_seed
        random.seed(random_seed)
        np.random.seed(random_seed)

    def _shuffle_trades(self, trades: List[Dict]) -> List[Dict]:
        shuffled = trades.copy()
        random.shuffle(shuffled)
        return shuffled

    def _bootstrap_trades(self, trades: List[Dict]) -> List[Dict]:
        return [random.choice(trades) for _ in trades]

    def _add_slippage_noise(self, trades: List[Dict], slippage_range=(0.0, 0.002)) -> List[Dict]:
        noisy = []
        for t in trades:
            nt = t.copy()
            slip = random.uniform(*slippage_range)
            # Reduce profit by slippage
            if "pnl" in nt:
                nt["pnl"] = nt["pnl"] * (1 - slip)
            noisy.append(nt)
        return noisy

    def validate(self, trades: List[Dict], evaluate_fn: Callable = None) -> Dict[str, Any]:
        if not trades or len(trades) < 20:
            return {"passed": False, "score": 0.0, "reason": "Not enough trades"}
        if evaluate_fn is None:
            evaluate_fn = lambda tr: sum(x.get("pnl", 0) for x in tr) / max(1, len(tr))

        original_score = evaluate_fn(trades)
        simulated_scores = []
        for _ in range(self.n_simulations):
            # Mix of methods
            r = random.random()
            if r < 0.4:
                sim = self._shuffle_trades(trades)
            elif r < 0.7:
                sim = self._bootstrap_trades(trades)
            else:
                sim = self._add_slippage_noise(trades)
            try:
                score = evaluate_fn(sim)
                simulated_scores.append(score)
            except:
                simulated_scores.append(0)

        if not simulated_scores:
            return {"passed": False, "score": 0.0}
        mean_sim = float(np.mean(simulated_scores))
        std_sim = float(np.std(simulated_scores))
        # Percentile of original vs simulations - should be above 20th percentile (not luck)
        percentile = sum(1 for s in simulated_scores if s < original_score) / len(simulated_scores)
        # Robustness: original should not be outlier
        passed = percentile > 0.2 and mean_sim > 0
        return {
            "passed": passed,
            "score": float(percentile),
            "original_score": float(original_score),
            "mean_simulated": mean_sim,
            "std_simulated": std_sim,
            "percentile": float(percentile),
            "n_simulations": self.n_simulations,
            "robustness": float(mean_sim / max(0.01, abs(original_score))) if original_score != 0 else 0
        }
