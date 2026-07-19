
from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime, timezone
import threading, time

class Scheduler:
    """Scheduling per blueprint - Cron-like, resource management"""
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.schedules: List[Dict[str, Any]] = []
        self.running = False
        self.thread = None

    def add_schedule(self, symbol: str, timeframe: str, optimizer_type, cron: str = "0 0 * * *", priority=5, n_trials=100):
        # cron simplified: daily at 00:00 UTC per blueprint
        self.schedules.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "optimizer_type": optimizer_type,
            "cron": cron,
            "priority": priority,
            "n_trials": n_trials,
            "last_run": None,
            "next_run": None
        })

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            now = datetime.now(timezone.utc)
            for sched in self.schedules:
                # Simple daily check
                if sched["last_run"] is None or (now - datetime.fromisoformat(sched["last_run"])).days >= 1:
                    # Schedule job
                    try:
                        self.orchestrator.submit_job(
                            symbol=sched["symbol"],
                            timeframe=sched["timeframe"],
                            optimizer_type=sched["optimizer_type"],
                            priority=sched["priority"],
                            n_trials=sched["n_trials"]
                        )
                        sched["last_run"] = now.isoformat()
                    except Exception as e:
                        pass
            time.sleep(60)  # Check every minute
