"""Portfolio Intelligence Engine - Manages capital, risk, and positions."""
from __future__ import annotations

import math
import time
from typing import Dict, List

from ..domain.trading import Position, Trade, PortfolioState

class PortfolioEngine:
    """Portfolio-level intelligence and management."""

    def __init__(self, initial_capital: float = 10000.0, max_drawdown: float = 0.15) -> None:
        self.initial_capital: float = initial_capital
        self.max_drawdown_limit: float = max_drawdown
        self.open_positions: Dict[str, Position] = {}
        self.closed_trades: List[Trade] = []
        self.realized_pnl: float = 0.0
        self.peak_equity: float = initial_capital
        self.kill_switch_active: bool = False

    @property
    def floating_pnl(self) -> float:
        return sum(p.floating_pnl for p in self.open_positions.values() if p.status == "OPEN")

    @property
    def total_equity(self) -> float:
        return self.initial_capital + self.realized_pnl + self.floating_pnl

    @property
    def total_exposure(self) -> float:
        return sum(p.quantity * p.current_price for p in self.open_positions.values() if p.status == "OPEN")

    @property
    def current_drawdown(self) -> float:
        if self.peak_equity <= 0: return 0.0
        return max(0.0, (self.peak_equity - self.total_equity) / self.peak_equity)

    def update_positions(self, market_prices: Dict[str, float]) -> None:
        for symbol, price in market_prices.items():
            for pos in self.open_positions.values():
                if pos.symbol == symbol and pos.status == "OPEN":
                    pos.update_market_price(price)
        if self.total_equity > self.peak_equity:
            self.peak_equity = self.total_equity
        if self.current_drawdown >= self.max_drawdown_limit and not self.kill_switch_active:
            self.kill_switch_active = True

    def add_position(self, position: Position) -> bool:
        if self.kill_switch_active: return False
        if position.position_id in self.open_positions: return False
        self.open_positions[position.position_id] = position
        return True

    def close_position(self, position_id: str, exit_price: float) -> Trade | None:
        position = self.open_positions.get(position_id)
        if position is None or position.status != "OPEN": return None
        
        trade = position.close(exit_price, time.time())
        self.realized_pnl += trade.pnl
        self.closed_trades.append(trade)
        
        if self.total_equity > self.peak_equity:
            self.peak_equity = self.total_equity
            
        # اصلاح: حذف پوزیشن بسته شده از لیست پوزیشن‌های باز
        del self.open_positions[position_id]
        
        return trade

    def get_state(self) -> PortfolioState:
        open_count = len(self.open_positions)  # حالا فقط پوزیشن‌های باز را شامل می‌شود
        health = max(0.0, 1.0 - (self.current_drawdown / self.max_drawdown_limit))
        return PortfolioState(
            total_equity=self.total_equity,
            available_capital=max(0.0, self.total_equity - self.total_exposure),
            total_exposure=self.total_exposure,
            open_positions_count=open_count,
            risk_budget=3.0,
            risk_budget_used=0.0,
            portfolio_heat=0.0,
            drawdown=self.current_drawdown,
            health_score=health
        )
