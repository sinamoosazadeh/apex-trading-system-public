"""Tests for Advanced Validation Platform - Phase 17."""
import pytest
import math
import random
from apex.research.statistical_validator import StatisticalValidator
from apex.research.monte_carlo import MonteCarloSimulator
from apex.infrastructure.data_validator import DataValidator
from apex.domain.market import MarketBar

def test_statistical_validator_significant_edge():
    validator = StatisticalValidator()
    # 50 trades with mean R = 0.5, std = 1.0
    random.seed(42)
    r_multiples = [0.5 + random.gauss(0, 1.0) for _ in range(50)]
    
    result = validator.validate_edge(r_multiples)
    assert result.sample_size == 50
    assert result.is_significant == True
    assert result.p_value < 0.05
    assert result.sharpe_ratio > 0

def test_statistical_validator_no_edge():
    validator = StatisticalValidator()
    random.seed(42)
    r_multiples = [random.gauss(0, 1.0) for _ in range(50)]
    
    result = validator.validate_edge(r_multiples)
    assert result.is_significant == False
    assert result.p_value > 0.05

def test_monte_carlo_generator_shocks():
    sim = MonteCarloSimulator(seed=123)
    bars = sim.generate_shock_bars(100.0, 1000, shock_prob=0.1, flash_crash_prob=0.05)
    
    assert len(bars) == 1000
    
    flash_crashes = 0
    for i in range(1, len(bars)):
        if bars[i].close < bars[i-1].close * 0.85:
            flash_crashes += 1
            
    assert flash_crashes > 0

def test_monte_carlo_resilience_test():
    sim = MonteCarloSimulator(seed=42)
    validator = DataValidator()
    
    def pipeline_callback(bar: MarketBar) -> None:
        result = validator.validate_bar(bar, tick_size=0.01)
        if not result.is_valid:
            raise ValueError(f"Invalid bar generated: {result.errors}")
            
    report = sim.run_resilience_test(pipeline_callback, num_iterations=10, bars_per_iter=100)
    
    # System should not crash, and should handle the synthetic data gracefully
    assert report["success_rate"] >= 0.9
    assert report["exceptions_raised"] <= 1
