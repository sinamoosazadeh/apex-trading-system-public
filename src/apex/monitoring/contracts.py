"""Observability contracts and DTOs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math
import time

@dataclass(frozen=True)
class LogEntry:
    """Immutable structured log entry."""
    timestamp: float
    level: str  # INFO, WARNING, ERROR, CRITICAL
    module: str
    message: str
    trace_id: str = ""
    correlation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Metric:
    """Metric data point for telemetry."""
    name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value):
            raise ValueError(f"Metric '{self.name}' contains NaN or Inf: {self.value}")

@dataclass(frozen=True)
class HealthReport:
    """Health status report for a system module."""
    module: str
    status: str  # HEALTHY, WARNING, CRITICAL, OFFLINE
    score: float
    last_heartbeat: float
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"Health score must be in [0, 1], got {self.score}")
        if self.status not in ('HEALTHY', 'WARNING', 'CRITICAL', 'OFFLINE'):
            raise ValueError(f"Invalid health status: {self.status}")
