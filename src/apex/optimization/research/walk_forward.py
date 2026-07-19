
from __future__ import annotations
import numpy as np
from typing import List, Dict, Any, Callable

class WalkForwardValidator:
    """Walk Forward Validation per blueprint: Expanding and Rolling Windows"""
    def __init__(self, n_splits=5, train_ratio=0.7, mode="expanding"):
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        self.mode = mode  # expanding or rolling

    def split(self, data: List[Any]) -> List[tuple]:
        n = len(data)
        splits = []
        fold_size = n // self.n_splits
        for i in range(1, self.n_splits):
            if self.mode == "expanding":
                train_end = int((i / self.n_splits) * n)
                test_end = int(((i+1) / self.n_splits) * n)
                train = data[:train_end]
                test = data[train_end:test_end]
            else:  # rolling
                train_start = int((i-1) * fold_size * self.train_ratio)
                train_end = train_start + int(fold_size * self.train_ratio)
                test_end = train_end + int(fold_size * (1-self.train_ratio))
                train = data[train_start:train_end]
                test = data[train_end:min(test_end, n)]
            if len(train) > 10 and len(test) > 5:
                splits.append((train, test))
        return splits

    def validate(self, data: List[Any], evaluate_fn: Callable) -> Dict[str, Any]:
        splits = self.split(data)
        scores = []
        in_sample_scores = []
        out_sample_scores = []
        for train, test in splits:
            try:
                in_score = evaluate_fn(train)
                out_score = evaluate_fn(test)
                in_sample_scores.append(in_score)
                out_sample_scores.append(out_score)
                # Stability: out/in ratio
                ratio = out_score / max(0.01, in_score) if in_score > 0 else 0
                scores.append(ratio)
            except Exception as e:
                scores.append(0.0)
        if not scores:
            return {"passed": False, "score": 0.0, "reason": "No splits"}
        avg_ratio = float(np.mean(scores)) if scores else 0.0
        # Blueprint: if OOS < 50% of IS, reject (overfit)
        passed = avg_ratio >= 0.5 and np.mean(out_sample_scores) > 0
        return {
            "passed": passed,
            "score": avg_ratio,
            "in_sample_mean": float(np.mean(in_sample_scores)) if in_sample_scores else 0,
            "out_sample_mean": float(np.mean(out_sample_scores)) if out_sample_scores else 0,
            "ratios": scores,
            "n_splits": len(splits)
        }
