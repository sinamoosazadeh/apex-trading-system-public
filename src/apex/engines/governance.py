"""Governance Layer - Enforces macro-level system rules."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class GovernancePolicy:
    max_concurrent_trades: int = 5
    max_drawdown_limit: float = 0.15
    min_decision_readiness: float = 0.15  # Re-enabled with balanced threshold
    max_uncertainty: float = 0.80         # Re-enabled with balanced threshold
    min_probability_threshold: float = 0.32 # Balanced for reasonable signal count
    min_prob_edge: float = 0.02           # Slightly lower for more opportunities
    min_contributors: int = 2
    min_expected_r: float = -0.3           # Re-enabled, allows small negative EV

class GovernanceEngine:
    def __init__(self, policy: GovernancePolicy) -> None:
        self.policy = policy

    def check_portfolio_limits(self, portfolio_state: Any) -> tuple[bool, str]:
        if portfolio_state.open_positions_count >= self.policy.max_concurrent_trades:
            return False, f"Max concurrent trades reached ({self.policy.max_concurrent_trades})"
        if portfolio_state.risk_budget_used >= portfolio_state.risk_budget:
            return False, "Daily risk budget exhausted"
        if portfolio_state.drawdown >= self.policy.max_drawdown_limit:
            return False, f"Max drawdown limit reached ({self.policy.max_drawdown_limit*100}%)"
        return True, "Portfolio limits OK"

    def check_kill_switch(self, portfolio_state: Any) -> tuple[bool, str]:
        if portfolio_state.health_score < 0.3:
            return True, "Portfolio health critical"
        return False, "Health nominal"
