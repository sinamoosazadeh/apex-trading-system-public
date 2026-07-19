"""Math helper functions for feature calculations."""
from __future__ import annotations
import math

def clamp(x: float, lo: float, hi: float) -> float:
    if math.isnan(x):
        return (lo + hi) / 2.0
    return max(lo, min(hi, x))

def entropy_01(p: float) -> float:
    p = clamp(p, 0.0001, 0.9999)
    return -(p * math.log(p) + (1.0 - p) * math.log(1.0 - p)) / math.log(2.0)

def percentile_rank(data: list, value: float) -> float:
    if not data:
        return 0.5
    count_below = sum(1 for v in data if v < value)
    return count_below / len(data) if len(data) > 0 else 0.5
