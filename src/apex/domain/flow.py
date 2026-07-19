"""Order Flow and Microstructure domain objects."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math

@dataclass(frozen=True)
class OrderFlowState:
    """Immutable order flow snapshot (Book II, 16.32)."""
    timestamp: float
    symbol: str
    
    # Trade Flow
    delta: float = 0.0
    cumulative_delta: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    aggression_ratio: float = 0.0
    
    # Order Book Pressure
    book_imbalance: float = 0.0
    micro_price: float = 0.0
    spread_bps: float = 0.0
    
    # Advanced Metrics
    absorption_score: float = 0.0
    exhaustion_score: float = 0.0
    
    def __post_init__(self) -> None:
        for val in [self.delta, self.cumulative_delta, self.buy_volume, self.sell_volume, 
                    self.aggression_ratio, self.book_imbalance, self.absorption_score, self.exhaustion_score]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"OrderFlowState contains NaN or Inf: {val}")
        if not (-1.0 <= self.aggression_ratio <= 1.0):
            raise ValueError(f"Aggression ratio out of bounds: {self.aggression_ratio}")
        if not (-1.0 <= self.book_imbalance <= 1.0):
            raise ValueError(f"Book imbalance out of bounds: {self.book_imbalance}")
