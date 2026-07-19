
from __future__ import annotations
from typing import Dict, Any
from datetime import datetime, timezone

class LifecycleManager:
    """Lifecycle management per blueprint - Created, Queued, Scheduled, Running, Paused, Resumed, Validation, Approved, Stored, Injected, Archived"""
    def __init__(self):
        self.audit_log: list = []

    def record_transition(self, job_id: str, from_state: str, to_state: str, reason: str, metadata: Dict[str, Any] = None):
        entry = {
            "job_id": job_id,
            "from": from_state,
            "to": to_state,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        self.audit_log.append(entry)
        return entry

    def get_audit_trail(self, job_id: str = None):
        if job_id:
            return [e for e in self.audit_log if e["job_id"] == job_id]
        return self.audit_log
