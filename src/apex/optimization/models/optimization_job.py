
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid

from .optimization_state import OptimizationState, OptimizerType

@dataclass
class OptimizationJob:
    job_id: str
    symbol: str
    timeframe: str
    optimizer_type: OptimizerType
    priority: int = 5  # 1 highest, 10 lowest
    status: OptimizationState = OptimizationState.CREATED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    artifact_path: Optional[str] = None
    n_trials: int = 100
    config: Dict[str, Any] = field(default_factory=dict)
    state_history: list = field(default_factory=list)
    resource_usage: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self._record_state(self.status, "Job created")

    def _record_state(self, state: OptimizationState, reason: str):
        self.state_history.append({
            "state": state.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason
        })
        self.status = state

    def transition(self, new_state: OptimizationState, reason: str = "") -> bool:
        if not self.status.can_transition_to(new_state):
            return False
        self._record_state(new_state, reason)
        if new_state == OptimizationState.RUNNING:
            self.started_at = datetime.now(timezone.utc).isoformat()
        if new_state in [OptimizationState.APPROVED, OptimizationState.REJECTED, OptimizationState.FAILED, OptimizationState.ARCHIVED]:
            self.finished_at = datetime.now(timezone.utc).isoformat()
        return True

    def can_retry(self) -> bool:
        return self.retries < self.max_retries

    @classmethod
    def create(cls, symbol: str, timeframe: str, optimizer_type: OptimizerType, priority=5, n_trials=100, config=None) -> "OptimizationJob":
        return cls(
            job_id=f"job_{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            timeframe=timeframe,
            optimizer_type=optimizer_type,
            priority=priority,
            n_trials=n_trials,
            config=config or {}
        )
