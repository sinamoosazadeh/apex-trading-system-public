
from __future__ import annotations
from collections import deque
from typing import List, Optional
import threading
from ..models.optimization_job import OptimizationJob
from ..models.optimization_state import OptimizationState

class QueueManager:
    """Queue management per blueprint - Priority, prevent incompatible concurrent execution"""
    def __init__(self):
        self.queue: deque[OptimizationJob] = deque()
        self.running: List[OptimizationJob] = []
        self.lock = threading.Lock()
        self.max_concurrent = 2  # Prevent overload

    def enqueue(self, job: OptimizationJob):
        with self.lock:
            job.transition(OptimizationState.QUEUED, "Enqueued")
            # Insert by priority
            inserted = False
            for i, existing in enumerate(self.queue):
                if job.priority < existing.priority:
                    self.queue.insert(i, job)
                    inserted = True
                    break
            if not inserted:
                self.queue.append(job)

    def dequeue(self) -> Optional[OptimizationJob]:
        with self.lock:
            if len(self.running) >= self.max_concurrent:
                return None
            if not self.queue:
                return None
            # Check for incompatible concurrent: same symbol/timeframe/optimizer_type should not run twice
            for idx, job in enumerate(self.queue):
                conflict = any(r.symbol == job.symbol and r.timeframe == job.timeframe and r.optimizer_type == job.optimizer_type for r in self.running)
                if not conflict:
                    job = self.queue[idx]
                    del self.queue[idx]
                    job.transition(OptimizationState.SCHEDULED, "Dequeued for execution")
                    self.running.append(job)
                    return job
            return None

    def mark_finished(self, job: OptimizationJob):
        with self.lock:
            self.running = [r for r in self.running if r.job_id != job.job_id]

    def get_queue_status(self):
        with self.lock:
            return {
                "queued": len(self.queue),
                "running": len(self.running),
                "queued_jobs": [{"job_id": j.job_id, "symbol": j.symbol, "timeframe": j.timeframe, "type": j.optimizer_type.value, "priority": j.priority} for j in self.queue],
                "running_jobs": [{"job_id": j.job_id, "symbol": j.symbol, "timeframe": j.timeframe} for j in self.running]
            }
