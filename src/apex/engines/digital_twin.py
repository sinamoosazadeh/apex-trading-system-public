"""Portfolio Digital Twin - Simulates decisions before execution (Book I, 8.29)."""
from __future__ import annotations

from typing import Dict

from ..domain.trading import PortfolioState, Position, TradeBlueprint

class DigitalTwin:
    """Shadow portfolio for risk-free simulation."""

    def __init__(self, initial_capital: float = 10000.0) -> None:
        self.shadow_capital: float = initial_capital
        self.shadow_positions: Dict[str, Position] = {}
        self.shadow_realized_pnl: float = 0.0

    def sync_with_real(self, real_portfolio: PortfolioState) -> None:
        """Synchronize the twin with the real portfolio state."""
        self.shadow_capital = real_portfolio.total_equity
        self.shadow_realized_pnl = real_portfolio.realized_pnl

    def simulate_blueprint(self, blueprint: TradeBlueprint) -> tuple[bool, PortfolioState]:
        """
        Simulate applying a trade blueprint to the shadow portfolio.
        Returns (is_safe, simulated_portfolio_state).
        """
        sim_position = Position(
            position_id=f"SIM_{blueprint.decision_id}",
            blueprint_id=blueprint.decision_id,
            symbol=blueprint.symbol,
            exchange="SIM",
            direction=blueprint.direction,
            entry_price=blueprint.entry_price,
            quantity=blueprint.position_size,
            stop_loss=blueprint.stop_loss,
            take_profit=blueprint.take_profit
        )
        
        notional = sim_position.quantity * sim_position.entry_price
        risk_amount = abs(sim_position.entry_price - sim_position.stop_loss) * sim_position.quantity
        
        # Rule 1: Cannot exceed max leverage (assume 3x)
        if notional > (self.shadow_capital * 3.0):
            return False, self._get_sim_state()
            
        # Rule 2: Cannot risk more than available capital (5% max risk per sim)
        if risk_amount > (self.shadow_capital * 0.05):
            return False, self._get_sim_state()
            
        # If safe, add to shadow positions temporarily to simulate
        self.shadow_positions[sim_position.position_id] = sim_position
        
        # Rollback immediately (we don't actually keep it, this was just a test)
        del self.shadow_positions[sim_position.position_id]
        
        # Return the state AFTER rollback, representing the unchanged portfolio
        return True, self._get_sim_state()

    def _get_sim_state(self) -> PortfolioState:
        """Get the current simulated portfolio state."""
        exposure = sum(p.quantity * p.current_price for p in self.shadow_positions.values())
        return PortfolioState(
            total_equity=self.shadow_capital,
            available_capital=max(0.0, self.shadow_capital - exposure),
            total_exposure=exposure,
            open_positions_count=len(self.shadow_positions),
            risk_budget_used=0.0,
            health_score=1.0
        )
