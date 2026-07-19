"""Tests for Probability Engine - Phase 4."""
import pytest
import math
from apex.engines.probability_engine import ProbabilityEngine, BayesianModel
from apex.domain.contracts import ProbabilityReport

def test_bayesian_model_posterior_and_update():
    model = BayesianModel(alpha=6.0, beta=6.0)
    assert 0.4 < model.posterior < 0.6
    
    # Test Win
    model.update(score=0.9, win=True, r=2.0)
    assert model.alpha > 6.0
    assert model.beta == 6.0
    assert model.posterior > 0.5
    
    # Test Loss in isolation to check expected_r logic
    loss_model = BayesianModel(alpha=6.0, beta=6.0)
    loss_model.update(score=0.8, win=False, r=-1.0)
    assert loss_model.beta > 6.0
    assert loss_model.expected_r < 0

def test_probability_engine_calibrate():
    engine = ProbabilityEngine()
    
    calibrated_low = engine.calibrate(0.2)
    assert 0.1 < calibrated_low < 0.3
    
    # Inject bias into bin 8 (0.8 probability)
    for _ in range(50):
        engine.update_calibration(0.8, win=True)
        
    # Read calibration from the same bin (0.8)
    calibrated_high = engine.calibrate(0.8)
    assert calibrated_high > 0.8

def test_probability_engine_compute_distribution_sums_to_1():
    engine = ProbabilityEngine()
    evidence_long = {"structure": 0.7, "liquidity": 0.6, "trend": 0.5}
    evidence_short = {"structure": 0.2, "liquidity": 0.3, "trend": 0.4}
    weights = {"structure": 0.3, "liquidity": 0.4, "trend": 0.3}

    report = engine.compute_probability(evidence_long, evidence_short, weights)

    assert isinstance(report, ProbabilityReport)
    total_prob = report.probability_long + report.probability_short + report.probability_neutral
    assert math.isclose(total_prob, 1.0, abs_tol=1e-6)
    
    assert report.probability_long > report.probability_short
    assert report.consensus > 0.0

def test_probability_engine_uncertainty_and_attribution():
    engine = ProbabilityEngine()
    
    evidence_long = {"structure": 0.9, "liquidity": 0.9}
    evidence_short = {"structure": 0.8, "liquidity": 0.8}
    weights = {"structure": 0.5, "liquidity": 0.5}
    
    report = engine.compute_probability(evidence_long, evidence_short, weights)
    assert report.uncertainty > 0.5
    
    assert report.feature_attribution["structure"] > 0
    assert report.feature_attribution["liquidity"] > 0

def test_probability_report_nan_rejection():
    with pytest.raises(ValueError):
        ProbabilityReport(probability_long=float('nan'), probability_short=0.5, probability_neutral=0.5)
