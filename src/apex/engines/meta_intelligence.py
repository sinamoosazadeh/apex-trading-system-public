"""Meta Intelligence Engine - System self-awareness and optimization suggestions."""
from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Deque, List

from ..domain.meta import MetaDecisionScore, ImprovementRecommendation, SystemHealthGraph
from ..monitoring.health_monitor import HealthMonitor

class MetaIntelligenceEngine:
    """Monitors system health, calibration, and generates recommendations."""

    def __init__(self, health_monitor: HealthMonitor, calibration_window: int = 50) -> None:
        self.health_monitor = health_monitor
        self.calibration_window = calibration_window
        self._decision_history: Deque[MetaDecisionScore] = deque(maxlen=calibration_window)
        self._recommendations: List[ImprovementRecommendation] = []

    def record_decision_outcome(self, score: MetaDecisionScore) -> None:
        """Record the outcome of a past decision for calibration tracking."""
        self._decision_history.append(score)
        
        if len(self._decision_history) == self.calibration_window:
            self._check_calibration_drift()

    def _check_calibration_drift(self) -> None:
        """Analyze calibration error over the window (Book III, 19.8)."""
        avg_error = sum(d.calibration_error for d in self._decision_history) / len(self._decision_history)
        
        if avg_error > 0.15:
            rec = ImprovementRecommendation(
                recommendation_id=str(uuid.uuid4()),
                category="retrain_model",
                severity="WARNING",
                description=f"Probability Engine calibration drift detected. Avg error: {avg_error:.2f}. Recommend retraining Bayesian models.",
                evidence={"avg_calibration_error": avg_error},
                timestamp=time.time()
            )
            self._recommendations.append(rec)

    def get_system_health_graph(self) -> SystemHealthGraph:
        """Aggregate health scores from all modules (Book III, 19.5)."""
        statuses = self.health_monitor.get_all_statuses()
        
        module_scores = {mod: report.score for mod, report in statuses.items()}
        overall_score = sum(module_scores.values()) / len(module_scores) if module_scores else 0.0
        
        critical = [mod for mod, score in module_scores.items() if score < 0.5]
        
        return SystemHealthGraph(
            overall_score=overall_score,
            module_scores=module_scores,
            critical_modules=critical,
            timestamp=time.time()
        )

    def get_recommendations(self, clear: bool = True) -> List[ImprovementRecommendation]:
        """Retrieve and optionally clear pending recommendations."""
        recs = list(self._recommendations)
        if clear:
            self._recommendations.clear()
        return recs
