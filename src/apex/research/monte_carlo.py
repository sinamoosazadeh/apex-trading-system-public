"""Monte Carlo Simulation Engine for stress testing (Book III, 23.10 & 2.44)."""
from __future__ import annotations

import random
import math
import numpy as np
from typing import Any, Callable

from ..domain.market import MarketBar

class MonteCarloSimulator:
    """Generates synthetic market scenarios to test system robustness."""

    def __init__(self, seed: int = 42) -> None:
        random.seed(seed)
        np.random.seed(seed)

    def generate_shock_bars(
        self, 
        start_price: float, 
        count: int, 
        base_vol: float = 0.02,
        shock_prob: float = 0.02,
        flash_crash_prob: float = 0.001
    ) -> list[MarketBar]:
        """Generate synthetic bars with random shocks and flash crashes."""
        bars = []
        price = start_price
        
        for i in range(count):
            ret = random.gauss(0, base_vol)
            
            if random.random() < shock_prob:
                ret *= random.uniform(5.0, 15.0)
                
            if random.random() < flash_crash_prob:
                price *= 0.80  # 20% instant drop
                bars.append(MarketBar(
                    timestamp=float(i), open=price*1.25, high=price*1.25, 
                    low=price*0.95, close=price, volume=random.uniform(500, 1000)
                ))
                price *= 1.15  # Partial recovery
                continue
                
            price = max(0.01, price * (1 + ret))
            
            o = price
            c = price * (1 + random.gauss(0, base_vol * 0.5))
            h = max(o, c) * (1 + abs(random.gauss(0, base_vol * 0.2)))
            l = min(o, c) * (1 - abs(random.gauss(0, base_vol * 0.2)))
            v = max(1.0, random.expovariate(1.0 / 100.0))
            
            bars.append(MarketBar(
                timestamp=float(i), open=o, high=h, low=l, close=c, volume=v
            ))
            
        return bars

    def run_resilience_test(
        self, 
        pipeline_callback: Callable[[MarketBar], None], 
        num_iterations: int,
        bars_per_iter: int
    ) -> dict[str, Any]:
        """
        Run the pipeline callback against synthetic data to check for crashes.
        Returns a report of any exceptions or numerical instabilities.
        """
        exceptions_count = 0
        nan_detected = False
        
        for i in range(num_iterations):
            try:
                start_p = random.uniform(10.0, 50000.0)
                bars = self.generate_shock_bars(start_p, bars_per_iter)
                
                for bar in bars:
                    pipeline_callback(bar)
                    
                    if math.isnan(bar.close) or math.isinf(bar.close):
                        nan_detected = True
                        
            except Exception:
                exceptions_count += 1
                
        return {
            "total_iterations": num_iterations,
            "exceptions_raised": exceptions_count,
            "nan_inf_detected": nan_detected,
            "success_rate": 1.0 - (exceptions_count / num_iterations) if num_iterations > 0 else 0.0
        }
