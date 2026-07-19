"""Health Monitor - Tracks heartbeat and status of all system modules."""
from __future__ import annotations

import time
from typing import Dict
import threading

from .contracts import HealthReport

class HealthMonitor:
    """Monitors the health and heartbeat of system services."""

    def __init__(self, heartbeat_timeout: float = 30.0) -> None:
        self._lock = threading.Lock()
        self._heartbeats: Dict[str, float] = {}
        self._statuses: Dict[str, HealthReport] = {}
        self._timeout: float = heartbeat_timeout

    def register_module(self, module: str) -> None:
        with self._lock:
            if module not in self._heartbeats:
                self._heartbeats[module] = time.time()
                self._statuses[module] = HealthReport(
                    module=module, status="HEALTHY", score=1.0, last_heartbeat=time.time()
                )

    def heartbeat(self, module: str) -> None:
        with self._lock:
            self._heartbeats[module] = time.time()

    def update_status(self, module: str, score: float, details: dict | None = None) -> None:
        with self._lock:
            current_time = time.time()
            self._heartbeats[module] = current_time
            if score >= 0.8: status = "HEALTHY"
            elif score >= 0.5: status = "WARNING"
            else: status = "CRITICAL"
            self._statuses[module] = HealthReport(
                module=module, status=status, score=score, 
                last_heartbeat=current_time, details=details or {}
            )

    def get_all_statuses(self) -> Dict[str, HealthReport]:
        with self._lock:
            current_time = time.time()
            result = {}
            for module, last_beat in self._heartbeats.items():
                if current_time - last_beat > self._timeout:
                    self._statuses[module] = HealthReport(
                        module=module, status="OFFLINE", score=0.0, last_heartbeat=last_beat,
                        details={"reason": "Heartbeat timeout"}
                    )
                result[module] = self._statuses[module]
            return result
