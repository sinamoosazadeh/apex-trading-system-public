"""Signal Decision Engine - The final decision authority."""
from __future__ import annotations

import time
from typing import Any

from ..domain.contracts import ProbabilityReport
from ..domain.trading import PortfolioState, Decision
from .governance import GovernanceEngine

class DecisionEngine:
    """Central decision kernel with multi-layer evaluation."""

    def __init__(self, governance: GovernanceEngine) -> None:
        self.governance = governance

    def evaluate(
        self,
        probability: ProbabilityReport,
        portfolio: PortfolioState,
        contributors_long: int = 0,
        contributors_short: int = 0,
    ) -> Decision:
        """Evaluate and produce final decision."""
        reasons: list[str] = []
        evidence: dict[str, float] = {}
        risk: dict[str, float] = {}
        portfolio_impact: dict[str, float] = {}

        # Layer 0: Kill Switch Check
        kill_triggered, kill_reason = self.governance.check_kill_switch(portfolio)
        if kill_triggered:
            return Decision(
                decision_type="NO_TRADE", direction="FLAT", confidence=1.0, priority=100,
                reasoning=(kill_reason, "Kill switch active"), risk_summary={"kill_switch": 1.0},
                timestamp=time.time()
            )

        # Layer 1: Portfolio Governance Check
        port_ok, port_reason = self.governance.check_portfolio_limits(portfolio)
        if not port_ok:
            return Decision(
                decision_type="NO_TRADE", direction="FLAT", confidence=1.0, priority=90,
                reasoning=(port_reason,), portfolio_impact={"blocked_by_governance": 1.0},
                timestamp=time.time()
            )

        # Layer 2: Decision Readiness & Uncertainty
        if probability.decision_readiness_index < self.governance.policy.min_decision_readiness:
            return Decision(
                decision_type="WAIT", direction="FLAT", confidence=probability.confidence,
                reasoning=(f"DRI too low ({probability.decision_readiness_index:.2f})",),
                timestamp=time.time()
            )

        if probability.uncertainty > self.governance.policy.max_uncertainty:
            return Decision(
                decision_type="WAIT", direction="FLAT", confidence=probability.confidence,
                reasoning=(f"Uncertainty too high ({probability.uncertainty:.2f})",),
                risk_summary={"uncertainty": probability.uncertainty}, timestamp=time.time()
            )

        # Layer 3: Probability & Edge Evaluation
        direction = "FLAT"
        chosen_prob = 0.0

        if probability.probability_long >= self.governance.policy.min_probability_threshold:
            if (probability.probability_long - probability.probability_short) >= self.governance.policy.min_prob_edge:
                if contributors_long >= self.governance.policy.min_contributors:
                    direction = "LONG"
                    chosen_prob = probability.probability_long
                    reasons.append(f"Long probability {probability.probability_long:.2f} above threshold")
                    evidence["probability_long"] = probability.probability_long
                else:
                    reasons.append(f"Insufficient long contributors ({contributors_long})")
            else:
                reasons.append("Long probability edge too small")
                
        elif probability.probability_short >= self.governance.policy.min_probability_threshold:
            if (probability.probability_short - probability.probability_long) >= self.governance.policy.min_prob_edge:
                if contributors_short >= self.governance.policy.min_contributors:
                    direction = "SHORT"
                    chosen_prob = probability.probability_short
                    reasons.append(f"Short probability {probability.probability_short:.2f} above threshold")
                    evidence["probability_short"] = probability.probability_short
                else:
                    reasons.append(f"Insufficient short contributors ({contributors_short})")
            else:
                reasons.append("Short probability edge too small")
        else:
            reasons.append("No probability above threshold")

        if direction == "FLAT":
            return Decision(
                decision_type="NO_TRADE", direction="FLAT", confidence=probability.confidence,
                reasoning=tuple(reasons), evidence_summary=evidence, timestamp=time.time()
            )

        # Layer 4: Expected Value Check
        if probability.expected_r < self.governance.policy.min_expected_r:
            return Decision(
                decision_type="NO_TRADE", direction="FLAT", confidence=probability.confidence,
                reasoning=(f"Expected R too low ({probability.expected_r:.2f})", *reasons),
                evidence_summary=evidence, timestamp=time.time()
            )

        # Layer 5: Final Approval
        risk["uncertainty"] = probability.uncertainty
        risk["expected_drawdown"] = probability.expected_drawdown
        portfolio_impact["current_exposure"] = portfolio.total_exposure
        portfolio_impact["portfolio_heat"] = portfolio.portfolio_heat

        return Decision(
            decision_type="TRADE", direction=direction,
            confidence=chosen_prob * (1.0 - probability.uncertainty),
            utility=probability.expected_value, priority=int(chosen_prob * 100),
            reasoning=("All gates passed", *reasons), evidence_summary=evidence,
            risk_summary=risk, portfolio_impact=portfolio_impact, timestamp=time.time()
        )
