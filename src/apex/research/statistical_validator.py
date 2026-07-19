"""Statistical Validation Engine for strategy verification (Book III, 23.11)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import math
import numpy as np
from scipy import stats

@dataclass(frozen=True)
class StatisticalResult:
    """Immutable result of statistical validation."""
    sample_size: int
    mean_r: float
    std_dev: float
    t_statistic: float
    p_value: float
    is_significant: bool  # True if p_value < 0.05 and mean_r > 0
    sharpe_ratio: float

class StatisticalValidator:
    """Validates trading strategy edges using rigorous statistical methods."""

    def validate_edge(self, r_multiples: Sequence[float]) -> StatisticalResult:
        """
        Perform a one-sample t-test to determine if the mean R-multiple
        is statistically significantly greater than 0.
        """
        n = len(r_multiples)
        if n < 5:
            return StatisticalResult(
                sample_size=n, mean_r=0.0, std_dev=0.0, t_statistic=0.0,
                p_value=1.0, is_significant=False, sharpe_ratio=0.0
            )

        arr = np.array(r_multiples, dtype=np.float64)
        mean_r = float(np.mean(arr))
        std_dev = float(np.std(arr, ddof=1))
        
        if std_dev == 0:
            t_stat = float('inf') if mean_r > 0 else float('-inf')
            p_val = 0.0 if mean_r > 0 else 1.0
        else:
            t_stat, p_val = stats.ttest_1samp(arr, 0.0)
            p_val = float(p_val) / 2.0  # One-tailed test
            t_stat = float(t_stat)

        sharpe = mean_r / std_dev * math.sqrt(n) if std_dev > 0 else 0.0
        is_sig = (p_val < 0.05) and (mean_r > 0)

        return StatisticalResult(
            sample_size=n,
            mean_r=mean_r,
            std_dev=std_dev,
            t_statistic=t_stat,
            p_value=p_val,
            is_significant=is_sig,
            sharpe_ratio=sharpe
        )
