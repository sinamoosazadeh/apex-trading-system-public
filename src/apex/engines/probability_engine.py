"""Institutional Probability Engine v2 - Bayesian inference with ensemble models."""
from __future__ import annotations

from dataclasses import dataclass
import math

from ..domain.contracts import ProbabilityReport

def _squash(x: float) -> float:
    if math.isnan(x): x = 0.0
    return 1.0 / (1.0 + math.exp(-x))

def _clamp(x: float, lo: float, hi: float) -> float:
    if math.isnan(x): return (lo + hi) / 2.0
    return max(lo, min(hi, x))

def _entropy_01(p: float) -> float:
    p = _clamp(p, 0.0001, 0.9999)
    return -(p * math.log(p) + (1.0 - p) * math.log(1.0 - p)) / math.log(2.0)

@dataclass
class BayesianModel:
    alpha: float = 6.0
    beta: float = 6.0
    r_sum: float = 0.0
    trades: float = 0.0

    @property
    def posterior(self) -> float:
        return self.alpha / max(self.alpha + self.beta, 0.0001)

    @property
    def expected_r(self) -> float:
        return self.r_sum / self.trades if self.trades > 0 else 0.0

    @property
    def sample_factor(self) -> float:
        return _clamp(self.trades / 25.0, 0.0, 1.0)

    def update(self, score: float, win: bool, r: float) -> None:
        s = _clamp(score, 0.0, 1.0)
        if s >= 0.20:
            self.alpha += s if win else 0.0
            self.beta += 0.0 if win else s
            self.r_sum += r * s
            self.trades += s

@dataclass
class CalibrationBin:
    wins: float = 0.0
    trades: float = 0.0

    @property
    def win_rate(self) -> float:
        return (self.wins + 1.0) / (self.trades + 2.0)

class ProbabilityEngine:
    def __init__(self, min_sample: float = 25.0, max_blend: float = 0.65) -> None:
        self.feature_models: list[BayesianModel] = [BayesianModel() for _ in range(13)]
        self.setup_models: dict[str, BayesianModel] = {}
        self.calibration_bins: list[CalibrationBin] = [CalibrationBin() for _ in range(10)]
        self.min_sample: float = min_sample
        self.max_blend: float = max_blend

    def calibrate(self, prob: float) -> float:
        pp = _clamp(prob, 0.01, 0.99)
        bin_idx = min(int(math.floor(pp * 10.0)), 9)
        cal_bin = self.calibration_bins[bin_idx]
        blend = _clamp(cal_bin.trades / self.min_sample, 0.0, self.max_blend)
        wr = cal_bin.win_rate
        return _clamp(pp * (1.0 - blend) + wr * blend, 0.01, 0.99)

    def update_calibration(self, prob: float, win: bool) -> None:
        bin_idx = min(int(math.floor(_clamp(prob, 0.0, 0.9999) * 10.0)), 9)
        self.calibration_bins[bin_idx].trades += 1.0
        if win:
            self.calibration_bins[bin_idx].wins += 1.0

    def update_feature_model(self, idx: int, score: float, win: bool, r: float) -> None:
        if 0 <= idx < len(self.feature_models):
            self.feature_models[idx].update(score, win, r)

    def update_setup(self, name: str, win: bool, r: float) -> None:
        if name not in self.setup_models:
            self.setup_models[name] = BayesianModel()
        self.setup_models[name].update(0.5, win, r)

    def compute_probability(
        self,
        evidence_long: dict[str, float],
        evidence_short: dict[str, float],
        weights: dict[str, float],
        trend_confidence: float = 0.5,
        interactions_long: float = 0.0,
        interactions_short: float = 0.0,
        penalties_long: float = 0.0,
        penalties_short: float = 0.0,
        crypto_bonus_long: float = 0.0,
        crypto_bonus_short: float = 0.0,
    ) -> ProbabilityReport:
        base_long = 0.0
        base_short = 0.0
        w_sum = sum(weights.values()) if weights else 1.0
        attribution: dict[str, float] = {}

        for key, weight in weights.items():
            ev_l = evidence_long.get(key, 0.0)
            ev_s = evidence_short.get(key, 0.0)
            w = weight / w_sum if w_sum > 0 else 0.0
            base_long += w * ev_l
            base_short += w * ev_s
            attribution[key] = (ev_l - ev_s) * w

        raw_long = base_long + interactions_long + crypto_bonus_long - penalties_long
        raw_short = base_short + interactions_short + crypto_bonus_short - penalties_short

        cal_gain = 5.4 + trend_confidence * 1.2
        prob_long_raw = _squash((raw_long - 0.45) * cal_gain)
        prob_short_raw = _squash((raw_short - 0.45) * cal_gain)

        prob_long = self.calibrate(prob_long_raw)
        prob_short = self.calibrate(prob_short_raw)
        
        max_prob = max(prob_long, prob_short)
        min_prob = min(prob_long, prob_short)
        prob_neutral = max(0.0, 1.0 - (max_prob + min_prob))
        
        total = prob_long + prob_short + prob_neutral
        prob_long /= total
        prob_short /= total
        prob_neutral /= total

        ambiguity = 1.0 - abs(prob_long - prob_short)
        uncertainty = _clamp(0.38 * ambiguity + 0.28 * _entropy_01(max_prob) + 0.34 * 0.5, 0.0, 1.0)
        
        confidence_long = prob_long * (1.0 - uncertainty)
        confidence_short = prob_short * (1.0 - uncertainty)
        confidence = max(confidence_long, confidence_short)

        base_rr = 3.5 / 2.0
        tp3_rr = base_rr * 1.50

        catalyst_l = max(evidence_long.values()) if evidence_long else 0.0
        catalyst_s = max(evidence_short.values()) if evidence_short else 0.0
        
        expected_rr_long = tp3_rr * _clamp(0.75 + 0.20 * 1.0 + 0.15 * catalyst_l - 0.10 * uncertainty, 0.50, 1.30)
        expected_rr_short = tp3_rr * _clamp(0.75 + 0.20 * 1.0 + 0.15 * catalyst_s - 0.10 * uncertainty, 0.50, 1.30)

        expected_r_long = prob_long * expected_rr_long - (1.0 - prob_long) - 0.02
        expected_r_short = prob_short * expected_rr_short - (1.0 - prob_short) - 0.02

        scenario_dist = {
            "trend_continuation": prob_long,
            "trend_failure": prob_short,
            "range": prob_neutral
        }

        dri = _clamp(
            (1.0 - uncertainty) * 0.30 +
            max(prob_long, prob_short) * 0.25 +
            (1.0 - _entropy_01(max_prob)) * 0.20 +
            0.25 * 1.0,
            0.0, 1.0
        )

        return ProbabilityReport(
            probability_long=prob_long,
            probability_short=prob_short,
            probability_neutral=prob_neutral,
            confidence=confidence,
            uncertainty=uncertainty,
            entropy=_entropy_01(max_prob),
            consensus=abs(prob_long - prob_short),
            calibration_score=1.0 - abs(prob_long - 0.5) * 0.5,
            expected_value=max(expected_r_long, expected_r_short),
            expected_r=max(expected_r_long, expected_r_short),
            expected_rr=max(expected_rr_long, expected_rr_short),
            expected_drawdown=uncertainty * 0.5,
            expected_adverse_excursion=0.5,
            expected_favorable_excursion=1.5,
            trade_survival_probability=max(prob_long, prob_short) * (1.0 - uncertainty),
            expected_holding_time=12,
            scenario_distribution=scenario_dist,
            feature_attribution=attribution,
            evidence_summary={**evidence_long, **{f"{k}_s": v for k, v in evidence_short.items()}},
            regime="neutral",
            decision_readiness_index=dri,
            model_version="2.0.0",
            health_score=1.0,
        )
