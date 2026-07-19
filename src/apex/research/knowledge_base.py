"""Knowledge Base - Long-term memory and experience repository."""
from __future__ import annotations

from collections import defaultdict
from typing import List, Dict, Any
import threading

from ..domain.knowledge import Experience, Knowledge

class KnowledgeBase:
    """Thread-safe repository for experiences and extracted knowledge."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._experiences: List[Experience] = []
        self._knowledge: Dict[str, Knowledge] = {}
        self._setup_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"wins": 0.0, "trades": 0.0, "r_sum": 0.0})

    def record_experience(self, experience: Experience) -> None:
        """Store a new trade experience and update aggregate stats."""
        with self._lock:
            self._experiences.append(experience)
            
            stats = self._setup_stats[experience.setup_name]
            stats["trades"] += 1.0
            if experience.win:
                stats["wins"] += 1.0
            stats["r_sum"] += experience.r_multiple

    def add_knowledge(self, knowledge: Knowledge) -> None:
        """Store extracted knowledge/rule."""
        with self._lock:
            self._knowledge[knowledge.knowledge_id] = knowledge

    def get_setup_stats(self, setup_name: str) -> dict[str, float]:
        """Get aggregate statistics for a specific setup."""
        with self._lock:
            stats = self._setup_stats.get(setup_name, {"wins": 0.0, "trades": 0.0, "r_sum": 0.0})
            return {
                "win_rate": (stats["wins"] + 1.0) / (stats["trades"] + 2.0),  # Beta-Binomial smoothing
                "expectancy": stats["r_sum"] / stats["trades"] if stats["trades"] > 0 else 0.0,
                "sample_size": stats["trades"]
            }

    def get_recent_experiences(self, limit: int = 100) -> List[Experience]:
        """Get recent experiences for analysis."""
        with self._lock:
            return list(self._experiences[-limit:])

    def get_all_knowledge(self) -> List[Knowledge]:
        """Retrieve all extracted knowledge rules."""
        with self._lock:
            return list(self._knowledge.values())
