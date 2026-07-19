"""Research Engine - Extracts knowledge and updates Probability Engine."""
from __future__ import annotations

import uuid
import logging
from typing import Any

from .knowledge_base import KnowledgeBase
from ..domain.knowledge import Experience, Knowledge
from ..domain.trading import Trade
from ..engines.probability_engine import ProbabilityEngine

log = logging.getLogger(__name__)

class ResearchEngine:
    """Analyzes trade outcomes and feeds learning back into the system."""

    def __init__(self, knowledge_base: KnowledgeBase, prob_engine: ProbabilityEngine) -> None:
        self.kb = knowledge_base
        self.prob_engine = prob_engine
        self._trade_context_map: dict[str, Experience] = {}  # Maps trade_id to context

    def record_trade_context(self, trade_id: str, experience: Experience) -> None:
        """Temporarily store context when a trade opens, to be used when it closes."""
        self._trade_context_map[trade_id] = experience

    def process_closed_trade(self, trade: Trade) -> None:
        """Process a closed trade: Record experience, update Bayesian models."""
        # اصلاح: استفاده از position_id به جای trade_id
        experience = self._trade_context_map.pop(trade.position_id, None)
        
        if experience is None:
            log.warning(f"No context found for closed trade {trade.position_id}")
            return
            
        full_experience = Experience(
            trade_id=experience.trade_id,
            symbol=experience.symbol,
            setup_name=experience.setup_name,
            direction=experience.direction,
            win=trade.win,
            r_multiple=trade.r_multiple,
            probability_at_entry=experience.probability_at_entry,
            uncertainty_at_entry=experience.uncertainty_at_entry,
            regime=experience.regime,
            feature_vector=experience.feature_vector
        )
        
        self.kb.record_experience(full_experience)
        log.info(f"Recorded experience for {trade.symbol} {full_experience.setup_name}. Win: {trade.win}, R: {trade.r_multiple:.2f}")
        
        self.prob_engine.update_calibration(full_experience.probability_at_entry, full_experience.win)
        self.prob_engine.update_setup(full_experience.setup_name, full_experience.win, full_experience.r_multiple)
        
        self._extract_knowledge(full_experience.setup_name)

    def _extract_knowledge(self, setup_name: str) -> None:
        """Analyze setup statistics and extract knowledge if an edge is found."""
        stats = self.kb.get_setup_stats(setup_name)
        
        if stats["sample_size"] < 30:
            return
            
        win_rate = stats["win_rate"]
        expectancy = stats["expectancy"]
        
        if win_rate > 0.55 and expectancy > 0.2:
            knowledge = Knowledge(
                knowledge_id=f"KNW_{setup_name}_EDGE_{int(stats['sample_size'])}",
                category="setup_performance",
                description=f"Setup '{setup_name}' shows statistical edge with {win_rate*100:.1f}% win rate over {int(stats['sample_size'])} trades.",
                confidence=min(1.0, (win_rate - 0.5) * 2.0 * (stats["sample_size"] / 100.0)),
                sample_size=int(stats["sample_size"]),
                evidence=stats
            )
            self.kb.add_knowledge(knowledge)
            log.info(f"Knowledge Extracted: {knowledge.description}")
            
        elif win_rate < 0.45 and expectancy < -0.2:
            knowledge = Knowledge(
                knowledge_id=f"KNW_{setup_name}_FLAW_{int(stats['sample_size'])}",
                category="setup_flaw",
                description=f"Setup '{setup_name}' shows negative edge with {win_rate*100:.1f}% win rate. Consider disabling or re-optimizing.",
                confidence=min(1.0, (0.5 - win_rate) * 2.0 * (stats["sample_size"] / 100.0)),
                sample_size=int(stats["sample_size"]),
                evidence=stats
            )
            self.kb.add_knowledge(knowledge)
            log.warning(f"Knowledge Extracted (Warning): {knowledge.description}")
