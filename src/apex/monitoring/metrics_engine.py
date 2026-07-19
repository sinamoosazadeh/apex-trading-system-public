"""Metrics Engine - Real-time collection of system performance data."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List
import threading
import time

from .contracts import Metric

class MetricsEngine:
    """Thread-safe collection of system metrics."""

    def __init__(self, max_history: int = 1000) -> None:
        self._lock = threading.Lock()
        self._metrics: Dict[str, List[Metric]] = defaultdict(list)
        self._max_history: int = max_history

    def record(self, name: str, value: float, unit: str = "", **tags: str) -> None:
        metric = Metric(name=name, value=value, unit=unit, tags=tags)
        with self._lock:
            self._metrics[name].append(metric)
            if len(self._metrics[name]) > self._max_history:
                self._metrics[name].pop(0)

    def get_latest(self, name: str) -> Metric | None:
        with self._lock:
            history = self._metrics.get(name, [])
            return history[-1] if history else None

    def get_history(self, name: str, limit: int = 100) -> List[Metric]:
        with self._lock:
            return list(self._metrics.get(name, [])[-limit:])

    def get_all_latest(self) -> Dict[str, Metric]:
        with self._lock:
            return {name: hist[-1] for name, hist in self._metrics.items() if hist}
