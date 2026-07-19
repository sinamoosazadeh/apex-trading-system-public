
from __future__ import annotations
from enum import Enum

class OptimizationState(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    RESUMED = "resumed"
    VALIDATION = "validation"
    APPROVED = "approved"
    REJECTED = "rejected"
    STORED = "stored"
    INJECTED = "injected"
    ARCHIVED = "archived"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    
    def can_transition_to(self, nxt: "OptimizationState") -> bool:
        allowed = {
            OptimizationState.CREATED: [OptimizationState.QUEUED, OptimizationState.SCHEDULED, OptimizationState.FAILED],
            OptimizationState.QUEUED: [OptimizationState.SCHEDULED, OptimizationState.RUNNING, OptimizationState.FAILED],
            OptimizationState.SCHEDULED: [OptimizationState.RUNNING, OptimizationState.FAILED],
            OptimizationState.RUNNING: [OptimizationState.PAUSED, OptimizationState.VALIDATION, OptimizationState.FAILED],
            OptimizationState.PAUSED: [OptimizationState.RESUMED, OptimizationState.FAILED],
            OptimizationState.RESUMED: [OptimizationState.RUNNING, OptimizationState.FAILED],
            OptimizationState.VALIDATION: [OptimizationState.APPROVED, OptimizationState.REJECTED, OptimizationState.FAILED],
            OptimizationState.APPROVED: [OptimizationState.STORED, OptimizationState.FAILED],
            OptimizationState.STORED: [OptimizationState.INJECTED, OptimizationState.FAILED],
            OptimizationState.INJECTED: [OptimizationState.ARCHIVED, OptimizationState.ROLLED_BACK],
            OptimizationState.REJECTED: [OptimizationState.ARCHIVED],
            OptimizationState.FAILED: [OptimizationState.QUEUED, OptimizationState.ARCHIVED],
            OptimizationState.ROLLED_BACK: [OptimizationState.ARCHIVED],
        }
        return nxt in allowed.get(self, [])

class OptimizerType(str, Enum):
    SIGNAL = "signal"
    RISK_EXECUTION = "risk_execution"
    RESEARCH = "research"
    PORTFOLIO = "portfolio"
    META = "meta"
